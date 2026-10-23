"""EGX market data provider backed by Yahoo Finance.

Yahoo is the current price source: it covers the large majority of EGX equities
(see :mod:`app.ingestion.egx.universe` for coverage reporting). The provider
takes its ticker list from the discovered universe, never from a hardcoded list,
so a newly listed company is picked up automatically.

Only prices are sourced here. Real fundamentals come from official EGX / FRA /
company disclosures and are intentionally not fabricated.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

import anyio

from app.ingestion.egx.universe import create_universe_source
from app.ingestion.provider import CompanyData, DailyPriceData, MarketDataProvider
from app.models.market import CompanyStatus


def _yfinance() -> Any:
    """Import yfinance on first use: it pulls in pandas/numpy (~1.3 s), which
    would otherwise be paid on every API start even when no sync runs."""
    import yfinance  # type: ignore[import-untyped]

    return yfinance

if TYPE_CHECKING:
    from app.ingestion.egx.universe import UniverseEntry, UniverseSource

logger = logging.getLogger(__name__)

YAHOO_SUFFIX = ".CA"
PRICE_QUANT = Decimal("0.0001")
VALUE_QUANT = Decimal("0.01")


def to_yahoo_ticker(ticker: str) -> str:
    """Convert an EGX ticker to its Yahoo Finance symbol."""
    return f"{ticker.upper()}{YAHOO_SUFFIX}"


def _dec(value: object, quant: Decimal) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(quant)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _text(info: dict[str, object], key: str, default: str | None = None) -> str | None:
    """Read a string field out of a loosely typed provider payload."""
    value = info.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def _free_float_ratio(
    float_shares: Decimal | None, shares: Decimal | None
) -> Decimal | None:
    """Return the free float as a fraction of shares outstanding.

    ``Company.free_float`` is a Numeric(10, 4) ratio, not a share count, so the
    raw ``floatShares`` value Yahoo reports must not be stored directly. Returns
    None when either side is missing or the result is not a sane fraction, rather
    than guessing.
    """
    if float_shares is None or shares is None or shares <= 0:
        return None
    ratio = float_shares / shares
    if not (Decimal(0) <= ratio <= Decimal(1)):
        return None
    return ratio.quantize(Decimal("0.0001"))


class EGXMarketDataProvider(MarketDataProvider):
    """Fetches EGX prices for every company in the discovered universe."""

    def __init__(
        self,
        universe: UniverseSource | None = None,
        max_concurrent: int = 8,
        use_live_universe: bool = True,
    ) -> None:
        self.universe = universe or create_universe_source(use_live=use_live_universe)
        self.max_concurrent = max_concurrent
        self._tickers: tuple[str, ...] | None = None

    async def universe_tickers(self) -> tuple[str, ...]:
        """Tickers of every company in the current universe snapshot."""
        if self._tickers is None:
            snapshot = await self.universe.fetch()
            self._tickers = snapshot.tickers()
        return self._tickers

    async def get_companies(self) -> list[CompanyData]:
        """List every universe company, enriched with Yahoo metadata when present.

        Yahoo frequently has no profile for thinly traded EGX names, so metadata
        is left empty rather than invented. Names always come from the universe
        source.
        """
        snapshot = await self.universe.fetch()
        self._tickers = snapshot.tickers()
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def enrich(entry: UniverseEntry) -> CompanyData:
            async with semaphore:
                info = await self._fetch_info(entry.ticker)
            shares = _dec(info.get("sharesOutstanding"), Decimal("1"))
            float_shares = _dec(info.get("floatShares"), Decimal("1"))
            return CompanyData(
                ticker=entry.ticker,
                isin=None,
                name=_text(info, "longName") or entry.name,
                name_ar=None,
                sector=_text(info, "sector"),
                industry=_text(info, "industry"),
                currency=_text(info, "currency", "EGP") or "EGP",
                shares_outstanding=shares,
                free_float=_free_float_ratio(float_shares, shares),
                listing_date=None,
                status=CompanyStatus.ACTIVE.value,
            )

        return list(await asyncio.gather(*(enrich(e) for e in snapshot.entries)))

    async def _fetch_info(self, ticker: str) -> dict[str, object]:
        def _load() -> dict[str, object]:
            try:
                info = _yfinance().Ticker(to_yahoo_ticker(ticker)).info or {}
            except Exception:  # noqa: BLE001 - metadata is best effort
                return {}
            return {k: v for k, v in info.items() if isinstance(v, (str, int, float))}

        return await anyio.to_thread.run_sync(_load)

    async def get_daily_prices(
        self,
        ticker: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[DailyPriceData]:
        """Daily OHLCV for one EGX ticker. Returns [] when Yahoo has no data."""
        end = end_date or date.today()
        start = start_date or date(end.year - 1, end.month, 1)

        def _load() -> Any:
            try:
                return _yfinance().Ticker(to_yahoo_ticker(ticker)).history(
                    start=start, end=end, interval="1d", auto_adjust=False
                )
            except Exception:  # noqa: BLE001 - missing coverage is expected
                return None

        hist = await anyio.to_thread.run_sync(_load)
        if hist is None or hist.empty:
            logger.debug("No Yahoo price data for %s", ticker)
            return []

        rows: list[DailyPriceData] = []
        for idx, row in hist.iterrows():
            bar = _bar_from_row(ticker, idx, row)
            if bar is not None:
                rows.append(bar)
        return rows

    def invalidate_cache(self) -> None:
        self._tickers = None


def _bar_from_row(ticker: str, idx: Any, row: Any) -> DailyPriceData | None:
    """Validate one Yahoo bar, returning None when it is unusable."""
    open_v = _dec(row.get("Open"), PRICE_QUANT)
    high_v = _dec(row.get("High"), PRICE_QUANT)
    low_v = _dec(row.get("Low"), PRICE_QUANT)
    close_v = _dec(row.get("Close"), PRICE_QUANT)
    if open_v is None or high_v is None or low_v is None or close_v is None:
        return None
    if open_v <= 0 or close_v <= 0:
        return None

    try:
        volume = int(row.get("Volume"))
    except (TypeError, ValueError):
        return None
    if volume < 0:
        return None

    # Enforce the OHLC invariant; Yahoo occasionally ships inconsistent bars.
    low_v = min(low_v, open_v, close_v)
    high_v = max(high_v, open_v, close_v)
    adj = _dec(row.get("Adj Close"), PRICE_QUANT) if "Adj Close" in row else None
    bar_date = idx.date() if hasattr(idx, "date") else idx

    return DailyPriceData(
        ticker=ticker,
        date=bar_date,
        open=open_v,
        high=high_v,
        low=low_v,
        close=close_v,
        adjusted_close=adj,
        volume=volume,
        value_traded=(close_v * Decimal(volume)).quantize(VALUE_QUANT),
        trades=None,
    )


def create_egx_provider(use_live_universe: bool = True) -> EGXMarketDataProvider:
    """Create the EGX price provider."""
    return EGXMarketDataProvider(use_live_universe=use_live_universe)
