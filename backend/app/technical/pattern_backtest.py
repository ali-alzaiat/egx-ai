"""Measured odds for chart patterns on EGX history (R47 P4, P6). Display only, not a forecast.

For every stock and every confirmed occurrence (``patterns.detect_patterns``, which uses only
data available at the confirmation session) the forward return is measured from the
confirmation close to ``h`` sessions later, ``h`` in (20, 60), on the stored daily closes (a
session is a stored bar).

* **Hit**: the forward return has the expected sign (up patterns > 0, down patterns < 0; an
  unchanged price is not a hit). A symmetrical triangle is split by the direction it broke.
* **Base rate**: the share of *all* stock-days in the same universe and the same period (every
  session from ``WARMUP_SESSIONS`` of each stock's history that has an ``h``-session forward
  return) whose forward return had that same sign. Occurrences earlier than the warm-up are
  excluded so both sides cover the same period.
* Per pattern key and horizon: n, hits, hit rate, base rate, difference, Wilson 95% interval of
  the hit rate, median forward return, and whether the interval excludes the base rate.
  Fewer than ``MIN_CASES`` (30) cases gives INSUFFICIENT_DATA ("too few cases (n)").
* Caveats carried in the result: occurrences overlap in time across stocks (a market-wide move
  confirms many patterns at once) and 20/60-session windows of neighbouring occurrences overlap,
  so cases are not independent and the Wilson interval understates the true uncertainty.

* **Forming odds (R47 P6)**, per pattern type, from ``patterns.forming_events``: every
  overlap-filtered shape from ``WARMUP_SESSIONS``, measured from the session it became known
  (``t0``), not from a breakout. Shapes still unresolved at the end of the data are left out
  (their outcome is unknown). Reported: how many confirmed (Wilson interval), failed or expired,
  and, for shapes with an expected direction, the same hit / base / median cells from ``t0``. A
  symmetrical triangle has no expected direction before it breaks, so it gets no hit cells; the
  share of its breaks that went up is reported instead.

The universe result is cached in-process, keyed by (newest price date, stored bar count,
``PATTERNS_VERSION``); the first request after new prices computes it (off the event loop).

CLI: ``python -m app.technical.pattern_backtest`` prints the stats table from the configured
database (read only).
"""

import asyncio
import math
import statistics
import uuid
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import DailyPrice
from app.repositories.company import CompanyRepository
from app.repositories.price import PriceRepository
from app.technical.patterns import (
    FORMING_DIRECTION,
    FORMING_NOTE,
    KEY_DIRECTION,
    MIN_SESSIONS,
    NOTE,
    PATTERN_TYPES,
    PATTERNS_VERSION,
    STATS_KEYS,
    Direction,
    FormingPattern,
    detect_patterns,
    forming_events,
    forming_now,
    forming_to_dict,
    occurrence_to_dict,
)

HORIZONS: tuple[int, ...] = (20, 60)
MIN_CASES = 30
WILSON_Z = 1.96
WARMUP_SESSIONS = MIN_SESSIONS
RECENT_DAYS = 365
MAX_HISTORY_SESSIONS = 2000

OVERLAP_NOTE = (
    "Occurrences overlap in time across stocks and forward windows overlap within a stock, so "
    "cases are not independent and the interval is narrower than the true uncertainty."
)

Series = Sequence[tuple[date, float]]


def wilson_interval(hits: int, n: int, z: float = WILSON_Z) -> tuple[float, float]:
    """Wilson score interval for a proportion (``n`` must be positive)."""
    p = hits / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


@dataclass(frozen=True, slots=True)
class HorizonStats:
    key: str
    horizon: int
    n: int
    n_companies: int
    hits: int
    hit_rate: float | None
    base_rate: float | None
    difference: float | None
    wilson_low: float | None
    wilson_high: float | None
    median_return: float | None
    reason: str | None

    @property
    def sufficient(self) -> bool:
        return self.reason is None

    def to_dict(self) -> dict[str, Any]:
        if not self.sufficient:
            return {
                "status": "INSUFFICIENT_DATA",
                "value": None,
                "reason": self.reason,
                "n": self.n,
                "n_companies": self.n_companies,
            }
        assert self.hit_rate is not None and self.base_rate is not None
        assert self.wilson_low is not None and self.wilson_high is not None
        return {
            "status": "OK",
            "n": self.n,
            "n_companies": self.n_companies,
            "hits": self.hits,
            "hit_rate": round(self.hit_rate, 4),
            "base_rate": round(self.base_rate, 4),
            "difference": round(self.hit_rate - self.base_rate, 4),
            "wilson_low": round(self.wilson_low, 4),
            "wilson_high": round(self.wilson_high, 4),
            "median_return": round(self.median_return or 0.0, 4),
            "interval_excludes_base": not (self.wilson_low <= self.base_rate <= self.wilson_high),
        }


