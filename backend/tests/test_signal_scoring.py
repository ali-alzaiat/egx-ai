"""Tests for the versioned cross-sectional scoring model."""

import dataclasses
from datetime import date

import pytest

from app.signals.factors import FactorSet
from app.signals.scoring import (
    DEFAULT_MODEL,
    PRICE_MODEL_V1,
    FactorDirection,
    FactorSpec,
    ScoringModel,
    SignalTier,
    explain,
    percentile_ranks,
    score_market,
    tier_for,
)

AS_OF = date(2026, 9, 24)


def fs(ticker: str, **kwargs) -> FactorSet:
    """Build a fully populated FactorSet, overridable per test."""
    defaults = dict(
        as_of=AS_OF,
        observations=260,
        momentum_1m=0.05,
        momentum_3m=0.15,
        momentum_6m=0.30,
        trend_alignment=0.4,
        distance_from_high=0.05,
        volatility=0.25,
        max_drawdown=0.10,
        liquidity=5_000_000.0,
        volume_confirmation=1.1,
    )
    defaults.update(kwargs)
    return FactorSet(ticker=ticker, **defaults)


class TestPercentileRanks:
    def test_empty_returns_empty(self):
        assert percentile_ranks({}) == {}

    def test_single_value_is_midpoint(self):
        assert percentile_ranks({"A": 1.0}) == {"A": 0.5}

    def test_ascending_order(self):
        ranks = percentile_ranks({"low": 1.0, "mid": 2.0, "high": 3.0})
        assert ranks["low"] < ranks["mid"] < ranks["high"]
        assert ranks["low"] == 0.0
        assert ranks["high"] == 1.0

    def test_ties_share_average_rank(self):
        ranks = percentile_ranks({"a": 5.0, "b": 5.0, "c": 9.0})
        assert ranks["a"] == ranks["b"]
        assert ranks["a"] < ranks["c"]

    def test_all_ties_all_equal(self):
        ranks = percentile_ranks({"a": 1.0, "b": 1.0, "c": 1.0})
        assert len(set(ranks.values())) == 1


class TestScoreMarket:
    def test_ranks_best_first(self):
        market = score_market([
            fs("WEAK", momentum_3m=-0.2, trend_alignment=-0.5, max_drawdown=0.6),
            fs("STRONG", momentum_3m=0.9, trend_alignment=0.9, max_drawdown=0.02),
            fs("MID", momentum_3m=0.1, trend_alignment=0.1, max_drawdown=0.2),
        ])
        assert [c.ticker for c in market.ranked] == ["STRONG", "MID", "WEAK"]
        assert [c.rank for c in market.ranked] == [1, 2, 3]

    def test_ranks_are_deterministic(self):
        sets = [fs(f"T{i}", momentum_3m=i / 10) for i in range(10)]
        first = [c.ticker for c in score_market(sets).ranked]
        second = [c.ticker for c in score_market(list(reversed(sets))).ranked]
        assert first == second

    def test_ties_broken_by_ticker(self):
        market = score_market([fs("ZZZ"), fs("AAA")])
        assert [c.ticker for c in market.ranked] == ["AAA", "ZZZ"]

    def test_scores_bounded_zero_to_hundred(self):
        market = score_market([fs(f"T{i}", momentum_3m=i) for i in range(50)])
        for scored in market.ranked:
            assert 0.0 <= scored.score <= 100.0

    def test_empty_input(self):
        market = score_market([])
        assert market.ranked == ()
        assert market.as_of is None

    def test_lower_is_better_factors_are_inverted(self):
        """A company with a *lower* drawdown must not be penalised."""
        market = score_market([
            fs("SAFE", max_drawdown=0.01, volatility=0.05),
            fs("RISKY", max_drawdown=0.90, volatility=1.50),
        ])
        assert market.ranked[0].ticker == "SAFE"
        assert market.ranked[0].percentiles["max_drawdown"] == 1.0
        assert market.ranked[1].percentiles["max_drawdown"] == 0.0

    def test_missing_factor_is_reweighted_not_zeroed(self):
        """A company lacking one factor is scored on the rest, and flagged."""
        partial = fs("PARTIAL")
        partial = FactorSet(
            ticker=partial.ticker,
            as_of=partial.as_of,
            observations=partial.observations,
            momentum_3m=partial.momentum_3m,
            trend_alignment=partial.trend_alignment,
            liquidity=partial.liquidity,
        )
        market = score_market([partial, fs("FULL")])
        by_ticker = {c.ticker: c for c in market.ranked}
        assert "PARTIAL" in by_ticker
        assert by_ticker["PARTIAL"].excluded
        assert by_ticker["PARTIAL"].used_weight < 1.0
        # Still ranked on comparable footing, not treated as all-zero.
        assert by_ticker["PARTIAL"].score > 0

    def test_all_factors_missing_is_excluded_not_scored(self):
        bare = FactorSet(ticker="BARE", as_of=AS_OF, observations=260)
        market = score_market([bare, fs("REAL")], unscorable={"BARE": "no data"})
        assert [c.ticker for c in market.ranked] == ["REAL"]
        assert market.unscorable["BARE"] == "no data"

    def test_unscorable_passthrough(self):
        market = score_market([fs("A")], unscorable={"B": "no price data"})
        assert market.unscorable == {"B": "no price data"}

    def test_only_latest_date_is_scored(self):
        """Companies on different dates must not be compared to each other."""
        market = score_market([
            fs("OLD", as_of=date(2026, 9, 23)),
            fs("NEW", as_of=AS_OF),
        ])
        assert [c.ticker for c in market.ranked] == ["NEW"]


