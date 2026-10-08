"""API endpoints for Shariah screening."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.screening import ScreeningRepository
from app.screening.methodology import DEFAULT_METHODOLOGY
from app.screening.service import ScreeningInput, ShariahScreeningService

router = APIRouter(prefix="/api/screening", tags=["screening"])


@router.get("/companies/{company_id}")
async def get_screening_result(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
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
        "created_at": result.created_at.isoformat(),
        "rule_results": [
            {
                "rule_name": r.rule_name,
                "verdict": r.verdict,
                "value": str(r.value) if r.value is not None else None,
                "threshold": str(r.threshold) if r.threshold is not None else None,
                "reason": r.reason,
            }
            for r in result.rule_results
        ],
        "data_quality": data_quality,
    }


@router.get("/companies")
async def list_screened_companies(
    is_compliant: bool | None = Query(None),
    methodology_version: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
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
) -> dict:
    """Screen a company for Shariah compliance."""
    from app.repositories.company import CompanyRepository

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Get financial data for screening
    from app.repositories.financial import FinancialFactRepository

    fact_repo = FinancialFactRepository(session)
    facts = await fact_repo.list_facts(company_id=company_id)

    # Build facts dictionary
    facts_dict = {}
    for fact in facts:
        label = fact.normalized_label or fact.reported_label
        value = fact.reported_value if fact.normalized_value is None else fact.normalized_value
        facts_dict[label] = value

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
        )

    await session.commit()

    return {
        "company_id": str(company_id),
        "ticker": output.ticker,
        "is_compliant": output.is_compliant,
        "methodology_version": output.methodology_version,
        "overall_reason": output.overall_reason,
        "rule_results": [
            {
                "rule_name": r.rule_name,
                "verdict": r.verdict.value,
                "value": str(r.value) if r.value is not None else None,
                "threshold": str(r.threshold) if r.threshold is not None else None,
                "reason": r.reason,
            }
            for r in output.rule_results
        ],
        "screened_at": output.screened_at.isoformat(),
    }
