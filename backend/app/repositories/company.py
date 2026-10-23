import uuid
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import Company, CompanyStatus
from app.schemas.company import CompanyCreate, CompanyUpdate

if TYPE_CHECKING:
    from sqlalchemy.engine import CursorResult


class CompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: CompanyCreate) -> Company:
        company = Company(**data.model_dump())
        self.session.add(company)
        await self.session.flush()
        return company

    async def upsert_many(self, rows: Sequence[dict[str, Any]]) -> int:
        """Insert or update many companies by ticker.

        ``name`` and ``status`` always come from the source. Optional descriptive
        fields use COALESCE so a source that cannot supply them (a price-only
        feed, for example) never erases values curated elsewhere.
        """
        if not rows:
            return 0

        payload = [
            {
                "ticker": str(row["ticker"]).upper(),
                "name": row.get("name") or str(row["ticker"]).upper(),
                "isin": row.get("isin"),
                "name_ar": row.get("name_ar"),
                "sector": row.get("sector"),
                "industry": row.get("industry"),
                "currency": row.get("currency") or "EGP",
                "shares_outstanding": row.get("shares_outstanding"),
                "free_float": row.get("free_float"),
                "listing_date": row.get("listing_date"),
                "status": CompanyStatus(row.get("status") or CompanyStatus.ACTIVE),
            }
            for row in rows
        ]

        stmt = pg_insert(Company).values(payload)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_company_ticker",
            set_={
                "name": stmt.excluded.name,
                "status": stmt.excluded.status,
                "currency": stmt.excluded.currency,
                "isin": func.coalesce(stmt.excluded.isin, Company.isin),
                "name_ar": func.coalesce(stmt.excluded.name_ar, Company.name_ar),
                "sector": func.coalesce(stmt.excluded.sector, Company.sector),
                "industry": func.coalesce(stmt.excluded.industry, Company.industry),
                "shares_outstanding": func.coalesce(
                    stmt.excluded.shares_outstanding, Company.shares_outstanding
                ),
                "free_float": func.coalesce(stmt.excluded.free_float, Company.free_float),
                "listing_date": func.coalesce(stmt.excluded.listing_date, Company.listing_date),
                "updated_at": func.now(),
            },
        )
        await self.session.execute(stmt)
        return len(payload)

    async def mark_absent_as(self, present_tickers: Sequence[str],
                             status: CompanyStatus = CompanyStatus.DELISTED) -> int:
        """Flag companies absent from the current universe snapshot.

        A company missing from a complete listing snapshot is no longer actively
        traded. This keeps the universe self-correcting when a name is delisted,
        rather than letting stale rows linger and get scored forever.
        """
        tickers = [t.upper() for t in present_tickers]
        query = update(Company).where(Company.status != status)
        if tickers:
            query = query.where(Company.ticker.notin_(tickers))
        result = await self.session.execute(query)
        return cast("CursorResult[Any]", result).rowcount or 0

    async def get_by_id(self, company_id: uuid.UUID) -> Company | None:
        return await self.session.get(Company, company_id)

    async def get_by_ticker(self, ticker: str) -> Company | None:
        result = await self.session.execute(select(Company).where(Company.ticker == ticker.upper()))
        return result.scalar_one_or_none()

    async def list_by_tickers(self, tickers: list[str]) -> Sequence[Company]:
        """Companies for the given tickers (case-insensitive); unknown tickers are skipped."""
        if not tickers:
            return []
        upper = [t.upper() for t in tickers]
        result = await self.session.execute(select(Company).where(Company.ticker.in_(upper)))
        return result.scalars().all()

    async def get_by_isin(self, isin: str) -> Company | None:
        result = await self.session.execute(select(Company).where(Company.isin == isin))
        return result.scalar_one_or_none()

    async def list_companies(
        self,
        page: int = 1,
        page_size: int = 50,
        sector: str | None = None,
        industry: str | None = None,
        status: CompanyStatus | None = None,
        search: str | None = None,
    ) -> tuple[Sequence[Company], int]:
        query = select(Company)
        count_query = select(func.count(Company.id))

        if sector:
            query = query.where(Company.sector == sector)
            count_query = count_query.where(Company.sector == sector)
        if industry:
            query = query.where(Company.industry == industry)
            count_query = count_query.where(Company.industry == industry)
        if status:
            query = query.where(Company.status == status)
            count_query = count_query.where(Company.status == status)
        if search:
            pattern = f"%{search}%"
            query = query.where((Company.ticker.ilike(pattern)) | (Company.name.ilike(pattern)))
            count_query = count_query.where(
                (Company.ticker.ilike(pattern)) | (Company.name.ilike(pattern))
            )

        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        query = query.order_by(Company.ticker)
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.session.execute(query)
        companies = result.scalars().all()

        return companies, total

    async def update(self, company: Company, data: CompanyUpdate) -> Company:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(company, field, value)
        await self.session.flush()
        return company

    async def list_by_ids(self, company_ids: list[uuid.UUID]) -> Sequence[Company]:
        """Get companies by a list of IDs."""
        if not company_ids:
            return []
        result = await self.session.execute(select(Company).where(Company.id.in_(company_ids)))
        return result.scalars().all()