@dataclass(frozen=True, slots=True)
class FormingStats:
    """Outcomes of shapes measured from the forming stage, for one pattern type."""

    pattern: str
    expected: Direction | None
    n: int  # resolved shapes
    n_companies: int
    confirmed: int
    confirmed_up: int
    failed: int
    expired: int
    horizons: dict[int, HorizonStats]

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "expected": self.expected,
            "n": self.n,
            "n_companies": self.n_companies,
            "horizons": {str(h): cell.to_dict() for h, cell in self.horizons.items()},
        }
        if self.n < MIN_CASES:
            out.update(
                {
                    "status": "INSUFFICIENT_DATA",
                    "value": None,
                    "reason": f"too few cases ({self.n})",
                }
            )
            return out
        low, high = wilson_interval(self.confirmed, self.n)
        out.update(
            {
                "status": "OK",
                "confirmed": self.confirmed,
                "failed": self.failed,
                "expired": self.expired,
                "confirm_rate": round(self.confirmed / self.n, 4),
                "confirm_wilson_low": round(low, 4),
                "confirm_wilson_high": round(high, 4),
                "up_break_share": (
                    round(self.confirmed_up / self.confirmed, 4) if self.confirmed else None
                ),
            }
        )
        return out


@dataclass(frozen=True, slots=True)
class BacktestResult:
    version: str
    as_of: date | None
    period_start: date | None
    companies: int
    stock_days: int
    stats: dict[str, dict[int, HorizonStats]] = field(default_factory=dict)
    forming: dict[str, FormingStats] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stats": {
                key: {str(h): cell.to_dict() for h, cell in by_h.items()}
                for key, by_h in self.stats.items()
            },
            "forming_stats": {key: s.to_dict() for key, s in self.forming.items()},
            "universe": {
                "companies": self.companies,
                "stock_days": self.stock_days,
                "period_start": self.period_start.isoformat() if self.period_start else None,
                "period_end": self.as_of.isoformat() if self.as_of else None,
                "horizons": list(HORIZONS),
                "min_cases": MIN_CASES,
            },
            "overlap_note": OVERLAP_NOTE,
        }


def _forward(closes: Sequence[float], idx: int, horizon: int) -> float | None:
    if idx + horizon >= len(closes):
        return None
    return closes[idx + horizon] / closes[idx] - 1.0


def base_counts(closes: Sequence[float], horizon: int) -> tuple[int, int, int]:
    """(up, down, total) stock-days from ``WARMUP_SESSIONS`` with a ``horizon``-session return."""
    up = down = total = 0
    for i in range(WARMUP_SESSIONS, len(closes) - horizon):
        r = closes[i + horizon] / closes[i] - 1.0
        total += 1
        if r > 0:
            up += 1
        elif r < 0:
            down += 1
    return up, down, total


def _cell(
    key: str,
    h: int,
    returns: Sequence[float],
    stocks: set[Any],
    direction: Direction,
    base: Sequence[int],
) -> HorizonStats:
    """Hit / base / interval / median for one key and horizon."""
    n = len(returns)
    up, down, total = base
    if n < MIN_CASES or total == 0:
        reason = f"too few cases ({n})" if n < MIN_CASES else "no stock-days for the base rate"
        return HorizonStats(key, h, n, len(stocks), 0, None, None, None, None, None, None, reason)
    hits = sum(1 for r in returns if (r > 0 if direction == "up" else r < 0))
    base_rate = (up if direction == "up" else down) / total
    low, high = wilson_interval(hits, n)
    hit_rate = hits / n
    return HorizonStats(
        key,
        h,
        n,
        len(stocks),
        hits,
        hit_rate,
        base_rate,
        hit_rate - base_rate,
        low,
        high,
        statistics.median(returns),
        None,
    )


