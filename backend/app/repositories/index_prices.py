"""Daily closes of market indices (R50 B10), e.g. EGX30."""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import IndexPrice


class IndexPriceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_many(
        self, index_code: str, closes: Sequence[tuple[date, Decimal]], source: str
    ) -> int:
        """Insert or update closes by (index_code, trade_date); returns rows written."""
        if not closes:
            return 0
        insert_stmt = pg_insert(IndexPrice).values(
            [
                {"index_code": index_code, "trade_date": d, "close": c, "source": source}
                for d, c in closes
            ]
        )
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["index_code", "trade_date"],
            set_={
                "close": insert_stmt.excluded.close,
                "source": insert_stmt.excluded.source,
            },
        )
        await self.session.execute(stmt)
        return len(closes)

    async def series(
        self, index_code: str, start: date | None = None, end: date | None = None
    ) -> list[tuple[date, Decimal]]:
        """Closes of one index within ``[start, end]``, oldest first."""
        query = select(IndexPrice.trade_date, IndexPrice.close).where(
            IndexPrice.index_code == index_code
        )
        if start is not None:
            query = query.where(IndexPrice.trade_date >= start)
        if end is not None:
            query = query.where(IndexPrice.trade_date <= end)
        rows = await self.session.execute(query.order_by(IndexPrice.trade_date))
        return [(row[0], row[1]) for row in rows.all()]
