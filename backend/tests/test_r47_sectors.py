"""R47 S1: EGX sector snapshot loader and the Shariah activity tags (R44 D-9)."""

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.industry import egx_sectors
from app.industry.backfill import EgxListingRow, backfill_egx_sectors, normalize_sector_name
from app.industry.constants import EGX_SECTOR_NAMES
from app.industry.egx_sectors import SectorRow, coverage, load_snapshot, validate_rows
from app.models.industry import EgxSector
from app.models.market import Company, CompanyStatus
from app.screening import service as screening_service
from app.screening.activity_tags import (
    ALLOWED_TAGS,
    ISLAMIC_BANK_TAGGED,
    OVERRIDES,
    REVIEW_SECTORS,
    SECTOR_DEFAULT_TAGS,
    TagBasis,
    resolve_activity_tag,
)
from app.screening.methodology import DEFAULT_METHODOLOGY
from app.screening.purification import ISLAMIC_BANK_TICKERS
from app.screening.rules import ScreeningVerdict
from app.screening.service import ShariahScreeningService
from app.screening.statement_input import build_screening_input_from_statements
from app.statements.bridge import CompanyStatements


def _row(**kw: Any) -> SectorRow:
    base: dict[str, Any] = {
        "ticker": "AAAA",
        "isin": "EGS000000012",
        "egx_sector": "Banks",
        "match_basis": "sector_index_reuters",
    }
    base.update(kw)
    return SectorRow(**base)


# --- snapshot validation -------------------------------------------------------------------


def test_every_egx_sector_is_tagged_or_review() -> None:
    names = {normalize_sector_name(n) for n in EGX_SECTOR_NAMES}
    assert names == set(SECTOR_DEFAULT_TAGS) | REVIEW_SECTORS
    assert not set(SECTOR_DEFAULT_TAGS) & REVIEW_SECTORS


def test_validate_rows_accepts_good_and_flags_bad() -> None:
    good = (
        _row(),
        _row(ticker="BBBB", isin="EGS000000013", match_basis="alias"),
        _row(
            ticker="CCCC",
            isin="EGS000000014",
            egx_sector="Industrial Goods , Services and Automobiles",
            match_basis="name_review",
            review_note="Listed as Cccc Co",
        ),
    )
    assert validate_rows(good) == []

    problems = validate_rows(
        (
            _row(ticker="aaaa"),
            _row(ticker="DDDD", isin="short"),
            _row(ticker="EEEE", egx_sector="Made Up"),
            _row(ticker="FFFF", match_basis="fuzzy"),
            _row(ticker="GGGG", match_basis="name_review"),  # no review note
            _row(ticker="AREH"),
            _row(ticker="HHHH", isin="EGS000000012"),  # duplicate ISIN
        )
    )
    text = " | ".join(problems)
    for fragment in (
        "upper-case",
        "not 12 characters",
        "unknown EGX sector",
        "match_basis 'fuzzy'",
        "review_note",
        "must stay without a sector",
        "duplicate ISIN",
    ):
        assert fragment in text


def test_coverage_counts_by_basis_and_sector() -> None:
    rows = (
        _row(),
        _row(ticker="B", isin="EGS000000013", match_basis="alias"),
        _row(ticker="C", isin="EGS000000014", egx_sector="Real Estate"),
    )
    cov = coverage(rows)
    assert cov["by_match_basis"] == {"sector_index_reuters": 2, "alias": 1}
    assert cov["by_sector"] == {"Banks": 2, "Real Estate": 1}


async def test_empty_snapshot_refuses_to_load(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="empty"):
        await load_snapshot(db_session, ())


async def test_invalid_snapshot_writes_nothing(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="invalid sector snapshot"):
        await load_snapshot(db_session, (_row(match_basis="fuzzy"),))


def test_shipped_snapshot_is_valid() -> None:
    assert validate_rows(egx_sectors.SECTOR_ROWS) == []


