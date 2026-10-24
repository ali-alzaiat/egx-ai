"""API tests for GET /api/scores/companies/{id} (R43: computed on read)."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dataquality.scores import METHODOLOGY_VERSION as DQ_VERSION
from app.industry.seed import seed_industry_taxonomy
from app.models.data_quality import DataQualityAssessment, DataQualityStatusDB
from app.models.financial import FinancialPeriod
from app.models.industry import EgxSector
from app.models.market import Company, CompanyStatus, DailyPrice, DataSource, DataSourceType
from app.models.metrics import FinancialMetric, MetricStatusDB
from app.models.scores import InvestmentScore
from app.scores.constants import SCORE_METHODOLOGY_VERSION
from app.scores.seed import seed_score_profiles
from app.valuation.seed import seed_valuation_profiles
from statement_seed import FULL_YEAR, seed_prices, seed_year

AS_OF = date(2026, 10, 10)







async def _seed(db_session: AsyncSession) -> None:
    await seed_industry_taxonomy(db_session, as_of=AS_OF)
    await seed_valuation_profiles(db_session)
    first = await seed_score_profiles(db_session)
    second = await seed_score_profiles(db_session)
    assert second["profiles_added"] == 0
    assert first["profiles_total"] == 2


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


async def _good_dq(db_session: AsyncSession, company: Company) -> None:
    await _add_assessment(
        db_session, company, "financial_statements", Decimal("85"), DataQualityStatusDB.OK
    )
    await _add_assessment(
        db_session, company, "price_history", Decimal("80"), DataQualityStatusDB.OK
    )


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
    db_session: AsyncSession, company: Company, code: str, value: Decimal, unit: str = "%"
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
            unit=unit,
            status=MetricStatusDB.AVAILABLE,
            reason=None,
            warnings=None,
            formula_version=1,
            calculated_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
    )
    await db_session.flush()


async def _seed_history(db_session: AsyncSession, company: Company) -> None:
    """Six synthetic years (FY2019..FY2024) with growing earnings, plus prices."""
    for i, year in enumerate(range(2019, 2025)):
        values = dict(FULL_YEAR)
        values["net_income"] = Decimal(100 + 20 * i)
        values["revenue"] = Decimal(800 + 40 * i)
        await seed_year(db_session, company, year, values)
    await seed_prices(db_session, company, bars=30, start=Decimal("10"))


async def test_unknown_company_404(client: AsyncClient) -> None:
    assert (await client.get(f"/api/scores/companies/{uuid.uuid4()}")).status_code == 404


async def test_assess_route_removed(client: AsyncClient, db_session: AsyncSession) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "SCNOPOST", egx_name=None)
    response = await client.post(f"/api/scores/companies/{company.id}/assess", json={})
    assert response.status_code in (404, 405)


async def test_known_company_always_gets_an_assessment(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-7: no ``assessment: null`` for a known company; gaps are INSUFFICIENT."""
    await _seed(db_session)
    company = await _make_company(db_session, "SCEMPTY", egx_name=None)
    data = (await client.get(f"/api/scores/companies/{company.id}")).json()
    assert data["compute_status"] == "ok"
    assert data["trigger"] == "first_view"
    assert data["assessment"] is not None
    assert data["assessment"]["headline"]["value"] is None
    assert data["assessment"]["headline"]["status"] == "INSUFFICIENT_DATA"


