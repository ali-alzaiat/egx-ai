import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import (
    FinancialDocument,
    FinancialFact,
    FinancialPeriod,
)
from app.schemas.financial import (
    FinancialDocumentCreate,
    FinancialFactCreate,
    FinancialPeriodCreate,
)


class FinancialPeriodRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: FinancialPeriodCreate) -> FinancialPeriod:
        period = FinancialPeriod(**data.model_dump())
        self.session.add(period)
        await self.session.flush()
        return period

    async def upsert(self, data: FinancialPeriodCreate) -> FinancialPeriod:
        stmt = (
            pg_insert(FinancialPeriod)
            .values(**data.model_dump())
            .on_conflict_do_update(
                constraint="uq_financial_period",
                set_={
                    "start_date": data.start_date,
                    "end_date": data.end_date,
                },
            )
            .returning(FinancialPeriod)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_id(self, period_id: uuid.UUID) -> FinancialPeriod | None:
        return await self.session.get(FinancialPeriod, period_id)

    async def list_periods(
        self,
        company_id: uuid.UUID,
        period_type: str | None = None,
        fiscal_year: int | None = None,
    ) -> Sequence[FinancialPeriod]:
        query = select(FinancialPeriod).where(FinancialPeriod.company_id == company_id)

        if period_type:
            query = query.where(FinancialPeriod.period_type == period_type)
        if fiscal_year:
            query = query.where(FinancialPeriod.fiscal_year == fiscal_year)

        query = query.order_by(FinancialPeriod.fiscal_year.desc())

        result = await self.session.execute(query)
        return result.scalars().all()


class FinancialDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: FinancialDocumentCreate) -> FinancialDocument:
        doc = FinancialDocument(**data.model_dump())
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def upsert(self, data: FinancialDocumentCreate) -> FinancialDocument:
        stmt = (
            pg_insert(FinancialDocument)
            .values(**data.model_dump())
            .on_conflict_do_update(
                constraint="uq_financial_document",
                set_={
                    "document_status": data.document_status,
                    "document_type": data.document_type,
                    "document_url": data.document_url,
                    "filing_date": data.filing_date,
                    "publication_date": data.publication_date,
                    "fiscal_year_end": data.fiscal_year_end,
                    "notes": data.notes,
                },
            )
            .returning(FinancialDocument)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_id(self, doc_id: uuid.UUID) -> FinancialDocument | None:
        return await self.session.get(FinancialDocument, doc_id)

    async def list_documents(
        self,
        period_id: uuid.UUID,
        document_status: str | None = None,
    ) -> Sequence[FinancialDocument]:
        query = select(FinancialDocument).where(
            FinancialDocument.period_id == period_id
        )

        if document_status:
            query = query.where(FinancialDocument.document_status == document_status)

        query = query.order_by(FinancialDocument.publication_date.desc())

        result = await self.session.execute(query)
        return result.scalars().all()


class FinancialFactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: FinancialFactCreate) -> FinancialFact:
        fact = FinancialFact(**data.model_dump())
        self.session.add(fact)
        await self.session.flush()
        return fact

    async def bulk_create(self, records: list[FinancialFactCreate]) -> int:
        if not records:
            return 0

        for record in records:
            fact = FinancialFact(**record.model_dump())
            self.session.add(fact)

        await self.session.flush()
        return len(records)

    async def get_by_id(self, fact_id: uuid.UUID) -> FinancialFact | None:
        return await self.session.get(FinancialFact, fact_id)

    async def list_facts(
        self,
        company_id: uuid.UUID,
        fact_type: str | None = None,
        reported_label: str | None = None,
        normalized_label: str | None = None,
        status: str | None = None,
        fiscal_year: int | None = None,
    ) -> Sequence[FinancialFact]:
        query = select(FinancialFact).where(FinancialFact.company_id == company_id)

        if fact_type:
            query = query.where(FinancialFact.fact_type == fact_type)
        if reported_label:
            query = query.where(FinancialFact.reported_label == reported_label)
        if normalized_label:
            query = query.where(FinancialFact.normalized_label == normalized_label)
        if status:
            query = query.where(FinancialFact.status == status)
        if fiscal_year:
            query = query.join(FinancialPeriod).where(
                FinancialPeriod.fiscal_year == fiscal_year
            )

        query = query.order_by(FinancialFact.reported_label)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def update(self, fact: FinancialFact, data: dict) -> FinancialFact:
        for field, value in data.items():
            setattr(fact, field, value)
        await self.session.flush()
        return fact
