"""API endpoints for investment scores."""

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.scores.checks import ScoreInputs
from app.scores.constants import DEFAULT_MARGIN_OF_SAFETY
from app.scores.service import ScoreService

router = APIRouter(prefix="/api/scores", tags=["scores"])


class ScoreAssessBody(BaseModel):
    """Caller-supplied check inputs; every field optional, fractions not percents.

    Anything left out is read from stored rows (latest price, Phase-3 fair-value
    snapshot, latest AVAILABLE metrics, data-quality assessments) or degrades
    its checks to NOT_RUN. Nothing is defaulted or invented.
    """

    margin_of_safety: float | None = Field(
        default=None, description="Buy-Zone margin, 0 <= mos < 1; default 0.20"
    )
    pe_ratio: float | None = None
    market_pe_avg: float | None = None
    industry_pe_avg: float | None = None
    pb_ratio: float | None = None
    industry_pb_avg: float | None = None
    eps_growth_1y: float | None = None
    industry_eps_growth_avg: float | None = None
    eps_now: float | None = None
    eps_5y_ago: float | None = None
    eps_growth_now: float | None = None
    eps_growth_5y_avg: float | None = None
    roe_now: float | None = None
    roce_now: float | None = None
    roce_3y_ago: float | None = None
    roa_now: float | None = None
    industry_roa_avg: float | None = None
    st_assets: float | None = None
    st_liabilities: float | None = None
    lt_liabilities: float | None = None
    de_ratio_now: float | None = None
    de_ratio_5y_ago: float | None = None
    operating_cash_flow: float | None = None
    total_debt: float | None = None
    ebit: float | None = None
    net_interest_expense: float | None = None
    total_assets: float | None = None
    total_equity: float | None = None
    bank_allowance: float | None = None
    bank_npl: float | None = None
    bank_deposits: float | None = None
    bank_total_liabilities: float | None = None
    bank_net_loans: float | None = None
    bank_net_charge_offs: float | None = None
    bank_avg_loans: float | None = None
    dps_history: list[float] | None = Field(
        default=None, description="DPS oldest -> newest; year count = length unless set"
    )
    dividend_years: int | None = None
    earnings_payout: float | None = None
    hist_earnings_growth: float | None = None
    hist_revenue_growth: float | None = None


def _dec(value: float | None) -> Decimal | None:
    """Body float to Decimal; None stays None and zero stays zero."""
    return Decimal(str(value)) if value is not None else None


def _to_inputs(body: ScoreAssessBody) -> ScoreInputs:
    return ScoreInputs(
        pe_ratio=_dec(body.pe_ratio),
        market_pe_avg=_dec(body.market_pe_avg),
        industry_pe_avg=_dec(body.industry_pe_avg),
        pb_ratio=_dec(body.pb_ratio),
        industry_pb_avg=_dec(body.industry_pb_avg),
        eps_growth_1y=_dec(body.eps_growth_1y),
        industry_eps_growth_avg=_dec(body.industry_eps_growth_avg),
        eps_now=_dec(body.eps_now),
        eps_5y_ago=_dec(body.eps_5y_ago),
        eps_growth_now=_dec(body.eps_growth_now),
        eps_growth_5y_avg=_dec(body.eps_growth_5y_avg),
        roe_now=_dec(body.roe_now),
        roce_now=_dec(body.roce_now),
        roce_3y_ago=_dec(body.roce_3y_ago),
        roa_now=_dec(body.roa_now),
        industry_roa_avg=_dec(body.industry_roa_avg),
        st_assets=_dec(body.st_assets),
        st_liabilities=_dec(body.st_liabilities),
        lt_liabilities=_dec(body.lt_liabilities),
        de_ratio_now=_dec(body.de_ratio_now),
        de_ratio_5y_ago=_dec(body.de_ratio_5y_ago),
        operating_cash_flow=_dec(body.operating_cash_flow),
        total_debt=_dec(body.total_debt),
        ebit=_dec(body.ebit),
        net_interest_expense=_dec(body.net_interest_expense),
        total_assets=_dec(body.total_assets),
        total_equity=_dec(body.total_equity),
        bank_allowance=_dec(body.bank_allowance),
        bank_npl=_dec(body.bank_npl),
        bank_deposits=_dec(body.bank_deposits),
        bank_total_liabilities=_dec(body.bank_total_liabilities),
        bank_net_loans=_dec(body.bank_net_loans),
        bank_net_charge_offs=_dec(body.bank_net_charge_offs),
        bank_avg_loans=_dec(body.bank_avg_loans),
        dps_history=tuple(Decimal(str(d)) for d in body.dps_history)
        if body.dps_history is not None
        else (),
        dividend_years=body.dividend_years,
        earnings_payout=_dec(body.earnings_payout),
        hist_earnings_growth=_dec(body.hist_earnings_growth),
        hist_revenue_growth=_dec(body.hist_revenue_growth),
    )


@router.get("/companies/{company_id}")
async def get_score(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Latest investment-score snapshot under the current methodology version.

    Read-only: 404 for an unknown company; a known but unassessed company
    returns ``assessment: null`` (never a default score).
    """
    service = ScoreService(session)
    return await service.latest_payload(company_id)


@router.post("/companies/{company_id}/assess")
async def assess_score(
    company_id: uuid.UUID,
    body: ScoreAssessBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Compute, snapshot, and return the investment score for a company.

    Last-writer-wins: the snapshot key is company + methodology version, so
    differing inputs overwrite one row and ``inputs_echo`` reflects the
    latest write. 404 for an unknown company.
    """
    margin = (
        _dec(body.margin_of_safety)
        if body.margin_of_safety is not None
        else DEFAULT_MARGIN_OF_SAFETY
    )
    assert margin is not None
    if margin < 0 or margin >= 1:
        raise HTTPException(
            status_code=400, detail="margin_of_safety must satisfy 0 <= mos < 1"
        )
    service = ScoreService(session)
    return await service.assess(company_id, _to_inputs(body), margin)
