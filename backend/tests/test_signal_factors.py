"""Tests for cross-sectional factors.

Covers the edge cases required by AGENTS.md: insufficient history, flat prices,
zero volume and single observations must never produce a fabricated value.
"""

from datetime import date, timedelta

import pytest

from app.signals.factors import (
    PriceBar,
    annualized_volatility,
    compute_factors,
    distance_from_high,
    max_drawdown,
    median_liquidity,
    momentum,
    trend_alignment,
    volume_confirmation,
)


def make_bars(
    count: int,
    start: float = 100.0,
    step: float = 1.0,
    volume: int = 1_000_000,
    start_day: date = date(2025, 1, 1),
) -> list[PriceBar]:
    """Build a simple ascending price series."""
    bars = []
    for i in range(count):
        close = start + step * i
        bars.append(
            PriceBar(
                date=start_day + timedelta(days=i),
                close=close,
                high=close * 1.01,
                low=close * 0.99,
                volume=volume,
            )
        )
    return bars


class TestMomentum:
    def test_positive_momentum(self):
        assert momentum([100.0, 110.0], 1) == pytest.approx(0.1)

    def test_negative_momentum(self):
        assert momentum([100.0, 90.0], 1) == pytest.approx(-0.1)

    def test_insufficient_history_returns_none(self):
        assert momentum([100.0, 110.0], 5) is None

    def test_zero_lookback_returns_none(self):
        assert momentum([100.0, 110.0], 0) is None

    def test_zero_prior_price_returns_none(self):
        """A zero base price cannot yield a percentage change."""
        assert momentum([0.0, 50.0], 1) is None


class TestTrendAlignment:
    def test_uptrend_is_positive(self):
        closes = [float(100 + i) for i in range(250)]
        assert trend_alignment(closes) > 0

    def test_downtrend_is_negative(self):
        closes = [float(300 - i) for i in range(250)]
        assert trend_alignment(closes) < 0

    def test_insufficient_history_returns_none(self):
        assert trend_alignment([1.0] * 50) is None

    def test_bounded_to_unit_range(self):
        closes = [float(100 + i * 50) for i in range(300)]
        value = trend_alignment(closes)
        assert value is not None
        assert -1.0 <= value <= 1.0


class TestDistanceFromHigh:
    def test_at_high_is_zero(self):
        assert distance_from_high([1.0, 2.0, 3.0]) == pytest.approx(0.0)

    def test_below_high_is_positive(self):
        assert distance_from_high([3.0, 2.0]) == pytest.approx(1 / 3)

    def test_single_price_returns_none(self):
        assert distance_from_high([5.0]) is None

    def test_all_zero_returns_none(self):
        assert distance_from_high([0.0, 0.0]) is None


class TestVolatility:
    def test_flat_prices_have_zero_volatility(self):
        assert annualized_volatility([100.0] * 30) == pytest.approx(0.0)

    def test_insufficient_returns_none(self):
        assert annualized_volatility([100.0, 101.0]) is None

    def test_volatile_prices_exceed_flat(self):
        calm = annualized_volatility([100.0 + (i % 2) for i in range(60)])
        wild = annualized_volatility([100.0 + (i % 11) * 5 for i in range(60)])
        assert calm is not None and wild is not None
        assert wild > calm


class TestMaxDrawdown:
    def test_monotonic_rise_has_no_drawdown(self):
        assert max_drawdown([1.0, 2.0, 3.0]) == pytest.approx(0.0)

    def test_known_drawdown(self):
        # peak 100 -> trough 50 is a 50% decline
        assert max_drawdown([100.0, 50.0]) == pytest.approx(0.5)

    def test_uses_worst_of_several(self):
        assert max_drawdown([100.0, 50.0, 100.0, 80.0]) == pytest.approx(0.5)

    def test_insufficient_returns_none(self):
        assert max_drawdown([1.0]) is None


class TestLiquidity:
    def test_uses_median(self):
        bars = make_bars(10, volume=100)
        outlier = PriceBar(
            date=bars[0].date, close=1.0, high=1.0, low=1.0, volume=10_000_000
        )
        value = median_liquidity([outlier, *bars[1:]])
        assert value == pytest.approx(100.0 * 105.5, rel=1e-6)

    def test_empty_returns_none(self):
        assert median_liquidity([]) is None

    def test_zero_volume_returns_none(self):
        bars = make_bars(5, volume=0)
        assert median_liquidity(bars) is None

    def test_falls_back_to_close_times_volume(self):
        bar = PriceBar(date=date(2025, 1, 1), close=10.0, high=10.0, low=10.0, volume=100)
        assert median_liquidity([bar]) == pytest.approx(1000.0)


class TestVolumeConfirmation:
    def test_rising_volume_above_baseline(self):
        bars = make_bars(80, volume=1_000_000)
        louder = [
            PriceBar(date=b.date, close=b.close, high=b.high, low=b.low, volume=2_000_000)
            if i >= 60
            else b
            for i, b in enumerate(bars)
        ]
        value = volume_confirmation(louder)
        assert value is not None
        assert value > 1.0

    def test_insufficient_history_returns_none(self):
        assert volume_confirmation(make_bars(10)) is None

    def test_zero_volume_returns_none(self):
        assert volume_confirmation(make_bars(80, volume=0)) is None


class TestComputeFactors:
    def test_returns_none_below_min_observations(self):
        """Too little history must yield no factors, not noisy ones."""
        assert compute_factors("TEST", make_bars(30), min_observations=60) is None

    def test_produces_full_factor_set(self):
        result = compute_factors("TEST", make_bars(260), min_observations=60)
        assert result is not None
        assert result.ticker == "TEST"
        assert result.observations == 260
        assert result.momentum_3m is not None
        assert result.trend_alignment is not None
        assert result.volatility is not None
        assert result.max_drawdown is not None
        assert result.liquidity is not None

    def test_rejects_non_positive_prices(self):
        bars = make_bars(260)
        bars[100] = PriceBar(
            date=bars[100].date, close=0.0, high=0.0, low=0.0, volume=1
        )
        assert compute_factors("TEST", bars, min_observations=60) is None

    def test_sorts_unordered_input(self):
        bars = make_bars(260)
        shuffled = list(reversed(bars))
        a = compute_factors("T", bars, min_observations=60)
        b = compute_factors("T", shuffled, min_observations=60)
        assert a is not None and b is not None
        assert a.as_of == b.as_of
        assert a.momentum_3m == b.momentum_3m

    def test_short_series_leaves_long_factors_none(self):
        """A 70-bar series can support momentum but not a 200-bar trend."""
        result = compute_factors("TEST", make_bars(70), min_observations=60)
        assert result is not None
        assert result.momentum_1m is not None
        assert result.trend_alignment is None
