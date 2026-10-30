"""Volatility cone (R47 P3): where the price would land 50% and 90% of the time.

Pure and deterministic: no database, clock or I/O. It is a **range of typical moves if past
volatility continues, not a prediction**: zero drift, no point forecast, no trend line.

Method (``VOLATILITY_CONE_VERSION``):

* sigma_daily  = sample standard deviation of daily log returns ``ln(close_t / close_t-1)``
  over the last ``WINDOW_SESSIONS`` (252) stored sessions; at least ``MIN_RETURNS`` (120)
  returns are needed, otherwise INSUFFICIENT_DATA with the reason. Closes are the stored
  daily closes as they are (Yahoo's split-adjusted, unadjusted-for-dividends ``Close``).
* sigma_annual = sigma_daily x sqrt(252).
* For a horizon of ``h`` trading days the log price is centred on today's close ``P0``
  (zero drift) with spread ``sigma_daily x sqrt(h)``; the bands are
  ``P0 x exp(+-z x sigma_daily x sqrt(h))`` with z = 0.6745 (the 25th/75th percentiles, the
  central 50%) and z = 1.6449 (the 5th/95th percentiles, the central 90%). p50 is ``P0``.
* Horizons are 21, 63 and 126 trading days (about 1, 3 and 6 months).
* ``approx_date`` steps forward from the last close date by trading days skipping Friday and
  Saturday (the EGX weekend) only. There is no holiday calendar, so the date is approximate.

Flat prices give sigma 0 and the bands collapse onto ``P0`` (still a valid answer). Changing
any constant requires bumping ``VOLATILITY_CONE_VERSION``.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

VOLATILITY_CONE_VERSION = "volatility-cone-1.0"
WINDOW_SESSIONS = 252
MIN_RETURNS = 120
TRADING_DAYS_PER_YEAR = 252
HORIZONS: tuple[int, ...] = (21, 63, 126)
#: Standard-normal z for the central 50% (p25/p75) and 90% (p05/p95) intervals.
Z_50 = 0.6745
Z_90 = 1.6449
EGX_WEEKEND = (4, 5)  # date.weekday(): Friday, Saturday

NOTE = "range of typical moves if past volatility continues, not a prediction"
CALENDAR_NOTE = (
    "Dates skip Friday and Saturday only; Egyptian public holidays are not in the calendar, "
    "so the dates are approximate."
)
_PRICE_Q = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class ConeHorizon:
    days: int
    approx_date: date
    p05: str
    p25: str
    p50: str
    p75: str
    p95: str


@dataclass(frozen=True, slots=True)
class VolatilityCone:
    version: str
    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    reason: str | None
    as_of: date | None
    last_close: str | None
    sigma_daily: float | None
    sigma_annual: float | None
    n_returns: int
    window_start: date | None
    horizons: tuple[ConeHorizon, ...]
    z_50: float = Z_50
    z_90: float = Z_90
    drift: str = "zero"
    calendar_note: str = CALENDAR_NOTE
    note: str = NOTE


def add_trading_days(start: date, days: int) -> date:
    """``start`` plus ``days`` trading days, skipping Friday and Saturday."""
    current = start
    remaining = days
    while remaining > 0:
        current += timedelta(days=1)
        if current.weekday() not in EGX_WEEKEND:
            remaining -= 1
    return current


def daily_sigma(closes: Sequence[float]) -> float:
    """Sample stdev of the daily log returns of ``closes`` (oldest first, all > 0, >= 3 values)."""
    returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    n = len(returns)
    mean = math.fsum(returns) / n
    return math.sqrt(math.fsum((r - mean) ** 2 for r in returns) / (n - 1))


def _price(x: float) -> str:
    return str(Decimal(repr(x)).quantize(_PRICE_Q))


def _insufficient(
    reason: str, as_of: date | None, last_close: Decimal | None, n_returns: int
) -> VolatilityCone:
    return VolatilityCone(
        version=VOLATILITY_CONE_VERSION,
        status="INSUFFICIENT_DATA",
        reason=reason,
        as_of=as_of,
        last_close=str(last_close.quantize(_PRICE_Q)) if last_close is not None else None,
        sigma_daily=None,
        sigma_annual=None,
        n_returns=n_returns,
        window_start=None,
        horizons=(),
    )


def volatility_cone(bars: Sequence[tuple[date, Decimal]]) -> VolatilityCone:
    """Cone from ``(date, close)`` bars; any order, one bar per date (the first one wins)."""
    by_date: dict[date, Decimal] = {}
    for d, close in bars:
        by_date.setdefault(d, close)
    ordered = sorted(by_date.items())
    if not ordered:
        return _insufficient("no stored prices", None, None, 0)

    as_of, last_close = ordered[-1]
    window = ordered[-(WINDOW_SESSIONS + 1) :]
    n_returns = len(window) - 1
    if n_returns < MIN_RETURNS:
        return _insufficient(
            f"needs at least {MIN_RETURNS} daily returns, have {max(n_returns, 0)}",
            as_of,
            last_close,
            max(n_returns, 0),
        )
    if any(close <= 0 for _, close in window):
        return _insufficient(
            "a non-positive close in the window: log returns undefined",
            as_of,
            last_close,
            n_returns,
        )

    closes = [float(c) for _, c in window]
    sigma = daily_sigma(closes)
    p0 = float(last_close)

    horizons: list[ConeHorizon] = []
    for h in HORIZONS:
        spread = sigma * math.sqrt(h)
        horizons.append(
            ConeHorizon(
                days=h,
                approx_date=add_trading_days(as_of, h),
                p05=_price(p0 * math.exp(-Z_90 * spread)),
                p25=_price(p0 * math.exp(-Z_50 * spread)),
                p50=str(last_close.quantize(_PRICE_Q)),
                p75=_price(p0 * math.exp(Z_50 * spread)),
                p95=_price(p0 * math.exp(Z_90 * spread)),
            )
        )
    return VolatilityCone(
        version=VOLATILITY_CONE_VERSION,
        status="AVAILABLE",
        reason=None,
        as_of=as_of,
        last_close=str(last_close.quantize(_PRICE_Q)),
        sigma_daily=round(sigma, 6),
        sigma_annual=round(sigma * math.sqrt(TRADING_DAYS_PER_YEAR), 6),
        n_returns=n_returns,
        window_start=window[0][0],
        horizons=tuple(horizons),
    )
