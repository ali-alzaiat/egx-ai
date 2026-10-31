"""Performance I/O: load stored closes, EGX30 and approved statement lines for the pure engine."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import FinancialPeriod
from app.models.market import Company, CompanyStatus, DailyPrice
from app.performance.constants import (
    BENCHMARK_INDEX,
    MIN_SECTOR_PEERS,
    NET_INCOME_CODE,
    PERFORMANCE_METHODOLOGY_VERSION,
    REVENUE_CODE,
)
from app.performance.engine import (
    PeriodValue,
    fundamentals_growth,
    insufficient,
    performance_windows,
    price_returns,
    sector_peer_benchmark,
)
from app.repositories.index_prices import IndexPriceRepository
from app.repositories.price import PriceRepository
from app.repositories.statements import StatementLineRepository

#: Calendar days of closes loaded: 1Y of trading days plus the previous year-end for YTD.
HISTORY_DAYS = 800


def to_jsonable(node: Any) -> Any:
    """Decimals as strings (as every tool returns them), so the result is plain JSON."""
    if isinstance(node, Decimal):
        return str(node)
    if isinstance(node, dict):
        return {k: to_jsonable(v) for k, v in node.items()}
    if isinstance(node, list):
        return [to_jsonable(v) for v in node]
    return node


class PerformanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _period_values(self, company_id: uuid.UUID) -> dict[str, list[PeriodValue]]:
        lines = [
            row
            for row in await StatementLineRepository(self.session).latest_approved(company_id)
            if row.ontology_code in (REVENUE_CODE, NET_INCOME_CODE) and row.value is not None
        ]
        period_ids = {row.period_id for row in lines}
        periods: dict[uuid.UUID, FinancialPeriod] = {}
        if period_ids:
            result = await self.session.execute(
                select(FinancialPeriod).where(FinancialPeriod.id.in_(period_ids))
            )
            periods = {p.id: p for p in result.scalars().all()}
        out: dict[str, list[PeriodValue]] = {REVENUE_CODE: [], NET_INCOME_CODE: []}
        for row in lines:
            period = periods.get(row.period_id)
            if period is None:
                continue
            out[row.ontology_code].append(
                PeriodValue(
                    period_type=period.period_type.value,
                    fiscal_year=int(period.fiscal_year),
                    start_date=period.start_date,
                    end_date=period.end_date,
                    value=row.value,
                )
            )
        return out

    async def _peer_closes(
        self, company_id: uuid.UUID, sector: str, start: date, end: date
    ) -> dict[str, list[tuple[date, Decimal]]]:
        """Closes of the active companies in ``sector`` except the company: one query."""
        rows = await self.session.execute(
            select(DailyPrice.company_id, DailyPrice.date, DailyPrice.close)
            .join(Company, Company.id == DailyPrice.company_id)
            .where(
                Company.sector == sector,
                Company.status == CompanyStatus.ACTIVE,
                Company.id != company_id,
                DailyPrice.date >= start,
                DailyPrice.date <= end,
            )
            .order_by(DailyPrice.company_id, DailyPrice.date)
        )
        peers: dict[str, list[tuple[date, Decimal]]] = {}
        for peer_id, day, close in rows.all():
            peers.setdefault(str(peer_id), []).append((day, close))
        return peers

    async def company_performance(self, company_id: uuid.UUID, as_of: date) -> dict[str, Any]:
        """Returns versus EGX30 and sector peers over the fixed windows, plus fundamentals."""
        start = as_of - timedelta(days=HISTORY_DAYS)
        company = await self.session.get(Company, company_id)
        sector = company.sector if company is not None else None
        stock = await PriceRepository(self.session).closes(company_id, start, as_of)
        index = await IndexPriceRepository(self.session).series(BENCHMARK_INDEX, start, as_of)
        values = await self._period_values(company_id)
        windows = performance_windows(stock, index, as_of)
        benchmark: dict[str, dict[str, Any]]
        if sector:
            peers = await self._peer_closes(company_id, sector, start, as_of)
            benchmark = sector_peer_benchmark(price_returns(stock, as_of), peers, as_of)
        else:
            reason = "the company has no sector, so it has no sector peers"
            benchmark = {w: {**insufficient(reason), "peer_count": 0} for w in windows}
        for window, block in windows.items():
            block["sector"] = benchmark[window]
        payload: dict[str, Any] = to_jsonable({
            "methodology_version": PERFORMANCE_METHODOLOGY_VERSION,
            "price_as_of": stock[-1][0].isoformat() if stock else None,
            "index_code": BENCHMARK_INDEX,
            "index_as_of": index[-1][0].isoformat() if index else None,
            "sector": sector,
            "sector_peer_rule": (
                f"median of the active sector peers excluding the company, "
                f"at least {MIN_SECTOR_PEERS} with a return"
            ),
            "returns": windows,
            "fundamentals": fundamentals_growth(values[REVENUE_CODE], values[NET_INCOME_CODE]),
        })
        return payload
