"""Repository for valuation persistence."""

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.valuation import (
    IndustryValuationProfile,
    ValuationFairValue,
    ValuationModelDB,
    ValuationResult,
    ValuationStatusDB,
)
from app.valuation.constants import (
    DEFAULT_VALUATION_PROFILE_KEY,
    VALUATION_METHODOLOGY_VERSION,
)


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
        calculated_at: datetime,
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


class ValuationProfileRepository:
    """Repository for versioned industry valuation profiles."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve(
        self,
        egx_sector_id: uuid.UUID | None,
        sub_industry_id: uuid.UUID | None,
    ) -> IndustryValuationProfile | None:
        """EGX-scoped profile, else sub-industry-scoped, else the default row."""
        if egx_sector_id is not None:
            scoped = await self.session.execute(
                select(IndustryValuationProfile)
                .where(IndustryValuationProfile.egx_sector_id == egx_sector_id)
                .where(
                    IndustryValuationProfile.methodology_version
                    == VALUATION_METHODOLOGY_VERSION
                )
            )
            row = scoped.scalars().first()
            if row is not None:
                return row
        if sub_industry_id is not None:
            scoped = await self.session.execute(
                select(IndustryValuationProfile)
                .where(IndustryValuationProfile.sub_industry_id == sub_industry_id)
                .where(
                    IndustryValuationProfile.methodology_version
                    == VALUATION_METHODOLOGY_VERSION
                )
            )
            row = scoped.scalars().first()
            if row is not None:
                return row
        default = await self.session.execute(
            select(IndustryValuationProfile)
            .where(IndustryValuationProfile.profile_key == DEFAULT_VALUATION_PROFILE_KEY)
            .where(
                IndustryValuationProfile.methodology_version
                == VALUATION_METHODOLOGY_VERSION
            )
        )
        return default.scalars().first()


class FairValueRepository:
    """Repository for weighted-fair-value snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_snapshot(
        self,
        company_id: uuid.UUID,
        profile_key: str,
        fair_value: Decimal | None,
        fair_value_status: str,
        legs: dict[str, Any],
        weights: dict[str, Any],
        scenarios: dict[str, Any],
        sensitivity: list[dict[str, Any]],
        confidence: dict[str, Any],
        verdict: dict[str, Any],
        inputs_echo: dict[str, Any],
        current_price: Decimal | None,
        price_as_of: date | None,
        computed_at: datetime,
    ) -> ValuationFairValue:
        """Create or replace the snapshot for one company + methodology version."""
        stmt = (
            pg_insert(ValuationFairValue)
            .values(
                company_id=company_id,
                profile_key=profile_key,
                methodology_version=VALUATION_METHODOLOGY_VERSION,
                fair_value=fair_value,
                fair_value_status=fair_value_status,
                legs=legs,
                weights=weights,
                scenarios=scenarios,
                sensitivity=sensitivity,
                confidence=confidence,
                verdict=verdict,
                inputs_echo=inputs_echo,
                current_price=current_price,
                price_as_of=price_as_of,
                computed_at=computed_at,
            )
            .on_conflict_do_update(
                constraint="uq_valuation_fair_value",
                set_={
                    "profile_key": profile_key,
                    "fair_value": fair_value,
                    "fair_value_status": fair_value_status,
                    "legs": legs,
                    "weights": weights,
                    "scenarios": scenarios,
                    "sensitivity": sensitivity,
                    "confidence": confidence,
                    "verdict": verdict,
                    "inputs_echo": inputs_echo,
                    "current_price": current_price,
                    "price_as_of": price_as_of,
                    "computed_at": computed_at,
                },
            )
            .returning(ValuationFairValue)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_snapshot(
        self, company_id: uuid.UUID
    ) -> ValuationFairValue | None:
        """Latest snapshot for one company under the current methodology."""
        result = await self.session.execute(
            select(ValuationFairValue)
            .where(ValuationFairValue.company_id == company_id)
            .where(
                ValuationFairValue.methodology_version == VALUATION_METHODOLOGY_VERSION
            )
        )
        return result.scalars().first()
