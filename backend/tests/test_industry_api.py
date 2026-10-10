"""API tests for GET /api/industry/companies/{id} + PUT peers override."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.industry.seed import seed_industry_taxonomy
from app.models.financial import FinancialPeriod
from app.models.industry import EgxSector, GicsSubIndustry
from app.models.market import Company, CompanyStatus
from app.models.metrics import FinancialMetric, MetricStatusDB

AS_OF = date(2026, 10, 10)


async def _egx_sector_id(db_session: AsyncSession, name: str) -> uuid.UUID:
    row = (
        await db_session.execute(select(EgxSector).where(EgxSector.name == name))
    ).scalar_one()
    return row.id


async def _make_company(
    db_session: AsyncSession,
    ticker: str,
    egx_name: str | None,
    sub_code: str | None = None,
) -> Company:
    egx_id = await _egx_sector_id(db_session, egx_name) if egx_name else None
    sub_id: uuid.UUID | None = None
    if sub_code is not None:
        sub = (
            await db_session.execute(
                select(GicsSubIndustry).where(GicsSubIndustry.code == sub_code)
            )
        ).scalar_one()
        sub_id = sub.id
    company = Company(
        id=uuid.uuid4(),
        ticker=ticker,
        isin=f"EG{uuid.uuid4().hex[:10].upper()}",
        name=f"{ticker} Company",
        sector=egx_name,
        industry=None,
        currency="EGP",
        status=CompanyStatus.ACTIVE,
        egx_sector_id=egx_id,
        gics_sub_industry_id=sub_id,
    )
    db_session.add(company)
    await db_session.flush()
    return company


async def _add_metric(
    db_session: AsyncSession,
    company: Company,
    metric_code: str,
    value: Decimal | None,
    status: MetricStatusDB = MetricStatusDB.AVAILABLE,
    calculated_at: datetime | None = None,
    fiscal_year: int = 2024,
) -> None:
    period = (
        await db_session.execute(
            select(FinancialPeriod).where(
                FinancialPeriod.company_id == company.id,
                FinancialPeriod.fiscal_year == fiscal_year,
            )
        )
    ).scalar_one_or_none()
    if period is None:
        period = FinancialPeriod(
            id=uuid.uuid4(),
            company_id=company.id,
            period_type="ANNUAL",
            fiscal_year=fiscal_year,
            start_date=date(fiscal_year, 1, 1),
            end_date=date(fiscal_year, 12, 31),
        )
        db_session.add(period)
        await db_session.flush()
    db_session.add(
        FinancialMetric(
            id=uuid.uuid4(),
            company_id=company.id,
            period_id=period.id,
            metric_code=metric_code,
            display_name=metric_code,
            value=value,
            unit="%",
            status=status,
            reason=None,
            warnings=None,
            formula_version=1,
            calculated_at=calculated_at or datetime(2026, 6, 1, tzinfo=UTC),
        )
    )
    await db_session.flush()


@pytest.fixture
async def bank_universe(db_session: AsyncSession) -> list[Company]:
    """Four banks with roe values 5/10/15/20 (target first)."""
    await seed_industry_taxonomy(db_session, as_of=AS_OF)
    companies = []
    for ticker in ("BANK_A", "BANK_B", "BANK_C", "BANK_D"):
        companies.append(await _make_company(db_session, ticker, "Banks", "40101010"))
    roes = (Decimal("5"), Decimal("10"), Decimal("15"), Decimal("20"))
    for company, roe in zip(companies, roes, strict=True):
        await _add_metric(db_session, company, "roe", roe)
    await db_session.flush()
    return companies


async def test_get_defaults_to_egx_sector_peers(
    client: AsyncClient, bank_universe: list[Company]
) -> None:
    target = bank_universe[0]
    response = await client.get(f"/api/industry/companies/{target.id}")
    assert response.status_code == 200
    data = response.json()

    assert data["company"]["ticker"] == "BANK_A"
    assert data["company"]["egx_sector"] == "Banks"
    assert data["peers"]["basis"] == "egx_sector"
    assert {p["ticker"] for p in data["peers"]["items"]} == {"BANK_B", "BANK_C", "BANK_D"}
    assert data["n_peers"] == 3
    assert data["methodology_version"] == "1.0"
    assert data["profile"]["profile_id"] == "banks"
    assert data["profile"]["methodology_version"] == "1.0"

    roe = next(m for m in data["percentiles"] if m["metric_key"] == "roe")
    assert roe["status"] == "OK"
    assert roe["value"] == "25.00"  # 1 of 4 values at or below 5
    assert roe["n_peers"] == 3
    assert roe["n_with_data"] == 4
    assert "BANK_A" in roe["explanation"]
    assert roe["display_name"] == "Return on Equity"
    assert roe["reason"] == roe["explanation"]

    # Metrics with no data degrade honestly, never zero.
    missing = next(m for m in data["percentiles"] if m["metric_key"] == "roa")
    assert missing == {
        "metric_key": "roa",
        "display_name": "Return on Assets",
        "value": None,
        "status": "INSUFFICIENT_DATA",
        "unit": None,
        "n_peers": 3,
        "n_with_data": 0,
        "explanation": missing["explanation"],
        "reason": missing["explanation"],
    }
    assert "insufficient data" in missing["explanation"]


async def test_single_peer_universe_is_insufficient(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_industry_taxonomy(db_session, as_of=AS_OF)
    a = await _make_company(db_session, "SOLO_A", "Banks", "40101010")
    b = await _make_company(db_session, "SOLO_B", "Banks", "40101010")
    await _add_metric(db_session, a, "roe", Decimal("10"))
    await _add_metric(db_session, b, "roe", Decimal("5"))
    await db_session.flush()

    data = (await client.get(f"/api/industry/companies/{a.id}")).json()
    roe = next(m for m in data["percentiles"] if m["metric_key"] == "roe")
    assert roe["status"] == "INSUFFICIENT_DATA"
    assert roe["value"] is None


async def test_put_override_wins_over_defaults(
    client: AsyncClient, bank_universe: list[Company]
) -> None:
    target, keeper = bank_universe[0], bank_universe[1]
    put = await client.put(
        f"/api/industry/companies/{target.id}/peers",
        json={"peer_company_ids": [str(keeper.id)]},
    )
    assert put.status_code == 200
    assert put.json()["peer_company_ids"] == [str(keeper.id)]
    assert put.json()["methodology_version"] == "1.0"

    data = (await client.get(f"/api/industry/companies/{target.id}")).json()
    assert data["peers"]["basis"] == "override"
    assert [p["ticker"] for p in data["peers"]["items"]] == ["BANK_B"]


async def test_put_rejects_unknown_self_and_missing_company(
    client: AsyncClient, bank_universe: list[Company]
) -> None:
    target = bank_universe[0]
    unknown = uuid.uuid4()

    bad_peer = await client.put(
        f"/api/industry/companies/{target.id}/peers",
        json={"peer_company_ids": [str(unknown)]},
    )
    assert bad_peer.status_code == 400

    self_peer = await client.put(
        f"/api/industry/companies/{target.id}/peers",
        json={"peer_company_ids": [str(target.id)]},
    )
    assert self_peer.status_code == 400

    missing = await client.put(
        f"/api/industry/companies/{unknown}/peers",
        json={"peer_company_ids": []},
    )
    assert missing.status_code == 404


async def test_put_empty_list_is_explicit_empty_override(
    client: AsyncClient, bank_universe: list[Company]
) -> None:
    """PUT [] pins explicit-empty-override semantics: basis override, no peers,
    percentiles floored at INSUFFICIENT_DATA (never a 1-of-1 rank)."""
    target = bank_universe[0]
    put = await client.put(
        f"/api/industry/companies/{target.id}/peers",
        json={"peer_company_ids": []},
    )
    assert put.status_code == 200
    assert put.json()["peer_company_ids"] == []

    data = (await client.get(f"/api/industry/companies/{target.id}")).json()
    assert data["peers"]["basis"] == "override"
    assert data["peers"]["items"] == []
    assert data["n_peers"] == 0
    roe = next(m for m in data["percentiles"] if m["metric_key"] == "roe")
    assert roe["status"] == "INSUFFICIENT_DATA"
    assert roe["value"] is None
    assert all(
        m["status"] == "INSUFFICIENT_DATA" and m["value"] is None
        for m in data["percentiles"]
    )


async def test_get_unknown_company_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/industry/companies/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_gics_fallback_when_no_egx_sector(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_industry_taxonomy(db_session, as_of=AS_OF)
    a = await _make_company(db_session, "FALL_A", None, "40101015")
    b = await _make_company(db_session, "FALL_B", None, "40101015")
    c = await _make_company(db_session, "FALL_C", None, "40101015")
    for company, roe in ((a, Decimal("1")), (b, Decimal("2")), (c, Decimal("3"))):
        await _add_metric(db_session, company, "roe", roe)
    await db_session.flush()

    data = (await client.get(f"/api/industry/companies/{a.id}")).json()
    assert data["peers"]["basis"] == "gics_sub_industry"
    assert data["company"]["gics"] is not None
    assert data["company"]["gics"]["sub_industry_code"] == "40101015"
    # No EGX sector -> default profile.
    assert data["profile"]["profile_id"] == "default"


async def test_latest_metric_value_wins(
    client: AsyncClient, bank_universe: list[Company], db_session: AsyncSession
) -> None:
    target = bank_universe[0]
    await _add_metric(
        db_session,
        target,
        "roe",
        Decimal("99"),
        calculated_at=datetime(2026, 9, 1, tzinfo=UTC),
        fiscal_year=2023,
    )
    await db_session.flush()

    data = (await client.get(f"/api/industry/companies/{target.id}")).json()
    roe = next(m for m in data["percentiles"] if m["metric_key"] == "roe")
    assert roe["value"] == "100.00"


async def test_gics_chain_lookup_returns_four_levels(
    db_session: AsyncSession,
) -> None:
    from app.repositories.industry import IndustryRepository

    await seed_industry_taxonomy(db_session, as_of=AS_OF)
    sub = (
        await db_session.execute(
            select(GicsSubIndustry).where(GicsSubIndustry.code == "40101010")
        )
    ).scalar_one()
    chain = await IndustryRepository(db_session).gics_chain_for_sub_industry(sub.id)
    assert chain is not None
    sector, group, industry, sub_row = chain
    assert (sector.code, sector.name) == ("40", "Financials")
    assert (group.code, group.name) == ("4010", "Banks")
    assert (industry.code, industry.name) == ("401010", "Banks")
    assert (sub_row.code, sub_row.name) == ("40101010", "Diversified Banks")
