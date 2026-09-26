"""Repository for Shariah screening persistence."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.screening import (
    ScreeningRuleResultDB,
    ScreeningStatusDB,
    ShariahScreeningResult,
)


class ScreeningRepository:
    """Repository for Shariah screening CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_screening_result(
        self,
        company_id: uuid.UUID,
        is_compliant: bool,
        methodology_version: str,
        methodology_name: str,
        overall_reason: str,
        screened_at,
    ) -> ShariahScreeningResult:
        """Create or update a screening result."""
        status = ScreeningStatusDB.COMPLIANT if is_compliant else ScreeningStatusDB.NON_COMPLIANT

        stmt = (
            pg_insert(ShariahScreeningResult)
            .values(
                company_id=company_id,
                is_compliant=is_compliant,
                status=status,
                methodology_version=methodology_version,
                methodology_name=methodology_name,
                overall_reason=overall_reason,
                screened_at=screened_at,
            )
            .on_conflict_do_update(
                constraint="uq_shariah_screening_result",
                set_={
                    "is_compliant": is_compliant,
                    "status": status,
                    "overall_reason": overall_reason,
                    "screened_at": screened_at,
                },
            )
            .returning(ShariahScreeningResult)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def add_rule_result(
        self,
        screening_result_id: uuid.UUID,
        rule_name: str,
        verdict: str,
        value: float | None,
        threshold: float | None,
        reason: str | None,
    ) -> ScreeningRuleResultDB:
        """Add a rule result to a screening result."""
        rule = ScreeningRuleResultDB(
            id=uuid.uuid4(),
            screening_result_id=screening_result_id,
            rule_name=rule_name,
            verdict=verdict,
            value=value,
            threshold=threshold,
            reason=reason,
        )
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def get_screening_result(
        self,
        company_id: uuid.UUID,
        methodology_version: str | None = None,
    ) -> ShariahScreeningResult | None:
        """Get the latest screening result for a company."""
        query = select(ShariahScreeningResult).where(
            ShariahScreeningResult.company_id == company_id,
        )
        if methodology_version:
            query = query.where(
                ShariahScreeningResult.methodology_version == methodology_version
            )
        query = query.order_by(ShariahScreeningResult.screened_at.desc())
        result = await self.session.execute(query)
        return result.scalars().first()

    async def list_screened_companies(
        self,
        is_compliant: bool | None = None,
        methodology_version: str | None = None,
    ) -> Sequence[ShariahScreeningResult]:
        """List all screening results, optionally filtered."""
        query = select(ShariahScreeningResult)

        if is_compliant is not None:
            query = query.where(ShariahScreeningResult.is_compliant == is_compliant)

        if methodology_version:
            query = query.where(
                ShariahScreeningResult.methodology_version == methodology_version
            )

        query = query.order_by(ShariahScreeningResult.screened_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()
