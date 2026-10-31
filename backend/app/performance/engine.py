"""Pure performance maths: price returns, stock versus index, TTM / YoY growth.

No database, clock or I/O. Every function works on caller-supplied series, refuses with
``INSUFFICIENT_DATA`` and a reason when the series does not reach back far enough (never a
zero), and only looks at closes dated on or before ``as_of`` (no look-ahead).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from statistics import median
from typing import Any

from app.ingestion.disclosures.comparison import (
    compute_ttm,
    quantize4,
    ttm_margin,
    yoy_delta,
)
from app.performance.constants import (
    ANNUAL_TYPE,
    MIN_SECTOR_PEERS,
    PEER_MAX_STALE_DAYS,
    QUARTER_MAX_SPAN_DAYS,
    QUARTER_TYPES,
    WINDOW_ORDER,
    WINDOW_TRADING_DAYS,
    YTD_WINDOW,
)

Closes = Sequence[tuple[date, Decimal]]


def insufficient(reason: str) -> dict[str, Any]:
    return {"value": None, "status": "INSUFFICIENT_DATA", "reason": reason}


def _return_block(start: tuple[date, Decimal], end: tuple[date, Decimal]) -> dict[str, Any]:
    if start[1] <= 0 or end[1] <= 0:
        return insufficient("a non-positive close is in the window; the return is undefined")
    return {
        "return": quantize4(end[1] / start[1] - 1),
        "start_date": start[0].isoformat(),
        "end_date": end[0].isoformat(),
    }


def price_returns(closes: Closes, as_of: date) -> dict[str, dict[str, Any]]:
    """Return per window as a fraction (4dp) from closes dated on or before ``as_of``.

    The N-trading-day windows start at the close N bars before the latest close; ``YTD`` starts
    at the latest close on or before 31 December of the previous year. A window the series
    does not reach back to is INSUFFICIENT_DATA with a reason.
    """
    series = sorted((d, c) for d, c in closes if d <= as_of)
    out: dict[str, dict[str, Any]] = {}
    if not series:
        for window in WINDOW_ORDER:
            out[window] = insufficient("no closes on or before the as-of date")
        return out
    latest = series[-1]
    for window in WINDOW_ORDER:
        if window == YTD_WINDOW:
            year_end = date(as_of.year - 1, 12, 31)
            before = [row for row in series if row[0] <= year_end]
            if not before:
                out[window] = insufficient(
                    f"no close on or before {year_end.isoformat()}; the series starts later"
                )
            elif latest[0] <= before[-1][0]:
                out[window] = insufficient("no close yet in the current calendar year")
            else:
                out[window] = _return_block(before[-1], latest)
            continue
        days = WINDOW_TRADING_DAYS[window]
        index = len(series) - 1 - days
        if index < 0:
            out[window] = insufficient(
                f"{window} needs {days + 1} closes; the series has {len(series)}"
            )
        else:
            out[window] = _return_block(series[index], latest)
    return out


def relative_returns(
    stock: dict[str, dict[str, Any]], index: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Stock return minus index return per window, only when both exist."""
    out: dict[str, dict[str, Any]] = {}
    for window in WINDOW_ORDER:
        s = stock.get(window, {})
        i = index.get(window, {})
        if "return" in s and "return" in i:
            out[window] = {"relative": quantize4(s["return"] - i["return"])}
        else:
            missing = "stock" if "return" not in s else "index"
            out[window] = insufficient(f"relative return needs both returns; {missing} is missing")
    return out


def performance_windows(
    stock_closes: Closes, index_closes: Closes, as_of: date
) -> dict[str, dict[str, Any]]:
    """Per window: the stock return, the index return and their difference."""
    stock = price_returns(stock_closes, as_of)
    if index_closes:
        index = price_returns(index_closes, as_of)
    else:
        reason = "no index closes stored"
        index = {w: insufficient(reason) for w in WINDOW_ORDER}
    relative = relative_returns(stock, index)
    return {
        w: {"stock": stock[w], "index": index[w], "relative": relative[w]} for w in WINDOW_ORDER
    }


