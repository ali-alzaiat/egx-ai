"""Cross-check I/O (R50 B11): load lines and prices, run the pure checks, store and read runs.

Each run appends one row per check with a shared ``computed_at``; "latest" is the newest run of
a company. Checks never write anywhere else.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dataquality import crosscheck
from app.dataquality.constants import (
    CHECK_ORDER,
    CROSSCHECK_METHODOLOGY_VERSION,
    PRICE_LOOKBACK_DAYS,
)
from app.dataquality.crosscheck import CheckResult, LineInfo
from app.models.data_quality import DataCrosscheck
from app.models.financial import FinancialPeriod
from app.models.statements import ExtractionMethod, FinancialStatementLine
from app.repositories.price import PriceRepository
from app.repositories.statements import StatementLineRepository


def _info(row: FinancialStatementLine, period: FinancialPeriod) -> LineInfo:
    return LineInfo(
        period=f"{period.period_type.value}-{period.fiscal_year}",
        period_end=period.end_date,
        code=row.ontology_code,
        value=row.value,
        vendor=row.extraction_method == ExtractionMethod.vendor_aggregator,
        has_document=row.source_document_id is not None,
        has_page=bool(row.source_page),
        xbrl=row.extraction_method == ExtractionMethod.xbrl,
    )


def payload(
    company_id: uuid.UUID,
    computed_at: datetime | None,
    rows: list[CheckResult],
    version: str = CROSSCHECK_METHODOLOGY_VERSION,
) -> dict[str, Any]:
    """The API / tool shape. ``overall`` is the worst status; no run gives no checks."""
    return {
        "company_id": str(company_id),
        "computed_at": computed_at.isoformat() if computed_at is not None else None,
        "methodology_version": version,
        "overall": crosscheck.worst_status([r.status for r in rows]) if rows else None,
        "checks": [r.as_dict() for r in rows],
    }


class CrosscheckService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _line_infos(self, company_id: uuid.UUID) -> tuple[list[LineInfo], list[LineInfo]]:
        repo = StatementLineRepository(self.session)
        latest = await repo.latest_approved(company_id)
        everything = await repo.approved_lines(company_id)
        period_ids = {row.period_id for row in everything}
        periods: dict[uuid.UUID, FinancialPeriod] = {}
        if period_ids:
            result = await self.session.execute(
                select(FinancialPeriod).where(FinancialPeriod.id.in_(period_ids))
            )
            periods = {p.id: p for p in result.scalars().all()}
        latest_infos = [_info(r, periods[r.period_id]) for r in latest if r.period_id in periods]
        all_infos = [_info(r, periods[r.period_id]) for r in everything if r.period_id in periods]
        return latest_infos, all_infos

    async def compute(self, company_id: uuid.UUID, as_of: date) -> list[CheckResult]:
        """Run the five pure checks over stored data (no writes)."""
        latest, everything = await self._line_infos(company_id)
        closes = await PriceRepository(self.session).closes(
            company_id, as_of - timedelta(days=PRICE_LOOKBACK_DAYS + 30), as_of
        )
        results = crosscheck.run_all(
            latest_lines=latest, all_lines=everything, closes=closes, as_of=as_of
        )
        order = {code: i for i, code in enumerate(CHECK_ORDER)}
        return sorted(results, key=lambda r: order[r.code])

    async def run(self, company_id: uuid.UUID, now: datetime | None = None) -> dict[str, Any]:
        """Run now, append the rows and return the stored run."""
        computed_at = now or datetime.now(UTC)
        results = await self.compute(company_id, computed_at.date())
        for r in results:
            self.session.add(
                DataCrosscheck(
                    company_id=company_id,
                    check_code=r.code,
                    status=r.status,
                    detail=r.detail,
                    evidence=r.evidence,
                    methodology_version=CROSSCHECK_METHODOLOGY_VERSION,
                    computed_at=computed_at,
                )
            )
        await self.session.flush()
        return payload(company_id, computed_at, results)

    async def latest(self, company_id: uuid.UUID) -> dict[str, Any]:
        """The newest stored run, or ``{checks: [], computed_at: None}`` when never run."""
        newest = (
            await self.session.execute(
                select(func.max(DataCrosscheck.computed_at)).where(
                    DataCrosscheck.company_id == company_id
                )
            )
        ).scalar()
        if newest is None:
            return payload(company_id, None, [])
        rows = (
            await self.session.execute(
                select(DataCrosscheck).where(
                    DataCrosscheck.company_id == company_id,
                    DataCrosscheck.computed_at == newest,
                )
            )
        ).scalars().all()
        order = {code: i for i, code in enumerate(CHECK_ORDER)}
        ordered = sorted(rows, key=lambda r: order.get(r.check_code, len(order)))
        results = [
            CheckResult(r.check_code, r.status, r.detail, dict(r.evidence)) for r in ordered
        ]
        return payload(company_id, newest, results, ordered[0].methodology_version)
