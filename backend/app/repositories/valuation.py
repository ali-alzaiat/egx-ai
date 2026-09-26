"""Repository for valuation persistence."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.valuation import ValuationModelDB, ValuationResult, ValuationStatusDB


class ValuationRepository:
    """Repository for valuation CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_valuation(
        self,
        company_id: uuid.UUID,
        model: ValuationModelDB,
        value: float | None,
        status: ValuationStatusDB,
        assumptions: str | None,
        reason: str | None,
        calculated_at,
    ) -> ValuationResult:
        """Create or update a valuation result."""
        stmt = (
            pg_insert(ValuationResult)
            .values(
                company_id=company_id,
                model=model,
                value=value,
                status=status,
                assumptions=assumptions,
                reason=reason,
                calculated_at=calculated_at,
            )
            .on_conflict_do_update(
                constraint="uq_valuation_result",
                set_={
                    "value": value,
                    "status": status,
                    "assumptions": assumptions,
                    "reason": reason,
                },
            )
            .returning(ValuationResult)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_valuations_for_company(
        self,
        company_id: uuid.UUID,
        model: ValuationModelDB | None = None,
    ) -> Sequence[ValuationResult]:
        """Get valuation results for a company."""
        query = select(ValuationResult).where(
            ValuationResult.company_id == company_id,
        )
        if model:
            query = query.where(ValuationResult.model == model)
        query = query.order_by(ValuationResult.calculated_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()
