import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import DataSource, DataSourceType


class DataSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_or_create(
        self,
        name: str,
        source_type: DataSourceType,
        base_url: str | None = None,
        description: str | None = None,
    ) -> DataSource:
        result = await self.session.execute(select(DataSource).where(DataSource.name == name))
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        ds = DataSource(
            name=name,
            source_type=source_type,
            base_url=base_url,
            description=description,
        )
        self.session.add(ds)
        await self.session.flush()
        return ds

    async def get_by_id(self, source_id: uuid.UUID) -> DataSource | None:
        return await self.session.get(DataSource, source_id)