async def test_statement_inputs_resolve_and_are_cited(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "SCLINES", egx_name=None)
    await _seed_history(db_session, company)

    data = (await client.get(f"/api/scores/companies/{company.id}")).json()
    assessment = data["assessment"]
    inputs = assessment["inputs_echo"]["inputs"]
    # FY2024: net income 200 / 100 weighted shares; FY2019: 100 / 100.
    assert Decimal(inputs["eps_now"]) == Decimal("2")
    assert Decimal(inputs["eps_5y_ago"]) == Decimal("1")
    assert Decimal(inputs["st_assets"]) == Decimal("800")
    assert Decimal(inputs["lt_liabilities"]) == Decimal("500")  # 900 - 400
    assert Decimal(inputs["total_debt"]) == Decimal("500")
    assert Decimal(inputs["operating_cash_flow"]) == Decimal("300")
    # R45 M4: the derived paid DPS never feeds the history checks.
    assert inputs["dps_history"] == []
    assert inputs["dividend_years"] is None
    # cash paid / EPS of the same year: 0.8 / 2 (ANALYST GATE D-6, labelled).
    assert Decimal(inputs["earnings_payout"]) == Decimal("0.4")
    assert inputs["pe_ratio"] is not None
    assert inputs["eps_growth_5y_avg"] is not None
    sources = assessment["inputs_echo"]["sources"]
    assert sources["dps_label"] == "cash dividends paid per share (derived)"
    assert sources["earnings_payout_basis"] == "cash dividends paid / EPS (same fiscal year)"
    assert sources["statement_period_end"] == "2024-12-31"
    assert isinstance(sources["statement_age_days"], int)
    assert "latest annual" in sources["pe_pb_basis"]
    assert sources["statements"], "every statement line used is cited"
    assert all(item["provisional"] is True for item in sources["statements"])
    assert data["provisional"] is True
    assert data["source_tier"] == "vendor"
    assert data["period_end"] == "2024-12-31"
    components = assessment["components"]
    assert components["health"]["ran"] >= 3
    assert components["past"]["ran"] >= 3
    dividend = {c["check_key"]: c for c in components["dividend"]["checks"]}
    for key in ("dividend_stability", "dividend_growing"):
        assert dividend[key]["status"] == "NOT_RUN", key
        assert "declared-DPS" in dividend[key]["reason"], key
    coverage = dividend["dividend_earnings_coverage"]
    assert coverage["status"] == "PASS"
    assert coverage["inputs"]["basis"] == "cash dividends paid / EPS (same fiscal year)"
    assert "Cash paid / EPS" in coverage["reason"]


async def test_second_get_does_not_recompute(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-7: a GET with no new inputs serves the snapshot (no new writes)."""
    await _seed(db_session)
    company = await _make_company(db_session, "SCFRESH", egx_name=None)
    await _seed_history(db_session, company)
    url = f"/api/scores/companies/{company.id}"
    first = (await client.get(url)).json()
    second = (await client.get(url)).json()
    assert second["calculated_at"] == first["calculated_at"]
    assert second["assessment"]["computed_at"] == first["assessment"]["computed_at"]
    count = (
        await db_session.execute(
            select(func.count())
            .select_from(InvestmentScore)
            .where(InvestmentScore.company_id == company.id)
        )
    ).scalar_one()
    assert count == 1


async def test_compute_failure_is_200_with_failed_status(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.scores.service import ScoreService

    async def boom(_self: Any, _company_id: uuid.UUID, *_a: Any, **_k: Any) -> Any:
        raise RuntimeError("simulated score failure")

    monkeypatch.setattr(ScoreService, "assess", boom)
    await _seed(db_session)
    company = await _make_company(db_session, "SCFAIL", egx_name=None)
    response = await client.get(f"/api/scores/companies/{company.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["compute_status"] == "failed"
    assert data["compute_error"] == "RuntimeError: simulated score failure"
    assert data["assessment"] is None


async def test_reads_filter_by_methodology_version(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "SCVERSION")
    db_session.add(
        InvestmentScore(
            id=uuid.uuid4(),
            company_id=company.id,
            profile_key="default",
            methodology_version="0.9",
            headline=None,
            headline_status="INSUFFICIENT_DATA",
            components={},
            checks=[],
            confidence={},
            buy_zone={},
            n_with_data=0,
            margin_of_safety=Decimal("0.2"),
            inputs_echo={},
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    got = (await client.get(f"/api/scores/companies/{company.id}")).json()
    assert got["assessment"]["methodology_version"] == SCORE_METHODOLOGY_VERSION
    versions = (
        await db_session.execute(
            select(InvestmentScore.methodology_version).where(
                InvestmentScore.company_id == company.id
            )
        )
    ).scalars().all()
    assert sorted(versions) == ["0.9", SCORE_METHODOLOGY_VERSION]
