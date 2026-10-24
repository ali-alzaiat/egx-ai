"""Technical analysis service."""

import json
import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import Company, DailyPrice
from app.models.technical import IndicatorStatusDB, IndicatorTypeDB, TechnicalIndicator
from app.technical.indicators import (
    IndicatorResult,
    IndicatorType,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_macd,
    calculate_obv,
    calculate_rsi,
    calculate_sma,
    calculate_vwap,
)

logger = logging.getLogger(__name__)

#: Compute-state version of the stored-prices technical engine (R43).
TECHNICAL_METHODOLOGY_VERSION = "technical-1.0"


class TechnicalInput(NamedTuple):
    """Input data for technical analysis."""
    company_id: str
    ticker: str
    prices: list[Decimal]
    volumes: list[int]
    highs: list[Decimal] | None = None
    lows: list[Decimal] | None = None


class TechnicalOutput(NamedTuple):
    """Output of technical analysis."""
    company_id: str
    ticker: str
    indicators: list[IndicatorResult]
    calculated_at: datetime


class TechnicalService:
    """Service for calculating technical indicators."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def calculate_indicators(
        self,
        technical_input: TechnicalInput,
        indicator_types: list[IndicatorType] | None = None,
    ) -> TechnicalOutput:
        """Calculate technical indicators.

        Args:
            technical_input: Price and volume data
            indicator_types: Specific indicators to calculate (default: all)

        Returns:
            TechnicalOutput with indicator results
        """
        if indicator_types is None:
            indicator_types = list(IndicatorType)

        indicators: list[IndicatorResult] = []

        # SMA
        if IndicatorType.SMA in indicator_types:
            sma_result = calculate_sma(technical_input.prices)
            indicators.append(sma_result)

        # EMA
        if IndicatorType.EMA in indicator_types:
            ema_result = calculate_ema(technical_input.prices)
            indicators.append(ema_result)

        # RSI
        if IndicatorType.RSI in indicator_types:
            rsi_result = calculate_rsi(technical_input.prices)
            indicators.append(rsi_result)

        # MACD
        if IndicatorType.MACD in indicator_types:
            macd_result = calculate_macd(technical_input.prices)
            indicators.append(macd_result)

        # Bollinger Bands
        if IndicatorType.BOLLINGER in indicator_types:
            bollinger_result = calculate_bollinger_bands(technical_input.prices)
            indicators.append(bollinger_result)

        # OBV
        if IndicatorType.OBV in indicator_types:
            obv_result = calculate_obv(technical_input.prices, technical_input.volumes)
            indicators.append(obv_result)

        # VWAP
        if IndicatorType.VWAP in indicator_types:
            vwap_result = calculate_vwap(
                technical_input.prices,
                technical_input.volumes,
                technical_input.highs,
                technical_input.lows,
            )
            indicators.append(vwap_result)

        return TechnicalOutput(
            company_id=technical_input.company_id,
            ticker=technical_input.ticker,
            indicators=indicators,
            calculated_at=datetime.now(UTC),
        )

    async def compute_from_prices(
        self, company_id: uuid.UUID
    ) -> tuple[TechnicalOutput, date | None]:
        """Indicators over every stored bar (ascending), replacing the company's set.

        Same lookback the client used to send (the full stored series). With no
        bars every indicator is INSUFFICIENT_DATA; nothing is invented.
        """
        company = await self.session.get(Company, company_id)
        if company is None:
            raise LookupError(f"company {company_id} not found")
        bars = (
            await self.session.execute(
                select(DailyPrice)
                .where(DailyPrice.company_id == company_id)
                .order_by(DailyPrice.date.asc())
            )
        ).scalars().all()
        price_as_of = bars[-1].date if bars else None
        output = await self.calculate_indicators(
            TechnicalInput(
                company_id=str(company_id),
                ticker=company.ticker,
                prices=[b.close for b in bars],
                volumes=[int(b.volume) for b in bars],
                highs=[b.high for b in bars],
                lows=[b.low for b in bars],
            )
        )
        await self.session.execute(
            delete(TechnicalIndicator).where(TechnicalIndicator.company_id == company_id)
        )
        for result in output.indicators:
            self.session.add(
                TechnicalIndicator(
                    company_id=company_id,
                    indicator_type=IndicatorTypeDB(result.indicator.value),
                    value=result.value,
                    status=IndicatorStatusDB(result.status.value),
                    parameters=json.dumps(result.parameters) if result.parameters else None,
                    reason=result.reason,
                    calculated_at=output.calculated_at,
                )
            )
        await self.session.flush()
        return output, price_as_of
