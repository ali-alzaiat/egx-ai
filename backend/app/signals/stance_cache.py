"""In-process cache of default stance results, keyed by the latest price date.

A stance is recomputed only when new prices land (the global latest
``daily_prices.date`` changes) or after ``CACHE_TTL_SECONDS``, which bounds
staleness from non-price inputs (valuation, score, Shariah records). Only the
default parameters are cached; calls with an entry price or a custom stop
always compute fresh. Per-process: each uvicorn worker keeps its own copy.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import date
    from decimal import Decimal

    from app.signals.stance import StanceResult

CACHE_TTL_SECONDS = 600.0
MAX_ENTRIES = 1000

_entries: dict[tuple[str, date | None], tuple[float, StanceResult]] = {}


def get(ticker: str, price_date: date | None, now: float | None = None) -> StanceResult | None:
    """Cached result for this ticker and price date, if still fresh."""
    entry = _entries.get((ticker.upper(), price_date))
    if entry is None:
        return None
    stored_at, result = entry
    if (now if now is not None else time.monotonic()) - stored_at > CACHE_TTL_SECONDS:
        _entries.pop((ticker.upper(), price_date), None)
        return None
    return result


def put(
    ticker: str, price_date: date | None, result: StanceResult, now: float | None = None
) -> None:
    if len(_entries) >= MAX_ENTRIES:
        _entries.clear()
    _entries[(ticker.upper(), price_date)] = (
        now if now is not None else time.monotonic(),
        result,
    )


# Market-wide fair-value discounts for the relative valuation sub-score (R46 S2): one query
# over stored snapshots, reused for every stance until the TTL ends or any recompute clears it.
_market: tuple[float, list[Decimal]] | None = None


def get_market_discounts(now: float | None = None) -> list[Decimal] | None:
    if _market is None:
        return None
    stored_at, values = _market
    if (now if now is not None else time.monotonic()) - stored_at > CACHE_TTL_SECONDS:
        return None
    return values


def put_market_discounts(values: list[Decimal], now: float | None = None) -> None:
    global _market
    _market = (now if now is not None else time.monotonic(), values)


def clear() -> None:
    global _market
    _entries.clear()
    _market = None
