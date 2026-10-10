"""Idempotent seeding of industry score profiles.

Profile shapes come from ``app.scores.constants`` (SWS dual health-track
routing; research §1). Nothing is invented: EGX scoping reuses the Phase-2
taxonomy rows, and a profile whose EGX sector is absent is stored unscoped
rather than guessed.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.industry import EgxSector
from app.models.scores import IndustryScoreProfile
from app.scores.constants import SCORE_METHODOLOGY_VERSION, SCORE_PROFILES


async def seed_score_profiles(session: AsyncSession) -> dict[str, int]:
    """Seed one row per profile key; safe to run twice. Flushes only."""
    added = 0
    for profile_key, egx_scope, health_track in SCORE_PROFILES:
        existing = (
            await session.execute(
                select(IndustryScoreProfile).where(
                    IndustryScoreProfile.profile_key == profile_key,
                    IndustryScoreProfile.methodology_version
                    == SCORE_METHODOLOGY_VERSION,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        egx_id: uuid.UUID | None = None
        if egx_scope is not None:
            egx = (
                await session.execute(
                    select(EgxSector).where(EgxSector.name == egx_scope)
                )
            ).scalar_one_or_none()
            egx_id = egx.id if egx is not None else None
        session.add(
            IndustryScoreProfile(
                id=uuid.uuid4(),
                profile_key=profile_key,
                sub_industry_id=None,
                egx_sector_id=egx_id,
                health_track=health_track,
                methodology_version=SCORE_METHODOLOGY_VERSION,
            )
        )
        added += 1
    await session.flush()
    return {"profiles_added": added, "profiles_total": len(SCORE_PROFILES)}
