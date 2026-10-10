"""Idempotent seeding of the GICS × EGX taxonomy, mappings, and profiles.

All names/codes come from the pinned sources in
``app.industry.constants`` (MSCI GICS methodology, EGX listed-stocks page).
Nothing is invented: only the three GICS branches Phase 2 profiles need are
seeded; remaining branches arrive when a later phase needs them (R22 cut).
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.industry.constants import (
    DEFAULT_PROFILE_KEY,
    EGX_LISTED_STOCKS_URL,
    EGX_SECTOR_NAMES,
    EGX_SECTOR_SOURCE_NAME,
    EGX_TO_GICS_SUB,
    GICS_BRANCH_SECTORS,
    GICS_BRANCHES,
    GICS_SECTORS,
    INDUSTRY_METHODOLOGY_VERSION,
    METRIC_PROFILES,
)
from app.models.industry import (
    EgxSector,
    EgxSectorGicsMap,
    GicsIndustry,
    GicsIndustryGroup,
    GicsSector,
    GicsSubIndustry,
    IndustryMetricProfile,
)
from app.models.market import DataSource, DataSourceType


async def _get_or_create_sector(session: AsyncSession, code: str, name: str) -> GicsSector:
    existing = (
        await session.execute(select(GicsSector).where(GicsSector.code == code))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    row = GicsSector(id=uuid.uuid4(), code=code, name=name)
    session.add(row)
    await session.flush()
    return row


async def _get_or_create_group(
    session: AsyncSession, sector_id: uuid.UUID, code: str, name: str
) -> GicsIndustryGroup:
    existing = (
        await session.execute(select(GicsIndustryGroup).where(GicsIndustryGroup.code == code))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    row = GicsIndustryGroup(id=uuid.uuid4(), sector_id=sector_id, code=code, name=name)
    session.add(row)
    await session.flush()
    return row


async def _get_or_create_industry(
    session: AsyncSession, group_id: uuid.UUID, code: str, name: str
) -> GicsIndustry:
    existing = (
        await session.execute(select(GicsIndustry).where(GicsIndustry.code == code))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    row = GicsIndustry(id=uuid.uuid4(), group_id=group_id, code=code, name=name)
    session.add(row)
    await session.flush()
    return row


async def _get_or_create_sub_industry(
    session: AsyncSession, industry_id: uuid.UUID, code: str, name: str
) -> GicsSubIndustry:
    existing = (
        await session.execute(select(GicsSubIndustry).where(GicsSubIndustry.code == code))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    row = GicsSubIndustry(id=uuid.uuid4(), industry_id=industry_id, code=code, name=name)
    session.add(row)
    await session.flush()
    return row


async def _get_or_create_egx_sector(session: AsyncSession, name: str) -> EgxSector:
    existing = (
        await session.execute(select(EgxSector).where(EgxSector.name == name))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    row = EgxSector(id=uuid.uuid4(), name=name)
    session.add(row)
    await session.flush()
    return row


async def seed_industry_taxonomy(
    session: AsyncSession,
    *,
    source_url: str = EGX_LISTED_STOCKS_URL,
    as_of: date,
) -> dict[str, int]:
    """Seed taxonomy + mappings + profiles; safe to run twice. Flushes only."""
    for code, name in GICS_SECTORS:
        await _get_or_create_sector(session, code, name)

    sub_by_code: dict[str, GicsSubIndustry] = {}
    for group_code, group_name, ind_code, ind_name, sub_code, sub_name in GICS_BRANCHES:
        sector_code = GICS_BRANCH_SECTORS[group_code]
        sector = (
            await session.execute(select(GicsSector).where(GicsSector.code == sector_code))
        ).scalar_one_or_none()
        if sector is None:  # pragma: no cover - GICS_SECTORS loop above always seeds it
            raise ValueError(f"GICS sector {sector_code} missing from seed")
        group = await _get_or_create_group(session, sector.id, group_code, group_name)
        industry = await _get_or_create_industry(session, group.id, ind_code, ind_name)
        sub = await _get_or_create_sub_industry(session, industry.id, sub_code, sub_name)
        sub_by_code[sub_code] = sub

    egx_by_name: dict[str, EgxSector] = {}
    for name in EGX_SECTOR_NAMES:
        egx_by_name[name] = await _get_or_create_egx_sector(session, name)

    source = (
        await session.execute(select(DataSource).where(DataSource.name == EGX_SECTOR_SOURCE_NAME))
    ).scalar_one_or_none()
    if source is None:
        source = DataSource(
            id=uuid.uuid4(),
            name=EGX_SECTOR_SOURCE_NAME,
            source_type=DataSourceType.EGX,
            base_url=source_url,
        )
        session.add(source)
        await session.flush()

    mappings = 0
    for egx_name, sub_code in EGX_TO_GICS_SUB:
        egx = egx_by_name[egx_name]
        sub = sub_by_code[sub_code]
        existing = (
            await session.execute(
                select(EgxSectorGicsMap).where(
                    EgxSectorGicsMap.egx_sector_id == egx.id,
                    EgxSectorGicsMap.sub_industry_id == sub.id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                EgxSectorGicsMap(
                    id=uuid.uuid4(),
                    egx_sector_id=egx.id,
                    sub_industry_id=sub.id,
                    source_id=source.id,
                    as_of=as_of,
                )
            )
            mappings += 1

    profiles = 0
    for profile_key, egx_scope, metric_keys in METRIC_PROFILES:
        egx_id = egx_by_name[egx_scope].id if egx_scope is not None else None
        for order, metric_key in enumerate(metric_keys):
            existing_profile = (
                await session.execute(
                    select(IndustryMetricProfile).where(
                        IndustryMetricProfile.profile_key == profile_key,
                        IndustryMetricProfile.metric_key == metric_key,
                        IndustryMetricProfile.methodology_version
                        == INDUSTRY_METHODOLOGY_VERSION,
                    )
                )
            ).scalar_one_or_none()
            if existing_profile is None:
                session.add(
                    IndustryMetricProfile(
                        id=uuid.uuid4(),
                        profile_key=profile_key,
                        sub_industry_id=None,
                        egx_sector_id=egx_id,
                        metric_key=metric_key,
                        display_order=order,
                        methodology_version=INDUSTRY_METHODOLOGY_VERSION,
                    )
                )
                profiles += 1

    await session.flush()
    # Re-read authoritative counts (idempotent: reruns add zero rows).
    n_subs = len(
        (await session.execute(select(GicsSubIndustry.id))).scalars().all()
    )
    return {
        "gics_sectors": len(GICS_SECTORS),
        "gics_sub_industries_seeded_branch": n_subs,
        "egx_sectors": len(EGX_SECTOR_NAMES),
        "mappings_added": mappings,
        "profiles_added": profiles,
    }


def default_profile_key() -> str:
    """Profile key used when no industry-scoped profile matches."""
    return DEFAULT_PROFILE_KEY