class TestScoringModel:
    def test_version_is_recorded(self):
        assert DEFAULT_MODEL.version
        assert DEFAULT_MODEL.name

    def test_weights_sum_to_one(self):
        assert DEFAULT_MODEL.total_weight == pytest.approx(1.0)

    def test_no_fundamental_factors_in_v1(self):
        """v1 is price-only by design; fundamentals arrive as a new version."""
        keys = {f.key for f in PRICE_MODEL_V1.factors}
        assert not keys & {"pe_ratio", "pb_ratio", "roe", "debt_to_equity"}

    def test_every_factor_exists_on_factorset(self):
        """A factor name in the model must resolve against FactorSet."""

        sample = fs("A")
        for spec in PRICE_MODEL_V1.factors:
            assert hasattr(sample, spec.key), spec.key

    def test_description_matches_actual_factors(self):
        """Guards against the description claiming a factor that is not weighted."""
        keys = {f.key for f in PRICE_MODEL_V1.factors}
        assert "liquidity" in keys
        assert "liquidity" in PRICE_MODEL_V1.description.lower()

    def test_all_computed_factors_are_used(self):
        """No factor is computed and then silently ignored by the model."""
        from app.signals.factors import FactorSet

        fields = {f.name for f in dataclasses.fields(FactorSet)}
        computed = {
            "momentum_1m", "momentum_3m", "momentum_6m", "trend_alignment",
            "distance_from_high", "volatility", "max_drawdown", "liquidity",
            "volume_confirmation",
        }
        assert computed <= fields
        keys = {f.key for f in PRICE_MODEL_V1.factors}
        assert computed - keys == {"momentum_1m"}, (
            "momentum_1m is intentionally informational only; everything else "
            "must be weighted"
        )

    def test_describe_is_serialisable(self):
        described = DEFAULT_MODEL.describe()
        assert described["version"] == DEFAULT_MODEL.version
        assert len(described["factors"]) == len(DEFAULT_MODEL.factors)

    def test_orient_flips_lower_is_better(self):
        spec = FactorSpec("x", 0.5, FactorDirection.LOWER_IS_BETTER, "X")
        assert spec.orient(0.2) == -0.2
        spec_high = FactorSpec("x", 0.5, FactorDirection.HIGHER_IS_BETTER, "X")
        assert spec_high.orient(0.2) == 0.2

    def test_custom_model_changes_weights(self):
        model = ScoringModel(
            name="momentum_only",
            version="9.9.9",
            description="test",
            factors=(FactorSpec("momentum_3m", 1.0, FactorDirection.HIGHER_IS_BETTER, "3M"),),
        )
        market = score_market([fs("A", momentum_3m=0.1), fs("B", momentum_3m=0.9)], model)
        assert market.ranked[0].ticker == "B"


