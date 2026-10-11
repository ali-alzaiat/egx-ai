import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.disclosure import DisclosureFactDiff, DisclosureFiling


class DisclosureFilingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_hash(self, content_hash: str) -> DisclosureFiling | None:
        result = await self.session.execute(
            select(DisclosureFiling).where(DisclosureFiling.content_hash == content_hash)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, filing_id: uuid.UUID) -> DisclosureFiling | None:
        return await self.session.get(DisclosureFiling, filing_id)

    async def create(self, filing: DisclosureFiling) -> DisclosureFiling:
        self.session.add(filing)
        await self.session.flush()
        return filing

    async def list_by_company(
        self, company_id: uuid.UUID
    ) -> Sequence[DisclosureFiling]:
        result = await self.session.execute(
            select(DisclosureFiling)
            .where(DisclosureFiling.company_id == company_id)
            .order_by(DisclosureFiling.report_date.desc())
        )
        return result.scalars().all()


class DisclosureFactDiffRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, diff: DisclosureFactDiff) -> DisclosureFactDiff:
        self.session.add(diff)
        await self.session.flush()
        return diff

    async def list_by_company(
        self, company_id: uuid.UUID
    ) -> Sequence[DisclosureFactDiff]:
        result = await self.session.execute(
            select(DisclosureFactDiff)
            .where(DisclosureFactDiff.company_id == company_id)
            .order_by(DisclosureFactDiff.created_at.desc())
        )
        return result.scalars().all()
