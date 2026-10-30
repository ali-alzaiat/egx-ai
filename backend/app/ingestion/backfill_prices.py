"""One-off backfill of daily prices from Yahoo Finance (R47 P2).

    python -m app.ingestion.backfill_prices --years 5 --dry-run     # report only, no writes
    python -m app.ingestion.backfill_prices --years 5               # insert missing days
    python -m app.ingestion.backfill_prices --years 5 --tickers COMI,SWDY

It uses the same Yahoo provider path as the regular sync (``get_daily_prices``, unadjusted
``Close``, source ``YAHOO_FINANCE_EGX``) and **only inserts (company, date) rows that are not
stored yet**: an existing bar is never overwritten. It is idempotent: a second run adds 0 rows.
Fetches are throttled by a small concurrency limit plus a pause per request. A company Yahoo
has no history for is reported, never filled in. Recompute (stances, scores) is NOT triggered;
run the usual sync afterwards for that.
"""

import argparse
import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import date, timedelta

import anyio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.ingestion.egx.provider import EGXMarketDataProvider
from app.ingestion.provider import DailyPriceData
from app.ingestion.sync import PRICE_SOURCE_NAME, PRICE_SOURCE_TYPE, PRICE_SOURCE_URL
from app.models.market import Company
from app.repositories.data_source import DataSourceRepository
from app.repositories.price import PriceRepository
from app.schemas.price import DailyPriceCreate

logger = logging.getLogger(__name__)

DEFAULT_YEARS = 5
DEFAULT_CONCURRENCY = 4
DEFAULT_PAUSE_SECONDS = 0.5


@dataclass(frozen=True, slots=True)
class CompanyBackfill:
    ticker: str
    status: str  # "ok" | "no_history" | "error"
    detail: str | None
    first_date_before: date | None
    first_date_after: date | None
    fetched: int
    already_stored: int
    rows_added: int


def missing_bars(
    bars: list[DailyPriceData], stored: set[date], start: date, end: date
) -> list[DailyPriceData]:
    """Bars inside the window whose date is not stored, one per date, oldest first."""
    seen: set[date] = set()
    out: list[DailyPriceData] = []
    for bar in sorted(bars, key=lambda b: b.date):
        if bar.date < start or bar.date > end or bar.date in stored or bar.date in seen:
            continue
        seen.add(bar.date)
        out.append(bar)
    return out


def window(years: int, today: date | None = None) -> tuple[date, date]:
    end = today or date.today()
    return end - timedelta(days=round(365.25 * years)), end


async def apply_backfill(
    session: AsyncSession,
    company: Company,
    bars: list[DailyPriceData] | Exception,
    start: date,
    end: date,
    *,
    source_id: uuid.UUID | None,
    dry_run: bool,
) -> CompanyBackfill:
    """Insert one company's missing bars (or count them on a dry run)."""
    prices = PriceRepository(session)
    stored = await prices.existing_dates(company.id, date(1990, 1, 1), end)
    first_before = min(stored) if stored else None
    if isinstance(bars, Exception):
        return CompanyBackfill(
            company.ticker, "error", str(bars), first_before, first_before, 0, len(stored), 0
        )
    if not bars:
        return CompanyBackfill(
            company.ticker, "no_history", "Yahoo returned no history", first_before,
            first_before, 0, len(stored), 0,
        )
    new = missing_bars(bars, stored, start, end)
    if dry_run or source_id is None:
        added = len(new)  # what would be inserted
    else:
        added = await prices.insert_missing(
            [
                DailyPriceCreate(
                    company_id=company.id,
                    date=b.date,
                    open=b.open,
                    high=b.high,
                    low=b.low,
                    close=b.close,
                    adjusted_close=b.adjusted_close,
                    volume=b.volume,
                    value_traded=b.value_traded,
                    trades=b.trades,
                    source_id=source_id,
                )
                for b in new
            ]
        )
    first_after = min([*stored, *(b.date for b in new)]) if (new or stored) else None
    return CompanyBackfill(
        company.ticker, "ok", None, first_before, first_after, len(bars), len(stored), added
    )


async def run_backfill(
    tickers: list[str] | None,
    years: int,
    concurrency: int,
    pause: float,
    dry_run: bool,
) -> list[CompanyBackfill]:
    start, end = window(years)
    provider = EGXMarketDataProvider(max_concurrent=concurrency)
    async with async_session_factory() as session:
        query = select(Company).order_by(Company.ticker)
        if tickers:
            query = query.where(Company.ticker.in_([t.upper() for t in tickers]))
        companies = list((await session.execute(query)).scalars().all())
        found = {c.ticker for c in companies}
        unknown = [t.upper() for t in tickers or [] if t.upper() not in found]
        if unknown:
            logger.warning("Unknown tickers (not in companies): %s", ", ".join(unknown))

        # Network fetches are throttled and run first; writes stay sequential on one session.
        semaphore = asyncio.Semaphore(concurrency)
        fetched: dict[str, list[DailyPriceData] | Exception] = {}

        async def fetch(company: Company) -> None:
            async with semaphore:
                try:
                    fetched[company.ticker] = await provider.get_daily_prices(
                        company.ticker, start, end
                    )
                except Exception as exc:  # noqa: BLE001 - one bad ticker must not stop the run
                    fetched[company.ticker] = exc
                await asyncio.sleep(pause)

        await asyncio.gather(*(fetch(c) for c in companies))

        source_id: uuid.UUID | None = None
        if not dry_run:
            source = await DataSourceRepository(session).get_or_create(
                name=PRICE_SOURCE_NAME,
                source_type=PRICE_SOURCE_TYPE,
                base_url=PRICE_SOURCE_URL,
            )
            source_id = source.id

        results = [
            await apply_backfill(
                session, c, fetched[c.ticker], start, end, source_id=source_id, dry_run=dry_run
            )
            for c in companies
        ]
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
    return results


def format_report(results: list[CompanyBackfill], dry_run: bool) -> str:
    lines = ["DRY RUN - nothing written" if dry_run else "Backfill done"]
    lines.append("ticker  status      first_before  first_after   fetched  stored  added")
    for r in results:
        lines.append(
            f"{r.ticker:<7} {r.status:<11} {r.first_date_before or '-'!s:<13} "
            f"{r.first_date_after or '-'!s:<13} {r.fetched:>7} {r.already_stored:>7} "
            f"{r.rows_added:>6}" + (f"  ({r.detail})" if r.detail else "")
        )
    ok = [r for r in results if r.status == "ok"]
    lines.append(
        f"{len(ok)}/{len(results)} companies with history; "
        f"{sum(r.rows_added for r in results)} rows {'would be ' if dry_run else ''}added"
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill daily prices (inserts missing days only)"
    )
    parser.add_argument("--years", type=int, default=DEFAULT_YEARS, help="Years back (default 5)")
    parser.add_argument("--tickers", help="Comma-separated tickers (default: every company)")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report; write nothing")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument(
        "--pause", type=float, default=DEFAULT_PAUSE_SECONDS,
        help="Seconds to wait after each fetch (throttle)",
    )
    args = parser.parse_args()
    if args.years < 1:
        parser.error("--years must be at least 1")
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()] if args.tickers else None

    async def run() -> None:
        results = await run_backfill(
            tickers, args.years, args.concurrency, args.pause, args.dry_run
        )
        print(format_report(results, args.dry_run))

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    anyio.run(run)


if __name__ == "__main__":
    main()