def test_shipped_snapshot_follows_owner_rulings() -> None:
    """R47 S3: unconfirmed two-listing pairs and AREH stay out; FAIT/FAITA load."""
    tickers = {r.ticker for r in egx_sectors.SECTOR_ROWS}
    assert tickers.isdisjoint({"AREH", "SEIG", "SEIGA", "VLMR", "VLMRA"})
    assert {"FAIT", "FAITA", "MAAL"} <= tickers


# --- loader -------------------------------------------------------------------------------


async def _company(db: AsyncSession, isin: str | None = None) -> Company:
    ticker = f"S{uuid.uuid4().hex[:6].upper()}"
    company = Company(
        id=uuid.uuid4(), ticker=ticker, isin=isin, name="Sector Co",
        currency="EGP", status=CompanyStatus.ACTIVE,
    )
    db.add(company)
    await db.flush()
    return company


async def test_loader_writes_sector_basis_and_isin_idempotently(db_session: AsyncSession) -> None:
    company = await _company(db_session)
    row = _row(
        ticker=company.ticker,
        isin="EGT" + uuid.uuid4().hex[:9].upper(),
        egx_sector="Industrial Goods , Services and Automobiles",
    )
    first = await load_snapshot(db_session, (row,))
    second = await load_snapshot(db_session, (row,))
    assert (first.updated, second.updated) == (1, 1)
    await db_session.refresh(company)
    assert company.sector == "Industrial Goods, Services and Automobiles"
    assert company.sector_match_basis == "sector_index_reuters"
    assert company.isin == row.isin
    assert company.industry is None  # the raw sector never lands in industry
    count = (
        await db_session.execute(
            select(func.count()).select_from(EgxSector).where(
                EgxSector.name.like("Industrial Goods%")
            )
        )
    ).scalar_one()
    assert count == 1  # no duplicate sector row for the spaced EGX spelling


async def test_loader_skips_isin_conflict(db_session: AsyncSession) -> None:
    company = await _company(db_session, isin="EGT000000001")
    report = await backfill_egx_sectors(
        db_session,
        [EgxListingRow("EGT000000002", f"{company.ticker}.CA", "Banks", "alias")],
        as_of=egx_sectors.FETCHED_ON,
    )
    assert report.updated == 0
    assert "isin conflict" in report.skipped[0].reason
    await db_session.refresh(company)
    assert company.sector is None and company.sector_match_basis is None


async def test_unmatched_company_stays_without_sector(db_session: AsyncSession) -> None:
    company = await _company(db_session)
    await load_snapshot(db_session, (_row(ticker="NOSUCH1", isin="EGT000000003"),))
    await db_session.refresh(company)
    assert company.sector is None and company.sector_match_basis is None


# --- activity tags -------------------------------------------------------------------------


def test_food_company_without_override_is_unknown_not_fail_not_pass() -> None:
    tag = resolve_activity_tag("JUFO", "Food, Beverages and Tobacco")
    assert tag.tag is None
    assert tag.basis is TagBasis.UNREVIEWED
    assert "no sector default" in tag.reason


@pytest.mark.parametrize("sector", sorted(REVIEW_SECTORS))
def test_review_sectors_have_no_default(sector: str) -> None:
    assert resolve_activity_tag("ZZZZ", sector).tag is None


def test_east_fails_as_tobacco() -> None:
    tag = resolve_activity_tag("EAST", "Food, Beverages and Tobacco")
    assert tag.tag == "tobacco" and tag.basis is TagBasis.COMPANY_OVERRIDE


def test_cib_fails_as_conventional_bank_and_islamic_banks_pass() -> None:
    assert resolve_activity_tag("COMI", "Banks").tag == "conventional_banking"
    for ticker in ("FAIT", "FAITA", "ADIB", "SAUD"):
        assert resolve_activity_tag(ticker, "Banks").tag == "islamic_bank"
    assert ISLAMIC_BANK_TAGGED == ISLAMIC_BANK_TICKERS