def sector_peer_benchmark(
    stock: dict[str, dict[str, Any]],
    peer_closes: Mapping[str, Closes],
    as_of: date,
    *,
    min_peers: int = MIN_SECTOR_PEERS,
) -> dict[str, dict[str, Any]]:
    """Median return of the sector peers per window, and the stock's return minus it.

    ``peer_closes`` maps a peer id to its closes and must not contain the company itself.
    Each peer is measured with ``price_returns`` (same windows, same as-of, no look-ahead); a
    peer whose latest close is more than ``PEER_MAX_STALE_DAYS`` before ``as_of`` is left out,
    and a peer that does not reach back far enough for a window is left out of that window
    only. Fewer than ``min_peers`` peers with a return is INSUFFICIENT_DATA, never a median of
    what is left. An even count averages the two middle returns (4dp).
    """
    fresh_from = as_of - timedelta(days=PEER_MAX_STALE_DAYS)
    peer_returns: list[dict[str, dict[str, Any]]] = []
    for closes in peer_closes.values():
        dated = [d for d, _ in closes if d <= as_of]
        if dated and max(dated) >= fresh_from:
            peer_returns.append(price_returns(closes, as_of))
    out: dict[str, dict[str, Any]] = {}
    for window in WINDOW_ORDER:
        values = [r[window]["return"] for r in peer_returns if "return" in r[window]]
        count = len(values)
        if count < min_peers:
            block = insufficient(
                f"{window}: {count} of {len(peer_closes)} sector peers have a return; "
                f"at least {min_peers} are needed"
            )
            block["peer_count"] = count
            out[window] = block
            continue
        mid = quantize4(Decimal(median(values)))
        own = stock.get(window, {})
        relative: dict[str, Any] | Decimal
        if "return" in own:
            relative = quantize4(own["return"] - mid)
        else:
            relative = insufficient("relative_to_sector needs the stock's own return, missing")
        out[window] = {"median": mid, "peer_count": count, "relative_to_sector": relative}
    return out


@dataclass(frozen=True)
class PeriodValue:
    """One approved statement value for one reporting period."""

    period_type: str
    fiscal_year: int
    start_date: date
    end_date: date
    value: Decimal | None


def _quarter_number(period_type: str) -> int:
    return QUARTER_TYPES.index(period_type) + 1


def discrete_quarters(values: Sequence[PeriodValue]) -> list[PeriodValue]:
    """Single-quarter values, oldest first. Cumulative (year-to-date) figures are excluded."""
    seen: dict[tuple[int, int], PeriodValue] = {}
    for v in values:
        if v.period_type not in QUARTER_TYPES or v.value is None:
            continue
        if (v.end_date - v.start_date).days > QUARTER_MAX_SPAN_DAYS:
            continue
        seen[(v.fiscal_year, _quarter_number(v.period_type))] = v
    return [seen[key] for key in sorted(seen)]


def _label(v: PeriodValue) -> str:
    return f"{v.period_type}-{v.fiscal_year}"


def _ttm_block(quarters: list[PeriodValue], metric: str, back: int) -> dict[str, Any]:
    """TTM over four consecutive quarters ending ``back`` quarters before the latest."""
    end = max(len(quarters) - back, 0)
    window = quarters[max(end - 4, 0) : end]
    block = compute_ttm([v.value for v in window], metric=metric)
    if len(window) < 4:
        return block
    slots = [v.fiscal_year * 4 + _quarter_number(v.period_type) for v in window]
    if slots != list(range(slots[0], slots[0] + 4)):
        return insufficient(
            f"TTM needs four consecutive reported quarters for {metric}; there is a gap"
        )
    block["quarters"] = [_label(v) for v in window]
    return block


def _decimal(block: dict[str, Any]) -> Decimal | None:
    return Decimal(block["value"]) if block.get("status") == "OK" else None


def _annual_block(values: Sequence[PeriodValue], metric: str) -> dict[str, Any]:
    annual = {
        v.fiscal_year: v for v in values if v.period_type == ANNUAL_TYPE and v.value is not None
    }
    if not annual:
        return insufficient(f"no annual {metric} reported")
    year = max(annual)
    current = annual[year]
    prior = annual.get(year - 1)
    return {
        "fiscal_year": year,
        "end_date": current.end_date.isoformat(),
        "value": str(current.value),
        "yoy": yoy_delta(
            current=current.value,
            prior=prior.value if prior is not None else None,
            metric=metric,
            current_label=f"FY-{year}",
            prior_label=f"FY-{year - 1}",
        ),
    }


def _metric_growth(values: Sequence[PeriodValue], metric: str) -> dict[str, Any]:
    quarters = discrete_quarters(values)
    ttm = _ttm_block(quarters, metric, 0)
    prior = _ttm_block(quarters, metric, 4)
    latest_label = _label(quarters[-1]) if quarters else "none"
    prior_label = (
        f"TTM to {_label(quarters[-5])}" if len(quarters) >= 5 else "none"
    )
    return {
        "ttm": ttm,
        "yoy": yoy_delta(
            current=_decimal(ttm),
            prior=_decimal(prior),
            metric=f"{metric} (TTM)",
            current_label=f"TTM to {latest_label}",
            prior_label=prior_label,
        ),
        "annual": _annual_block(values, metric),
    }


def fundamentals_growth(
    revenue: Sequence[PeriodValue], net_income: Sequence[PeriodValue]
) -> dict[str, Any]:
    """Revenue and net income TTM + YoY, the TTM net margin and the latest annual figures.

    TTM needs four consecutive single-quarter values (reusing the disclosure comparison
    rules); anything less is INSUFFICIENT_DATA, never a partial sum.
    """
    rev = _metric_growth(revenue, "revenue")
    inc = _metric_growth(net_income, "net_income")
    return {
        "revenue": rev,
        "net_income": inc,
        "ttm_net_margin": ttm_margin(
            ttm_net_income=_decimal(inc["ttm"]), ttm_revenue=_decimal(rev["ttm"])
        ),
    }
