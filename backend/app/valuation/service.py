"""Valuation service for orchestrating valuation calculations."""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.valuation.models import (
    ValuationModel,
    ValuationResult,
    calculate_dcf_valuation,
    calculate_ev_ebitda_valuation,
    calculate_pb_valuation,
    calculate_pe_valuation,
)

logger = logging.getLogger(__name__)


class ValuationInput(NamedTuple):
    """Input data for valuation."""
    company_id: str
    ticker: str
    # P/E inputs
    earnings_per_share: Decimal | None
    pe_ratio: Decimal | None
    # P/B inputs
    book_value_per_share: Decimal | None
    pb_ratio: Decimal | None
    # EV/EBITDA inputs
    ebitda: Decimal | None
    ev_ebitda_ratio: Decimal | None
    net_debt: Decimal | None
    shares_outstanding: Decimal | None
    # DCF inputs
    free_cash_flow: Decimal | None
    growth_rate: Decimal | None
    discount_rate: Decimal | None
    terminal_growth_rate: Decimal | None


class ValuationOutput(NamedTuple):
    """Output of valuation calculation."""
    company_id: str
    ticker: str
    results: list[ValuationResult]
    calculated_at: datetime


class ValuationService:
    """Service for calculating valuations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def calculate_valuations(
        self,
        valuation_input: ValuationInput,
        models: list[ValuationModel] | None = None,
    ) -> ValuationOutput:
        """Calculate valuations for a company.

        Args:
            valuation_input: Company financial data
            models: Specific models to calculate (default: all)

        Returns:
            ValuationOutput with results for each model
        """
        if models is None:
            models = list(ValuationModel)

        results: list[ValuationResult] = []

        # P/E Valuation
        if ValuationModel.PE in models:
            pe_result = calculate_pe_valuation(
                earnings_per_share=valuation_input.earnings_per_share,
                pe_ratio=valuation_input.pe_ratio,
            )
            results.append(pe_result)

        # P/B Valuation
        if ValuationModel.PB in models:
            pb_result = calculate_pb_valuation(
                book_value_per_share=valuation_input.book_value_per_share,
                pb_ratio=valuation_input.pb_ratio,
            )
            results.append(pb_result)

        # EV/EBITDA Valuation
        if ValuationModel.EV_EBITDA in models:
            ev_result = calculate_ev_ebitda_valuation(
                ebitda=valuation_input.ebitda,
                ev_ebitda_ratio=valuation_input.ev_ebitda_ratio,
                net_debt=valuation_input.net_debt,
                shares_outstanding=valuation_input.shares_outstanding,
            )
            results.append(ev_result)

        # DCF Valuation
        if ValuationModel.DCF in models:
            dcf_result = calculate_dcf_valuation(
                free_cash_flow=valuation_input.free_cash_flow,
                growth_rate=valuation_input.growth_rate,
                discount_rate=valuation_input.discount_rate,
                terminal_growth_rate=valuation_input.terminal_growth_rate,
                shares_outstanding=valuation_input.shares_outstanding,
            )
            results.append(dcf_result)

        return ValuationOutput(
            company_id=valuation_input.company_id,
            ticker=valuation_input.ticker,
            results=results,
            calculated_at=datetime.now(UTC),
        )
