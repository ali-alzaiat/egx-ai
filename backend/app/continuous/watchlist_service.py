"""Watchlist service: badge population (B1).

Populates per-entry badges from Phase 1/4/5/6 surfaces.
Every field is INSUFFICIENT_DATA if source missing — never blank.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dataquality.service import DataQualityService
from app.models.continuous import WatchlistEntry
from app.models.market import DailyPrice
from app.models.scores import InvestmentScore
from app.models.screening import ShariahScreeningResult
from app.models.thesis import InvestmentThesis
from app.repositories.company import CompanyRepository


@dataclass
class BadgeResult:
    """Result of badge computation."""

    price: dict[str, Any]
    change: dict[str, Any]
    as_of: dict[str, Any]
    staleness: dict[str, Any]
    score: dict[str, Any]
    shariah_state: dict[str, Any]
    thesis_link: dict[str, Any]


class WatchlistService:
    """Watchlist badge population service."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.companies = CompanyRepository(session)
        self.data_quality = DataQualityService(session)

    async def populate_badges(self, entries: Sequence[WatchlistEntry]) -> Sequence[WatchlistEntry]:
        """Populate badges for a list of watchlist entries."""
        if not entries:
            return entries

        company_ids = [e.company_id for e in entries]
        companies = {c.id: c for c in await self.companies.list_by_ids(company_ids)}

        # Batch fetch latest prices
        prices = await self._latest_prices(company_ids)

        # Batch fetch latest scores
        scores = await self._latest_scores(company_ids)

        # Batch fetch latest shariah screening
        shariah = await self._latest_shariah(company_ids)

        # Batch fetch latest thesis
        theses = await self._latest_theses(company_ids)

        for entry in entries:
            company = companies.get(entry.company_id)
            if company is None:
                # Company deleted? Still populate with INSUFFICIENT_DATA
                entry.price = self._insufficient_badge("Company not found")  # type: ignore[attr-defined]
                entry.change = self._insufficient_badge("Company not found")  # type: ignore[attr-defined]
                entry.as_of = self._insufficient_badge("Company not found")  # type: ignore[attr-defined]
                entry.staleness = self._insufficient_badge("Company not found")  # type: ignore[attr-defined]
                entry.score = self._insufficient_badge("Company not found")  # type: ignore[attr-defined]
                entry.shariah_state = self._insufficient_badge("Company not found")  # type: ignore[attr-defined]
                entry.thesis_link_badge = self._insufficient_badge("Company not found")  # type: ignore[attr-defined]
                continue

            # Price badge (Phase 1: DailyPrice)
            price_row = prices.get(entry.company_id)
            if price_row is not None:
                close = price_row.close
                # Compute change from previous close
                prev_close = await self._previous_close(entry.company_id, price_row.date)
                if prev_close is not None and prev_close != 0:
                    change_pct = ((close - prev_close) / prev_close) * Decimal("100")
                    change_str = f"{change_pct:.2f}%"
                else:
                    change_str = "N/A"
                entry.price = {  # type: ignore[attr-defined]
                    "value": str(close), "status": "AVAILABLE", "reason": None
                }
                entry.change = {  # type: ignore[attr-defined]
                    "value": change_str, "status": "AVAILABLE", "reason": None
                }
                entry.as_of = {  # type: ignore[attr-defined]
                    "value": price_row.date.isoformat(), "status": "AVAILABLE", "reason": None
                }
                staleness_days = (datetime.now(UTC).date() - price_row.date).days
                entry.staleness = {  # type: ignore[attr-defined]
                    "value": str(staleness_days),
                    "status": "AVAILABLE",
                    "reason": f"{staleness_days} days since last trade",
                }
            else:
                reason = "No price history available"
                entry.price = self._insufficient_badge(reason)  # type: ignore[attr-defined]
                entry.change = self._insufficient_badge(reason)  # type: ignore[attr-defined]
                entry.as_of = self._insufficient_badge(reason)  # type: ignore[attr-defined]
                entry.staleness = self._insufficient_badge(reason)  # type: ignore[attr-defined]

            # Score badge (Phase 4: InvestmentScore)
            score_row = scores.get(entry.company_id)
            if score_row is not None and score_row.headline is not None:
                entry.score = {  # type: ignore[attr-defined]
                    "value": str(score_row.headline),
                    "status": score_row.headline_status,
                    "reason": "Investment score available",
                }
            else:
                entry.score = self._insufficient_badge("Investment score unassessed")  # type: ignore[attr-defined]

            # Shariah state badge (Phase 6: ShariahScreeningResult)
            shariah_row = shariah.get(entry.company_id)
            if shariah_row is not None:
                if shariah_row.is_compliant is True:
                    state = "Compliant"
                elif shariah_row.is_compliant is False:
                    state = "Non-Compliant"
                else:
                    state = "Insufficient Data"
                entry.shariah_state = {  # type: ignore[attr-defined]
                    "value": state,
                    "status": (
                        "AVAILABLE"
                        if shariah_row.is_compliant is not None
                        else "INSUFFICIENT_DATA"
                    ),
                    "reason": shariah_row.overall_reason or "Shariah screening available",
                }
            else:
                entry.shariah_state = self._insufficient_badge("Shariah screening unassessed")  # type: ignore[attr-defined]

            # Thesis link badge (Phase 5: InvestmentThesis)
            thesis_row = theses.get(entry.company_id)
            thesis_uuid = entry.thesis_link  # Preserve the original UUID
            if thesis_uuid is not None:
                # User-specified thesis link
                if thesis_row is not None and thesis_row.id == thesis_uuid:
                    entry.thesis_link_badge = {  # type: ignore[attr-defined]
                        "value": str(thesis_uuid),
                        "status": "AVAILABLE",
                        "reason": "Linked to thesis",
                    }
                else:
                    entry.thesis_link_badge = self._insufficient_badge("Linked thesis not found")  # type: ignore[attr-defined]
            elif thesis_row is not None:
                # Auto-link to latest thesis
                entry.thesis_link_badge = {  # type: ignore[attr-defined]
                    "value": str(thesis_row.id),
                    "status": "AVAILABLE",
                    "reason": "Latest thesis available",
                }
            else:
                entry.thesis_link_badge = self._insufficient_badge("No thesis on file")  # type: ignore[attr-defined]

        return entries

    async def _latest_prices(self, company_ids: list[uuid.UUID]) -> dict[uuid.UUID, DailyPrice]:
        """Fetch latest DailyPrice for each company."""
        if not company_ids:
            return {}
        stmt = (
            select(DailyPrice)
            .where(DailyPrice.company_id.in_(company_ids))
            .order_by(DailyPrice.company_id, DailyPrice.date.desc())
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        latest: dict[uuid.UUID, DailyPrice] = {}
        for row in rows:
            if row.company_id not in latest:
                latest[row.company_id] = row
        return latest

    async def _previous_close(self, company_id: uuid.UUID, as_of: date) -> Decimal | None:
        """Get previous trading day close."""
        stmt = (
            select(DailyPrice.close)
            .where(DailyPrice.company_id == company_id)
            .where(DailyPrice.date < as_of)
            .order_by(DailyPrice.date.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _latest_scores(
        self, company_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, InvestmentScore]:
        """Fetch latest InvestmentScore for each company."""
        if not company_ids:
            return {}
        from app.repositories.scores import ScoreRepository
        repo = ScoreRepository(self.session)
        scores: dict[uuid.UUID, InvestmentScore] = {}
        for cid in company_ids:
            row = await repo.get_snapshot(cid)
            if row is not None:
                scores[cid] = row
        return scores

    async def _latest_shariah(
        self, company_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, ShariahScreeningResult]:
        """Fetch latest ShariahScreeningResult for each company."""
        if not company_ids:
            return {}
        stmt = (
            select(ShariahScreeningResult)
            .where(ShariahScreeningResult.company_id.in_(company_ids))
            .order_by(ShariahScreeningResult.company_id, ShariahScreeningResult.screened_at.desc())
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        latest: dict[uuid.UUID, ShariahScreeningResult] = {}
        for row in rows:
            if row.company_id not in latest:
                latest[row.company_id] = row
        return latest

    async def _latest_theses(
        self, company_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, InvestmentThesis]:
        """Fetch latest InvestmentThesis for each company."""
        if not company_ids:
            return {}
        from app.repositories.thesis import ThesisRepository
        repo = ThesisRepository(self.session)
        theses: dict[uuid.UUID, InvestmentThesis] = {}
        for cid in company_ids:
            row = await repo.get_thesis(cid)
            if row is not None:
                theses[cid] = row
        return theses

    @staticmethod
    def _insufficient_badge(reason: str) -> dict[str, Any]:
        """Create an INSUFFICIENT_DATA badge."""
        return {"value": None, "status": "INSUFFICIENT_DATA", "reason": reason}
