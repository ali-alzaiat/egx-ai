"""API endpoints for Shariah screening (R32 Phase 6 served under this router)."""

import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.financial import FinancialDocument
from app.repositories.screening import ScreeningRepository
from app.screening.methodology import DEFAULT_METHODOLOGY
from app.screening.purification import (
    NOT_ZAKAT_COPY,
    PURIFICATION_DOCTRINE,
    PurificationEstimate,
    estimate_dividend_purification,
)
from app.screening.rules import ScreeningVerdict
from app.screening.service import RuleProvenance, ScreeningInput, ShariahScreeningService

router = APIRouter(prefix="/api/screening", tags=["screening"])

# Fact labels backing each ratio rule (mirrors POST /screen lookup).
RULE_FACT_LABELS: dict[str, tuple[str, ...]] = {
    "debt_ratio": ("total_debt", "total_assets"),
    "interest_income_ratio": ("interest_income", "revenue"),
    "cash_securities_ratio": ("cash_and_equivalents", "total_assets"),
}

# EGX33 runs semi-annual reviews effective February + August (research §3).
REVIEW_CYCLE_RE = re.compile(r"^\d{4}-(02|08)$")

# Displayed whenever a member name fails our strict screen. The 10%/70%
# figures are an unverified press summary (AGBI) until the official EGX33
# methodology PDF is retrieved — membership never overrides our verdict.
EGX33_DISCREPANCY_NOTE = (
    "EGX33 press summary reports a 10% non-compliant-income ceiling and a "
    "70% liquidity cap versus our 5%/33% (AGBI, unverified against the "
    "official EGX methodology PDF); membership is shown side by side and "
    "never overrides our verdict."
)


class PurificationBody(BaseModel):
    """Dividend-method purification inputs; every field optional.

    The ratio comes only from cited filing inputs — never proxied from other
    facts. Missing ratio degrades to INSUFFICIENT_DATA (R32 B4).
    """

    dividend_egp: float | None = None
    dps: float | None = None
    shares_held: float | None = None
    non_permissible_revenue: float | None = None
    total_revenue: float | None = None
    ratio_provenance: str | None = None
    dps_source: str | None = None
    dps_date: date | None = None


class EgxMembershipBody(BaseModel):
    """One dated EGX33 membership catalyst record (Feb/Aug review cycle)."""

    member: bool
    review_cycle: str
    effective_date: date | None = None
    source: str = Field(min_length=1)
    note: str | None = None


def _doc_descriptor(doc: FinancialDocument) -> str:
    """Cite the filing behind a fact (deterministic, human-readable)."""
    if doc.filing_date is not None:
        return f"{doc.document_type} filing {doc.filing_date.isoformat()}"
    return f"{doc.document_type} (filing date unknown)"


def _rule_provenance(
    labels: tuple[str, ...],
    docs: dict[str, FinancialDocument],
) -> RuleProvenance | None:
    """Provenance for one rule: latest filing among its present inputs."""
    present = [docs[label] for label in labels if label in docs]
    if not present:
        return None
    best = max(present, key=lambda doc: doc.filing_date or date.min)
    return RuleProvenance(source=_doc_descriptor(best), source_date=best.filing_date)


def _rule_payload(rule: Any) -> dict[str, Any]:
    """Serialize a rule result (ORM row or engine dataclass)."""
    value = getattr(rule, "value", None)
    threshold = getattr(rule, "threshold", None)
    source_date = getattr(rule, "source_date", None)
    raw_verdict = getattr(rule, "verdict", None)
    verdict = raw_verdict.value if isinstance(raw_verdict, ScreeningVerdict) else raw_verdict
    return {
        "rule_name": rule.rule_name,
        "verdict": verdict,
        "value": str(value) if value is not None else None,
        "threshold": str(threshold) if threshold is not None else None,
        "reason": rule.reason,
        "missing_input": getattr(rule, "missing_input", None),
        "source": getattr(rule, "source", None),
        "source_date": source_date.isoformat() if source_date is not None else None,
    }


