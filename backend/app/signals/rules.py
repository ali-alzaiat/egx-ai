"""Pure stance rules (signal-rules-2.0): no I/O, no clock, no database.

The composite is a weighted average over the engines that actually produced
an input, so a missing engine lowers confidence instead of dragging the
stance toward ``reduce`` (the signal-rules-1.0 defect: missing engines scored
0 and BUY was unreachable). Every threshold here is part of the methodology
version; changing one requires a version bump.

Sub-scores live in [-1, 1]; the composite is scaled to [-100, 100].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from app.technical.indicators import (
    IndicatorStatus,
    calculate_atr,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
)

SIGNAL_RULES_VERSION = "signal-rules-2.0"

# Engine weights in the composite (only engines with inputs are averaged).
ENGINE_WEIGHTS: dict[str, Decimal] = {
    "technical": Decimal("40"),
    "valuation": Decimal("35"),
    "score": Decimal("25"),
}
BUY_THRESHOLD = Decimal("25")
REDUCE_THRESHOLD = Decimal("-25")

# Confidence caps.
TECHNICAL_ONLY_CONFIDENCE_CAP = 50
LOW_LIQUIDITY_CONFIDENCE_CAP = 30
STALE_STATEMENTS_CONFIDENCE_CAP = 40

# Technical parameters.
MIN_TECHNICAL_BARS = 20
RSI_PERIOD = 14
RSI_OVERBOUGHT = Decimal("70")
RSI_OVERSOLD = Decimal("30")
RSI_MIDLINE = Decimal("50")
MOMENTUM_BARS = 20
MOMENTUM_BAND = Decimal("0.05")
VOLUME_SURGE_RATIO = Decimal("2")
ATR_PERIOD = 14
UPSIDE_ATR_MULTIPLE = Decimal("2")
DOWNSIDE_ATR_MULTIPLE = Decimal("1.5")
REFERENCE_HORIZON = "swing (1-3 weeks)"

# Liquidity gate (Phase 10/14 rule): trailing average daily value traded.
LIQUIDITY_WINDOW = 20
LOW_LIQUIDITY_EGP = Decimal("500000")

# Statements older than this many days cap confidence.
STALE_STATEMENT_DAYS = 400

_ONE = Decimal("1")
_HUNDRED = Decimal("100")


class Stance(StrEnum):
    BUY = "buy"
    HOLD = "hold"
    REDUCE = "reduce"


@dataclass(frozen=True)
class Bar:
    """One daily bar, oldest first in any sequence passed to this module."""

    close: Decimal
    high: Decimal | None = None
    low: Decimal | None = None
    volume: int | None = None


@dataclass(frozen=True)
class Component:
    """One directional technical vote in {-1, 0, +1} with its explanation."""

    name: str
    vote: int
    detail: str


@dataclass
class TechnicalView:
    subscore: Decimal
    components: list[Component]
    inputs: dict[str, str]
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Liquidity:
    avg_value_traded: Decimal | None
    window: int
    low: bool | None  # None = not enough volume data to judge


@dataclass(frozen=True)
class ReferenceLevels:
    entry: Decimal
    upside: Decimal
    downside: Decimal
    atr: Decimal
    horizon: str


def _q(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _available(result_value: Decimal | None, status: IndicatorStatus) -> Decimal | None:
    return result_value if status == IndicatorStatus.AVAILABLE else None


def technical_view(bars: list[Bar]) -> TechnicalView | None:
    """Technical sub-score: the mean of available trend/momentum votes.

    Returns None when there are fewer than ``MIN_TECHNICAL_BARS`` closes.
    """
    closes = [b.close for b in bars]
    if len(closes) < MIN_TECHNICAL_BARS:
        return None
    price = closes[-1]
    components: list[Component] = []
    inputs: dict[str, str] = {"price": str(price)}
    notes: list[str] = []

    sma20_r = calculate_sma(closes, 20)
    sma50_r = calculate_sma(closes, 50)
    sma200_r = calculate_sma(closes, 200)
    sma20 = _available(sma20_r.value, sma20_r.status)
    sma50 = _available(sma50_r.value, sma50_r.status)
    sma200 = _available(sma200_r.value, sma200_r.status)

    trend_ma, trend_label = (sma50, "SMA50") if sma50 is not None else (sma20, "SMA20")
    if trend_ma is not None:
        inputs[trend_label.lower()] = str(trend_ma)
        vote = 1 if price > trend_ma else -1 if price < trend_ma else 0
        side = "above" if vote > 0 else "below" if vote < 0 else "at"
        components.append(Component("trend", vote, f"Price {side} {trend_label}."))

    if sma50 is not None and sma200 is not None:
        inputs["sma200"] = str(sma200)
        vote = 1 if sma50 > sma200 else -1 if sma50 < sma200 else 0
        side = "above" if vote > 0 else "below" if vote < 0 else "at"
        components.append(Component("long_trend", vote, f"SMA50 {side} SMA200."))

    rsi_r = calculate_rsi(closes, RSI_PERIOD)
    rsi = _available(rsi_r.value, rsi_r.status)
    if rsi is not None:
        inputs["rsi14"] = str(rsi)
        if rsi >= RSI_OVERBOUGHT:
            components.append(Component("rsi", 0, f"RSI {rsi} overbought: no momentum credit."))
        elif rsi <= RSI_OVERSOLD:
            components.append(Component("rsi", 0, f"RSI {rsi} oversold: no momentum penalty."))
        elif rsi > RSI_MIDLINE:
            components.append(Component("rsi", 1, f"RSI {rsi} above 50."))
        else:
            components.append(Component("rsi", -1, f"RSI {rsi} below 50."))

    macd_r = calculate_macd(closes)
    macd = _available(macd_r.value, macd_r.status)
    if macd is not None:
        inputs["macd_line"] = str(macd)
        vote = 1 if macd > 0 else -1 if macd < 0 else 0
        side = "positive" if vote > 0 else "negative" if vote < 0 else "flat"
        components.append(Component("macd", vote, f"MACD line {side} (EMA12 vs EMA26)."))

    if len(closes) > MOMENTUM_BARS and closes[-1 - MOMENTUM_BARS] > 0:
        change = closes[-1] / closes[-1 - MOMENTUM_BARS] - _ONE
        inputs["momentum_20d"] = str(_q(change, "0.0001"))
        pct = _q(change * _HUNDRED, "0.1")
        if change > MOMENTUM_BAND:
            components.append(Component("momentum", 1, f"Up {pct}% over 20 sessions."))
        elif change < -MOMENTUM_BAND:
            components.append(Component("momentum", -1, f"Down {abs(pct)}% over 20 sessions."))
        else:
            components.append(Component("momentum", 0, f"Flat ({pct}%) over 20 sessions."))

    volumes = [b.volume for b in bars[-(LIQUIDITY_WINDOW + 1):] if b.volume is not None]
    if len(volumes) == LIQUIDITY_WINDOW + 1:
        prior = volumes[:-1]
        avg = Decimal(sum(prior)) / Decimal(len(prior))
        if avg > 0:
            ratio = Decimal(volumes[-1]) / avg
            inputs["volume_ratio_20d"] = str(_q(ratio))
            if ratio >= VOLUME_SURGE_RATIO:
                notes.append(f"Unusual volume: {_q(ratio, '0.1')}x the 20-session average.")

    if not components:
        return None
    total = sum((Decimal(c.vote) for c in components), Decimal("0"))
    subscore = total / Decimal(len(components))
    return TechnicalView(subscore=subscore, components=components, inputs=inputs, notes=notes)


def valuation_subscore(
    price: Decimal, bear: Decimal | None, base: Decimal, bull: Decimal | None
) -> Decimal:
    """Price position inside the bear/base/bull scenario range."""
    if bear is not None and price < bear:
        return Decimal("1")
    if price < base:
        return Decimal("0.5")
    if bull is not None and price > bull:
        return Decimal("-1")
    return Decimal("-0.5")


def score_subscore(headline: Decimal) -> Decimal:
    """Investment score 0..100 mapped linearly to -1..1 around 50."""
    return max(Decimal("-1"), min(_ONE, (headline - Decimal("50")) / Decimal("50")))


def composite(subscores: dict[str, Decimal | None]) -> tuple[Decimal | None, Decimal]:
    """Weighted mean of available sub-scores (x100) and engine coverage (0..1)."""
    total_weight = sum(ENGINE_WEIGHTS.values(), Decimal("0"))
    used = {k: v for k, v in subscores.items() if v is not None and k in ENGINE_WEIGHTS}
    if not used:
        return None, Decimal("0")
    weight = sum((ENGINE_WEIGHTS[k] for k in used), Decimal("0"))
    weighted = sum((ENGINE_WEIGHTS[k] * v for k, v in used.items()), Decimal("0"))
    return _q(weighted / weight * _HUNDRED, "0.1"), weight / total_weight


def stance_for(score: Decimal) -> Stance:
    if score >= BUY_THRESHOLD:
        return Stance.BUY
    if score <= REDUCE_THRESHOLD:
        return Stance.REDUCE
    return Stance.HOLD


def confidence_for(
    score: Decimal,
    coverage: Decimal,
    *,
    technical_only: bool,
    low_liquidity: bool,
    stale_statements: bool,
) -> int:
    """Conviction (|score|) scaled by engine coverage, then capped by data gates."""
    raw = (Decimal("50") + abs(score) / Decimal("2")) * coverage
    value = int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    caps = [100]
    if technical_only:
        caps.append(TECHNICAL_ONLY_CONFIDENCE_CAP)
    if low_liquidity:
        caps.append(LOW_LIQUIDITY_CONFIDENCE_CAP)
    if stale_statements:
        caps.append(STALE_STATEMENTS_CONFIDENCE_CAP)
    return max(0, min(value, *caps))


def liquidity(bars: list[Bar]) -> Liquidity:
    """Trailing average daily value traded (close x volume) over the window."""
    window = bars[-LIQUIDITY_WINDOW:]
    values = [b.close * Decimal(b.volume) for b in window if b.volume is not None]
    if len(window) < LIQUIDITY_WINDOW or len(values) < LIQUIDITY_WINDOW:
        return Liquidity(avg_value_traded=None, window=LIQUIDITY_WINDOW, low=None)
    avg = _q(sum(values, Decimal("0")) / Decimal(len(values)))
    return Liquidity(avg_value_traded=avg, window=LIQUIDITY_WINDOW, low=avg < LOW_LIQUIDITY_EGP)


def reference_levels(bars: list[Bar]) -> ReferenceLevels | None:
    """ATR band around the last close: a volatility reference, not a forecast."""
    if any(b.high is None or b.low is None for b in bars):
        bars = [b for b in bars if b.high is not None and b.low is not None]
    highs = [b.high for b in bars if b.high is not None]
    lows = [b.low for b in bars if b.low is not None]
    closes = [b.close for b in bars]
    atr_r = calculate_atr(highs, lows, closes, ATR_PERIOD)
    atr = _available(atr_r.value, atr_r.status)
    if atr is None or atr <= 0:
        return None
    entry = closes[-1]
    downside = entry - DOWNSIDE_ATR_MULTIPLE * atr
    if downside <= 0:
        return None
    return ReferenceLevels(
        entry=_q(entry),
        upside=_q(entry + UPSIDE_ATR_MULTIPLE * atr),
        downside=_q(downside),
        atr=_q(atr, "0.0001"),
        horizon=REFERENCE_HORIZON,
    )
