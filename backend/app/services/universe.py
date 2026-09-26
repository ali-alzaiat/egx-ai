"""Keeps the ``companies`` table in step with the discovered EGX universe.

This is the replacement for a hardcoded ticker list: the universe is fetched,
upserted, and companies that vanish from the listing are flagged as delisted so
they stop being scored.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.ingestion.egx.universe import create_universe_source
from app.models.market import Company, CompanyStatus, DailyPrice
from app.repositories.company import CompanyRepository

if TYPE_CHECKING:
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ingestion.egx.universe import UniverseSource

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class UniverseSyncResult:
    """Outcome of one universe synchronisation."""

    discovered: int
    inserted_or_updated: int
    marked_delisted: int
    source_name: str
    source_url: str
    fetched_at: datetime
    is_fallback: bool


@dataclass(frozen=True, slots=True)
class CoverageReport:
    """How much of the universe the app can actually analyse."""

    universe_total: int
    active_total: int
    with_price_data: int
    priced_of_active: float
    min_history_days: int
    analyzable: int
    unscorable: int
    unpriced_tickers: tuple[str, ...]
    thin_history_tickers: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "universe_total": self.universe_total,
            "active_total": self.active_total,
            "with_price_data": self.with_price_data,
            "priced_of_active": round(self.priced_of_active, 4),
            "min_history_days": self.min_history_days,
            "analyzable": self.analyzable,
            "unscorable": self.unscorable,
            "unpriced_tickers": list(self.unpriced_tickers),
            "thin_history_tickers": list(self.thin_history_tickers),
        }


class UniverseService:
    """Synchronises the company universe and reports data coverage."""

    def __init__(
        self,
        session: AsyncSession,
        source: UniverseSource | None = None,
    ) -> None:
        self.session = session
        self.source = source or create_universe_source()
        self.company_repo = CompanyRepository(session)

    async def sync(self, mark_missing_delisted: bool = True) -> UniverseSyncResult:
        """Discover the universe and upsert every company it contains."""
        snapshot = await self.source.fetch()
        entries = snapshot.entries

        rows = [
            {
                "ticker": entry.ticker,
                "name": entry.name,
                "currency": "EGP",
                "status": CompanyStatus.ACTIVE.value,
            }
            for entry in entries
        ]
        touched = await self.company_repo.upsert_many(rows)

        marked = 0
        if mark_missing_delisted:
            marked = await self.company_repo.mark_absent_as(
                [e.ticker for e in entries], CompanyStatus.DELISTED
            )

        await self.session.commit()
        logger.info(
            "Universe sync: %d discovered, %d written, %d marked delisted (source=%s)",
            len(entries), touched, marked, snapshot.source_name,
        )
        return UniverseSyncResult(
            discovered=len(entries),
            inserted_or_updated=touched,
            marked_delisted=marked,
            source_name=snapshot.source_name,
            source_url=snapshot.source_url,
            fetched_at=snapshot.fetched_at,
            is_fallback=snapshot.is_fallback,
        )

    async def coverage(self, min_history_days: int = 120) -> CoverageReport:
        """Report how many universe companies have enough data to be scored.

        A market-wide tool must state its own blind spots, otherwise a ranking
        silently describes only part of the market.
        """
        universe_total = (
            await self.session.execute(select(func.count(Company.id)))
        ).scalar_one()
        active_total = (
            await self.session.execute(
                select(func.count(Company.id)).where(Company.status == CompanyStatus.ACTIVE)
            )
        ).scalar_one()

        rows = (
            await self.session.execute(
                select(Company.ticker, func.count(DailyPrice.id))
                .join(DailyPrice, DailyPrice.company_id == Company.id)
                .where(Company.status == CompanyStatus.ACTIVE)
                .group_by(Company.ticker)
            )
        ).all()
        counts = {ticker: n for ticker, n in rows}

        all_active = (
            await self.session.execute(
                select(Company.ticker).where(Company.status == CompanyStatus.ACTIVE).order_by(
                    Company.ticker
                )
            )
        ).scalars().all()

        unpriced = tuple(t for t in all_active if counts.get(t, 0) == 0)
        thin = tuple(
            t for t in all_active if 0 < counts.get(t, 0) < min_history_days
        )
        with_prices = len(all_active) - len(unpriced)
        analyzable = len(all_active) - len(unpriced) - len(thin)

        return CoverageReport(
            universe_total=universe_total,
            active_total=active_total,
            with_price_data=with_prices,
            priced_of_active=(with_prices / active_total) if active_total else 0.0,
            min_history_days=min_history_days,
            analyzable=analyzable,
            unscorable=len(unpriced) + len(thin),
            unpriced_tickers=unpriced,
            thin_history_tickers=thin,
        )
