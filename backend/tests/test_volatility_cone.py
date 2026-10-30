"""Volatility cone and its calibration (R47 P3): pure maths plus the read-only endpoint."""

import math
import random
import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import Company, DailyPrice, DataSource, DataSourceType
from app.technical import cone_calibration
from app.technical.cone_calibration import (
    CONE_CALIBRATION_VERSION,
    calibrate,
    calibrate_cached,
    calibration_cases,
    wilson_interval,
)
from app.technical.volatility_cone import (
    HORIZONS,
    NOTE,
    VOLATILITY_CONE_VERSION,
    add_trading_days,
    volatility_cone,
)

Bars = list[tuple[date, Decimal]]


def _bars(closes: list[float], start: date = date(2020, 1, 5)) -> Bars:
    """One bar per EGX trading day (Friday/Saturday skipped) from the day after ``start``."""
    bars: Bars = []
    day = start
    for c in closes:
        day = add_trading_days(day, 1)
        bars.append((day, Decimal(repr(round(c, 4)))))
    return bars


def _lognormal_closes(sigmas: list[float], seed: int) -> list[float]:
    rng = random.Random(seed)
    price = 100.0
    closes: list[float] = []
    for s in sigmas:
        price *= math.exp(rng.gauss(0.0, s))
        closes.append(price)
    return closes


def _lognormal(sigmas: list[float], seed: int) -> Bars:
    return _bars(_lognormal_closes(sigmas, seed))


def _split(bars: Bars) -> tuple[list[date], list[float]]:
    return [d for d, _ in bars], [float(c) for _, c in bars]


# ---- cone maths ---------------------------------------------------------------------------------


def test_cone_matches_hand_calculation() -> None:
    # 121 closes alternating 100, 101, ... ending on 100: 120 returns of +-a, a = ln(1.01).
    # Mean 0, so sigma = a x sqrt(120 / 119).
    bars = _bars([100.0 if i % 2 == 0 else 101.0 for i in range(121)])
    cone = volatility_cone(bars)
    a = math.log(1.01)
    sigma = a * math.sqrt(120 / 119)
    assert cone.status == "AVAILABLE"
    assert cone.reason is None
    assert cone.n_returns == 120
    assert cone.sigma_daily == pytest.approx(sigma, abs=1e-6)
    assert cone.sigma_daily == pytest.approx(0.009992, abs=1e-6)
    assert cone.sigma_annual == pytest.approx(sigma * math.sqrt(252), abs=1e-6)
    assert cone.last_close == "100.0000"
    assert cone.as_of == bars[-1][0]
    assert cone.version == VOLATILITY_CONE_VERSION
    assert cone.note == NOTE
    assert cone.drift == "zero"
    assert [h.days for h in cone.horizons] == [21, 63, 126]

    h21, h126 = cone.horizons[0], cone.horizons[2]
    assert Decimal(h21.p05) == Decimal("92.7448")
    assert Decimal(h21.p25) == Decimal("96.9587")
    assert Decimal(h21.p50) == Decimal("100.0000")
    assert Decimal(h21.p75) == Decimal("103.1367")
    assert Decimal(h21.p95) == Decimal("107.8228")
    assert Decimal(h126.p05) == Decimal("83.1526")
    assert Decimal(h126.p95) == Decimal("120.2608")
    # Independent formula check: P0 x exp(+-z x sigma x sqrt(h)).
    assert float(h21.p95) == pytest.approx(100 * math.exp(1.6449 * sigma * math.sqrt(21)), abs=1e-4)
    assert float(h21.p25) == pytest.approx(
        100 * math.exp(-0.6745 * sigma * math.sqrt(21)), abs=1e-4
    )


def test_cone_bands_are_ordered_and_widen_with_horizon() -> None:
    cone = volatility_cone(_lognormal([0.02] * 300, seed=7))
    widths = []
    for h in cone.horizons:
        assert Decimal(h.p05) < Decimal(h.p25) < Decimal(h.p50) < Decimal(h.p75) < Decimal(h.p95)
        widths.append(Decimal(h.p95) - Decimal(h.p05))
    assert widths == sorted(widths)


def test_cone_uses_only_the_last_252_sessions() -> None:
    wild = [100.0 * (1.5 if i % 2 else 1.0) for i in range(200)]  # old, very volatile
    calm = [100.0 + 0.1 * (i % 2) for i in range(253)]  # the last 252 returns are calm
    cone = volatility_cone(_bars(wild + calm))
    assert cone.n_returns == 252
    assert cone.sigma_daily is not None
    assert cone.sigma_daily < 0.002


