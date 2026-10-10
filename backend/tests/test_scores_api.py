"""API tests for GET /api/scores/companies/{id} + assess POST."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

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

GEN_PARAMS = {
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

DPS_10Y = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.0]

BANK_BODY = {
    "pe_ratio": 12.0, "market_pe_avg": 18.0, "industry_pe_avg": 15.0,
    "pb_ratio": 1.2, "industry_pb_avg": 1.8,
    "eps_growth_1y": 0.15, "industry_eps_growth_avg": 0.10,
    "eps_now": 5.0, "eps_5y_ago": 3.0,
    "eps_growth_now": 0.15, "eps_growth_5y_avg": 0.08,
    "roe_now": 0.25, "roce_now": 0.18, "roce_3y_ago": 0.12,
    "roa_now": 0.06, "industry_roa_avg": 0.04,
    "total_assets": 1000.0, "total_equity": 100.0,
    "bank_allowance": 50.0, "bank_npl": 30.0,
    "bank_deposits": 700.0, "bank_total_liabilities": 1200.0,
    "bank_net_loans": 800.0, "bank_net_charge_offs": 5.0, "bank_avg_loans": 500.0,
    "dps_history": DPS_10Y, "earnings_payout": 0.5,
    "hist_earnings_growth": 0.25, "hist_revenue_growth": 0.30,
}

STD_BODY = {
    "pe_ratio": 12.0, "market_pe_avg": 18.0, "industry_pe_avg": 15.0,
    "pb_ratio": 1.2, "industry_pb_avg": 1.8,
    "eps_growth_1y": 0.15, "industry_eps_growth_avg": 0.10,
    "eps_now": 5.0, "eps_5y_ago": 3.0,
    "eps_growth_now": 0.15, "eps_growth_5y_avg": 0.08,
    "roe_now": 0.25, "roce_now": 0.18, "roce_3y_ago": 0.12,
    "roa_now": 0.06, "industry_roa_avg": 0.04,
    "st_assets": 200.0, "st_liabilities": 100.0, "lt_liabilities": 150.0,
    "de_ratio_now": 0.3, "de_ratio_5y_ago": 0.5,
    "operating_cash_flow": 50.0, "total_debt": 100.0,
    "ebit": 100.0, "net_interest_expense": 10.0,
    "dps_history": DPS_10Y, "earnings_payout": 0.5,
    "hist_earnings_growth": 0.25, "hist_revenue_growth": 0.30,
}


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


async def _seed_fair_value(
    client: AsyncClient, company: Company, params: dict[str, str]
) -> dict[str, object]:
    response = await client.get(
        f"/api/valuation/companies/{company.id}/fair-value", params=params
    )
    assert response.status_code == 200
    data = response.json()
    assert data["fair_value"]["status"] == "AVAILABLE"
    return data


async def test_unknown_company_404(client: AsyncClient) -> None:
    assert (await client.get(f"/api/scores/companies/{uuid.uuid4()}")).status_code == 404
    response = await client.post(f"/api/scores/companies/{uuid.uuid4()}/assess", json={})
    assert response.status_code == 404


async def test_get_unassessed_returns_null_assessment(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "SCNOASSESS")
    data = (await client.get(f"/api/scores/companies/{company.id}")).json()
    assert data["company_id"] == str(company.id)
    assert data["ticker"] == "SCNOASSESS"
    assert data["assessment"] is None
    assert data["methodology_version"] == SCORE_METHODOLOGY_VERSION


async def test_bank_happy_path(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "SCBANK")
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("30"))
    await _seed_fair_value(client, company, BANK_PARAMS)

    response = await client.post(
        f"/api/scores/companies/{company.id}/assess", json=BANK_BODY
    )
    assert response.status_code == 200
    data = response.json()

    assert data["company_id"] == str(company.id)
    assert data["ticker"] == "SCBANK"
    assert data["methodology_version"] == SCORE_METHODOLOGY_VERSION
    assert data["profile"] == {
        "profile_id": "banks",
        "methodology_version": SCORE_METHODOLOGY_VERSION,
        "health_track": "banks",
    }
    assert data["headline"]["status"] == "AVAILABLE"
    assert data["headline"]["value"] == 100.0
    assert "under these assumptions" in data["headline"]["detail"]
    assert set(data["components"]) == {"value", "past", "health", "dividend", "growth"}
    for comp in data["components"].values():
        assert comp["status"] == "AVAILABLE"
        assert comp["score"] == 100.0
    assert data["checks_not_run"] == []
    assert data["n_with_data"] == 23
    assert data["n_checks_total"] == 23
    assert data["confidence"]["level"] == "VeryHigh"
    assert data["buy_zone"]["status"] == "AVAILABLE"
    assert data["buy_zone"]["in_buy_zone"] is True
    assert data["buy_zone"]["margin_of_safety"] == "0.20"
    assert data["scale"].startswith("0-100")
    assert "not a recommendation" in data["disclaimer"]
    assert data["inputs_echo"]["sources"]["fair_value"] is not None
    assert data["inputs_echo"]["sources"]["price_as_of"] == "2026-10-10"

    row = (
        await db_session.execute(
            select(InvestmentScore).where(InvestmentScore.company_id == company.id)
        )
    ).scalar_one()
    assert row.profile_key == "banks"
    assert row.methodology_version == SCORE_METHODOLOGY_VERSION
    assert row.headline is not None and float(row.headline) == 100.0

    # GET reads the snapshot back under the same methodology version.
    got = (await client.get(f"/api/scores/companies/{company.id}")).json()
    assert got["assessment"] is not None
    assert got["assessment"]["headline"]["value"] == 100.0
    assert got["assessment"]["n_with_data"] == 23


async def test_standard_track_routing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "SCGEN", egx_name=None)
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("10"))
    await _seed_fair_value(client, company, GEN_PARAMS)

    data = (
        await client.post(f"/api/scores/companies/{company.id}/assess", json=STD_BODY)
    ).json()

    assert data["profile"]["profile_id"] == "default"
    assert data["profile"]["health_track"] == "standard"
    assert data["headline"]["value"] == 100.0
    keys = {c["check_key"] for c in data["checks"]}
    assert "health_liquidity_st" in keys
    assert not any(k.startswith("bank_") for k in keys)


async def test_empty_inputs_degrade_to_null_headline(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "SCEMPTY", egx_name=None)

    data = (await client.post(f"/api/scores/companies/{company.id}/assess", json={})).json()

    assert data["headline"] == {
        "value": None,
        "status": "INSUFFICIENT_DATA",
        "reason": data["headline"]["reason"],
        "detail": data["headline"]["detail"],
    }
    assert "INSUFFICIENT_DATA" in data["headline"]["reason"]
    for comp in data["components"].values():
        assert comp["status"] == "INSUFFICIENT_DATA"
        assert comp["score"] is None
    # No DQ on file caps confidence at Low without failing the run.
    assert data["confidence"]["level"] == "Low"
    assert data["buy_zone"]["status"] == "INSUFFICIENT_DATA"


async def test_missing_dq_scope_caps_confidence_not_score(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "SCMISSINGDQ")
    await _add_assessment(
        db_session, company, "financial_statements", Decimal("0"), DataQualityStatusDB.MISSING
    )
    await _add_assessment(
        db_session, company, "price_history", Decimal("80"), DataQualityStatusDB.OK
    )
    await _add_price(db_session, company, Decimal("30"))
    # Phase-3 nulls the headline FV when filings DQ is MISSING (relative leg
    # alone never becomes a fair value); the snapshot row is still written.
    missing_fv = await client.get(
        f"/api/valuation/companies/{company.id}/fair-value", params=BANK_PARAMS
    )
    assert missing_fv.json()["fair_value"]["status"] == "INSUFFICIENT_DATA"

    data = (
        await client.post(f"/api/scores/companies/{company.id}/assess", json=BANK_BODY)
    ).json()

    # The FV check degrades to not-run; every other component still scores.
    assert "value_fv_discount" in data["checks_not_run"]
    assert data["components"]["value"]["status"] == "AVAILABLE"
    assert data["headline"]["status"] == "AVAILABLE"
    assert data["confidence"]["level"] == "Low"
    assert "MISSING" in data["confidence"]["reason"]


async def test_margin_of_safety_validation_and_zero(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "SCMOS")
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("30"))
    await _seed_fair_value(client, company, BANK_PARAMS)

    bad = await client.post(
        f"/api/scores/companies/{company.id}/assess",
        json={**BANK_BODY, "margin_of_safety": 1.5},
    )
    assert bad.status_code == 400

    zero = (
        await client.post(
            f"/api/scores/companies/{company.id}/assess",
            json={**BANK_BODY, "margin_of_safety": 0.0},
        )
    ).json()
    assert zero["buy_zone"]["margin_of_safety"] == "0.0"
    # A zero margin never moves the score.
    assert zero["headline"]["value"] == 100.0


async def test_snapshot_last_writer_wins(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "SCPIN")
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("30"))
    await _seed_fair_value(client, company, BANK_PARAMS)
    url = f"/api/scores/companies/{company.id}/assess"

    first = (await client.post(url, json=BANK_BODY)).json()
    assert first["headline"]["value"] == 100.0

    weaker = dict(BANK_BODY)
    weaker["earnings_payout"] = 0.95  # breaks dividend coverage: 2/3 pass
    second = (await client.post(url, json=weaker)).json()
    assert second["headline"]["value"] != first["headline"]["value"]
    assert second["components"]["dividend"]["score"] == round(2 / 3 * 100, 1)

    rows = (
        await db_session.execute(
            select(InvestmentScore)
            .where(InvestmentScore.company_id == company.id)
            .where(InvestmentScore.methodology_version == SCORE_METHODOLOGY_VERSION)
            .execution_options(populate_existing=True)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].inputs_echo["inputs"]["earnings_payout"] == "0.95"
    assert float(str(rows[0].headline)) == float(second["headline"]["value"])


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

    # A stale-version row is invisible to reads.
    got = (await client.get(f"/api/scores/companies/{company.id}")).json()
    assert got["assessment"] is None

    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("10"))
    await _seed_fair_value(client, company, GEN_PARAMS)
    await client.post(f"/api/scores/companies/{company.id}/assess", json=STD_BODY)
    versions = (
        await db_session.execute(
            select(InvestmentScore.methodology_version).where(
                InvestmentScore.company_id == company.id
            )
        )
    ).scalars().all()
    assert sorted(versions) == ["0.9", SCORE_METHODOLOGY_VERSION]


async def test_post_get_round_trip_parity(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """POST→GET round-trip: headline, health_track, ticker, value types agree."""
    await _seed(db_session)
    company = await _make_company(db_session, "SCROUNDTRIP")
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("30"))
    await _seed_fair_value(client, company, BANK_PARAMS)

    post = (
        await client.post(f"/api/scores/companies/{company.id}/assess", json=BANK_BODY)
    ).json()
    assessment = (
        await client.get(f"/api/scores/companies/{company.id}")
    ).json()["assessment"]
    assert assessment is not None
    assert assessment["ticker"] == post["ticker"] == "SCROUNDTRIP"
    assert assessment["headline"]["value"] == post["headline"]["value"]
    assert assessment["headline"]["status"] == post["headline"]["status"]
    assert assessment["headline"]["reason"] == post["headline"]["reason"]
    assert "under these assumptions" not in assessment["headline"]["reason"]
    assert (
        assessment["profile"]["health_track"]
        == post["profile"]["health_track"]
        == "banks"
    )
    assert isinstance(post["headline"]["value"], float)
    assert isinstance(assessment["headline"]["value"], float)
    for comp in assessment["components"].values():
        assert comp["score"] is None or isinstance(comp["score"], (int, float))

    # Null-headline path: reason still survives the round trip.
    thin = await _make_company(db_session, "SCROUNDTRIPTHIN", egx_name=None)
    thin_post = (
        await client.post(f"/api/scores/companies/{thin.id}/assess", json={})
    ).json()
    thin_get = (await client.get(f"/api/scores/companies/{thin.id}")).json()[
        "assessment"
    ]
    assert thin_get is not None
    assert thin_get["ticker"] == thin_post["ticker"] == "SCROUNDTRIPTHIN"
    assert thin_get["headline"]["value"] is None
    assert thin_get["headline"]["status"] == "INSUFFICIENT_DATA"
    assert thin_get["headline"]["reason"] == thin_post["headline"]["reason"]
    assert "INSUFFICIENT_DATA" in thin_get["headline"]["reason"]
    assert (
        thin_get["profile"]["health_track"]
        == thin_post["profile"]["health_track"]
        == "standard"
    )


async def test_get_is_read_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "SCREADONLY")
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("30"))
    await _seed_fair_value(client, company, BANK_PARAMS)
    await client.post(f"/api/scores/companies/{company.id}/assess", json=BANK_BODY)

    async def count() -> int:
        result = await db_session.execute(
            select(func.count()).select_from(InvestmentScore)
        )
        return result.scalar_one()

    before = await count()
    await client.get(f"/api/scores/companies/{company.id}")
    assert await count() == before


async def test_metric_sourced_inputs_cited(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "SCMETRIC", egx_name=None)
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("10"))
    await _seed_fair_value(client, company, GEN_PARAMS)
    await _add_metric(db_session, company, "roe", Decimal("25.00"))
    await _add_metric(db_session, company, "eps_growth_yoy", Decimal("30.00"))
    await _add_metric(db_session, company, "revenue_growth_yoy", Decimal("25.00"))
    await _add_metric(db_session, company, "debt_to_equity", Decimal("0.30"), unit="ratio")

    body = dict(STD_BODY)
    for key in ("roe_now", "de_ratio_now", "hist_earnings_growth", "hist_revenue_growth",
                "eps_growth_1y", "eps_growth_now"):
        body.pop(key)
    data = (
        await client.post(f"/api/scores/companies/{company.id}/assess", json=body)
    ).json()

    echo = data["inputs_echo"]["inputs"]
    assert echo["roe_now"] == "0.2500"
    assert echo["de_ratio_now"] == "0.3000"
    assert echo["hist_earnings_growth"] == "0.3000"
    assert echo["hist_revenue_growth"] == "0.2500"
    assert data["inputs_echo"]["sources"]["metrics_used"]["roe"] == "25.0000"
    assert data["headline"]["value"] == 100.0
