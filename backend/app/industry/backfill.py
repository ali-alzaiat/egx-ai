"""One-shot EGX sector backfill of companies (ISIN join, no scheduler).

Every update traces to a source row (EGX page URL + as-of). Rows that match
no company, or carry no sector, are reported as skipped — never fabricated.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.industry.constants import EGX_LISTED_STOCKS_URL, EGX_SECTOR_SOURCE_NAME
from app.models.industry import EgxSector
from app.models.market import Company, DataSource, DataSourceType


@dataclass(frozen=True, slots=True)
class EgxListingRow:
    """One EGX listed-stocks page row: ISIN is the join key, Reuters secondary."""

    isin: str | None
    reuters_code: str | None
    sector_name: str


@dataclass(frozen=True, slots=True)
class SkippedRow:
    isin: str | None
    reuters_code: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class BackfillReport:
    updated: int
    skipped: tuple[SkippedRow, ...]
    source_id: str
    as_of: str


def normalize_isin(isin: str | None) -> str | None:
    """Upper-case stripped ISIN, or None when blank."""
    if isin is None:
        return None
    cleaned = isin.strip().upper()
    return cleaned or None


def normalize_reuters_ticker(reuters_code: str | None) -> str | None:
    """Map a Reuters code like ``COMI.CA`` to the local ticker ``COMI``."""
    if reuters_code is None:
        return None
    cleaned = reuters_code.strip().upper()
    if cleaned.endswith(".CA"):
        cleaned = cleaned[: -len(".CA")]
    return cleaned or None


async def _ensure_source(
    session: AsyncSession, source_url: str, source_name: str
) -> DataSource:
    stmt = select(DataSource).where(DataSource.name == source_name)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing
    source = DataSource(
        id=uuid.uuid4(),
        name=source_name,
        source_type=DataSourceType.EGX,
        base_url=source_url,
    )
    session.add(source)
    await session.flush()
    return source


async def _ensure_egx_sector(session: AsyncSession, name: str) -> EgxSector:
    stmt = select(EgxSector).where(EgxSector.name == name)
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        return existing
    sector = EgxSector(id=uuid.uuid4(), name=name)
    session.add(sector)
    await session.flush()
    return sector


async def backfill_egx_sectors(
    session: AsyncSession,
    rows: list[EgxListingRow],
    *,
    source_url: str = EGX_LISTED_STOCKS_URL,
    source_name: str = EGX_SECTOR_SOURCE_NAME,
    as_of: date,
) -> BackfillReport:
    """Apply EGX listing rows to companies; flush only (caller commits)."""
    source = await _ensure_source(session, source_url, source_name)
    updated = 0
    skipped: list[SkippedRow] = []
    sector_cache: dict[str, EgxSector] = {}

    for row in rows:
        isin = normalize_isin(row.isin)
        ticker = normalize_reuters_ticker(row.reuters_code)
        sector_name = row.sector_name.strip()

        if not sector_name:
            skipped.append(SkippedRow(isin, row.reuters_code, "missing sector name"))
            continue

        company: Company | None = None
        if isin is not None:
            company = (
                await session.execute(select(Company).where(Company.isin == isin))
            ).scalar_one_or_none()
        if company is None and ticker is not None:
            company = (
                await session.execute(select(Company).where(Company.ticker == ticker))
            ).scalar_one_or_none()
        if company is None:
            skipped.append(SkippedRow(isin, row.reuters_code, "no company match"))
            continue

        sector = sector_cache.get(sector_name)
        if sector is None:
            sector = await _ensure_egx_sector(session, sector_name)
            sector_cache[sector_name] = sector

        company.sector = sector_name
        company.egx_sector_id = sector.id
        updated += 1

    await session.flush()
    return BackfillReport(
        updated=updated,
        skipped=tuple(skipped),
        source_id=str(source.id),
        as_of=as_of.isoformat(),
    )
