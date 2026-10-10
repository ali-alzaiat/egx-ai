"""Repository for investment-score profiles and snapshots."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scores import IndustryScoreProfile, InvestmentScore
from app.scores.constants import DEFAULT_SCORE_PROFILE_KEY, SCORE_METHODOLOGY_VERSION


class ScoreProfileRepository:
    """Repository for versioned industry score profiles."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def resolve(
        self,
        egx_sector_id: uuid.UUID | None,
        sub_industry_id: uuid.UUID | None,
    ) -> IndustryScoreProfile | None:
        """EGX-scoped profile, else sub-industry-scoped, else the default row."""
        if egx_sector_id is not None:
            scoped = await self.session.execute(
                select(IndustryScoreProfile)
                .where(IndustryScoreProfile.egx_sector_id == egx_sector_id)
                .where(
                    IndustryScoreProfile.methodology_version
                    == SCORE_METHODOLOGY_VERSION
                )
            )
            row = scoped.scalars().first()
            if row is not None:
                return row
        if sub_industry_id is not None:
            scoped = await self.session.execute(
                select(IndustryScoreProfile)
                .where(IndustryScoreProfile.sub_industry_id == sub_industry_id)
                .where(
                    IndustryScoreProfile.methodology_version
                    == SCORE_METHODOLOGY_VERSION
                )
            )
            row = scoped.scalars().first()
            if row is not None:
                return row
        default = await self.session.execute(
            select(IndustryScoreProfile)
            .where(IndustryScoreProfile.profile_key == DEFAULT_SCORE_PROFILE_KEY)
            .where(
                IndustryScoreProfile.methodology_version == SCORE_METHODOLOGY_VERSION
            )
        )
        return default.scalars().first()

    async def get_by_key(self, profile_key: str) -> IndustryScoreProfile | None:
        """Row for an exact profile key under the current methodology."""
        result = await self.session.execute(
            select(IndustryScoreProfile)
            .where(IndustryScoreProfile.profile_key == profile_key)
            .where(
                IndustryScoreProfile.methodology_version
                == SCORE_METHODOLOGY_VERSION
            )
        )
        return result.scalars().first()


class ScoreRepository:
    """Repository for investment-score snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_snapshot(
        self,
        company_id: uuid.UUID,
        profile_key: str,
        headline: Decimal | None,
        headline_status: str,
        components: dict[str, Any],
        checks: list[dict[str, Any]],
        confidence: dict[str, Any],
        buy_zone: dict[str, Any],
        n_with_data: int,
        margin_of_safety: Decimal,
        inputs_echo: dict[str, Any],
        computed_at: datetime,
    ) -> InvestmentScore:
        """Create or replace the snapshot for one company + methodology version.

        Last-writer-wins: the unique key is company + methodology version
        (inputs do not participate), so differing inputs overwrite the single
        row and ``inputs_echo`` reflects only the latest write.
        """
        stmt = (
            pg_insert(InvestmentScore)
            .values(
                company_id=company_id,
                profile_key=profile_key,
                methodology_version=SCORE_METHODOLOGY_VERSION,
                headline=headline,
                headline_status=headline_status,
                components=components,
                checks=checks,
                confidence=confidence,
                buy_zone=buy_zone,
                n_with_data=n_with_data,
                margin_of_safety=margin_of_safety,
                inputs_echo=inputs_echo,
                computed_at=computed_at,
            )
            .on_conflict_do_update(
                constraint="uq_investment_score",
                set_={
                    "profile_key": profile_key,
                    "headline": headline,
                    "headline_status": headline_status,
                    "components": components,
                    "checks": checks,
                    "confidence": confidence,
                    "buy_zone": buy_zone,
                    "n_with_data": n_with_data,
                    "margin_of_safety": margin_of_safety,
                    "inputs_echo": inputs_echo,
                    "computed_at": computed_at,
                },
            )
            .returning(InvestmentScore)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_snapshot(
        self, company_id: uuid.UUID
    ) -> InvestmentScore | None:
        """Latest snapshot for one company under the current methodology."""
        result = await self.session.execute(
            select(InvestmentScore)
            .where(InvestmentScore.company_id == company_id)
            .where(
                InvestmentScore.methodology_version == SCORE_METHODOLOGY_VERSION
            )
        )
        return result.scalars().first()