def _purification_payload(estimate: PurificationEstimate) -> dict[str, Any]:
    """Serialize an estimate; the amount stays null until a ratio exists."""
    return {
        "status": estimate.status.value,
        "branch": estimate.branch.value,
        "doctrine": estimate.doctrine,
        "amount_egp": str(estimate.amount_egp) if estimate.amount_egp is not None else None,
        "dividend_egp": (
            str(estimate.dividend_egp) if estimate.dividend_egp is not None else None
        ),
        "ratio": str(estimate.ratio) if estimate.ratio is not None else None,
        "ratio_provenance": estimate.ratio_provenance,
        "dps": str(estimate.dps) if estimate.dps is not None else None,
        "dps_source": estimate.dps_source,
        "dps_date": estimate.dps_date.isoformat() if estimate.dps_date is not None else None,
        "reason": estimate.reason,
        "missing_input": estimate.missing_input,
        "note": estimate.note,
    }


def _to_decimal(value: float | None) -> Decimal | None:
    """Convert request floats without binary-float artifacts."""
    return Decimal(str(value)) if value is not None else None


@router.get("/companies/{company_id}")
async def get_screening_result(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get the screening result for a company."""
    from app.repositories.company import CompanyRepository

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    screening_repo = ScreeningRepository(session)
    result = await screening_repo.get_screening_result(company_id)

    if not result:
        raise HTTPException(status_code=404, detail="Screening result not found")

    from app.dataquality.service import DataQualityService

    dq_result = await DataQualityService(session).latest(
        company_id, "financial_statements"
    )
    data_quality = dq_result.as_dict() if dq_result is not None else None

    return {
        "id": str(result.id),
        "company_id": str(result.company_id),
        "is_compliant": result.is_compliant,
        "status": result.status.value,
        "methodology_version": result.methodology_version,
        "methodology_name": result.methodology_name,
        "overall_reason": result.overall_reason,
        "screened_at": result.screened_at.isoformat(),
        "report_date": result.report_date.isoformat() if result.report_date else None,
        "report_date_reason": result.report_date_reason,
        "created_at": result.created_at.isoformat(),
        "rule_results": [_rule_payload(r) for r in result.rule_results],
        "data_quality": data_quality,
    }


@router.get("/companies")
async def list_screened_companies(
    is_compliant: bool | None = Query(None),
    methodology_version: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List all screened companies."""
    screening_repo = ScreeningRepository(session)
    results = await screening_repo.list_screened_companies(
        is_compliant=is_compliant,
        methodology_version=methodology_version,
    )

    return [
        {
            "id": str(r.id),
            "company_id": str(r.company_id),
            "is_compliant": r.is_compliant,
            "status": r.status.value,
            "methodology_version": r.methodology_version,
            "overall_reason": r.overall_reason,
            "screened_at": r.screened_at.isoformat(),
        }
        for r in results
    ]


@router.post("/companies/{company_id}/screen")
async def screen_company(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Screen a company for Shariah compliance."""
    from app.repositories.company import CompanyRepository

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Get financial data with source documents for per-rule provenance.
    from app.repositories.financial import FinancialFactRepository

    fact_repo = FinancialFactRepository(session)
    rows = await fact_repo.list_facts_with_documents(company_id=company_id)

    # Build facts dictionary (last row wins per label, as before).
    facts_dict: dict[str, Decimal | None] = {}
    docs_dict: dict[str, FinancialDocument] = {}
    for fact, doc in rows:
        label = fact.normalized_label or fact.reported_label
        value = fact.reported_value if fact.normalized_value is None else fact.normalized_value
        facts_dict[label] = value
        docs_dict[label] = doc

    provenance: dict[str, RuleProvenance] = {
        "industry_screen": RuleProvenance(source="company record", source_date=None)
    }
    for rule_name, labels in RULE_FACT_LABELS.items():
        prov = _rule_provenance(labels, docs_dict)
        if prov is not None:
            provenance[rule_name] = prov

    # Create screening input
    screening_input = ScreeningInput(
        company_id=str(company_id),
        ticker=company.ticker,
        industry=company.industry,
        total_debt=facts_dict.get("total_debt"),
        total_assets=facts_dict.get("total_assets"),
        interest_income=facts_dict.get("interest_income"),
        total_revenue=facts_dict.get("revenue"),
        cash_and_securities=facts_dict.get("cash_and_equivalents"),
        provenance=provenance,
    )

    # Run screening
    service = ShariahScreeningService(session)
    output = await service.screen_company(screening_input)

    # Persist results
    screening_repo = ScreeningRepository(session)
    result = await screening_repo.upsert_screening_result(
        company_id=company_id,
        is_compliant=output.is_compliant,
        methodology_version=output.methodology_version,
        methodology_name=DEFAULT_METHODOLOGY.name,
        overall_reason=output.overall_reason,
        screened_at=output.screened_at,
        report_date=output.report_date,
        report_date_reason=output.report_date_reason,
    )

    # Add rule results
    for rule_result in output.rule_results:
        await screening_repo.add_rule_result(
            screening_result_id=result.id,
            rule_name=rule_result.rule_name,
            verdict=rule_result.verdict.value,
            value=float(rule_result.value) if rule_result.value is not None else None,
            threshold=float(rule_result.threshold) if rule_result.threshold is not None else None,
            reason=rule_result.reason,
            missing_input=rule_result.missing_input,
            source=rule_result.source,
            source_date=rule_result.source_date,
        )

    await session.commit()

    return {
        "company_id": str(company_id),
        "ticker": output.ticker,
        "is_compliant": output.is_compliant,
        "methodology_version": output.methodology_version,
        "overall_reason": output.overall_reason,
        "rule_results": [_rule_payload(r) for r in output.rule_results],
        "screened_at": output.screened_at.isoformat(),
        "report_date": output.report_date.isoformat() if output.report_date else None,
        "report_date_reason": output.report_date_reason,
    }


@router.post("/companies/{company_id}/screen-statements")
async def screen_company_from_statements(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Screen a company using approved statement lines as inputs."""
    from fastapi.responses import JSONResponse

    from app.repositories.company import CompanyRepository
    from app.repositories.statements import StatementLineRepository
    from app.screening.statement_input import build_screening_input_from_statements

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    stmt_repo = StatementLineRepository(session)
    lines = await stmt_repo.latest_approved(company_id)
    screening_input, reason = build_screening_input_from_statements(
        company_id=company_id,
        company=company,
        lines=lines,
        market_cap=None,
    )
    if screening_input is None:
        return JSONResponse(
            status_code=409,
            content={"status": "INSUFFICIENT_DATA", "reason": reason},
        )

    service = ShariahScreeningService(session)
    output = await service.screen_company(screening_input)

    screening_repo = ScreeningRepository(session)
    result = await screening_repo.upsert_screening_result(
        company_id=company_id,
        is_compliant=output.is_compliant,
        methodology_version=output.methodology_version,
        methodology_name=DEFAULT_METHODOLOGY.name,
        overall_reason=output.overall_reason,
        screened_at=output.screened_at,
        report_date=output.report_date,
        report_date_reason=output.report_date_reason,
    )
    for rule_result in output.rule_results:
        await screening_repo.add_rule_result(
            screening_result_id=result.id,
            rule_name=rule_result.rule_name,
            verdict=rule_result.verdict.value,
            value=float(rule_result.value) if rule_result.value is not None else None,
            threshold=float(rule_result.threshold) if rule_result.threshold is not None else None,
            reason=rule_result.reason,
            missing_input=rule_result.missing_input,
            source=rule_result.source,
            source_date=rule_result.source_date,
        )
    await session.commit()

    return {
        "company_id": str(company_id),
        "ticker": output.ticker,
        "is_compliant": output.is_compliant,
        "methodology_version": output.methodology_version,
        "overall_reason": output.overall_reason,
        "rule_results": [_rule_payload(r) for r in output.rule_results],
        "screened_at": output.screened_at.isoformat(),
        "report_date": output.report_date.isoformat() if output.report_date else None,
        "report_date_reason": output.report_date_reason,
    }


@router.post("/companies/{company_id}/purification")
async def estimate_purification(
    company_id: uuid.UUID,
    body: PurificationBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Estimate dividend purification in EGP (dividend-method, R32 B3/B4)."""
    from app.repositories.company import CompanyRepository

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    screening_repo = ScreeningRepository(session)
    verdict = await screening_repo.get_screening_result(company_id)

    estimate = estimate_dividend_purification(
        ticker=company.ticker,
        is_compliant=verdict.is_compliant if verdict is not None else None,
        dividend_egp=_to_decimal(body.dividend_egp),
        dps=_to_decimal(body.dps),
        shares_held=_to_decimal(body.shares_held),
        non_permissible_revenue=_to_decimal(body.non_permissible_revenue),
        total_revenue=_to_decimal(body.total_revenue),
        ratio_provenance=body.ratio_provenance,
        dps_source=body.dps_source,
        dps_date=body.dps_date,
    )

    row = await screening_repo.upsert_purification_estimate(
        company_id=company_id,
        methodology_version=DEFAULT_METHODOLOGY.version.value,
        doctrine=estimate.doctrine,
        branch=estimate.branch.value,
        status=estimate.status.value,
        amount_egp=estimate.amount_egp,
        dividend_egp=estimate.dividend_egp,
        ratio=estimate.ratio,
        ratio_provenance=estimate.ratio_provenance,
        dps=estimate.dps,
        dps_source=estimate.dps_source,
        dps_date=estimate.dps_date,
        reason=estimate.reason,
        missing_input=estimate.missing_input,
        computed_at=datetime.now(UTC),
    )
    await session.commit()

    payload = _purification_payload(estimate)
    payload.update(
        {
            "id": str(row.id),
            "company_id": str(company_id),
            "methodology_version": row.methodology_version,
            "computed_at": row.computed_at.isoformat(),
        }
    )
    return payload


@router.get("/companies/{company_id}/purification")
async def get_purification(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get the latest purification estimate for a company."""
    from app.repositories.company import CompanyRepository

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    screening_repo = ScreeningRepository(session)
    row = await screening_repo.get_purification_estimate(company_id)
    if not row:
        raise HTTPException(status_code=404, detail="Purification estimate not found")

    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "methodology_version": row.methodology_version,
        "status": row.status,
        "branch": row.branch,
        "doctrine": row.doctrine or PURIFICATION_DOCTRINE,
        "amount_egp": str(row.amount_egp) if row.amount_egp is not None else None,
        "dividend_egp": str(row.dividend_egp) if row.dividend_egp is not None else None,
        "ratio": str(row.ratio) if row.ratio is not None else None,
        "ratio_provenance": row.ratio_provenance,
        "dps": str(row.dps) if row.dps is not None else None,
        "dps_source": row.dps_source,
        "dps_date": row.dps_date.isoformat() if row.dps_date else None,
        "reason": row.reason,
        "missing_input": row.missing_input,
        "note": NOT_ZAKAT_COPY,
        "computed_at": row.computed_at.isoformat(),
    }


@router.post("/companies/{company_id}/egx-membership")
async def record_egx_membership(
    company_id: uuid.UUID,
    body: EgxMembershipBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Record a dated EGX33 membership catalyst (Feb/Aug review, R32 B5)."""
    from app.repositories.company import CompanyRepository

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if not REVIEW_CYCLE_RE.match(body.review_cycle):
        raise HTTPException(
            status_code=422,
            detail="review_cycle must be a Feb/Aug cycle like '2026-02' or '2026-08'",
        )

    screening_repo = ScreeningRepository(session)
    row = await screening_repo.upsert_egx_membership(
        company_id=company_id,
        methodology_version=DEFAULT_METHODOLOGY.version.value,
        member=body.member,
        review_cycle=body.review_cycle,
        effective_date=body.effective_date,
        source=body.source,
        note=body.note,
    )
    await session.commit()

    return {
        "id": str(row.id),
        "company_id": str(company_id),
        "methodology_version": row.methodology_version,
        "member": row.member,
        "review_cycle": row.review_cycle,
        "effective_date": row.effective_date.isoformat() if row.effective_date else None,
        "source": row.source,
        "note": row.note,
    }


@router.get("/companies/{company_id}/egx-membership")
async def get_egx_membership(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Show our verdict side by side with EGX33 membership (never override)."""
    from app.repositories.company import CompanyRepository

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    screening_repo = ScreeningRepository(session)
    verdict = await screening_repo.get_screening_result(company_id)
    memberships = await screening_repo.list_egx_memberships(company_id)

    our_verdict: dict[str, Any] | None = None
    if verdict is not None:
        our_verdict = {
            "is_compliant": verdict.is_compliant,
            "status": verdict.status.value,
            "methodology_version": verdict.methodology_version,
            "screened_at": verdict.screened_at.isoformat(),
            "report_date": verdict.report_date.isoformat() if verdict.report_date else None,
        }

    history = [
        {
            "member": m.member,
            "review_cycle": m.review_cycle,
            "effective_date": m.effective_date.isoformat() if m.effective_date else None,
            "source": m.source,
            "note": m.note,
        }
        for m in memberships
    ]
    latest = history[0] if history else None

    flagged = bool(
        latest is not None
        and latest["member"] is True
        and verdict is not None
        and verdict.is_compliant is False
    )
    return {
        "company_id": str(company_id),
        "our_verdict": our_verdict,
        "egx33": latest,
        "history": history,
        "discrepancy": {
            "flagged": flagged,
            "note": EGX33_DISCREPANCY_NOTE if flagged else None,
        },
    }
