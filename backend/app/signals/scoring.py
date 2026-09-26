"""Versioned, deterministic scoring model for market-wide ranking.

The model is intentionally transparent: a fixed set of weighted factors, each
converted to a cross-sectional percentile so a 3-month return in EGP is directly
comparable with a volume ratio, then combined into a 0-100 score.

Design rules this module enforces:

* The model is versioned. Scores are only comparable within a version, and every
  persisted signal records the version that produced it.
* No fundamentals. There are no real financial statements yet, so valuation and
  quality factors are absent by design rather than estimated.
* Missing factors are re-weighted away, never treated as zero. A company with no
  liquidity data is not penalised as if it had none.
* The output is a research signal, not a trade instruction.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from app.signals.factors import FactorSet


class SignalTier(enum.StrEnum):
    """Relative standing within the market on a given day."""

    STRONGEST = "STRONGEST"
    STRONG = "STRONG"
    NEUTRAL = "NEUTRAL"
    WEAK = "WEAK"
    WEAKEST = "WEAKEST"


class FactorDirection(enum.StrEnum):
    """Whether a higher raw factor value is better or worse."""

    HIGHER_IS_BETTER = "HIGHER_IS_BETTER"
    LOWER_IS_BETTER = "LOWER_IS_BETTER"


@dataclass(frozen=True, slots=True)
class FactorSpec:
    """One weighted input to the composite score."""

    key: str
    weight: float
    direction: FactorDirection
    label: str

    def orient(self, value: float) -> float:
        """Flip a value so that higher always means more attractive."""
        return -value if self.direction is FactorDirection.LOWER_IS_BETTER else value


@dataclass(frozen=True, slots=True)
class ScoringModel:
    """A named, versioned set of factor weights."""

    name: str
    version: str
    description: str
    factors: tuple[FactorSpec, ...]
    min_history_days: int = 120
    tiers: tuple[float, float, float, float] = (0.90, 0.75, 0.25, 0.10)

    @property
    def total_weight(self) -> float:
        return sum(f.weight for f in self.factors)

    def describe(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "min_history_days": self.min_history_days,
            "factors": [
                {
                    "key": f.key,
                    "label": f.label,
                    "weight": round(f.weight, 4),
                    "direction": f.direction.value,
                }
                for f in self.factors
            ],
        }


# v1.0.0: price-based only. Fundamentals arrive with the disclosure ingestion
# layer and will be added as a new version, never retro-fitted into this one.
PRICE_MODEL_V1 = ScoringModel(
    name="egx_price_momentum",
    version="1.1.0",
    description=(
        "Cross-sectional blend of medium-term momentum, trend quality, drawdown "
        "risk, volatility, liquidity and volume confirmation. Prices only: no "
        "fundamentals are available yet, so no value or quality factor is "
        "included."
    ),
    factors=(
        FactorSpec("momentum_3m", 0.25, FactorDirection.HIGHER_IS_BETTER,
                   "3-month price momentum"),
        FactorSpec("momentum_6m", 0.10, FactorDirection.HIGHER_IS_BETTER,
                   "6-month price momentum"),
        FactorSpec("trend_alignment", 0.15, FactorDirection.HIGHER_IS_BETTER,
                   "Trend alignment (price vs moving averages)"),
        FactorSpec("volume_confirmation", 0.10, FactorDirection.HIGHER_IS_BETTER,
                   "Volume confirmation"),
        FactorSpec("distance_from_high", 0.10, FactorDirection.LOWER_IS_BETTER,
                   "Distance below 52-week high"),
        FactorSpec("max_drawdown", 0.15, FactorDirection.LOWER_IS_BETTER,
                   "Maximum drawdown (risk)"),
        FactorSpec("volatility", 0.05, FactorDirection.LOWER_IS_BETTER,
                   "Annualised volatility (risk)"),
        FactorSpec("liquidity", 0.10, FactorDirection.HIGHER_IS_BETTER,
                   "Median traded value (tradability)"),
    ),
)

DEFAULT_MODEL = PRICE_MODEL_V1


def percentile_ranks(values: Mapping[str, float]) -> dict[str, float]:
    """Rank values into [0, 1] percentiles, ties sharing their average rank."""
    if not values:
        return {}
    ordered = sorted(values.items(), key=lambda kv: kv[1])
    n = len(ordered)
    ranks: dict[str, float] = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and ordered[j + 1][1] == ordered[i][1]:
            j += 1
        # Average rank across the tied block, normalised to [0, 1].
        avg_rank = (i + j) / 2
        pct = avg_rank / (n - 1) if n > 1 else 0.5
        for k in range(i, j + 1):
            ranks[ordered[k][0]] = pct
        i = j + 1
    return ranks


@dataclass(frozen=True, slots=True)
class ScoredCompany:
    """A company with its composite score and per-factor breakdown."""

    ticker: str
    score: float
    rank: int
    factors: dict[str, float] = field(default_factory=dict)
    percentiles: dict[str, float] = field(default_factory=dict)
    used_weight: float = 0.0
    excluded: tuple[str, ...] = ()
    tier: SignalTier | None = None
    score_percentile: float | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "score": self.score,
            "rank": self.rank,
            "tier": self.tier.value if self.tier else None,
            "score_percentile": self.score_percentile,
            "factors": self.factors,
            "percentiles": self.percentiles,
            "used_weight": round(self.used_weight, 4),
            "excluded_factors": list(self.excluded),
        }


@dataclass(frozen=True, slots=True)
class RankedMarket:
    """The scored market for one date."""

    as_of: object
    model: ScoringModel
    ranked: tuple[ScoredCompany, ...]
    unscorable: Mapping[str, str]

    @property
    def scored_count(self) -> int:
        return len(self.ranked)

    def top(self, limit: int) -> tuple[ScoredCompany, ...]:
        return self.ranked[:limit]


def score_market(
    factor_sets: Sequence[FactorSet],
    model: ScoringModel = DEFAULT_MODEL,
    unscorable: Mapping[str, str] | None = None,
) -> RankedMarket:
    """Score every company against every other company on the same date.

    Args:
        factor_sets: one entry per company, all as of the same date.
        model: the versioned model to apply.
        unscorable: ticker -> reason for companies excluded before scoring.

    Returns:
        A :class:`RankedMarket` with companies ordered best-first. Companies with
        insufficient history are reported in ``unscorable`` with a reason instead
        of being ranked on partial data.
    """
    usable = [fs for fs in factor_sets if fs is not None]
    if not usable:
        return RankedMarket(
            as_of=None, model=model, ranked=(), unscorable=dict(unscorable or {})
        )

    as_of = max(fs.as_of for fs in usable)
    same_day = [fs for fs in usable if fs.as_of == as_of]

    # Cross-sectional percentile for each factor, across the whole market.
    percentile_by_factor: dict[str, dict[str, float]] = {}
    for spec in model.factors:
        raw = {}
        for fs in same_day:
            value = getattr(fs, spec.key, None)
            if value is not None:
                raw[fs.ticker] = spec.orient(float(value))
        percentile_by_factor[spec.key] = percentile_ranks(raw)

    scored: list[ScoredCompany] = []
    for fs in same_day:
        contributions: dict[str, float] = {}
        percentiles: dict[str, float] = {}
        used_weight = 0.0
        weighted_sum = 0.0
        excluded: list[str] = []

        for spec in model.factors:
            value = getattr(fs, spec.key, None)
            pct = percentile_by_factor[spec.key].get(fs.ticker)
            if value is None or pct is None:
                excluded.append(spec.key)
                continue
            contributions[spec.key] = float(value)
            percentiles[spec.key] = pct
            used_weight += spec.weight
            weighted_sum += pct * spec.weight

        if used_weight <= 0:
            # No usable factor at all: do not invent a score.
            continue

        # Re-weight over available factors so a missing input is neutral rather
        # than penalising. A company with only 40% of the model available is
        # still ranked, but its coverage is recorded so callers can discount it.
        score = weighted_sum / used_weight * 100
        score = min(100.0, max(0.0, score))

        scored.append(
            ScoredCompany(
                ticker=fs.ticker,
                score=round(score, 4),
                rank=0,
                factors=contributions,
                percentiles={k: round(v, 6) for k, v in percentiles.items()},
                used_weight=used_weight / model.total_weight
                if model.total_weight
                else 0.0,
                excluded=tuple(excluded),
            )
        )

    scored.sort(key=lambda s: (-s.score, s.ticker))
    # Score percentile is taken over the ranked market so tiers describe
    # relative standing, which is what this model actually measures.
    score_pct = percentile_ranks({s.ticker: s.score for s in scored})
    ranked = tuple(
        ScoredCompany(
            ticker=s.ticker,
            score=s.score,
            rank=i,
            factors=s.factors,
            percentiles=s.percentiles,
            used_weight=s.used_weight,
            excluded=s.excluded,
            score_percentile=round(score_pct[s.ticker], 6),
            tier=tier_for(score_pct[s.ticker], model),
        )
        for i, s in enumerate(scored, start=1)
    )
    return RankedMarket(
        as_of=as_of,
        model=model,
        ranked=ranked,
        unscorable=dict(unscorable or {}),
    )


def tier_for(percentile: float, model: ScoringModel = DEFAULT_MODEL) -> SignalTier:
    """Bucket a company's *score percentile* into a relative standing label.

    ``percentile`` is where the company sits among the scored market on that
    date, in [0, 1]. Tiers are deliberately cut on that relative standing rather
    than on the absolute score: a percentile-weighted composite is by
    construction centred near 50 with a standard deviation around 15, so
    absolute thresholds would leave the top tier permanently empty — measured
    across 199 companies, no score exceeded 79.4.

    This also keeps tiers consistent with the rest of the model, which ranks
    every factor against the market rather than against a fixed level.
    """
    strongest, strong, neutral, weak = model.tiers
    if percentile >= strongest:
        return SignalTier.STRONGEST
    if percentile >= strong:
        return SignalTier.STRONG
    if percentile >= neutral:
        return SignalTier.NEUTRAL
    if percentile >= weak:
        return SignalTier.WEAK
    return SignalTier.WEAKEST


def explain(scored: ScoredCompany, model: ScoringModel = DEFAULT_MODEL) -> str:
    """Build a factual, non-prescriptive description of why a company scored.

    Names the factors that actually contributed, using their percentile standing
    within the market on that date. Deliberately avoids imperative language: this
    is a research observation, not advice.
    """
    if not scored.percentiles:
        return "No comparable factors available on this date."

    by_spec = {s.key: s for s in model.factors}
    parts: list[str] = []
    for key, pct in sorted(
        scored.percentiles.items(), key=lambda kv: kv[1], reverse=True
    ):
        spec = by_spec.get(key)
        if spec is None:
            continue
        parts.append(f"{spec.label} at the {pct * 100:.0f}th percentile of the market")

    if scored.excluded:
        parts.append(
            f"not scored on {len(scored.excluded)} factor(s) due to insufficient data"
        )
    return "; ".join(parts) + "."
