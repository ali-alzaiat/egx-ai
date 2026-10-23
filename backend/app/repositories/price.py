import uuid
from collections.abc import Sequence
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import DailyPrice
from app.schemas.price import DailyPriceCreate


class PriceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(self, data: DailyPriceCreate) -> DailyPrice:
        stmt = (
            pg_insert(DailyPrice)
            .values(**data.model_dump())
            .on_conflict_do_update(
                constraint="uq_daily_price_company_date",
                set_={
                    "open": data.open,
                    "high": data.high,
                    "low": data.low,
                    "close": data.close,
                    "adjusted_close": data.adjusted_close,
                    "volume": data.volume,
                    "value_traded": data.value_traded,
                    "trades": data.trades,
                    "source_id": data.source_id,
                },
            )
            .returning(DailyPrice)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def bulk_upsert(self, records: list[DailyPriceCreate]) -> int:
        if not records:
            return 0

        insert_stmt = pg_insert(DailyPrice).values([r.model_dump() for r in records])
        stmt = insert_stmt.on_conflict_do_update(
            constraint="uq_daily_price_company_date",
            set_={
                "open": insert_stmt.excluded.open,
                "high": insert_stmt.excluded.high,
                "low": insert_stmt.excluded.low,
                "close": insert_stmt.excluded.close,
                "adjusted_close": insert_stmt.excluded.adjusted_close,
                "volume": insert_stmt.excluded.volume,
                "value_traded": insert_stmt.excluded.value_traded,
                "trades": insert_stmt.excluded.trades,
                "source_id": insert_stmt.excluded.source_id,
            },
        )
        await self.session.execute(stmt)
        return len(records)

    async def get_latest(self, company_id: uuid.UUID) -> DailyPrice | None:
        result = await self.session.execute(
            select(DailyPrice)
            .where(DailyPrice.company_id == company_id)
            .order_by(DailyPrice.date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_prices(
        self,
        company_id: uuid.UUID,
        start_date: date | None = None,
        end_date: date | None = None,
        page: int = 1,
        page_size: int = 200,
    ) -> tuple[Sequence[DailyPrice], int]:
        query = select(DailyPrice).where(DailyPrice.company_id == company_id)
        count_query = select(func.count(DailyPrice.id)).where(DailyPrice.company_id == company_id)

        if start_date:
            query = query.where(DailyPrice.date >= start_date)
            count_query = count_query.where(DailyPrice.date >= start_date)
        if end_date:
            query = query.where(DailyPrice.date <= end_date)
            count_query = count_query.where(DailyPrice.date <= end_date)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        query = query.order_by(DailyPrice.date.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.session.execute(query)
        prices = result.scalars().all()

        return prices, total

    async def latest_price_date(self) -> date | None:
        """Newest stored price date across all companies (the stance cache key)."""
        return (await self.session.execute(select(func.max(DailyPrice.date)))).scalar()

    async def most_traded_company_ids(
        self,
        limit: int,
        lookback_days: int = 30,
        company_ids: Sequence[uuid.UUID] | None = None,
    ) -> list[uuid.UUID]:
        """Companies ranked by average daily value traded (close x volume).

        The window is ``lookback_days`` calendar days back from the newest
        stored price date, so a stale database still ranks consistently.
        """
        latest = await self.latest_price_date()
        if latest is None:
            return []
        avg_value = func.avg(DailyPrice.close * DailyPrice.volume)
        query = (
            select(DailyPrice.company_id)
            .where(DailyPrice.date >= latest - timedelta(days=lookback_days))
            .group_by(DailyPrice.company_id)
            .order_by(avg_value.desc().nulls_last(), DailyPrice.company_id)
            .limit(limit)
        )
        if company_ids is not None:
            query = query.where(DailyPrice.company_id.in_(company_ids))
        result = await self.session.execute(query)
        return list(result.scalars().all())
