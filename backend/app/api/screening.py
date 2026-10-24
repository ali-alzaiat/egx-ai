"""API endpoints for Shariah screening (R32 Phase 6 served under this router)."""

import re
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.screening import ScreeningRepository
from app.screening.methodology import DEFAULT_METHODOLOGY
from app.screening.purification import NOT_ZAKAT_COPY, PURIFICATION_DOCTRINE
from app.screening.rules import ScreeningVerdict
from app.services.recompute import Engine, RecomputeService, compute_meta
from app.statements.bridge import DPS_DERIVATION, DPS_LABEL

router = APIRouter(prefix="/api/screening", tags=["screening"])

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


class EgxMembershipBody(BaseModel):
    """One dated EGX33 membership catalyst record (Feb/Aug review cycle)."""

    member: bool
    review_cycle: str
    effective_date: date | None = None
    source: str = Field(min_length=1)
    note: str | None = None


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


@router.get("/companies/{company_id}")
async def get_screening_result(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Shariah verdict from approved statement lines, computed on first view.

    Never 404 for a known company: missing inputs make each rule
    INSUFFICIENT_DATA naming the statement line (``is_compliant: null``).
    """
    from app.repositories.company import CompanyRepository

    company = await CompanyRepository(session).get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    recompute = RecomputeService(session)
    state = await recompute.ensure_fresh(company_id, Engine.SHARIAH)
    await recompute.ensure_fresh(company_id, Engine.DQ_FS)  # the embedded DQ block
    meta = compute_meta(state)
    result = await ScreeningRepository(session).get_screening_result(
        company_id, DEFAULT_METHODOLOGY.version.value
    )

    from app.dataquality.service import DataQualityService

    dq_result = await DataQualityService(session).latest(company_id, "financial_statements")
    data_quality = dq_result.as_dict() if dq_result is not None else None

    if result is None:
        reason = f"computation failed: {meta.get('compute_error') or 'no snapshot'}"
        payload: dict[str, Any] = {
            "id": None,
            "company_id": str(company_id),
            "is_compliant": None,
            "status": "INSUFFICIENT_DATA",
            "methodology_name": DEFAULT_METHODOLOGY.name,
            "overall_reason": reason,
            "screened_at": None,
            "report_date": None,
            "report_date_reason": None,
            "created_at": None,
            "rule_results": [],
        }
    else:
        payload = {
            "id": str(result.id),
            "company_id": str(result.company_id),
            "is_compliant": result.is_compliant,
            "status": result.status.value,
            "methodology_name": result.methodology_name,
            "overall_reason": result.overall_reason,
            "screened_at": result.screened_at.isoformat(),
            "report_date": result.report_date.isoformat() if result.report_date else None,
            "report_date_reason": result.report_date_reason,
            "created_at": result.created_at.isoformat(),
            "rule_results": [_rule_payload(r) for r in result.rule_results],
        }
    payload.update(meta)
    payload["methodology_version"] = DEFAULT_METHODOLOGY.version.value
    payload["engine"] = "statement_lines"
    payload["data_quality"] = data_quality
    return payload


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


@router.get("/companies/{company_id}/purification")
async def get_purification(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Automatic per-share purification estimate (EGP per share), computed on first view.

    DPS = cash dividends paid in the fiscal year / shares outstanding; the
    ratio is interest income / revenue. Missing lines -> INSUFFICIENT_DATA
    naming the line. Never 404 for a known company.
    """
    from app.repositories.company import CompanyRepository

    company = await CompanyRepository(session).get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    state = await RecomputeService(session).ensure_fresh(company_id, Engine.PURIFICATION)
    meta = compute_meta(state)
    row = await ScreeningRepository(session).get_purification_estimate(company_id)
    if row is None:
        payload: dict[str, Any] = {
            "id": None,
            "company_id": str(company_id),
            "status": "INSUFFICIENT_DATA",
            "branch": "insufficient-data",
            "doctrine": PURIFICATION_DOCTRINE,
            "amount_egp": None,
            "dividend_egp": None,
            "ratio": None,
            "ratio_provenance": None,
            "dps": None,
            "dps_source": None,
            "dps_date": None,
            "reason": f"computation failed: {meta.get('compute_error') or 'no snapshot'}",
            "missing_input": None,
            "note": NOT_ZAKAT_COPY,
            "computed_at": None,
        }
    else:
        payload = {
            "id": str(row.id),
            "company_id": str(row.company_id),
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
    payload.update(meta)
    payload["methodology_version"] = DEFAULT_METHODOLOGY.version.value
    payload["basis"] = "per_share"
    payload["dps_derivation"] = DPS_DERIVATION
    payload["dps_label"] = DPS_LABEL
    return payload


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
