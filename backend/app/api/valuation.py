"""API endpoints for valuation."""

import json
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.valuation import ValuationModelDB, ValuationStatusDB
from app.repositories.valuation import ValuationRepository
from app.valuation.service import FairValueInput, FairValueService, ValuationInput, ValuationService

router = APIRouter(prefix="/api/valuation", tags=["valuation"])


@router.get("/companies/{company_id}")
async def get_valuations(
    company_id: uuid.UUID,
    model: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Get valuation results for a company."""
    from app.repositories.company import CompanyRepository

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    valuation_repo = ValuationRepository(session)
    model_enum = ValuationModelDB(model) if model else None
    results = await valuation_repo.get_valuations_for_company(
        company_id=company_id,
        model=model_enum,
    )

    return [
        {
            "id": str(r.id),
            "company_id": str(r.company_id),
            "model": r.model.value,
            "value": str(r.value) if r.value is not None else None,
            "status": r.status.value,
            "assumptions": json.loads(r.assumptions) if r.assumptions else None,
            "reason": r.reason,
            "calculated_at": r.calculated_at.isoformat(),
            "created_at": r.created_at.isoformat(),
        }
        for r in results
    ]


@router.post("/companies/{company_id}/calculate")
async def calculate_valuations(
    company_id: uuid.UUID,
    # P/E inputs
    earnings_per_share: float | None = Query(None),
    pe_ratio: float | None = Query(None),
    # P/B inputs
    book_value_per_share: float | None = Query(None),
    pb_ratio: float | None = Query(None),
    # EV/EBITDA inputs
    ebitda: float | None = Query(None),
    ev_ebitda_ratio: float | None = Query(None),
    net_debt: float | None = Query(None),
    # DCF inputs
    free_cash_flow: float | None = Query(None),
    growth_rate: float | None = Query(None),
    discount_rate: float | None = Query(None),
    terminal_growth_rate: float | None = Query(None),
    # General
    shares_outstanding: float | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Calculate valuations for a company."""
    from app.repositories.company import CompanyRepository

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # Create valuation input
    valuation_input = ValuationInput(
        company_id=str(company_id),
        ticker=company.ticker,
        earnings_per_share=Decimal(str(earnings_per_share)) if earnings_per_share else None,
        pe_ratio=Decimal(str(pe_ratio)) if pe_ratio else None,
        book_value_per_share=Decimal(str(book_value_per_share)) if book_value_per_share else None,
        pb_ratio=Decimal(str(pb_ratio)) if pb_ratio else None,
        ebitda=Decimal(str(ebitda)) if ebitda else None,
        ev_ebitda_ratio=Decimal(str(ev_ebitda_ratio)) if ev_ebitda_ratio else None,
        net_debt=Decimal(str(net_debt)) if net_debt else None,
        shares_outstanding=Decimal(str(shares_outstanding)) if shares_outstanding else None,
        free_cash_flow=Decimal(str(free_cash_flow)) if free_cash_flow else None,
        growth_rate=Decimal(str(growth_rate)) if growth_rate else None,
        discount_rate=Decimal(str(discount_rate)) if discount_rate else None,
        terminal_growth_rate=Decimal(str(terminal_growth_rate)) if terminal_growth_rate else None,
    )

    # Calculate valuations
    service = ValuationService(session)
    output = await service.calculate_valuations(valuation_input)

    # Persist results
    valuation_repo = ValuationRepository(session)
    for result in output.results:
        model_enum = ValuationModelDB(result.model.value)
        status_enum = ValuationStatusDB(result.status.value)

        await valuation_repo.upsert_valuation(
            company_id=company_id,
            model=model_enum,
            value=float(result.value) if result.value is not None else None,
            status=status_enum,
            assumptions=json.dumps(result.assumptions) if result.assumptions else None,
            reason=result.reason,
            calculated_at=output.calculated_at,
        )

    await session.commit()

    return {
        "company_id": str(company_id),
        "ticker": output.ticker,
        "valuations": [
            {
                "model": r.model.value,
                "value": str(r.value) if r.value is not None else None,
                "status": r.status.value,
                "assumptions": r.assumptions,
                "reason": r.reason,
            }
            for r in output.results
        ],
        "calculated_at": output.calculated_at.isoformat(),
    }


@router.get("/companies/{company_id}/fair-value")
async def get_fair_value(
    company_id: uuid.UUID,
    free_cash_flow: float | None = Query(None),
    growth_rate: float | None = Query(None),
    stable_growth: float | None = Query(None),
    discount_rate: float | None = Query(None),
    terminal_growth_rate: float | None = Query(None),
    expected_dps: float | None = Query(None),
    stable_roe: float | None = Query(None),
    affo: float | None = Query(None),
    ffo: float | None = Query(None),
    earnings_per_share: float | None = Query(None),
    pe_ratio: float | None = Query(None),
    revenue_per_share: float | None = Query(None),
    ps_ratio: float | None = Query(None),
    book_value_per_share: float | None = Query(None),
    pb_ratio: float | None = Query(None),
    shares_outstanding: float | None = Query(None),
    revenue_growth: float | None = Query(None),
    operating_margin: float | None = Query(None),
    exit_multiple: float | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Weighted fair value with profile routing, scenarios, and confidence.

    Additive sub-resource: the existing GET on this router keeps its contract.
    All inputs are optional; missing inputs degrade to INSUFFICIENT_DATA.
    Computed snapshot is flushed (never committed) as a deterministic cache.
    """
    service = FairValueService(session)
    return await service.fair_value(
        company_id,
        FairValueInput(
            free_cash_flow=_dec(free_cash_flow),
            growth_rate=_dec(growth_rate),
            stable_growth=_dec(stable_growth),
            discount_rate=_dec(discount_rate),
            terminal_growth_rate=_dec(terminal_growth_rate),
            expected_dps=_dec(expected_dps),
            stable_roe=_dec(stable_roe),
            affo=_dec(affo),
            ffo=_dec(ffo),
            earnings_per_share=_dec(earnings_per_share),
            pe_ratio=_dec(pe_ratio),
            revenue_per_share=_dec(revenue_per_share),
            ps_ratio=_dec(ps_ratio),
            book_value_per_share=_dec(book_value_per_share),
            pb_ratio=_dec(pb_ratio),
            shares_outstanding=_dec(shares_outstanding),
            revenue_growth=_dec(revenue_growth),
            operating_margin=_dec(operating_margin),
            exit_multiple=_dec(exit_multiple),
        ),
    )


def _dec(value: float | None) -> Decimal | None:
    """Query float to Decimal; None stays None and zero stays zero."""
    return Decimal(str(value)) if value is not None else None
