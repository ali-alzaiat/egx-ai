"""Volatility-cone calibration (R47 P3, owner-approved): did the cone hold on this stock's history?

Pure and deterministic: no database, clock or I/O (the in-process cache only memoises results).

For every past date ``t`` (every ``STEP_SESSIONS`` = 5 sessions, starting once ``MIN_RETURNS``
returns exist and ending ``h`` sessions before the last close) the cone is rebuilt from the closes
up to and including ``t`` only, with the same sigma rule as ``volatility_cone`` (last 252
sessions). The close ``h`` sessions later is then checked against the 50% and 90% bands:
``|ln(close_t+h / close_t)| <= z x sigma x sqrt(h)``. The report per horizon is the share of
cases that landed inside each band, with a Wilson 95% interval. A horizon with fewer than
``MIN_CASES`` (30) cases is INSUFFICIENT_DATA with the reason.

Sessions are stored bars (one per date), as in the cone itself. Cases are 5 sessions apart while
the horizon is 21-126 sessions, so they overlap heavily: the intervals treat cases as
independent and are therefore optimistic. Changing any constant requires bumping
``CONE_CALIBRATION_VERSION``.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from app.technical.volatility_cone import (
    HORIZONS,
    MIN_RETURNS,
    VOLATILITY_CONE_VERSION,
    WINDOW_SESSIONS,
    Z_50,
    Z_90,
    daily_sigma,
)

CONE_CALIBRATION_VERSION = "cone-calibration-1.0"
STEP_SESSIONS = 5
MIN_CASES = 30
#: Wilson interval confidence: 95% (two-sided standard-normal z).
WILSON_Z = 1.96
CACHE_MAX_ENTRIES = 256

OVERLAP_NOTE = (
    "Cases are 5 sessions apart but each looks 21-126 sessions ahead, so they overlap and are "
    "not independent: the intervals are optimistic. Past coverage does not guarantee future "
    "coverage."
)


@dataclass(frozen=True, slots=True)
class CalibrationCase:
    """One past date: the cone built from prices up to ``as_of`` and where the price landed."""

    as_of: date
    sigma_daily: float
    inside_50: bool
    inside_90: bool


@dataclass(frozen=True, slots=True)
class HorizonCalibration:
    days: int
    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    reason: str | None
    n_cases: int
    first_case: date | None = None
    last_case: date | None = None
    inside_50: float | None = None
    inside_50_low: float | None = None
    inside_50_high: float | None = None
    inside_90: float | None = None
    inside_90_low: float | None = None
    inside_90_high: float | None = None


@dataclass(frozen=True, slots=True)
class ConeCalibration:
    version: str
    cone_version: str
    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    reason: str | None
    n_closes: int
    horizons: tuple[HorizonCalibration, ...]
    step_sessions: int = STEP_SESSIONS
    min_cases: int = MIN_CASES
    nominal_50: float = 0.5
    nominal_90: float = 0.9
    interval: str = "Wilson 95%"
    note: str = OVERLAP_NOTE


def wilson_interval(successes: int, n: int, z: float = WILSON_Z) -> tuple[float, float]:
    """Wilson score interval for a share ``successes / n`` (``n`` > 0)."""
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def _ordered(bars: Sequence[tuple[date, Decimal]]) -> list[tuple[date, Decimal]]:
    by_date: dict[date, Decimal] = {}
    for d, close in bars:
        by_date.setdefault(d, close)
    return sorted(by_date.items())


def calibration_cases(
    dates: Sequence[date], closes: Sequence[float], horizon: int
) -> list[CalibrationCase]:
    """Back-tested cones for one horizon. ``closes`` are oldest first and all positive.

    The cone at index ``i`` reads ``closes[max(0, i - 252) : i + 1]`` for sigma and
    ``closes[i + horizon]`` only as the outcome it is scored against.
    """
    cases: list[CalibrationCase] = []
    spread = math.sqrt(horizon)
    for i in range(MIN_RETURNS, len(closes) - horizon, STEP_SESSIONS):
        sigma = daily_sigma(closes[max(0, i - WINDOW_SESSIONS) : i + 1])
        move = abs(math.log(closes[i + horizon] / closes[i]))
        cases.append(
            CalibrationCase(
                as_of=dates[i],
                sigma_daily=sigma,
                inside_50=move <= Z_50 * sigma * spread,
                inside_90=move <= Z_90 * sigma * spread,
            )
        )
    return cases


def _horizon_result(horizon: int, cases: Sequence[CalibrationCase]) -> HorizonCalibration:
    n = len(cases)
    if n < MIN_CASES:
        return HorizonCalibration(
            days=horizon,
            status="INSUFFICIENT_DATA",
            reason=f"needs at least {MIN_CASES} back-tested cases, have {n}",
            n_cases=n,
        )
    k50 = sum(1 for c in cases if c.inside_50)
    k90 = sum(1 for c in cases if c.inside_90)
    lo50, hi50 = wilson_interval(k50, n)
    lo90, hi90 = wilson_interval(k90, n)
    return HorizonCalibration(
        days=horizon,
        status="AVAILABLE",
        reason=None,
        n_cases=n,
        first_case=cases[0].as_of,
        last_case=cases[-1].as_of,
        inside_50=round(k50 / n, 4),
        inside_50_low=round(lo50, 4),
        inside_50_high=round(hi50, 4),
        inside_90=round(k90 / n, 4),
        inside_90_low=round(lo90, 4),
        inside_90_high=round(hi90, 4),
    )


def calibrate(bars: Sequence[tuple[date, Decimal]]) -> ConeCalibration:
    """Calibration of the cone over ``(date, close)`` bars (any order, first bar per date wins)."""
    ordered = _ordered(bars)
    n_closes = len(ordered)

    def insufficient(reason: str) -> ConeCalibration:
        return ConeCalibration(
            version=CONE_CALIBRATION_VERSION,
            cone_version=VOLATILITY_CONE_VERSION,
            status="INSUFFICIENT_DATA",
            reason=reason,
            n_closes=n_closes,
            horizons=tuple(
                HorizonCalibration(days=h, status="INSUFFICIENT_DATA", reason=reason, n_cases=0)
                for h in HORIZONS
            ),
        )

    if any(close <= 0 for _, close in ordered):
        return insufficient("a non-positive close in the history: log returns undefined")
    dates = [d for d, _ in ordered]
    closes = [float(c) for _, c in ordered]
    results = tuple(_horizon_result(h, calibration_cases(dates, closes, h)) for h in HORIZONS)
    if all(r.status == "INSUFFICIENT_DATA" for r in results):
        return ConeCalibration(
            version=CONE_CALIBRATION_VERSION,
            cone_version=VOLATILITY_CONE_VERSION,
            status="INSUFFICIENT_DATA",
            reason=f"{n_closes} stored closes are too few to back-test any horizon",
            n_closes=n_closes,
            horizons=results,
        )
    return ConeCalibration(
        version=CONE_CALIBRATION_VERSION,
        cone_version=VOLATILITY_CONE_VERSION,
        status="AVAILABLE",
        reason=None,
        n_closes=n_closes,
        horizons=results,
    )


_CacheKey = tuple[str, date, date, int, str, str, str]
_CACHE: dict[_CacheKey, ConeCalibration] = {}


def clear_cache() -> None:
    _CACHE.clear()


def calibrate_cached(company_key: str, bars: Sequence[tuple[date, Decimal]]) -> ConeCalibration:
    """``calibrate`` memoised per (company, first/last date, bar count, sum of closes, versions).

    The first date, bar count and sum of closes are part of the key so a history backfill or a
    price correction that leaves the last date unchanged is not served a stale answer.
    """
    if not bars:
        return calibrate(bars)
    dates = [d for d, _ in bars]
    key: _CacheKey = (
        company_key,
        min(dates),
        max(dates),
        len(bars),
        str(sum(close for _, close in bars)),
        CONE_CALIBRATION_VERSION,
        VOLATILITY_CONE_VERSION,
    )
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    result = calibrate(bars)
    if len(_CACHE) >= CACHE_MAX_ENTRIES:
        _CACHE.clear()
    _CACHE[key] = result
    return result
