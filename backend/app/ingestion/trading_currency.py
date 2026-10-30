"""One-off backfill of each listing's trading currency from Yahoo price metadata (R46 C1).

    python -m app.ingestion.trading_currency                 # every company
    python -m app.ingestion.trading_currency --tickers EGBE,COMI
    python -m app.ingestion.trading_currency --dry-run       # report only, no writes

The currency is what Yahoo reports the price series in (``history_metadata.currency``). A
ticker Yahoo does not answer for keeps ``trading_currency`` NULL: nothing is guessed, and
``companies.currency`` (defaulted to EGP) is never used as a fallback. Prices are never
converted; a listing whose trading currency differs from its statements' currency simply
gets no price comparison (verdict and stance valuation are INSUFFICIENT_DATA).
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.models.market import Company

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class BackfillSummary:
    checked: int = 0
    updated: int = 0
    unreported: list[str] = field(default_factory=list)
    by_currency: Counter[str] = field(default_factory=Counter)
    changed: list[tuple[str, str | None, str]] = field(default_factory=list)

    def lines(self) -> list[str]:
        counts = ", ".join(f"{c}: {n}" for c, n in sorted(self.by_currency.items())) or "none"
        out = [
            f"Checked {self.checked} companies; trading currency set for {self.updated}.",
            f"By currency: {counts}.",
        ]
        non_egp = [f"{t} ({new})" for t, _old, new in self.changed if new != "EGP"]
        if non_egp:
            out.append("Quoted in a non-EGP currency: " + ", ".join(sorted(non_egp)))
        if self.unreported:
            out.append(
                f"Yahoo reported no currency for {len(self.unreported)} (left NULL): "
                + ", ".join(sorted(self.unreported)[:40])
                + (" ..." if len(self.unreported) > 40 else "")
            )
        return out


async def backfill_trading_currency(
    session: AsyncSession,
    fetch: Callable[[str], Awaitable[str | None]],
    tickers: Sequence[str] | None = None,
    *,
    concurrency: int = 4,
    dry_run: bool = False,
    now: datetime | None = None,
) -> BackfillSummary:
    """Read each company's trading currency through ``fetch`` and store it."""
    query = select(Company).order_by(Company.ticker)
    if tickers:
        query = query.where(Company.ticker.in_([t.upper() for t in tickers]))
    companies = list((await session.execute(query)).scalars().all())
    semaphore = asyncio.Semaphore(concurrency)

    async def one(company: Company) -> tuple[Company, str | None]:
        async with semaphore:
            return company, await fetch(company.ticker)

    checked_at = now or datetime.now(UTC)
    summary = BackfillSummary()
    for company, currency in await asyncio.gather(*(one(c) for c in companies)):
        summary.checked += 1
        if currency is None:
            summary.unreported.append(company.ticker)
            continue
        summary.by_currency[currency] += 1
        summary.changed.append((company.ticker, company.trading_currency, currency))
        if not dry_run:
            company.trading_currency = currency
            company.trading_currency_checked_at = checked_at
            summary.updated += 1
    if not dry_run:
        await session.flush()
    return summary


def main() -> int:  # pragma: no cover - CLI wrapper
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tickers", help="comma-separated tickers (default: all companies)")
    parser.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()] if args.tickers else None

    async def _run() -> BackfillSummary:
        from app.db.session import async_session_factory
        from app.ingestion.egx.provider import EGXMarketDataProvider

        provider = EGXMarketDataProvider(use_live_universe=False)
        async with async_session_factory() as session:
            summary = await backfill_trading_currency(
                session,
                provider.fetch_trading_currency,
                tickers,
                concurrency=args.concurrency,
                dry_run=args.dry_run,
            )
            if not args.dry_run:
                await session.commit()
            return summary

    for line in asyncio.run(_run()).lines():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
