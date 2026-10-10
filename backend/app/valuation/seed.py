"""Idempotent seeding of industry valuation profiles.

Profile shapes come from ``app.valuation.constants`` (SWS 4-model split +
P/E→P/S→P/B router; research §1). Nothing is invented: EGX scoping reuses
the Phase-2 taxonomy rows, and a profile whose EGX sector is absent is
stored unscoped rather than guessed.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.industry import EgxSector
from app.models.valuation import IndustryValuationProfile
from app.valuation.constants import (
    VALUATION_METHODOLOGY_VERSION,
    VALUATION_PROFILES,
)


async def seed_valuation_profiles(session: AsyncSession) -> dict[str, int]:
    """Seed one row per profile key; safe to run twice. Flushes only."""
    added = 0
    for profile_key, shape in VALUATION_PROFILES.items():
        existing = (
            await session.execute(
                select(IndustryValuationProfile).where(
                    IndustryValuationProfile.profile_key == profile_key,
                    IndustryValuationProfile.methodology_version
                    == VALUATION_METHODOLOGY_VERSION,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        egx_id: uuid.UUID | None = None
        egx_name = shape["egx_sector"]
        if egx_name is not None:
            egx = (
                await session.execute(
                    select(EgxSector).where(EgxSector.name == egx_name)
                )
            ).scalar_one_or_none()
            egx_id = egx.id if egx is not None else None
        assert shape["primary_model"] is not None
        assert shape["fallback_model"] is not None
        assert shape["preferred_multiple"] is not None
        session.add(
            IndustryValuationProfile(
                id=uuid.uuid4(),
                profile_key=profile_key,
                sub_industry_id=None,
                egx_sector_id=egx_id,
                primary_model=shape["primary_model"],
                fallback_model=shape["fallback_model"],
                preferred_multiple=shape["preferred_multiple"],
                methodology_version=VALUATION_METHODOLOGY_VERSION,
            )
        )
        added += 1
    await session.flush()
    return {"profiles_added": added, "profiles_total": len(VALUATION_PROFILES)}
