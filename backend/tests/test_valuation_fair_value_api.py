"""API tests for GET /api/valuation/companies/{id}/fair-value (additive)."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dataquality.scores import METHODOLOGY_VERSION as DQ_VERSION
from app.industry.seed import seed_industry_taxonomy
from app.models.data_quality import DataQualityAssessment, DataQualityStatusDB
from app.models.financial import FinancialPeriod
from app.models.industry import EgxSector
from app.models.market import Company, CompanyStatus, DailyPrice, DataSource, DataSourceType
from app.models.metrics import FinancialMetric, MetricStatusDB
from app.models.valuation import ValuationFairValue
from app.valuation.constants import VALUATION_METHODOLOGY_VERSION
from app.valuation.seed import seed_valuation_profiles

AS_OF = date(2026, 10, 10)

BANK_PARAMS = {
    "book_value_per_share": "35.38",
    "stable_roe": "0.098",
    "discount_rate": "0.0761",
    "terminal_growth_rate": "0.02",
    "expected_dps": "2",
    "earnings_per_share": "5",
    "pe_ratio": "10",
    "revenue_growth": "0.05",
    "operating_margin": "0.15",
    "exit_multiple": "12",
}


async def _seed(db_session: AsyncSession) -> None:
    await seed_industry_taxonomy(db_session, as_of=AS_OF)
    await seed_valuation_profiles(db_session)


async def _make_company(
    db_session: AsyncSession, ticker: str, egx_name: str | None = "Banks"
) -> Company:
    egx_id = None
    if egx_name is not None:
        egx_id = (
            await db_session.execute(select(EgxSector).where(EgxSector.name == egx_name))
        ).scalar_one().id
    company = Company(
        id=uuid.uuid4(),
        ticker=ticker,
        isin=f"EG{uuid.uuid4().hex[:10].upper()}",
        name=f"{ticker} Company",
        sector=egx_name,
        currency="EGP",
        status=CompanyStatus.ACTIVE,
        egx_sector_id=egx_id,
    )
    db_session.add(company)
    await db_session.flush()
    return company


async def _add_assessment(
    db_session: AsyncSession,
    company: Company,
    scope: str,
    score: Decimal,
    status: DataQualityStatusDB,
) -> None:
    db_session.add(
        DataQualityAssessment(
            id=uuid.uuid4(),
            company_id=company.id,
            scope=scope,
            as_of=AS_OF,
            score=score,
            status=status,
            components=[],
            issues=[],
            methodology_version=DQ_VERSION,
            source_id=None,
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.flush()


async def _add_price(
    db_session: AsyncSession, company: Company, close: Decimal
) -> None:
    source = DataSource(
        id=uuid.uuid4(),
        name=f"Price Source {uuid.uuid4().hex[:8]}",
        source_type=DataSourceType.EGX,
    )
    db_session.add(source)
    await db_session.flush()
    db_session.add(
        DailyPrice(
            id=uuid.uuid4(),
            company_id=company.id,
            date=AS_OF,
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1000,
            source_id=source.id,
        )
    )
    await db_session.flush()


async def _add_metric(
    db_session: AsyncSession, company: Company, code: str, value: Decimal
) -> None:
    period = (
        await db_session.execute(
            select(FinancialPeriod).where(
                FinancialPeriod.company_id == company.id,
                FinancialPeriod.fiscal_year == 2024,
            )
        )
    ).scalar_one_or_none()
    if period is None:
        period = FinancialPeriod(
            id=uuid.uuid4(),
            company_id=company.id,
            period_type="ANNUAL",
            fiscal_year=2024,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        db_session.add(period)
        await db_session.flush()
    db_session.add(
        FinancialMetric(
            id=uuid.uuid4(),
            company_id=company.id,
            period_id=period.id,
            metric_code=code,
            display_name=code,
            value=value,
            unit="%",
            status=MetricStatusDB.AVAILABLE,
            reason=None,
            warnings=None,
            formula_version=1,
            calculated_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
    )
    await db_session.flush()


async def _good_dq(db_session: AsyncSession, company: Company) -> None:
    await _add_assessment(
        db_session, company, "financial_statements", Decimal("85"), DataQualityStatusDB.OK
    )
    await _add_assessment(
        db_session, company, "price_history", Decimal("80"), DataQualityStatusDB.OK
    )


async def test_fair_value_unknown_company_404(client: AsyncClient) -> None:
    response = await client.get(f"/api/valuation/companies/{uuid.uuid4()}/fair-value")
    assert response.status_code == 404


async def test_bank_happy_path(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "BANKFV")
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("30"))

    response = await client.get(
        f"/api/valuation/companies/{company.id}/fair-value", params=BANK_PARAMS
    )
    assert response.status_code == 200
    data = response.json()

    assert data["company_id"] == str(company.id)
    assert data["ticker"] == "BANKFV"
    assert data["methodology_version"] == VALUATION_METHODOLOGY_VERSION
    assert data["profile"]["profile_id"] == "banks"
    assert data["profile"]["primary_model"] == "excess_returns"
    assert data["profile"]["preferred_multiple"] == "pb"
    assert data["weights"] == {"intrinsic": "0.6", "relative": "0.4"}
    assert data["n_with_data"] == 2

    fv = data["fair_value"]
    assert fv["status"] == "AVAILABLE"
    assert fv["value"] is not None
    # 0.6 × excess-returns (~49.19) + 0.4 × PE (5 × exit 12 = 60) ≈ 53.5.
    # Exit multiple takes precedence over pe_ratio (disclosed fallback).
    assert abs(Decimal(fv["value"]) - Decimal("53.5")) < Decimal("0.5")
    assert Decimal(data["legs"]["relative"]["value"]) == Decimal("60")

    assert data["legs"]["intrinsic"]["model"] == "excess_returns"
    assert data["legs"]["relative"]["model"] == "price_to_earnings"
    assert data["legs"]["fallback"]["model"] == "dividend_discount"

    scenarios = data["scenarios"]
    assert scenarios["note"].startswith("Bull/base/bear values are a range")
    assert scenarios["base"]["value"] == fv["value"]
    assert (
        Decimal(scenarios["bear"]["value"])
        < Decimal(scenarios["base"]["value"])
        < Decimal(scenarios["bull"]["value"])
    )

    discount_rows = [r for r in data["sensitivity"] if r["parameter"] == "discount_rate"]
    assert len(discount_rows) == 4
    ordered = sorted(discount_rows, key=lambda r: Decimal(r["value"]))
    fvs = [Decimal(r["fair_value"]) for r in ordered]
    assert fvs == sorted(fvs, reverse=True)  # higher discount → lower value

    assert data["confidence"]["level"] == "VeryHigh"
    assert data["verdict"]["label"] == "POTENTIALLY_UNDERVALUED"
    assert "under these assumptions" in data["verdict"]["detail"]
    assert data["current_price"] == {"value": "30.0000", "as_of": "2026-10-10"}

    # Snapshot persisted.
    row = (
        await db_session.execute(
            select(ValuationFairValue).where(ValuationFairValue.company_id == company.id)
        )
    ).scalar_one()
    assert row.profile_key == "banks"
    assert row.fair_value is not None


async def test_missing_dq_degrades_honestly(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "BANKMISS")
    await _add_assessment(
        db_session, company, "financial_statements", Decimal("0"), DataQualityStatusDB.MISSING
    )
    await _add_assessment(
        db_session, company, "price_history", Decimal("80"), DataQualityStatusDB.OK
    )
    await _add_price(db_session, company, Decimal("30"))

    data = (
        await client.get(
            f"/api/valuation/companies/{company.id}/fair-value", params=BANK_PARAMS
        )
    ).json()

    assert data["fair_value"] == {
        "value": None,
        "status": "INSUFFICIENT_DATA",
        "reason": data["fair_value"]["reason"],
    }
    assert "MISSING" in data["fair_value"]["reason"]
    assert data["legs"]["intrinsic"]["status"] == "INSUFFICIENT_DATA"
    assert data["legs"]["intrinsic"]["value"] is None
    assert data["legs"]["fallback"]["status"] == "INSUFFICIENT_DATA"
    # Relative leg still computed: prices are OK.
    assert data["legs"]["relative"]["status"] == "AVAILABLE"
    assert data["confidence"]["level"] == "MISSING"
    assert data["verdict"]["label"] == "INSUFFICIENT_DATA"
    for case in ("bull", "base", "bear"):
        assert data["scenarios"][case]["status"] == "INSUFFICIENT_DATA"
        assert data["scenarios"][case]["value"] is None


async def test_no_dq_row_caps_confidence_poor(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "BANKNODQ")
    await _add_price(db_session, company, Decimal("30"))

    data = (
        await client.get(
            f"/api/valuation/companies/{company.id}/fair-value", params=BANK_PARAMS
        )
    ).json()

    # Computation proceeds (inputs supplied) but confidence is capped.
    assert data["fair_value"]["status"] == "AVAILABLE"
    assert data["confidence"]["level"] == "POOR"
    assert data["confidence"]["required_discount"] == "0.30"


async def test_default_profile_routing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "GENFV", egx_name=None)
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("10"))

    params = {
        "free_cash_flow": "100",
        "growth_rate": "0.08",
        "stable_growth": "0.03",
        "discount_rate": "0.12",
        "terminal_growth_rate": "0.02",
        "shares_outstanding": "50",
        "earnings_per_share": "5",
        "pe_ratio": "10",
        "revenue_growth": "0.08",
        "operating_margin": "0.15",
        "exit_multiple": "12",
    }
    data = (
        await client.get(f"/api/valuation/companies/{company.id}/fair-value", params=params)
    ).json()

    assert data["profile"]["profile_id"] == "default"
    assert data["profile"]["primary_model"] == "fcfe_two_stage"
    assert data["legs"]["intrinsic"]["model"] == "fcfe_two_stage"
    assert data["fair_value"]["status"] == "AVAILABLE"
    assert data["n_with_data"] == 2


async def test_metric_prefill_for_growth_and_margin(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "GENPRE", egx_name=None)
    await _good_dq(db_session, company)
    await _add_metric(db_session, company, "revenue_growth_yoy", Decimal("8.00"))
    await _add_metric(db_session, company, "operating_margin", Decimal("15.00"))

    params = {
        "free_cash_flow": "100",
        "stable_growth": "0.03",
        "discount_rate": "0.12",
        "terminal_growth_rate": "0.02",
        "shares_outstanding": "50",
        "exit_multiple": "12",
    }
    data = (
        await client.get(f"/api/valuation/companies/{company.id}/fair-value", params=params)
    ).json()

    assert data["input_sources"]["revenue_growth"] == "metric:revenue_growth_yoy"
    assert data["input_sources"]["operating_margin"] == "metric:operating_margin"
    assert Decimal(data["inputs"]["resolved_growth_high"]) == Decimal("0.08")
    assert data["legs"]["intrinsic"]["status"] == "AVAILABLE"
    # Scenarios resolve: growth + margin pre-filled, exit caller-supplied.
    assert data["scenarios"]["base"]["status"] == "AVAILABLE"


async def test_snapshot_pinning_determinism_last_writer_wins(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Pin the fair-value snapshot cache: determinism, one-row-per-key, latest-wins."""
    from app.models.valuation import IndustryValuationProfile, ValuationResult

    await _seed(db_session)
    company = await _make_company(db_session, "BANKPIN")
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("30"))
    url = f"/api/valuation/companies/{company.id}/fair-value"
    profiles_before = (
        await db_session.execute(select(IndustryValuationProfile))
    ).scalars().all()

    first = (await client.get(url, params=BANK_PARAMS)).json()
    second = (await client.get(url, params=BANK_PARAMS)).json()
    assert first["fair_value"] == second["fair_value"]
    assert first["fair_value"]["status"] == "AVAILABLE"
    rows = (
        await db_session.execute(
            select(ValuationFairValue)
            .where(ValuationFairValue.company_id == company.id)
            .where(
                ValuationFairValue.methodology_version
                == VALUATION_METHODOLOGY_VERSION
            )
        )
    ).scalars().all()
    assert len(rows) == 1

    altered = dict(BANK_PARAMS)
    altered["exit_multiple"] = "20"
    third = (await client.get(url, params=altered)).json()
    assert third["fair_value"]["status"] == "AVAILABLE"
    assert third["fair_value"]["value"] != first["fair_value"]["value"]
    rows_after = (
        await db_session.execute(
            select(ValuationFairValue)
            .where(ValuationFairValue.company_id == company.id)
            .where(
                ValuationFairValue.methodology_version
                == VALUATION_METHODOLOGY_VERSION
            )
            .execution_options(populate_existing=True)
        )
    ).scalars().all()
    assert len(rows_after) == 1
    row = rows_after[0]
    # Numeric(20, 4) rounds the payload value; compare within rounding.
    assert row.fair_value is not None
    assert abs(Decimal(str(row.fair_value)) - Decimal(third["fair_value"]["value"])) < Decimal(
        "0.0001"
    )
    assert row.legs == third["legs"]
    assert row.weights == third["weights"]
    assert Decimal(row.inputs_echo["inputs"]["exit_multiple"]) == Decimal("20")

    # GET writes only its own domain table: no legacy rows, profiles untouched.
    legacy = (
        await db_session.execute(
            select(ValuationResult).where(ValuationResult.company_id == company.id)
        )
    ).scalars().all()
    assert legacy == []
    profiles_after = (
        await db_session.execute(select(IndustryValuationProfile))
    ).scalars().all()
    assert len(profiles_after) == len(profiles_before)


async def test_existing_get_contract_unchanged(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The live-frontend GET keeps its list shape alongside the sub-resource."""
    await _seed(db_session)
    company = await _make_company(db_session, "BANKOLD")
    response = await client.get(f"/api/valuation/companies/{company.id}")
    assert response.status_code == 200
    assert response.json() == []
