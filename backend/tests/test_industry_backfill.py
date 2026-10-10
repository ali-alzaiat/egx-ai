"""Tests for the one-shot EGX sector backfill (ISIN join, no fabrication)."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.industry.backfill import (
    EgxListingRow,
    backfill_egx_sectors,
    normalize_isin,
    normalize_reuters_ticker,
)
from app.models.industry import EgxSector
from app.models.market import Company, CompanyStatus

AS_OF = date(2026, 10, 10)


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:6].upper()}"


async def _make_company(
    db_session: AsyncSession,
    ticker: str,
    isin: str | None,
    exact_ticker: bool = False,
) -> Company:
    """Tickers are uniquified (dev DB holds real rows); ISINs pass through exactly."""
    company = Company(
        id=uuid.uuid4(),
        ticker=ticker if exact_ticker else _uid(ticker),
        isin=isin,
        name=f"{ticker} Company",
        sector=None,
        industry=None,
        currency="EGP",
        status=CompanyStatus.ACTIVE,
    )
    db_session.add(company)
    await db_session.flush()
    return company


def test_normalize_helpers() -> None:
    assert normalize_isin(" eg12345678 ") == "EG12345678"
    assert normalize_isin("  ") is None
    assert normalize_isin(None) is None
    assert normalize_reuters_ticker("COMI.CA") == "COMI"
    assert normalize_reuters_ticker("comi.ca ") == "COMI"
    assert normalize_reuters_ticker("COMI") == "COMI"
    assert normalize_reuters_ticker(None) is None


async def test_backfill_matches_on_isin(db_session: AsyncSession) -> None:
    company = await _make_company(db_session, "COMI", "EGTST101C018")
    report = await backfill_egx_sectors(
        db_session,
        [EgxListingRow(isin="EGTST101C018", reuters_code="COMI.CA", sector_name="Banks")],
        as_of=AS_OF,
    )
    assert report.updated == 1
    assert report.skipped == ()
    assert report.as_of == "2026-10-10"
    assert report.source_id

    await db_session.refresh(company)
    assert company.sector == "Banks"
    assert company.egx_sector_id is not None
    egx = await db_session.get(EgxSector, company.egx_sector_id)
    assert egx is not None and egx.name == "Banks"


async def test_backfill_falls_back_to_reuters_ticker(db_session: AsyncSession) -> None:
    unique = _uid("RW")
    company = await _make_company(db_session, unique, None, exact_ticker=True)
    report = await backfill_egx_sectors(
        db_session,
        [EgxListingRow(isin=None, reuters_code=f"{unique}.CA", sector_name="Real Estate")],
        as_of=AS_OF,
    )
    assert report.updated == 1
    await db_session.refresh(company)
    assert company.sector == "Real Estate"


async def test_backfill_skips_unknown_without_fabricating(db_session: AsyncSession) -> None:
    report = await backfill_egx_sectors(
        db_session,
        [EgxListingRow(isin="EGXXXXXXX000", reuters_code="NOPE.CA", sector_name="Banks")],
        as_of=AS_OF,
    )
    assert report.updated == 0
    assert len(report.skipped) == 1
    assert report.skipped[0].reason == "no company match"
    # No company row was invented for the unknown ISIN.
    unknown = (
        await db_session.execute(select(Company).where(Company.isin == "EGXXXXXXX000"))
    ).scalar_one_or_none()
    assert unknown is None


async def test_backfill_skips_blank_sector(db_session: AsyncSession) -> None:
    company = await _make_company(db_session, "ETEL", "EGTST102C018")
    report = await backfill_egx_sectors(
        db_session,
        [EgxListingRow(isin="EGTST102C018", reuters_code="ETEL.CA", sector_name="  ")],
        as_of=AS_OF,
    )
    assert report.updated == 0
    assert report.skipped[0].reason == "missing sector name"
    await db_session.refresh(company)
    assert company.sector is None


async def test_backfill_is_idempotent(db_session: AsyncSession) -> None:
    await _make_company(db_session, "COMI", "EGTST101C018")
    rows = [EgxListingRow(isin="EGTST101C018", reuters_code="COMI.CA", sector_name="Banks")]
    first = await backfill_egx_sectors(db_session, rows, as_of=AS_OF)
    second = await backfill_egx_sectors(db_session, rows, as_of=AS_OF)
    assert (first.updated, second.updated) == (1, 1)
    sectors = (
        await db_session.execute(select(EgxSector).where(EgxSector.name == "Banks"))
    ).scalars().all()
    assert len(sectors) == 1


@pytest.mark.asyncio
async def test_backfill_isin_beats_reuters_on_conflict(db_session: AsyncSession) -> None:
    """ISIN is the primary join key even when the Reuters code matches another row."""
    isin_owner = await _make_company(db_session, "AAA", "EGTST103C018")
    await _make_company(db_session, "BBB", "EGTST104C018")
    report = await backfill_egx_sectors(
        db_session,
        [EgxListingRow(isin="EGTST103C018", reuters_code="ZZZBOGUS.CA", sector_name="Banks")],
        as_of=AS_OF,
    )
    assert report.updated == 1
    await db_session.refresh(isin_owner)
    assert isin_owner.sector == "Banks"
