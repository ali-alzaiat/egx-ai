"""Market-wide signal ranking: factors, scoring and the cross-sectional engine."""

from app.signals.engine import SignalEngine, SignalRunResult
from app.signals.factors import FactorSet, PriceBar, compute_factors
from app.signals.scoring import (
    DEFAULT_MODEL,
    PRICE_MODEL_V1,
    RankedMarket,
    ScoredCompany,
    ScoringModel,
    SignalTier,
    explain,
    score_market,
    tier_for,
)

__all__ = [
    "DEFAULT_MODEL",
    "PRICE_MODEL_V1",
    "FactorSet",
    "PriceBar",
    "RankedMarket",
    "ScoredCompany",
    "ScoringModel",
    "SignalEngine",
    "SignalRunResult",
    "SignalTier",
    "compute_factors",
    "explain",
    "score_market",
    "tier_for",
]