class TestTier:
    """Tiers are cut on score percentile within the market, not absolute score."""

    def test_thresholds(self):
        assert tier_for(1.0) is SignalTier.STRONGEST
        assert tier_for(0.80) is SignalTier.STRONG
        assert tier_for(0.50) is SignalTier.NEUTRAL
        assert tier_for(0.15) is SignalTier.WEAK
        assert tier_for(0.0) is SignalTier.WEAKEST

    def test_boundaries(self):
        assert tier_for(0.90) is SignalTier.STRONGEST
        assert tier_for(0.8999) is SignalTier.STRONG
        assert tier_for(0.75) is SignalTier.STRONG
        assert tier_for(0.7499) is SignalTier.NEUTRAL

    def test_every_tier_is_reachable(self):
        """A percentile-average score never reaches 90, so absolute cuts would
        leave STRONGEST empty forever. Ranking the tiers must still populate it."""
        market = score_market([fs(f"T{i:03d}", momentum_3m=i / 200) for i in range(100)])
        tiers = {c.tier for c in market.ranked}
        assert SignalTier.STRONGEST in tiers
        assert SignalTier.WEAKEST in tiers

    def test_tier_share_is_reasonable(self):
        market = score_market([fs(f"T{i:03d}", momentum_3m=i / 200) for i in range(200)])
        counts: dict[SignalTier, int] = {}
        for c in market.ranked:
            counts[c.tier] = counts.get(c.tier, 0) + 1
        # Top decile at most, bottom tail small.
        assert counts[SignalTier.STRONGEST] == 20
        assert counts[SignalTier.WEAKEST] <= 30

    def test_low_absolute_score_can_still_be_top_tier(self):
        """Guards the regression: 0.80 top-decile beats a 0.79 absolute cut."""
        market = score_market([fs("A", momentum_3m=0.9), fs("B", momentum_3m=0.0)])
        assert market.ranked[0].ticker == "A"
        assert market.ranked[0].tier is SignalTier.STRONGEST
        assert market.ranked[1].tier is SignalTier.WEAKEST

    def test_tied_scores_share_a_tier(self):
        market = score_market([fs("A"), fs("B"), fs("C")])
        assert {c.tier for c in market.ranked} == {SignalTier.NEUTRAL}


class TestExplain:
    def test_mentions_top_factors(self):
        market = score_market([fs("A", momentum_3m=0.9, trend_alignment=0.8), fs("B")])
        text = explain(market.ranked[0], DEFAULT_MODEL)
        assert "percentile" in text
        assert "momentum" in text.lower()

    def test_empty_percentiles_message(self):
        from app.signals.scoring import ScoredCompany

        scored = ScoredCompany(ticker="X", score=50.0, rank=1)
        assert "No comparable factors" in explain(scored, DEFAULT_MODEL)

    def test_notes_missing_data(self):
        from app.signals.scoring import ScoredCompany

        scored = ScoredCompany(
            ticker="X", score=50.0, rank=1,
            percentiles={"momentum_3m": 0.9},
            excluded=("volatility", "max_drawdown"),
        )
        text = explain(scored, DEFAULT_MODEL)
        assert "insufficient data" in text

    def test_never_gives_trading_instruction(self):
        """AGENTS.md: output must not read as a buy/sell instruction."""
        market = score_market([fs(f"T{i}", momentum_3m=i / 10) for i in range(20)])
        for scored in market.ranked:
            text = explain(scored, DEFAULT_MODEL).lower()
            for forbidden in ("buy", "sell", "should buy", "recommend buying"):
                assert forbidden not in text