def test_insurer_fails_by_name_review() -> None:
    tag = resolve_activity_tag("DEIN", "Non-bank financial services")
    assert tag.tag == "conventional_insurance" and tag.basis is TagBasis.NAME_REVIEW


def test_sector_default_passes_with_basis_shown() -> None:
    tag = resolve_activity_tag("MASR", "Real Estate")
    assert tag.tag == "permitted" and tag.basis is TagBasis.SECTOR_DEFAULT
    assert "Real Estate" in tag.source
    spaced = resolve_activity_tag("XXXX", "Industrial Goods , Services and Automobiles")
    assert spaced.tag == "permitted"


def test_no_sector_is_unknown() -> None:
    assert resolve_activity_tag("MASR", None).tag is None
    assert resolve_activity_tag("MASR", "  ").tag is None
    assert resolve_activity_tag("MASR", "Not A Sector").tag is None


def test_every_tag_is_a_known_value() -> None:
    assert {o.tag for o in OVERRIDES} <= ALLOWED_TAGS
    assert set(SECTOR_DEFAULT_TAGS.values()) <= ALLOWED_TAGS
    for override in OVERRIDES:
        assert override.source.strip()


async def test_raw_sector_names_never_reach_screen_industry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str | None] = []
    real = screening_service.screen_industry

    def spy(industry: str | None, prohibited_industries: tuple[str, ...] = ()) -> Any:
        seen.append(industry)
        return real(industry=industry, prohibited_industries=prohibited_industries)

    monkeypatch.setattr(screening_service, "screen_industry", spy)
    service = ShariahScreeningService(None, DEFAULT_METHODOLOGY)  # type: ignore[arg-type]
    statements = CompanyStatements(company_id=uuid.uuid4(), periods=())
    verdicts: dict[str, ScreeningVerdict] = {}
    for sector in EGX_SECTOR_NAMES:
        company = SimpleNamespace(
            id=uuid.uuid4(), ticker="ZZZZ", sector=sector, industry="Tobacco Trading"
        )
        inp = build_screening_input_from_statements(company, statements)  # type: ignore[arg-type]
        out = await service.screen_company(inp)
        industry_rule = next(r for r in out.rule_results if r.rule_name == "industry_screen")
        verdicts[sector] = industry_rule.verdict
    assert len(seen) == len(EGX_SECTOR_NAMES)
    assert all(v is None or v in ALLOWED_TAGS for v in seen)
    # company.industry ('Tobacco Trading') is ignored: Food stays UNKNOWN, not FAIL.
    assert verdicts["Food, Beverages and Tobacco"] is ScreeningVerdict.INSUFFICIENT_DATA
    assert verdicts["Banks"] is ScreeningVerdict.FAIL
    assert verdicts["Real Estate"] is ScreeningVerdict.PASS


async def test_service_reason_shows_tag_and_basis() -> None:
    service = ShariahScreeningService(None, DEFAULT_METHODOLOGY)  # type: ignore[arg-type]
    statements = CompanyStatements(company_id=uuid.uuid4(), periods=())
    company = SimpleNamespace(id=uuid.uuid4(), ticker="MASR", sector="Real Estate", industry=None)
    out = await service.screen_company(
        build_screening_input_from_statements(company, statements)  # type: ignore[arg-type]
    )
    rule = next(r for r in out.rule_results if r.rule_name == "industry_screen")
    assert rule.reason is not None
    assert "permitted" in rule.reason and "sector_default" in rule.reason
    assert rule.source is not None and "activity tags 1.0" in rule.source

    unknown = SimpleNamespace(
        id=uuid.uuid4(), ticker="JUFO", sector="Food, Beverages and Tobacco", industry=None
    )
    out2 = await service.screen_company(
        build_screening_input_from_statements(unknown, statements)  # type: ignore[arg-type]
    )
    rule2 = next(r for r in out2.rule_results if r.rule_name == "industry_screen")
    assert rule2.verdict is ScreeningVerdict.INSUFFICIENT_DATA
    assert rule2.reason is not None and "unknown" in rule2.reason
