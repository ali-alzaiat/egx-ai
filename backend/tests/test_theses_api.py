"""API tests for GET /api/theses/companies/{id} + assess/update POSTs."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dataquality.scores import METHODOLOGY_VERSION as DQ_VERSION
from app.industry.seed import seed_industry_taxonomy
from app.models.data_quality import DataQualityAssessment, DataQualityStatusDB
from app.models.financial import FinancialPeriod
from app.models.market import Company, CompanyStatus, DailyPrice, DataSource, DataSourceType
from app.models.metrics import FinancialMetric, MetricStatusDB
from app.models.scores import InvestmentScore
from app.models.thesis import (
    InvestmentThesis,
)
from app.thesis.constants import DEFAULT_HORIZON_YEARS, THESIS_METHODOLOGY_VERSION
from app.valuation.seed import seed_valuation_profiles
from statement_seed import FULL_YEAR, seed_prices, seed_year

AS_OF = date(2026, 10, 10)

GEN_LEGS = {
    "free_cash_flow": 100.0,
    "stable_growth": 0.03,
    "discount_rate": 0.12,
    "terminal_growth_rate": 0.02,
    "shares_outstanding": 50.0,
    "earnings_per_share": 5.0,
    "revenue_growth": 0.08,
    "operating_margin": 0.15,
    "exit_multiple": 12.0,
}

BULLS = ["Ecosystem lock-in", "In-house chips", "Balance sheet buybacks"]
BEARS = ["Consumer cyclicality", "Supply concentration", "Regulation risk"]

ASSUMPTIONS = [
    {
        "metric": "revenue",
        "value": "8%/yr",
        "horizon": "5 years",
        "source": "https://www.egx.com.eg/filing.pdf",
        "author": "caller",
    },
    {
        "metric": "net_margin",
        "value": None,
        "horizon": "5 years",
        "source": "https://www.egx.com.eg/filing.pdf",
        "author": "caller",
    },
]

INVALIDATIONS = [
    {
        "metric": "revenue_growth_yoy",
        "threshold": 0.0,
        "direction": "below",
        "period": "two consecutive quarters",
        "evidence_source": "quarterly_financial_statements",
    },
    {
        "metric": "roe",
        "threshold": 0.0,
        "direction": "below",
        "period": "annual",
        "evidence_source": "annual_financial_statements",
    },
]

CALLER_CATALYST = {
    "event": "Q2 2026 results release",
    "window": "quarterly",
    "variable": "earnings_power",
    "expectation": "Revenue growth holds above zero",
    "outcome": "Pending",
    "provenance": "https://www.egx.com.eg/disclosure.pdf",
    "label": "Confirmed",
}


def _body(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        **GEN_LEGS,
        "horizon_years": 5,
        "is_shareholder": True,
        "assumptions": ASSUMPTIONS,
        "bulls": BULLS,
        "bears": BEARS,
        "invalidations": INVALIDATIONS,
        "catalysts": [CALLER_CATALYST],
    }
    base.update(overrides)
    return base


async def _seed(db_session: AsyncSession) -> None:
    await seed_industry_taxonomy(db_session, as_of=AS_OF)
    await seed_valuation_profiles(db_session)


async def _make_company(db_session: AsyncSession, ticker: str) -> Company:
    company = Company(
        id=uuid.uuid4(),
        ticker=ticker,
        isin=f"EG{uuid.uuid4().hex[:10].upper()}",
        name=f"{ticker} Company",
        currency="EGP",
        status=CompanyStatus.ACTIVE,
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


async def _add_score_row(db_session: AsyncSession, company: Company) -> None:
    db_session.add(
        InvestmentScore(
            id=uuid.uuid4(),
            company_id=company.id,
            profile_key="default",
            methodology_version="1.0",
            headline=Decimal("80"),
            headline_status="AVAILABLE",
            components={},
            checks=[],
            confidence={"level": "High"},
            buy_zone={},
            n_with_data=10,
            margin_of_safety=Decimal("0.2"),
            inputs_echo={},
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.flush()


async def _seed_lines(db_session: AsyncSession, company: Company) -> None:
    for year, ni in ((2023, Decimal("180")), (2024, Decimal("200"))):
        values = dict(FULL_YEAR)
        values["net_income"] = ni
        await seed_year(db_session, company, year, values)
    await seed_prices(db_session, company, bars=30)


async def test_unknown_company_404(client: AsyncClient) -> None:
    missing = uuid.uuid4()
    assert (await client.get(f"/api/theses/companies/{missing}")).status_code == 404
    assert (
        await client.post(f"/api/theses/companies/{missing}/update", json={"rationale": "x"})
    ).status_code == 404


async def test_assess_route_removed(client: AsyncClient, db_session: AsyncSession) -> None:
    company = await _make_company(db_session, "THNOPOST")
    response = await client.post(f"/api/theses/companies/{company.id}/assess", json={})
    assert response.status_code in (404, 405)


async def test_get_auto_assesses_with_methodology_default_horizon(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-7: never ``assessment: null`` for a known company."""
    await _seed(db_session)
    company = await _make_company(db_session, "THAUTO")
    await _seed_lines(db_session, company)
    data = (await client.get(f"/api/theses/companies/{company.id}")).json()
    assert data["compute_status"] == "ok"
    assert data["trigger"] == "first_view"
    assessment = data["assessment"]
    assert assessment is not None
    assert assessment["header"]["horizon_years"] == DEFAULT_HORIZON_YEARS
    assert assessment["header"]["is_shareholder"] is None
    assert assessment["horizon_source"] == "methodology_default"
    assert len(assessment["invalidations"]) >= 2  # methodology-default padding
    assert len(assessment["ledger"]) == 1
    assert assessment["ledger"][0]["rationale"].startswith(
        "Automatic recompute (first_view): Thesis assessed"
    )


