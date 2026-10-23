"""Pure stance rules (signal-rules-2.0): composite, thresholds, caps, levels."""

from decimal import Decimal

import pytest

from app.signals.rules import (
    BUY_THRESHOLD,
    LOW_LIQUIDITY_CONFIDENCE_CAP,
    REDUCE_THRESHOLD,
    STALE_STATEMENTS_CONFIDENCE_CAP,
    TECHNICAL_ONLY_CONFIDENCE_CAP,
    Bar,
    Stance,
    composite,
    confidence_for,
    liquidity,
    reference_levels,
    score_subscore,
    stance_for,
    technical_view,
    valuation_subscore,
)

D = Decimal


def _bars(
    closes: list[Decimal], spread: Decimal = D("1"), volume: int | None = 100_000
) -> list[Bar]:
    return [Bar(close=c, high=c + spread, low=c - spread, volume=volume) for c in closes]


def _trend(start: Decimal, daily: Decimal, n: int) -> list[Decimal]:
    out = [start]
    for _ in range(n - 1):
        out.append((out[-1] * (D("1") + daily)).quantize(D("0.0001")))
    return out


class TestComposite:
    def test_missing_engines_do_not_bias_the_score(self) -> None:
        # v1 defect: a perfect technical read with no fundamentals was "reduce".
        score, coverage = composite({"technical": D("1"), "valuation": None, "score": None})
        assert score == D("100.0")
        assert coverage == D("0.4")
        assert stance_for(score) == Stance.BUY

    def test_weighted_mean_over_available_engines(self) -> None:
        score, coverage = composite({"technical": D("1"), "valuation": D("-1"), "score": None})
        # (40*1 + 35*-1) / 75 * 100 = 6.67
        assert score == D("6.7")
        assert coverage == D("0.75")

    def test_all_missing_is_none_not_zero(self) -> None:
        score, coverage = composite({"technical": None, "valuation": None, "score": None})
        assert score is None
        assert coverage == D("0")

    def test_negative_zero_and_full_coverage(self) -> None:
        score, coverage = composite({"technical": D("0"), "valuation": D("0"), "score": D("0")})
        assert score == D("0.0")
        assert coverage == D("1")


class TestStanceThresholds:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (BUY_THRESHOLD, Stance.BUY),
            (BUY_THRESHOLD - D("0.1"), Stance.HOLD),
            (D("0"), Stance.HOLD),
            (REDUCE_THRESHOLD + D("0.1"), Stance.HOLD),
            (REDUCE_THRESHOLD, Stance.REDUCE),
            (D("-100"), Stance.REDUCE),
        ],
    )
    def test_boundaries(self, score: Decimal, expected: Stance) -> None:
        assert stance_for(score) == expected


class TestConfidence:
    def test_full_conviction_full_coverage(self) -> None:
        assert confidence_for(
            D("100"), D("1"), technical_only=False, low_liquidity=False, stale_statements=False
        ) == 100

    def test_neutral_score_is_fifty_times_coverage(self) -> None:
        assert confidence_for(
            D("0"), D("0.4"), technical_only=False, low_liquidity=False, stale_statements=False
        ) == 20

    @pytest.mark.parametrize(
        ("flags", "cap"),
        [
            ({"technical_only": True}, TECHNICAL_ONLY_CONFIDENCE_CAP),
            ({"low_liquidity": True}, LOW_LIQUIDITY_CONFIDENCE_CAP),
            ({"stale_statements": True}, STALE_STATEMENTS_CONFIDENCE_CAP),
        ],
    )
    def test_caps(self, flags: dict[str, bool], cap: int) -> None:
        kwargs = {"technical_only": False, "low_liquidity": False, "stale_statements": False}
        kwargs.update(flags)
        assert confidence_for(D("100"), D("1"), **kwargs) == cap

    def test_lowest_cap_wins(self) -> None:
        assert confidence_for(
            D("100"), D("1"), technical_only=True, low_liquidity=True, stale_statements=True
        ) == LOW_LIQUIDITY_CONFIDENCE_CAP


