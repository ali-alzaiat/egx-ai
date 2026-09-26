"""API endpoints for technical analysis."""

import json
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.technical import IndicatorStatusDB, IndicatorTypeDB
from app.repositories.technical import TechnicalRepository
from app.technical.service import TechnicalInput, TechnicalService

router = APIRouter(prefix="/api/technical", tags=["technical"])


@router.get("/companies/{company_id}")
async def get_indicators(
    company_id: uuid.UUID,
    indicator_type: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Get technical indicators for a company."""
    from app.repositories.company import CompanyRepository

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    tech_repo = TechnicalRepository(session)
    type_enum = IndicatorTypeDB(indicator_type) if indicator_type else None
    results = await tech_repo.get_indicators_for_company(
        company_id=company_id,
        indicator_type=type_enum,
    )

    return [
        {
            "id": str(r.id),
            "company_id": str(r.company_id),
            "indicator_type": r.indicator_type.value,
            "value": str(r.value) if r.value is not None else None,
            "status": r.status.value,
            "parameters": json.loads(r.parameters) if r.parameters else None,
            "reason": r.reason,
            "calculated_at": r.calculated_at.isoformat(),
            "created_at": r.created_at.isoformat(),
        }
        for r in results
    ]


@router.post("/companies/{company_id}/calculate")
async def calculate_indicators(
    company_id: uuid.UUID,
    prices: str = Query(..., description="Comma-separated prices"),
    volumes: str = Query(..., description="Comma-separated volumes"),
    indicator_types: str | None = Query(None, description="Comma-separated indicator types"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Calculate technical indicators for a company."""
    from app.repositories.company import CompanyRepository

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Parse inputs
    try:
        price_list = [Decimal(p.strip()) for p in prices.split(",")]
        volume_list = [int(v.strip()) for v in volumes.split(",")]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid input: {e}") from e

    if len(price_list) != len(volume_list):
        raise HTTPException(status_code=400, detail="Prices and volumes must have same length")

    # Parse indicator types
    types = None
    if indicator_types:
        try:
            from app.technical.indicators import IndicatorType
            types = [IndicatorType(t.strip()) for t in indicator_types.split(",")]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid indicator type: {e}") from e

    # Create input
    technical_input = TechnicalInput(
        company_id=str(company_id),
        ticker=company.ticker,
        prices=price_list,
        volumes=volume_list,
    )

    # Calculate indicators
    service = TechnicalService(session)
    output = await service.calculate_indicators(technical_input, types)

    # Persist results
    tech_repo = TechnicalRepository(session)
    for result in output.indicators:
        type_enum = IndicatorTypeDB(result.indicator.value)
        status_enum = IndicatorStatusDB(result.status.value)

        await tech_repo.upsert_indicator(
            company_id=company_id,
            indicator_type=type_enum,
            value=float(result.value) if result.value is not None else None,
            status=status_enum,
            parameters=json.dumps(result.parameters) if result.parameters else None,
            reason=result.reason,
            calculated_at=output.calculated_at,
        )

    await session.commit()

    return {
        "company_id": str(company_id),
        "ticker": output.ticker,
        "indicators": [
            {
                "indicator": r.indicator.value,
                "value": str(r.value) if r.value is not None else None,
                "status": r.status.value,
                "parameters": r.parameters,
                "reason": r.reason,
            }
            for r in output.indicators
        ],
        "calculated_at": output.calculated_at.isoformat(),
    }