async def test_second_get_does_not_append_ledger(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "THFRESH")
    await _seed_lines(db_session, company)
    url = f"/api/theses/companies/{company.id}"
    first = (await client.get(url)).json()
    second = (await client.get(url)).json()
    assert second["calculated_at"] == first["calculated_at"]
    assert len(second["assessment"]["ledger"]) == 1
    rows = (
        await db_session.execute(
            select(func.count())
            .select_from(InvestmentThesis)
            .where(InvestmentThesis.company_id == company.id)
            .where(InvestmentThesis.methodology_version == THESIS_METHODOLOGY_VERSION)
        )
    ).scalar_one()
    assert rows == 1


async def test_auto_reassess_keeps_documented_update(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """An automatic re-assess never erases what an admin documented update wrote."""
    await _seed(db_session)
    company = await _make_company(db_session, "THKEEP")
    await _seed_lines(db_session, company)
    url = f"/api/theses/companies/{company.id}"
    assessed = (await client.get(url)).json()["assessment"]
    metric = assessed["invalidations"][0]["metric"]
    catalyst = assessed["catalysts"][0]

    updated = (
        await client.post(
            f"{url}/update",
            json={
                "rationale": "Reviewed the filing; documented.",
                "classification": "Confirmed",
                "invalidations": [{"metric": metric, "status": "Reassessed"}],
                "catalysts": [{"catalyst_id": catalyst["id"], "outcome": "Hit"}],
            },
        )
    ).json()
    assert {i["metric"]: i for i in updated["invalidations"]}[metric]["status"] == "Reassessed"
    ledger_after_update = len(updated["ledger"])

    # New statement input -> the next GET re-assesses automatically.
    await seed_year(db_session, company, 2024, {"inventory": Decimal("90")}, tier="filing")
    again = (await client.get(url)).json()
    assert again["calculated_at"] != assessed["computed_at"]
    keep = again["assessment"]
    assert {i["metric"]: i for i in keep["invalidations"]}[metric]["status"] == "Reassessed"
    assert {c["event"]: c for c in keep["catalysts"]}[catalyst["event"]]["outcome"] == "Hit"
    assert len(keep["ledger"]) == ledger_after_update + 1


async def test_fair_value_snapshot_not_overwritten_by_thesis(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Per-scenario sensitivity reruns use compute(); the stored snapshot stays put."""
    from app.models.valuation import ValuationFairValue

    await _seed(db_session)
    company = await _make_company(db_session, "THFVKEEP")
    await _seed_lines(db_session, company)
    await client.get(f"/api/valuation/companies/{company.id}/fair-value")
    before = (
        await db_session.execute(
            select(ValuationFairValue.computed_at, ValuationFairValue.inputs_echo).where(
                ValuationFairValue.company_id == company.id
            )
        )
    ).one()
    await client.get(f"/api/theses/companies/{company.id}")
    after = (
        await db_session.execute(
            select(ValuationFairValue.computed_at, ValuationFairValue.inputs_echo).where(
                ValuationFairValue.company_id == company.id
            )
        )
    ).one()
    assert after == before


async def test_update_validation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "THUPDVAL")
    await client.get(f"/api/theses/companies/{company.id}")

    no_rationale = await client.post(
        f"/api/theses/companies/{company.id}/update",
        json={"rationale": "  ", "invalidations": []},
    )
    assert no_rationale.status_code == 400

    unknown_metric = await client.post(
        f"/api/theses/companies/{company.id}/update",
        json={
            "rationale": "documented",
            "invalidations": [{"metric": "nope", "status": "Reassessed"}],
        },
    )
    assert unknown_metric.status_code == 400

    bad_catalyst = await client.post(
        f"/api/theses/companies/{company.id}/update",
        json={
            "rationale": "documented",
            "catalysts": [{"catalyst_id": str(uuid.uuid4()), "outcome": "Hit"}],
        },
    )
    assert bad_catalyst.status_code == 400

    fresh = await _make_company(db_session, "THUPDNONE")
    assert (
        await client.post(
            f"/api/theses/companies/{fresh.id}/update",
            json={"rationale": "documented"},
        )
    ).status_code == 404


async def test_service_assess_validation(db_session: AsyncSession) -> None:
    """Carried-over rows still pass the assess validation gates."""
    from fastapi import HTTPException

    from app.thesis.service import AssessInput, ThesisService

    await _seed(db_session)
    company = await _make_company(db_session, "THVAL")
    service = ThesisService(db_session)

    def body(**kw: object) -> AssessInput:
        base: dict[str, object] = {
            "horizon_years": DEFAULT_HORIZON_YEARS,
            "is_shareholder": None,
            "assumptions": [],
            "bulls": [],
            "bears": [],
            "invalidations": [],
            "catalysts": [],
        }
        base.update(kw)
        return AssessInput(**base)  # type: ignore[arg-type]

    with pytest.raises(HTTPException) as horizon:
        await service.assess(company.id, body(horizon_years=0))
    assert horizon.value.status_code == 400
    with pytest.raises(HTTPException) as bulls:
        await service.assess(company.id, body(bulls=["a", "b", "c", "d"]))
    assert bulls.value.status_code == 400