def backtest(universe: Mapping[Any, Series]) -> BacktestResult:
    """Hit / base rates per pattern key and horizon over ``universe`` (key -> dated closes)."""
    # Base rate counters: horizon -> [up, down, total] over all stock-days.
    base: dict[int, list[int]] = {h: [0, 0, 0] for h in HORIZONS}
    cases: dict[tuple[str, int], list[float]] = defaultdict(list)
    case_stocks: dict[tuple[str, int], set[Any]] = defaultdict(set)
    f_counts: dict[str, Counter[str]] = defaultdict(Counter)
    f_stocks: dict[str, set[Any]] = defaultdict(set)
    f_cases: dict[tuple[str, int], list[float]] = defaultdict(list)
    f_case_stocks: dict[tuple[str, int], set[Any]] = defaultdict(set)
    as_of: date | None = None
    period_start: date | None = None
    companies = 0
    stock_days = 0

    for stock, series in universe.items():
        bars = sorted({d: c for d, c in series if c > 0}.items())
        if not bars:
            continue
        companies += 1
        closes = [c for _, c in bars]
        as_of = bars[-1][0] if as_of is None else max(as_of, bars[-1][0])
        period_start = bars[0][0] if period_start is None else min(period_start, bars[0][0])
        stock_days += len(bars)
        for h in HORIZONS:
            up, down, total = base_counts(closes, h)
            counts = base[h]
            counts[0] += up
            counts[1] += down
            counts[2] += total
        for occ in detect_patterns(bars):
            if occ.confirmation_index < WARMUP_SESSIONS:
                continue
            for h in HORIZONS:
                r = _forward(closes, occ.confirmation_index, h)
                if r is not None:
                    cases[(occ.stats_key, h)].append(r)
                    case_stocks[(occ.stats_key, h)].add(stock)
        for ev in forming_events(bars):
            if ev.known_index < WARMUP_SESSIONS or ev.outcome == "open":
                continue
            tally = f_counts[ev.pattern]
            tally["n"] += 1
            tally[ev.outcome] += 1
            if ev.outcome == "confirmed" and ev.direction == "up":
                tally["confirmed_up"] += 1
            f_stocks[ev.pattern].add(stock)
            if FORMING_DIRECTION[ev.pattern] is None:
                continue
            for h in HORIZONS:
                r = _forward(closes, ev.known_index, h)
                if r is not None:
                    f_cases[(ev.pattern, h)].append(r)
                    f_case_stocks[(ev.pattern, h)].add(stock)

    stats = {
        key: {
            h: _cell(
                key,
                h,
                cases.get((key, h), []),
                case_stocks.get((key, h), set()),
                KEY_DIRECTION[key],
                base[h],
            )
            for h in HORIZONS
        }
        for key in STATS_KEYS
    }
    forming: dict[str, FormingStats] = {}
    for pattern in PATTERN_TYPES:
        expected = FORMING_DIRECTION[pattern]
        tally = f_counts[pattern]
        forming[pattern] = FormingStats(
            pattern,
            expected,
            tally["n"],
            len(f_stocks[pattern]),
            tally["confirmed"],
            tally["confirmed_up"],
            tally["failed"],
            tally["expired"],
            {}
            if expected is None
            else {
                h: _cell(
                    pattern,
                    h,
                    f_cases.get((pattern, h), []),
                    f_case_stocks.get((pattern, h), set()),
                    expected,
                    base[h],
                )
                for h in HORIZONS
            },
        )
    return BacktestResult(
        PATTERNS_VERSION, as_of, period_start, companies, stock_days, stats, forming
    )


# ---- universe loading, cache ----------------------------------------------------------------

_CacheKey = tuple[date | None, int, str]
_cache: dict[_CacheKey, BacktestResult] = {}
_forming_cache: dict[_CacheKey, dict[uuid.UUID, list[FormingPattern]]] = {}


def clear_cache() -> None:
    _cache.clear()
    _forming_cache.clear()


async def _prices_key(session: AsyncSession) -> _CacheKey:
    """Changes whenever prices are added: (newest price date, stored bar count, version)."""
    latest, count = (
        await session.execute(select(func.max(DailyPrice.date), func.count(DailyPrice.id)))
    ).one()
    return (latest, int(count), PATTERNS_VERSION)


async def load_universe(session: AsyncSession) -> dict[uuid.UUID, list[tuple[date, float]]]:
    """Every stored daily close, per company, oldest first (read only)."""
    rows = await session.execute(
        select(DailyPrice.company_id, DailyPrice.date, DailyPrice.close).order_by(
            DailyPrice.company_id, DailyPrice.date
        )
    )
    out: dict[uuid.UUID, list[tuple[date, float]]] = defaultdict(list)
    for company_id, day, close in rows.all():
        out[company_id].append((day, float(close)))
    return dict(out)


async def universe_stats(session: AsyncSession) -> BacktestResult:
    """Cached universe statistics; computed on the first call after new prices."""
    key = await _prices_key(session)
    cached = _cache.get(key)
    if cached is not None:
        return cached
    universe = await load_universe(session)
    result = await asyncio.to_thread(backtest, universe)
    _cache.clear()
    _cache[key] = result
    return result


def _forming_scan(
    universe: Mapping[uuid.UUID, Series],
) -> dict[uuid.UUID, list[FormingPattern]]:
    return {cid: shapes for cid, series in universe.items() if (shapes := forming_now(series))}


