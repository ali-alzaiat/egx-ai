"""Synchronise the EGX market into the database.

    python -m app.ingestion.sync --universe-only   # refresh the company list
    python -m app.ingestion.sync                   # universe + prices for everything
    python -m app.ingestion.sync --tickers COMI,SWDY
    python -m app.ingestion.sync --coverage        # report only, no writes

Prices come from Yahoo Finance. Financial statements are intentionally absent:
real fundamentals are sourced from official EGX / FRA / company disclosures, and
nothing is fabricated to fill the gap.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

import anyio

from app.db.session import async_session_factory
from app.ingestion.egx.provider import EGXMarketDataProvider
from app.ingestion.service import MarketDataIngestionService
from app.models.market import DataSourceType
from app.services.universe import CoverageReport, UniverseService

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ingestion.provider import DailyPriceData, MarketDataProvider

logger = logging.getLogger(__name__)

PRICE_SOURCE_NAME = "YAHOO_FINANCE_EGX"
PRICE_SOURCE_TYPE = DataSourceType.DATA_PROVIDER
PRICE_SOURCE_URL = "https://finance.yahoo.com"


@dataclass(frozen=True, slots=True)
class PriceSyncSummary:
    """Outcome of one price fetch+write pass."""

    companies_total: int
    companies_fetched: int
    records_written: int
    failures: tuple[tuple[str, str], ...]
    fetched_tickers: tuple[str, ...] = ()


async def fetch_and_write_prices(
    session: AsyncSession,
    provider: MarketDataProvider,
    targets: list[str],
    start: date,
    end: date,
    concurrency: int,
    on_progress: Callable[[int, int], None] | None = None,
) -> PriceSyncSummary:
    """Fetch prices concurrently, write them sequentially, and summarise the run.

    Network fetches run concurrently; database writes stay sequential because a
    single AsyncSession is not safe for concurrent use. One bad ticker is
    recorded as a failure and never stops the run.
    """
    logger.info("Fetching prices for %d companies, %s..%s", len(targets), start, end)
    semaphore = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    fetched: dict[str, list[DailyPriceData]] = {}
    failures: list[tuple[str, str]] = []
    completed = 0

    async def fetch_one(ticker: str) -> None:
        nonlocal completed
        try:
            async with semaphore:
                bars = await provider.get_daily_prices(ticker, start, end)
        except Exception as exc:  # noqa: BLE001 - one bad ticker must not stop the run
            async with lock:
                failures.append((ticker, str(exc)))
        else:
            async with lock:
                if bars:
                    fetched[ticker] = bars
                else:
                    failures.append((ticker, "Yahoo returned no history"))
        async with lock:
            completed += 1
            if on_progress is not None:
                on_progress(completed, len(targets))

    await asyncio.gather(*(fetch_one(t) for t in targets))
    logger.info(
        "Fetched price history for %d/%d companies; writing to database",
        len(fetched),
        len(targets),
    )

    service = MarketDataIngestionService(
        session=session,
        provider=provider,
        source_name=PRICE_SOURCE_NAME,
        source_type=PRICE_SOURCE_TYPE,
        source_url=PRICE_SOURCE_URL,
    )

    total = 0
    for ticker, bars in fetched.items():
        total += await service.write_prices(ticker, bars)

    logger.info("Prices: %d records across %d companies", total, len(fetched))
    if failures:
        logger.warning(
            "%d tickers failed: %s",
            len(failures),
            "; ".join(f"{ticker}: {error}" for ticker, error in failures[:10]),
        )

    return PriceSyncSummary(
        companies_total=len(targets),
        companies_fetched=len(fetched),
        records_written=total,
        failures=tuple(failures),
        fetched_tickers=tuple(sorted(fetched)),
    )


def _log_coverage(coverage: CoverageReport) -> None:
    logger.info(
        "Coverage: %d/%d active companies have prices (%.1f%%); %d analyzable, %d unscorable",
        coverage.with_price_data,
        coverage.active_total,
        coverage.priced_of_active * 100,
        coverage.analyzable,
        coverage.unscorable,
    )
    if coverage.unpriced_tickers:
        logger.info(
            "No price coverage (%d): %s",
            len(coverage.unpriced_tickers),
            " ".join(coverage.unpriced_tickers),
        )


async def sync_universe() -> None:
    async with async_session_factory() as session:
        service = UniverseService(session)
        result = await service.sync()
        logger.info(
            "Universe: %d discovered from %s (%s)",
            result.discovered, result.source_name,
            "snapshot" if result.is_fallback else "live",
        )
        _log_coverage(await service.coverage())


async def sync_prices(
    tickers: list[str] | None,
    start_date: date | None,
    history_days: int,
    concurrency: int,
    recompute: bool = True,
) -> None:
    async with async_session_factory() as session:
        universe_service = UniverseService(session)
        await universe_service.sync()

        provider = EGXMarketDataProvider(max_concurrent=concurrency)
        targets = (
            [t.upper() for t in tickers] if tickers else list(await provider.universe_tickers())
        )

        end = date.today()
        start = start_date or (end - timedelta(days=history_days))

        summary = await fetch_and_write_prices(
            session, provider, targets, start, end, concurrency
        )
        _log_coverage(await universe_service.coverage())
        await session.commit()
        from app.services.recompute import after_price_sync, company_ids_for_tickers

        ids = await company_ids_for_tickers(session, summary.fetched_tickers)
    if recompute and ids:
        result = await after_price_sync(ids)
        logger.info("Recompute after price sync: %s", result.as_dict())


async def show_coverage() -> None:
    async with async_session_factory() as session:
        _log_coverage(await UniverseService(session).coverage())


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync EGX market data")
    parser.add_argument("--tickers", help="Comma-separated tickers (default: all)")
    parser.add_argument("--start-date", type=date.fromisoformat, help="First price date")
    parser.add_argument("--history-days", type=int, default=400, help="Days of history")
    parser.add_argument("--concurrency", type=int, default=8, help="Parallel fetches")
    parser.add_argument("--universe-only", action="store_true", help="Only refresh companies")
    parser.add_argument("--coverage", action="store_true", help="Report coverage and exit")
    parser.add_argument("--offline", action="store_true", help="Use the cached universe snapshot")
    parser.add_argument(
        "--no-recompute", action="store_true", help="Skip the automatic snapshot recompute"
    )
    args = parser.parse_args()

    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else None

    async def run() -> None:
        if args.coverage:
            await show_coverage()
        elif args.universe_only:
            await sync_universe()
        else:
            await sync_prices(
                tickers,
                args.start_date,
                args.history_days,
                args.concurrency,
                recompute=not args.no_recompute,
            )

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    anyio.run(run)


if __name__ == "__main__":
    main()