def test_cone_needs_120_returns() -> None:
    short = volatility_cone(_lognormal([0.02] * 120, seed=1))  # 120 closes = 119 returns
    assert short.status == "INSUFFICIENT_DATA"
    assert short.n_returns == 119
    assert short.reason is not None and "120" in short.reason and "119" in short.reason
    assert short.sigma_daily is None and short.sigma_annual is None
    assert short.horizons == ()
    assert short.as_of is not None
    enough = volatility_cone(_lognormal([0.02] * 121, seed=1))
    assert enough.status == "AVAILABLE"


def test_cone_without_prices_is_insufficient_not_zero() -> None:
    cone = volatility_cone([])
    assert cone.status == "INSUFFICIENT_DATA"
    assert cone.reason == "no stored prices"
    assert cone.sigma_daily is None
    assert cone.as_of is None


def test_cone_flat_prices_collapse_but_stay_valid() -> None:
    cone = volatility_cone(_bars([50.0] * 200))
    assert cone.status == "AVAILABLE"
    assert cone.sigma_daily == 0.0
    assert cone.sigma_annual == 0.0
    for h in cone.horizons:
        assert Decimal(h.p05) == Decimal(h.p25) == Decimal(h.p50) == Decimal("50.0000")
        assert Decimal(h.p75) == Decimal(h.p95) == Decimal("50.0000")


def test_cone_rejects_non_positive_close() -> None:
    closes = [10.0 + (i % 3) for i in range(200)]
    closes[100] = 0.0
    cone = volatility_cone(_bars(closes))
    assert cone.status == "INSUFFICIENT_DATA"
    assert cone.reason is not None and "non-positive" in cone.reason


def test_cone_input_order_and_duplicates_do_not_matter() -> None:
    bars = _lognormal([0.02] * 200, seed=3)
    shuffled = list(reversed(bars)) + bars[:5]
    assert volatility_cone(shuffled) == volatility_cone(bars)


def test_add_trading_days_skips_friday_and_saturday() -> None:
    thursday = date(2026, 10, 29)
    assert thursday.weekday() == 3
    assert add_trading_days(thursday, 0) == thursday
    assert add_trading_days(thursday, 1) == date(2026, 11, 1)  # Sunday
    sunday = date(2026, 11, 1)
    assert add_trading_days(sunday, 4) == date(2026, 11, 5)  # Thursday
    assert add_trading_days(sunday, 5) == date(2026, 11, 8)  # next Sunday
    friday = date(2026, 10, 30)
    assert add_trading_days(friday, 1) == date(2026, 11, 1)
    assert add_trading_days(thursday, 20) == date(2026, 11, 26)  # four weeks of 5 days
    assert add_trading_days(thursday, 21) == date(2026, 11, 29)


def test_cone_approx_dates_never_fall_on_the_weekend() -> None:
    cone = volatility_cone(_lognormal([0.02] * 200, seed=5))
    assert cone.as_of is not None
    for h in cone.horizons:
        assert h.approx_date.weekday() not in (4, 5)
        assert h.approx_date == add_trading_days(cone.as_of, h.days)
    assert "holiday" in cone.calendar_note


# ---- calibration --------------------------------------------------------------------------------


def test_wilson_interval_known_values() -> None:
    low, high = wilson_interval(50, 100)
    assert low == pytest.approx(0.4038, abs=1e-3)
    assert high == pytest.approx(0.5962, abs=1e-3)
    low0, high0 = wilson_interval(0, 30)
    assert low0 == 0.0 and 0.0 < high0 < 0.15
    low1, high1 = wilson_interval(30, 30)
    assert high1 == 1.0 and 0.85 < low1 < 1.0


def test_calibration_on_stable_lognormal_prices_is_near_nominal() -> None:
    k50 = k90 = n = 0
    for seed in range(1, 9):
        dates, closes = _split(_lognormal([0.02] * 1300, seed))
        cases = calibration_cases(dates, closes, horizon=21)
        k50 += sum(c.inside_50 for c in cases)
        k90 += sum(c.inside_90 for c in cases)
        n += len(cases)
    assert n > 1500
    assert k50 / n == pytest.approx(0.50, abs=0.05)
    assert k90 / n == pytest.approx(0.90, abs=0.05)


def test_calibration_report_shape_on_stable_prices() -> None:
    result = calibrate(_lognormal([0.02] * 1300, seed=2))
    assert result.status == "AVAILABLE"
    assert result.version == CONE_CALIBRATION_VERSION
    assert result.cone_version == VOLATILITY_CONE_VERSION
    assert result.step_sessions == 5
    assert "overlap" in result.note and "optimistic" in result.note
    assert [h.days for h in result.horizons] == list(HORIZONS)
    for h in result.horizons:
        assert h.status == "AVAILABLE" and h.reason is None
        assert h.n_cases >= 30
        assert h.inside_50 is not None and h.inside_50_low is not None
        assert h.inside_50_high is not None and h.inside_90 is not None
        assert h.inside_90_low is not None and h.inside_90_high is not None
        assert h.inside_50_low <= h.inside_50 <= h.inside_50_high
        assert h.inside_90_low <= h.inside_90 <= h.inside_90_high
        assert h.first_case is not None and h.last_case is not None


