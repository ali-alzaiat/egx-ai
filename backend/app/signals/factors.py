"""Cross-sectional price factors for market-wide ranking.

Every factor is a pure function of one company's price history, expressed in
units that are comparable across the whole market. Nothing here looks at a
fundamental, because no real fundamentals exist yet; nothing here invents data,
because a company with too little history yields ``None`` rather than a guess.

Factors return raw values. Turning them into comparable scores is the job of
:mod:`app.signals.scoring`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True, slots=True)
class PriceBar:
    """One daily bar. ``close``/``high``/``low`` are already floats."""

    date: date
    close: float
    high: float
    low: float
    volume: int
    value_traded: float | None = None


@dataclass(frozen=True, slots=True)
class FactorSet:
    """Raw factor values for one company on one date.

    Any factor may be ``None`` when the history cannot support it. The scoring
    layer re-weights around missing factors rather than substituting zero.
    """

    ticker: str
    as_of: date
    observations: int
    momentum_1m: float | None = None
    momentum_3m: float | None = None
    momentum_6m: float | None = None
    trend_alignment: float | None = None
    distance_from_high: float | None = None
    volatility: float | None = None
    max_drawdown: float | None = None
    liquidity: float | None = None
    volume_confirmation: float | None = None

    def as_dict(self) -> dict[str, float | int | str | None]:
        return {
            "ticker": self.ticker,
            "as_of": self.as_of.isoformat(),
            "observations": self.observations,
            "momentum_1m": self.momentum_1m,
            "momentum_3m": self.momentum_3m,
            "momentum_6m": self.momentum_6m,
            "trend_alignment": self.trend_alignment,
            "distance_from_high": self.distance_from_high,
            "volatility": self.volatility,
            "max_drawdown": self.max_drawdown,
            "liquidity": self.liquidity,
            "volume_confirmation": self.volume_confirmation,
        }


def _pct_change(closes: Sequence[float], lookback: int) -> float | None:
    """Percentage change over ``lookback`` bars, or None if unavailable."""
    if len(closes) <= lookback or lookback <= 0:
        return None
    past, now = closes[-1 - lookback], closes[-1]
    if past <= 0:
        return None
    return (now - past) / past


def _sma(values: Sequence[float], window: int) -> float | None:
    if len(values) < window or window <= 0:
        return None
    return sum(values[-window:]) / window


def _stdev(values: Sequence[float]) -> float | None:
    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return math.sqrt(var)


def _max_drawdown(closes: Sequence[float]) -> float | None:
    """Worst peak-to-trough decline, as a positive fraction."""
    if len(closes) < 2:
        return None
    peak = closes[0]
    worst = 0.0
    for price in closes:
        peak = max(peak, price)
        if peak > 0:
            worst = max(worst, (peak - price) / peak)
    return worst


def momentum(closes: Sequence[float], lookback: int) -> float | None:
    """Trailing return over ``lookback`` trading days."""
    return _pct_change(closes, lookback)


def trend_alignment(closes: Sequence[float], short: int = 50, long: int = 200) -> float | None:
    """How strongly price sits above its moving averages.

    Returns a value in roughly [-1, 1]: positive when the short average is above
    the long one and price is above both (an intact uptrend), negative in the
    mirror case.
    """
    if len(closes) < long:
        return None
    price = closes[-1]
    sma_short = _sma(closes, short)
    sma_long = _sma(closes, long)
    if not sma_short or not sma_long or sma_long <= 0:
        return None

    spread = (sma_short - sma_long) / sma_long
    above_short = (price - sma_short) / sma_short
    score = spread + (above_short / 2)
    return max(-1.0, min(1.0, score * 10))


def distance_from_high(closes: Sequence[float], window: int = 252) -> float | None:
    """Gap below the window high, as a fraction. 0.0 means at the high."""
    if len(closes) < 2:
        return None
    recent = closes[-window:] if len(closes) > window else closes
    high = max(recent)
    if high <= 0:
        return None
    return (high - closes[-1]) / high


def annualized_volatility(closes: Sequence[float], window: int = 60) -> float | None:
    """Annualised standard deviation of daily log-free returns."""
    if len(closes) < 3:
        return None
    recent = closes[-window:] if len(closes) > window else closes
    returns = [
        (recent[i] - recent[i - 1]) / recent[i - 1]
        for i in range(1, len(recent))
        if recent[i - 1] > 0
    ]
    sd = _stdev(returns)
    if sd is None:
        return None
    return sd * math.sqrt(TRADING_DAYS_PER_YEAR)


def max_drawdown(closes: Sequence[float]) -> float | None:
    """Worst peak-to-trough decline as a positive fraction."""
    return _max_drawdown(closes)


def median_liquidity(bars: Sequence[PriceBar], window: int = 60) -> float | None:
    """Median daily traded value (EGP). Falls back to close*volume if absent."""
    if not bars:
        return None
    recent = bars[-window:] if len(bars) > window else bars
    values = [
        b.value_traded if b.value_traded and b.value_traded > 0 else b.close * b.volume
        for b in recent
    ]
    values = [v for v in values if v > 0]
    if not values:
        return None
    values.sort()
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2


def volume_confirmation(bars: Sequence[PriceBar], window: int = 20) -> float | None:
    """Ratio of recent average volume to the longer-run average.

    Above 1.0 means participation is building, which corroborates a price move.
    """
    if len(bars) < window + 5:
        return None
    recent = [b.volume for b in bars[-window:]]
    baseline = [b.volume for b in bars[-(window * 3) : -window]] or [
        b.volume for b in bars[:-window]
    ]
    baseline = [v for v in baseline if v > 0]
    recent = [v for v in recent if v > 0]
    if not recent or not baseline:
        return None
    base_avg = sum(baseline) / len(baseline)
    if base_avg <= 0:
        return None
    return (sum(recent) / len(recent)) / base_avg


def compute_factors(
    ticker: str,
    bars: Sequence[PriceBar],
    min_observations: int = 60,
) -> FactorSet | None:
    """Compute the full factor set for one company.

    Returns ``None`` when there is not enough history to say anything
    defensible, so the caller can record the company as unscorable rather than
    ranking it on noise.
    """
    if len(bars) < min_observations:
        return None

    ordered = sorted(bars, key=lambda b: b.date)
    closes = [b.close for b in ordered]
    if any(c <= 0 for c in closes):
        return None

    return FactorSet(
        ticker=ticker,
        as_of=ordered[-1].date,
        observations=len(ordered),
        momentum_1m=momentum(closes, 21),
        momentum_3m=momentum(closes, 63),
        momentum_6m=momentum(closes, 126),
        trend_alignment=trend_alignment(closes),
        distance_from_high=distance_from_high(closes),
        volatility=annualized_volatility(closes),
        max_drawdown=max_drawdown(closes),
        liquidity=median_liquidity(ordered),
        volume_confirmation=volume_confirmation(ordered),
    )
