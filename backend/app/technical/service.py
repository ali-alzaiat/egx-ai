"""Technical analysis service."""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

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
