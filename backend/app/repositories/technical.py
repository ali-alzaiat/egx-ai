"""Repository for technical indicators persistence."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.technical import IndicatorStatusDB, IndicatorTypeDB, TechnicalIndicator


class TechnicalRepository:
    """Repository for technical indicator CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_indicator(
        self,
        company_id: uuid.UUID,
        indicator_type: IndicatorTypeDB,
        value: float | None,
        status: IndicatorStatusDB,
        parameters: str | None,
        reason: str | None,
        calculated_at: datetime,
    ) -> TechnicalIndicator:
        """Create or update a technical indicator."""
        stmt = (
            pg_insert(TechnicalIndicator)
            .values(
                company_id=company_id,
                indicator_type=indicator_type,
                value=value,
                status=status,
                parameters=parameters,
                reason=reason,
                calculated_at=calculated_at,
            )
            .on_conflict_do_update(
                constraint="uq_technical_indicator",
                set_={
                    "value": value,
                    "status": status,
                    "parameters": parameters,
                    "reason": reason,
                },
            )
            .returning(TechnicalIndicator)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_indicators_for_company(
        self,
        company_id: uuid.UUID,
        indicator_type: IndicatorTypeDB | None = None,
    ) -> Sequence[TechnicalIndicator]:
        """Get technical indicators for a company."""
        query = select(TechnicalIndicator).where(
            TechnicalIndicator.company_id == company_id,
        )
        if indicator_type:
            query = query.where(TechnicalIndicator.indicator_type == indicator_type)
        query = query.order_by(TechnicalIndicator.calculated_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def latest_set(self, company_id: uuid.UUID) -> Sequence[TechnicalIndicator]:
        """Only the most recent computed set (R43: one snapshot per company)."""
        latest = (
            await self.session.execute(
                select(func.max(TechnicalIndicator.calculated_at)).where(
                    TechnicalIndicator.company_id == company_id
                )
            )
        ).scalar_one_or_none()
        if latest is None:
            return []
        result = await self.session.execute(
            select(TechnicalIndicator)
            .where(TechnicalIndicator.company_id == company_id)
            .where(TechnicalIndicator.calculated_at == latest)
            .order_by(TechnicalIndicator.indicator_type)
        )
        return result.scalars().all()