def test_calibration_coverage_drops_after_a_volatility_jump() -> None:
    """Cases dated just before a 10x volatility jump see a calm sigma but a wild future."""

    def pooled(sigmas: list[float]) -> float:
        k = n = 0
        for seed in range(1, 41):
            dates, closes = _split(_lognormal(sigmas, seed))
            for case in calibration_cases(dates, closes, horizon=21):
                if 580 <= dates.index(case.as_of) < 600:  # the jump is at index 600
                    k += case.inside_90
                    n += 1
        assert n >= 150
        return k / n

    stable = pooled([0.005] * 700)
    jumped = pooled([0.005] * 600 + [0.05] * 100)
    assert stable > 0.85
    assert jumped < 0.50
    assert jumped < stable - 0.35


def test_calibration_cases_start_after_120_returns_step_by_5_and_end_h_before_last() -> None:
    dates, closes = _split(_lognormal([0.02] * 400, seed=4))
    cases = calibration_cases(dates, closes, horizon=21)
    assert cases[0].as_of == dates[120]  # 120 returns exist at index 120
    idx = [dates.index(c.as_of) for c in cases]
    assert [b - a for a, b in zip(idx, idx[1:], strict=False)] == [5] * (len(idx) - 1)
    assert idx[-1] + 21 <= len(closes) - 1 < idx[-1] + 21 + 5


def test_calibration_case_sigma_equals_the_cone_built_from_prices_up_to_then() -> None:
    bars = _lognormal([0.02] * 400, seed=6)
    dates, closes = _split(bars)
    for case in calibration_cases(dates, closes, horizon=21)[::7]:
        i = dates.index(case.as_of)
        cone = volatility_cone(bars[: i + 1])
        assert cone.sigma_daily == pytest.approx(case.sigma_daily, abs=1e-6)
        # The verdict agrees with the cone's published 90% band for that date.
        band = cone.horizons[0]
        assert case.inside_90 == (float(band.p05) <= closes[i + 21] <= float(band.p95))


def test_calibration_never_reads_closes_after_the_case_date() -> None:
    dates, closes = _split(_lognormal([0.02] * 400, seed=9))
    horizon = 21
    base = calibration_cases(dates, closes, horizon)
    cut = 250  # scramble every close after this index
    rng = random.Random(0)
    scrambled = closes[: cut + 1] + [rng.uniform(1.0, 1000.0) for _ in closes[cut + 1 :]]
    other = calibration_cases(dates, scrambled, horizon)
    assert len(base) == len(other)
    straddling = 0
    for a, b in zip(base, other, strict=True):
        i = dates.index(a.as_of)
        assert a.as_of == b.as_of
        if i <= cut:
            # Sigma is built from prices up to the case date only: later closes never touch it.
            assert a.sigma_daily == b.sigma_daily
        else:
            assert a.sigma_daily != b.sigma_daily  # its own past did change
        if i + horizon <= cut:
            assert a == b  # case and target both before the cut: identical verdicts
        if i <= cut < i + horizon:
            straddling += 1
    assert straddling > 0  # the test did exercise cases whose future was scrambled


def test_calibration_horizon_needs_30_cases() -> None:
    # 300 closes: cases for h=21 -> idx 120..278 step 5 = 32, h=63 -> 24, h=126 -> 11.
    result = calibrate(_lognormal([0.02] * 300, seed=8))
    by_days = {h.days: h for h in result.horizons}
    assert result.status == "AVAILABLE"
    assert by_days[21].status == "AVAILABLE" and by_days[21].n_cases == 32
    assert by_days[63].status == "INSUFFICIENT_DATA" and by_days[63].n_cases == 24
    assert by_days[126].status == "INSUFFICIENT_DATA" and by_days[126].n_cases == 11
    for days in (63, 126):
        h = by_days[days]
        assert h.reason is not None and "30" in h.reason
        assert h.inside_50 is None and h.inside_90 is None
        assert h.inside_50_low is None and h.inside_90_high is None


def test_calibration_with_too_little_history_is_insufficient_for_every_horizon() -> None:
    result = calibrate(_lognormal([0.02] * 150, seed=8))
    assert result.status == "INSUFFICIENT_DATA"
    assert result.reason is not None and "150" in result.reason
    assert all(h.status == "INSUFFICIENT_DATA" and h.inside_50 is None for h in result.horizons)
    empty = calibrate([])
    assert empty.status == "INSUFFICIENT_DATA"
    assert empty.n_closes == 0


