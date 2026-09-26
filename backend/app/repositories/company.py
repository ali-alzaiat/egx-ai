import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import Company, CompanyStatus
from app.schemas.company import CompanyCreate, CompanyUpdate


class CompanyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: CompanyCreate) -> Company:
        company = Company(**data.model_dump())
        self.session.add(company)
        await self.session.flush()
        return company

    async def get_by_id(self, company_id: uuid.UUID) -> Company | None:
        return await self.session.get(Company, company_id)

    async def get_by_ticker(self, ticker: str) -> Company | None:
        result = await self.session.execute(select(Company).where(Company.ticker == ticker.upper()))
        return result.scalar_one_or_none()

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