class TestValuationSubscore:
    @pytest.mark.parametrize(
        ("price", "expected"),
        [
            (D("79"), D("1")),  # below bear
            (D("80"), D("0.5")),  # at bear, below base
            (D("99"), D("0.5")),
            (D("100"), D("-0.5")),  # at base
            (D("120"), D("-0.5")),  # at bull
            (D("121"), D("-1")),  # above bull
        ],
    )
    def test_regions(self, price: Decimal, expected: Decimal) -> None:
        assert valuation_subscore(price, D("80"), D("100"), D("120")) == expected

    def test_missing_bear_and_bull(self) -> None:
        assert valuation_subscore(D("50"), None, D("100"), None) == D("0.5")
        assert valuation_subscore(D("150"), None, D("100"), None) == D("-0.5")


class TestScoreSubscore:
    @pytest.mark.parametrize(
        ("headline", "expected"),
        [(D("100"), D("1")), (D("0"), D("-1")), (D("50"), D("0")), (D("75"), D("0.5")),
         (D("130"), D("1")), (D("-10"), D("-1"))],
    )
    def test_linear_and_clamped(self, headline: Decimal, expected: Decimal) -> None:
        assert score_subscore(headline) == expected


class TestTechnicalView:
    def test_insufficient_bars(self) -> None:
        assert technical_view(_bars([D("10")] * 19)) is None
        assert technical_view([]) is None

    def test_uptrend_is_positive_and_buy_reachable(self) -> None:
        view = technical_view(_bars(_trend(D("10"), D("0.01"), 220)))
        assert view is not None
        votes = {c.name: c.vote for c in view.components}
        assert votes["trend"] == 1
        assert votes["long_trend"] == 1
        assert votes["macd"] == 1
        assert votes["momentum"] == 1
        assert votes["rsi"] == 0  # straight-line gains: RSI 100, overbought gets no credit
        score, _ = composite({"technical": view.subscore})
        assert score is not None and stance_for(score) == Stance.BUY

    def test_downtrend_is_negative(self) -> None:
        view = technical_view(_bars(_trend(D("50"), D("-0.01"), 220)))
        assert view is not None
        assert view.subscore < 0
        score, _ = composite({"technical": view.subscore})
        assert score is not None and stance_for(score) == Stance.REDUCE

    def test_flat_series_is_hold(self) -> None:
        view = technical_view(_bars([D("10")] * 60))
        assert view is not None
        assert view.subscore == 0

    def test_short_history_uses_sma20_and_skips_long_trend(self) -> None:
        view = technical_view(_bars(_trend(D("10"), D("0.01"), 30)))
        assert view is not None
        names = {c.name for c in view.components}
        assert "trend" in names
        assert "long_trend" not in names
        assert "sma20" in view.inputs

    def test_volume_surge_note_does_not_vote(self) -> None:
        bars = _bars(_trend(D("10"), D("0.01"), 60))
        bars[-1] = Bar(close=bars[-1].close, high=bars[-1].high, low=bars[-1].low, volume=500_000)
        view = technical_view(bars)
        assert view is not None
        assert any("Unusual volume" in note for note in view.notes)
        assert all(c.name != "volume" for c in view.components)


class TestLiquidity:
    def test_liquid(self) -> None:
        liq = liquidity(_bars([D("10")] * 20, volume=100_000))  # 1,000,000 EGP/day
        assert liq.avg_value_traded == D("1000000.00")
        assert liq.low is False

    def test_low(self) -> None:
        liq = liquidity(_bars([D("10")] * 20, volume=10_000))  # 100,000 EGP/day
        assert liq.low is True

    def test_short_window_is_unknown(self) -> None:
        liq = liquidity(_bars([D("10")] * 19))
        assert liq.low is None
        assert liq.avg_value_traded is None

    def test_missing_volume_is_unknown_not_zero(self) -> None:
        liq = liquidity(_bars([D("10")] * 20, volume=None))
        assert liq.low is None


class TestReferenceLevels:
    def test_atr_band(self) -> None:
        levels = reference_levels(_bars([D("10")] * 20, spread=D("1")))  # ATR 2
        assert levels is not None
        assert levels.entry == D("10.00")
        assert levels.upside == D("14.00")  # +2 ATR
        assert levels.downside == D("7.00")  # -1.5 ATR
        assert levels.atr == D("2.0000")

    def test_zero_volatility_has_no_levels(self) -> None:
        assert reference_levels(_bars([D("10")] * 20, spread=D("0"))) is None

    def test_downside_at_or_below_zero_has_no_levels(self) -> None:
        assert reference_levels(_bars([D("1")] * 20, spread=D("1"))) is None

    def test_too_few_bars(self) -> None:
        assert reference_levels(_bars([D("10")] * 14)) is None