def test_calibration_flat_prices_are_inside_every_band() -> None:
    result = calibrate(_bars([50.0] * 400))
    assert result.status == "AVAILABLE"
    h = result.horizons[0]
    assert h.inside_50 == 1.0 and h.inside_90 == 1.0  # zero move, zero-width band: still inside


def test_calibration_cache_is_keyed_on_history_and_versions() -> None:
    cone_calibration.clear_cache()
    bars = _lognormal([0.02] * 300, seed=11)
    first = calibrate_cached("co-1", bars)
    assert calibrate_cached("co-1", bars) is first  # served from the cache
    assert calibrate_cached("co-2", bars) is not first  # other company
    older = _lognormal([0.02] * 320, seed=11)
    assert calibrate_cached("co-1", older) is not first  # backfill: other count and last date
    corrected = [*bars[:-1], (bars[-1][0], bars[-1][1] + Decimal("1"))]
    assert calibrate_cached("co-1", corrected) is not first  # same dates, corrected close
    cone_calibration.clear_cache()


# ---- endpoint -----------------------------------------------------------------------------------


async def _seed_prices(db_session: AsyncSession, company: Company, closes: list[float]) -> Bars:
    source = DataSource(
        id=uuid.uuid4(),
        name=f"Cone Source {uuid.uuid4().hex[:8]}",
        source_type=DataSourceType.EGX,
    )
    db_session.add(source)
    await db_session.flush()
    bars = _bars(closes, start=date(2024, 1, 4))
    for d, close in bars:
        db_session.add(
            DailyPrice(
                id=uuid.uuid4(),
                company_id=company.id,
                date=d,
                open=close,
                high=close,
                low=close,
                close=close,
                volume=1000,
                source_id=source.id,
            )
        )
    await db_session.flush()
    return bars


async def test_endpoint_unknown_company_is_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/technical/companies/{uuid.uuid4()}/volatility-cone")
    assert response.status_code == 404


async def test_endpoint_requires_the_token(anon_client: AsyncClient) -> None:
    response = await anon_client.get(f"/api/technical/companies/{uuid.uuid4()}/volatility-cone")
    assert response.status_code in (401, 403)


async def test_endpoint_without_prices_is_200_insufficient_data(
    client: AsyncClient, test_company: Company
) -> None:
    response = await client.get(f"/api/technical/companies/{test_company.id}/volatility-cone")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "INSUFFICIENT_DATA"
    assert body["reason"] == "no stored prices"
    assert body["sigma_daily"] is None
    assert body["horizons"] == []
    assert body["calibration"]["status"] == "INSUFFICIENT_DATA"
    assert [h["status"] for h in body["calibration"]["horizons"]] == ["INSUFFICIENT_DATA"] * 3


async def test_endpoint_returns_cone_and_calibration(
    client: AsyncClient, db_session: AsyncSession, test_company: Company
) -> None:
    bars = await _seed_prices(db_session, test_company, _lognormal_closes([0.02] * 300, seed=12))
    response = await client.get(f"/api/technical/companies/{test_company.id}/volatility-cone")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "version", "status", "reason", "as_of", "last_close", "sigma_daily", "sigma_annual",
        "n_returns", "window_start", "horizons", "z_50", "z_90", "drift", "calendar_note",
        "note", "calibration", "company_id",
    }  # fmt: skip
    assert body["company_id"] == str(test_company.id)
    assert body["status"] == "AVAILABLE"
    assert body["version"] == VOLATILITY_CONE_VERSION
    assert body["as_of"] == bars[-1][0].isoformat()
    assert body["n_returns"] == 252
    assert body["note"] == NOTE
    assert set(body["horizons"][0]) == {"days", "approx_date", "p05", "p25", "p50", "p75", "p95"}
    assert [h["days"] for h in body["horizons"]] == [21, 63, 126]
    assert Decimal(body["horizons"][0]["p50"]) == bars[-1][1]

    calibration = body["calibration"]
    assert calibration["version"] == CONE_CALIBRATION_VERSION
    assert calibration["status"] == "AVAILABLE"
    assert set(calibration) == {
        "version", "cone_version", "status", "reason", "n_closes", "horizons", "step_sessions",
        "min_cases", "nominal_50", "nominal_90", "interval", "note",
    }  # fmt: skip
    assert calibration["n_closes"] == 300
    by_days = {h["days"]: h for h in calibration["horizons"]}
    assert set(by_days[21]) == {
        "days", "status", "reason", "n_cases", "first_case", "last_case", "inside_50",
        "inside_50_low", "inside_50_high", "inside_90", "inside_90_low", "inside_90_high",
    }  # fmt: skip
    assert by_days[21]["status"] == "AVAILABLE" and by_days[21]["n_cases"] == 32
    assert by_days[126]["status"] == "INSUFFICIENT_DATA"
    assert by_days[126]["inside_50"] is None