async def forming_by_company(session: AsyncSession) -> dict[uuid.UUID, list[FormingPattern]]:
    """Companies with a shape forming at their last session (R47 P7); cached like the odds."""
    key = await _prices_key(session)
    cached = _forming_cache.get(key)
    if cached is not None:
        return cached
    universe = await load_universe(session)
    result = await asyncio.to_thread(_forming_scan, universe)
    _forming_cache.clear()
    _forming_cache[key] = result
    return result


async def patterns_for_company(
    session: AsyncSession, company_id: uuid.UUID
) -> dict[str, Any] | None:
    """The patterns endpoint payload; None when the company does not exist."""
    if await CompanyRepository(session).get_by_id(company_id) is None:
        return None
    rows = await PriceRepository(session).get_last(company_id, MAX_HISTORY_SESSIONS)
    series = [(r.date, float(r.close)) for r in rows]
    as_of = max((d for d, _ in series), default=None)
    result = await universe_stats(session)
    payload: dict[str, Any] = {
        "company_id": str(company_id),
        "version": PATTERNS_VERSION,
        "as_of": as_of.isoformat() if as_of else None,
        "status": "OK",
        "reason": None,
        "patterns": [],
        "forming": [],
        "note": NOTE,
        "forming_note": FORMING_NOTE,
        **result.to_dict(),
    }
    if len(series) < MIN_SESSIONS:
        payload["status"] = "INSUFFICIENT_DATA"
        payload["reason"] = f"too little price history ({len(series)} of {MIN_SESSIONS} sessions)"
        return payload
    assert as_of is not None
    cutoff = as_of - timedelta(days=RECENT_DAYS)
    recent = [o for o in detect_patterns(series) if o.confirmation_date >= cutoff]
    payload["patterns"] = [occurrence_to_dict(o) for o in reversed(recent)]
    payload["forming"] = [forming_to_dict(f) for f in forming_now(series)]
    return payload


# ---- CLI ------------------------------------------------------------------------------------


def format_table(result: BacktestResult) -> str:
    lines = [
        f"{PATTERNS_VERSION}  companies={result.companies}  stock_days={result.stock_days}  "
        f"period={result.period_start}..{result.as_of}",
        f"{'pattern':<28}{'h':>4}{'n':>6}{'hit%':>7}{'base%':>7}{'diff':>7}"
        f"{'wilson95':>16}{'median':>9}",
    ]
    for key, by_h in result.stats.items():
        for h, c in by_h.items():
            if not c.sufficient:
                lines.append(f"{key:<28}{h:>4}{c.n:>6}  INSUFFICIENT_DATA: {c.reason}")
                continue
            assert c.hit_rate is not None and c.base_rate is not None
            assert c.wilson_low is not None and c.wilson_high is not None
            lines.append(
                f"{key:<28}{h:>4}{c.n:>6}{c.hit_rate * 100:>7.1f}{c.base_rate * 100:>7.1f}"
                f"{(c.hit_rate - c.base_rate) * 100:>+7.1f}"
                f"{f'{c.wilson_low * 100:.1f}-{c.wilson_high * 100:.1f}':>16}"
                f"{(c.median_return or 0.0) * 100:>+8.1f}%"
            )
    lines.append("forming (measured from the session the shape became known)")
    lines.append(
        f"{'pattern':<28}{'n':>6}{'conf%':>7}{'fail%':>7}{'exp%':>7}{'up%':>6}  20/60 hit vs base"
    )
    for key, s in result.forming.items():
        if s.n < MIN_CASES:
            lines.append(f"{key:<28}{s.n:>6}  INSUFFICIENT_DATA: too few cases ({s.n})")
            continue
        up = f"{s.confirmed_up / s.confirmed * 100:>6.1f}" if s.confirmed else f"{'-':>6}"
        cells = []
        for h, c in s.horizons.items():
            if c.sufficient and c.hit_rate is not None and c.base_rate is not None:
                cells.append(f"{h}:{c.hit_rate * 100:.1f}/{c.base_rate * 100:.1f}")
            else:
                cells.append(f"{h}:n/a")
        lines.append(
            f"{key:<28}{s.n:>6}{s.confirmed / s.n * 100:>7.1f}{s.failed / s.n * 100:>7.1f}"
            f"{s.expired / s.n * 100:>7.1f}{up}  {' '.join(cells) or 'no expected direction'}"
        )
    lines.append(OVERLAP_NOTE)
    return "\n".join(lines)


async def _run() -> BacktestResult:
    from app.db.session import async_session_factory

    async with async_session_factory() as session:
        universe = await load_universe(session)
    return await asyncio.to_thread(backtest, universe)


def main() -> None:
    print(format_table(asyncio.run(_run())))


if __name__ == "__main__":
    main()
