"""Repository for technical indicators persistence."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
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
        calculated_at,
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
