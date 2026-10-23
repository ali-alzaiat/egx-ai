"""Deterministic technical indicators calculated from market data.

All indicators are pure functions of price data.
No AI or ML is used for indicator calculation.
Each indicator documents its formula and parameters.

References:
- John Murphy - Technical Analysis of the Financial Markets
- Investopedia - Technical Indicators
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import Enum
from typing import NamedTuple


class IndicatorType(Enum):
    """Supported technical indicators."""
    SMA = "sma"
    EMA = "ema"
    RSI = "rsi"
    MACD = "macd"
    BOLLINGER = "bollinger"
    OBV = "obv"
    VWAP = "vwap"
    ATR = "atr"


class IndicatorStatus(Enum):
    """Status of indicator calculation."""
    AVAILABLE = "AVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INVALID = "INVALID"


class IndicatorResult(NamedTuple):
    """Result of a technical indicator calculation."""
    value: Decimal | None
    status: IndicatorStatus
    indicator: IndicatorType
    parameters: dict[str, str | None]
    reason: str | None = None


def _safe_divide(
    numerator: Decimal,
    denominator: Decimal,
    precision: int = 4,
) -> Decimal | None:
    """Safely divide two Decimals."""
    if denominator == 0:
        return None
    try:
        result = numerator / denominator
        return result.quantize(Decimal(10) ** -precision, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def calculate_sma(
    prices: list[Decimal],
    period: int = 20,
) -> IndicatorResult:
    """Calculate Simple Moving Average.

    Formula: SMA = (P1 + P2 + ... + Pn) / n

    Args:
        prices: List of historical prices (oldest first)
        period: Number of periods (default 20)

    Returns:
        IndicatorResult with SMA value
    """
    if len(prices) < period:
        return IndicatorResult(
            value=None,
            status=IndicatorStatus.INSUFFICIENT_DATA,
            indicator=IndicatorType.SMA,
            parameters={"period": str(period)},
            reason=f"Need {period} prices, got {len(prices)}",
        )

    # Use the last 'period' prices
    recent_prices = prices[-period:]
    sma = sum(recent_prices) / Decimal(str(period))

    return IndicatorResult(
        value=sma.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        status=IndicatorStatus.AVAILABLE,
        indicator=IndicatorType.SMA,
        parameters={"period": str(period)},
    )


def calculate_ema(
    prices: list[Decimal],
    period: int = 20,
) -> IndicatorResult:
    """Calculate Exponential Moving Average.

    Formula: EMA = Price × k + EMA_prev × (1 - k)
    where k = 2 / (period + 1)

    Args:
        prices: List of historical prices (oldest first)
        period: Number of periods (default 20)

    Returns:
        IndicatorResult with EMA value
    """
    if len(prices) < period:
        return IndicatorResult(
            value=None,
            status=IndicatorStatus.INSUFFICIENT_DATA,
            indicator=IndicatorType.EMA,
            parameters={"period": str(period)},
            reason=f"Need {period} prices, got {len(prices)}",
        )

    # Calculate multiplier
    k = Decimal("2") / (Decimal(str(period)) + Decimal("1"))

    # Start with SMA of first 'period' prices
    ema = sum(prices[:period]) / Decimal(str(period))

    # Calculate EMA for remaining prices
    for price in prices[period:]:
        ema = price * k + ema * (Decimal("1") - k)

    return IndicatorResult(
        value=ema.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        status=IndicatorStatus.AVAILABLE,
        indicator=IndicatorType.EMA,
        parameters={"period": str(period)},
    )


def calculate_rsi(
    prices: list[Decimal],
    period: int = 14,
) -> IndicatorResult:
    """Calculate Relative Strength Index.

    Formula: RSI = 100 - (100 / (1 + RS))
    where RS = Average Gain / Average Loss

    Args:
        prices: List of historical prices (oldest first)
        period: Number of periods (default 14)

    Returns:
        IndicatorResult with RSI value (0-100)
    """
    if len(prices) < period + 1:
        return IndicatorResult(
            value=None,
            status=IndicatorStatus.INSUFFICIENT_DATA,
            indicator=IndicatorType.RSI,
            parameters={"period": str(period)},
            reason=f"Need {period + 1} prices, got {len(prices)}",
        )

    # Calculate price changes
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]

    # Separate gains and losses
    gains = [c if c > 0 else Decimal("0") for c in changes]
    losses = [-c if c < 0 else Decimal("0") for c in changes]

    # Initial average gain/loss
    avg_gain = sum(gains[:period]) / Decimal(str(period))
    avg_loss = sum(losses[:period]) / Decimal(str(period))

    # Calculate RSI using smoothed averages
    period_decimal = Decimal(str(period))
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period_decimal - Decimal("1")) + gains[i]) / period_decimal
        avg_loss = (avg_loss * (period_decimal - Decimal("1")) + losses[i]) / period_decimal

    # Calculate RS and RSI
    if avg_loss == 0:
        rsi = Decimal("100")
    else:
        rs = avg_gain / avg_loss
        rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))

    return IndicatorResult(
        value=rsi.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        status=IndicatorStatus.AVAILABLE,
        indicator=IndicatorType.RSI,
        parameters={"period": str(period)},
    )


def calculate_macd(
    prices: list[Decimal],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> IndicatorResult:
    """Calculate MACD (Moving Average Convergence Divergence).

    Formula:
    MACD Line = EMA(fast) - EMA(slow)
    Signal Line = EMA(MACD Line, signal_period)
    Histogram = MACD Line - Signal Line

    Args:
        prices: List of historical prices (oldest first)
        fast_period: Fast EMA period (default 12)
        slow_period: Slow EMA period (default 26)
        signal_period: Signal line period (default 9)

    Returns:
        IndicatorResult with MACD line value
    """
    min_required = slow_period + signal_period
    if len(prices) < min_required:
        return IndicatorResult(
            value=None,
            status=IndicatorStatus.INSUFFICIENT_DATA,
            indicator=IndicatorType.MACD,
            parameters={
                "fast_period": str(fast_period),
                "slow_period": str(slow_period),
                "signal_period": str(signal_period),
            },
            reason=f"Need {min_required} prices, got {len(prices)}",
        )

    # Calculate EMAs
    fast_ema_result = calculate_ema(prices, fast_period)
    slow_ema_result = calculate_ema(prices, slow_period)

    if fast_ema_result.value is None or slow_ema_result.value is None:
        return IndicatorResult(
            value=None,
            status=IndicatorStatus.INVALID,
            indicator=IndicatorType.MACD,
            parameters={},
            reason="EMA calculation failed",
        )

    # MACD Line = Fast EMA - Slow EMA
    macd_line = fast_ema_result.value - slow_ema_result.value

    return IndicatorResult(
        value=macd_line.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        status=IndicatorStatus.AVAILABLE,
        indicator=IndicatorType.MACD,
        parameters={
            "fast_period": str(fast_period),
            "slow_period": str(slow_period),
            "signal_period": str(signal_period),
        },
    )


def calculate_bollinger_bands(
    prices: list[Decimal],
    period: int = 20,
    std_dev: Decimal = Decimal("2"),
) -> IndicatorResult:
    """Calculate Bollinger Bands (middle band = SMA).

    Formula:
    Middle Band = SMA(period)
    Upper Band = Middle Band + (std_dev × Standard Deviation)
    Lower Band = Middle Band - (std_dev × Standard Deviation)

    Args:
        prices: List of historical prices (oldest first)
        period: Number of periods (default 20)
        std_dev: Standard deviation multiplier (default 2)

    Returns:
        IndicatorResult with middle band value (SMA)
    """
    if len(prices) < period:
        return IndicatorResult(
            value=None,
            status=IndicatorStatus.INSUFFICIENT_DATA,
            indicator=IndicatorType.BOLLINGER,
            parameters={"period": str(period), "std_dev": str(std_dev)},
            reason=f"Need {period} prices, got {len(prices)}",
        )

    # Calculate SMA (middle band)
    recent_prices = prices[-period:]
    sma = sum(recent_prices) / Decimal(str(period))

    return IndicatorResult(
        value=sma.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        status=IndicatorStatus.AVAILABLE,
        indicator=IndicatorType.BOLLINGER,
        parameters={"period": str(period), "std_dev": str(std_dev)},
    )


def calculate_obv(
    prices: list[Decimal],
    volumes: list[int],
) -> IndicatorResult:
    """Calculate On-Balance Volume.

    Formula:
    If close > previous close: OBV = previous OBV + volume
    If close < previous close: OBV = previous OBV - volume
    If close = previous close: OBV = previous OBV

    Args:
        prices: List of historical closing prices (oldest first)
        volumes: List of historical volumes (oldest first)

    Returns:
        IndicatorResult with OBV value
    """
    if len(prices) < 2 or len(volumes) < 2:
        return IndicatorResult(
            value=None,
            status=IndicatorStatus.INSUFFICIENT_DATA,
            indicator=IndicatorType.OBV,
            parameters={},
            reason="Need at least 2 prices and volumes",
        )

    if len(prices) != len(volumes):
        return IndicatorResult(
            value=None,
            status=IndicatorStatus.INVALID,
            indicator=IndicatorType.OBV,
            parameters={},
            reason="Prices and volumes must have same length",
        )

    # Calculate OBV
    obv = Decimal("0")
    for i in range(1, len(prices)):
        if prices[i] > prices[i - 1]:
            obv += Decimal(str(volumes[i]))
        elif prices[i] < prices[i - 1]:
            obv -= Decimal(str(volumes[i]))

    return IndicatorResult(
        value=obv,
        status=IndicatorStatus.AVAILABLE,
        indicator=IndicatorType.OBV,
        parameters={},
    )


def calculate_vwap(
    prices: list[Decimal],
    volumes: list[int],
    highs: list[Decimal] | None = None,
    lows: list[Decimal] | None = None,
) -> IndicatorResult:
    """Calculate Volume Weighted Average Price.

    Formula: VWAP = Σ(Price × Volume) / Σ(Volume)

    Args:
        prices: List of typical prices (or close prices)
        volumes: List of volumes
        highs: Optional list of high prices (for typical price calculation)
        lows: Optional list of low prices (for typical price calculation)

    Returns:
        IndicatorResult with VWAP value
    """
    if len(prices) == 0 or len(volumes) == 0:
        return IndicatorResult(
            value=None,
            status=IndicatorStatus.INSUFFICIENT_DATA,
            indicator=IndicatorType.VWAP,
            parameters={},
            reason="No data provided",
        )

    if len(prices) != len(volumes):
        return IndicatorResult(
            value=None,
            status=IndicatorStatus.INVALID,
            indicator=IndicatorType.VWAP,
            parameters={},
            reason="Prices and volumes must have same length",
        )

    # Calculate VWAP
    total_pv = Decimal("0")
    total_volume = Decimal("0")

    for i in range(len(prices)):
        price = prices[i]
        volume = Decimal(str(volumes[i]))
        total_pv += price * volume
        total_volume += volume

    if total_volume == 0:
        return IndicatorResult(
            value=None,
            status=IndicatorStatus.INVALID,
            indicator=IndicatorType.VWAP,
            parameters={},
            reason="Total volume is zero",
        )

    vwap = total_pv / total_volume

    return IndicatorResult(
        value=vwap.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        status=IndicatorStatus.AVAILABLE,
        indicator=IndicatorType.VWAP,
        parameters={},
    )


def calculate_atr(
    highs: list[Decimal],
    lows: list[Decimal],
    closes: list[Decimal],
    period: int = 14,
) -> IndicatorResult:
    """Calculate Average True Range (Wilder).

    Formula:
    TR_t = max(high_t - low_t, |high_t - close_{t-1}|, |low_t - close_{t-1}|)
    ATR = SMA of the first ``period`` TRs, then Wilder smoothing:
    ATR_t = (ATR_{t-1} * (period - 1) + TR_t) / period

    Args:
        highs: List of high prices (oldest first)
        lows: List of low prices (oldest first)
        closes: List of close prices (oldest first)
        period: Number of periods (default 14)

    Returns:
        IndicatorResult with ATR value in price units
    """
    parameters: dict[str, str | None] = {"period": str(period)}
    if not (len(highs) == len(lows) == len(closes)):
        return IndicatorResult(
            value=None,
            status=IndicatorStatus.INVALID,
            indicator=IndicatorType.ATR,
            parameters=parameters,
            reason="Highs, lows and closes must have same length",
        )
    if period < 1 or len(closes) < period + 1:
        return IndicatorResult(
            value=None,
            status=IndicatorStatus.INSUFFICIENT_DATA,
            indicator=IndicatorType.ATR,
            parameters=parameters,
            reason=f"Need {period + 1} bars, got {len(closes)}",
        )
    if any(h < lo for h, lo in zip(highs, lows, strict=True)):
        return IndicatorResult(
            value=None,
            status=IndicatorStatus.INVALID,
            indicator=IndicatorType.ATR,
            parameters=parameters,
            reason="A high is below its low",
        )

    true_ranges = [
        max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        for i in range(1, len(closes))
    ]
    period_decimal = Decimal(period)
    atr = sum(true_ranges[:period], Decimal("0")) / period_decimal
    for tr in true_ranges[period:]:
        atr = (atr * (period_decimal - Decimal("1")) + tr) / period_decimal

    return IndicatorResult(
        value=atr.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        status=IndicatorStatus.AVAILABLE,
        indicator=IndicatorType.ATR,
        parameters=parameters,
    )
