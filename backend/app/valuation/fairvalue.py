"""Pure, deterministic fair-value composition (no I/O, no clock, no database).

Weighting, bull/base/bear derivation, the data-quality-fed confidence ladder,
and verdict copy all live here so they are unit-testable in isolation.
Thresholds and weights come from ``app.valuation.constants`` (methodology
version 1.0); changing any value requires a version bump.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.valuation.constants import (
    CONFIDENCE_LADDER,
    SCENARIO_EXIT_DELTA,
    SCENARIO_GROWTH_DELTA,
    SCENARIO_MARGIN_DELTA,
)


@dataclass(frozen=True, slots=True)
class TikrInputs:
    """The three adjustable valuation inputs (TIKR-style)."""

    revenue_growth: Decimal
    operating_margin: Decimal
    exit_multiple: Decimal


@dataclass(frozen=True, slots=True)
class Confidence:
    """Confidence level derived from a data-quality score."""

    level: str
    required_discount: Decimal
    dq_score: float | None
    dq_status: str | None
    reason: str


def weighted_fair_value(
    legs: dict[str, Decimal | None],
    weights: dict[str, Decimal],
) -> tuple[Decimal | None, int]:
    """Weight per-model values; missing legs are skipped, never zero-filled.

    Returns (weighted value or None when no leg has data, n_with_data).
    """
    total = Decimal("0")
    weight_sum = Decimal("0")
    n_with_data = 0
    for key, value in legs.items():
        weight = weights.get(key)
        if value is None or weight is None:
            continue
        total += value * weight
        weight_sum += weight
        n_with_data += 1
    if n_with_data == 0 or weight_sum <= 0:
        return (None, 0)
    return (total / weight_sum, n_with_data)


def scenario_inputs(base: TikrInputs, direction: int) -> TikrInputs:
    """Derive bull (+1) / base (0) / bear (-1) inputs with fixed deltas."""
    if direction == 0:
        return base
    sign = Decimal("1") if direction > 0 else Decimal("-1")
    return TikrInputs(
        revenue_growth=base.revenue_growth + sign * SCENARIO_GROWTH_DELTA,
        operating_margin=base.operating_margin + sign * SCENARIO_MARGIN_DELTA,
        exit_multiple=base.exit_multiple + sign * SCENARIO_EXIT_DELTA,
    )


def confidence_for_dq(
    dq_score: float | None,
    dq_status: str | None,
) -> Confidence:
    """Map a financial-statements quality score onto the confidence ladder.

    No assessment on file caps confidence at POOR (most conservative
    required discount); a MISSING assessment reports MISSING. Both degrade
    honestly instead of defaulting to a confident verdict.
    """
    if dq_status == "MISSING":
        return Confidence(
            level="MISSING",
            required_discount=Decimal("0.30"),
            dq_score=dq_score,
            dq_status=dq_status,
            reason="Financial-statements data-quality assessment is MISSING",
        )
    if dq_score is None:
        return Confidence(
            level="POOR",
            required_discount=Decimal("0.30"),
            dq_score=None,
            dq_status=dq_status,
            reason="No financial-statements quality assessment on file",
        )
    for level, threshold, required in CONFIDENCE_LADDER:
        if dq_score >= threshold:
            return Confidence(
                level=level,
                required_discount=required,
                dq_score=dq_score,
                dq_status=dq_status,
                reason=f"Financial-statements quality score {dq_score:.1f}/100",
            )
    return Confidence(
        level="POOR",
        required_discount=Decimal("0.30"),
        dq_score=dq_score,
        dq_status=dq_status,
        reason=f"Financial-statements quality score {dq_score:.1f}/100",
    )


def verdict_for(
    fair_value: Decimal | None,
    current_price: Decimal | None,
    required_discount: Decimal,
) -> dict[str, Any]:
    """Compare fair value to price with widening-margin language.

    Never a BUY/SELL instruction: only "potentially ... under these
    assumptions" phrasing. Missing inputs report INSUFFICIENT_DATA.
    """
    if fair_value is None or current_price is None or fair_value <= 0:
        return {
            "label": "INSUFFICIENT_DATA",
            "detail": (
                "No verdict: fair value or current price is unavailable, "
                "so no comparison is made."
            ),
            "discount": None,
        }
    discount = (fair_value - current_price) / fair_value
    if discount >= required_discount:
        return {
            "label": "POTENTIALLY_UNDERVALUED",
            "detail": (
                "Price is below fair value by more than the required margin "
                "for this confidence level; potentially undervalued under "
                "these assumptions."
            ),
            "discount": str(discount),
        }
    if discount <= -required_discount:
        return {
            "label": "POTENTIALLY_OVERVALUED",
            "detail": (
                "Price is above fair value by more than the required margin "
                "for this confidence level; potentially overvalued under "
                "these assumptions."
            ),
            "discount": str(discount),
        }
    return {
        "label": "AROUND_FAIR_VALUE",
        "detail": (
            "Price is within the required margin of fair value for this "
            "confidence level; around fair value under these assumptions."
        ),
        "discount": str(discount),
    }
