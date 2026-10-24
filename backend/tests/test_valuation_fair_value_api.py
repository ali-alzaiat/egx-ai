"""API tests for GET /api/valuation/companies/{id}/fair-value (additive)."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

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
from app.valuation.assumptions import record_assumption
from app.valuation.constants import VALUATION_METHODOLOGY_VERSION
from app.valuation.seed import seed_valuation_profiles
from app.valuation.service import FairValueInput, FairValueService
from statement_seed import FULL_YEAR, seed_year

AS_OF = date(2026, 10, 10)

BANK_PARAMS = {
    "book_value_per_share": "35.38",
    "stable_roe": "0.098",
    "discount_rate": "0.0761",
    "terminal_growth_rate": "0.02",
    "long_run_cost_of_equity": "0.0761",
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


async def _fv(
    db_session: AsyncSession, company: Company, params: dict[str, str]
) -> dict[str, Any]:
    """Engine call with explicit inputs (R43: the API no longer takes caller inputs)."""
    inputs = FairValueInput(**{k: Decimal(v) for k, v in params.items()})
    return await FairValueService(db_session).compute(company.id, inputs)


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

    data = await _fv(db_session, company, BANK_PARAMS)

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

    # compute() never persists (R43: thesis/stance reruns must not overwrite it).
    rows = (
        await db_session.execute(
            select(ValuationFairValue).where(ValuationFairValue.company_id == company.id)
        )
    ).scalars().all()
    assert rows == []


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

    data = await _fv(db_session, company, BANK_PARAMS)

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

    data = await _fv(db_session, company, BANK_PARAMS)

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
        "long_run_cost_of_equity": "0.10",
        "shares_outstanding": "50",
        "earnings_per_share": "5",
        "pe_ratio": "10",
        "revenue_growth": "0.08",
        "operating_margin": "0.15",
        "exit_multiple": "12",
    }
    data = await _fv(db_session, company, params)

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
        "long_run_cost_of_equity": "0.10",
        "revenue_growth": "0.08",
        "shares_outstanding": "50",
        "exit_multiple": "12",
    }
    data = await _fv(db_session, company, params)

    # F13: stage-1 growth is never the single-year metric; it comes from the caller
    # here (the snapshot path supplies the capped 3-year CAGR).
    assert data["input_sources"]["revenue_growth"] == "input:revenue_growth"
    assert data["input_sources"]["operating_margin"] == "metric:operating_margin FY2024"
    assert Decimal(data["inputs"]["resolved_growth_high"]) == Decimal("0.08")
    assert data["legs"]["intrinsic"]["status"] == "AVAILABLE"
    # Scenarios resolve: growth + margin pre-filled, exit caller-supplied.
    assert data["scenarios"]["base"]["status"] == "AVAILABLE"


async def test_get_computes_snapshot_once_and_names_missing_assumptions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """R43: GET computes from statement lines; no sourced assumption -> legs name it."""
    await _seed(db_session)
    company = await _make_company(db_session, "GENSNAP", egx_name=None)
    await seed_year(db_session, company, 2023, FULL_YEAR)
    await seed_year(db_session, company, 2024, FULL_YEAR)
    await _add_price(db_session, company, Decimal("30"))
    url = f"/api/valuation/companies/{company.id}/fair-value"

    first = (await client.get(url)).json()
    assert first["compute_status"] == "ok"
    assert first["trigger"] == "first_view"
    assert first["provisional"] is True
    assert first["period_end"] == "2024-12-31"
    assert first["fair_value"]["value"] is None
    assert first["fair_value"]["status"] == "INSUFFICIENT_DATA"
    assert "no sourced risk_free_rate" in first["fair_value"]["reason"]
    assert first["legs"]["intrinsic"]["reason"] == (
        "no sourced risk_free_rate, equity_risk_premium, long_run_inflation, "
        "long_run_cost_of_equity, nominal_gdp_growth "
        f"in valuation assumptions {VALUATION_METHODOLOGY_VERSION}"
    )
    assert first["assumptions"]["items"] == []
    assert "target_pe" in first["assumptions"]["missing"]
    # Statement-derived inputs carry provenance strings.
    assert first["inputs"]["earnings_per_share"] == "2"
    assert first["input_sources"]["earnings_per_share"] == (
        "statement:net_income,weighted_avg_shares_basic FY2024 (vendor)"
    )

    second = (await client.get(url)).json()
    assert second["calculated_at"] == first["calculated_at"]
    rows = (
        await db_session.execute(
            select(ValuationFairValue).where(ValuationFairValue.company_id == company.id)
        )
    ).scalars().all()
    assert len(rows) == 1

    # A sourced assumption changes the fingerprint: the next GET recomputes.
    await record_assumption(
        db_session, key="target_pe", scope="market", value=Decimal("10"),
        source_url="https://example.test/pe", source_title="Synthetic test source",
        as_of=date(2026, 1, 1),
    )
    third = (await client.get(url)).json()
    assert third["calculated_at"] != first["calculated_at"]
    assert Decimal(third["legs"]["relative"]["value"]) == Decimal("20")
    assert third["assumptions"]["items"][0]["key"] == "target_pe"
    assert third["input_sources"]["pe_target"] == "assumption:target_pe market as_of 2026-01-01"


async def test_caller_input_routes_removed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The legacy per-model list and the 12-field calculate POST are gone (R43 #1)."""
    await _seed(db_session)
    company = await _make_company(db_session, "BANKOLD")
    assert (await client.get(f"/api/valuation/companies/{company.id}")).status_code == 404
    calc = await client.post(f"/api/valuation/companies/{company.id}/calculate")
    assert calc.status_code in (404, 405)
