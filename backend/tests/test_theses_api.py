"""API tests for GET /api/theses/companies/{id} + assess/update POSTs."""

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
from app.models.market import Company, CompanyStatus, DailyPrice, DataSource, DataSourceType
from app.models.metrics import FinancialMetric, MetricStatusDB
from app.models.scores import InvestmentScore
from app.models.thesis import (
    InvestmentThesis,
    ThesisCatalyst,
    ThesisInvalidation,
    ThesisLedger,
)
from app.thesis.constants import THESIS_METHODOLOGY_VERSION
from app.valuation.seed import seed_valuation_profiles

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


async def test_unknown_company_404(client: AsyncClient) -> None:
    missing = uuid.uuid4()
    assert (await client.get(f"/api/theses/companies/{missing}")).status_code == 404
    assert (
        await client.post(f"/api/theses/companies/{missing}/assess", json={})
    ).status_code == 404
    assert (
        await client.post(
            f"/api/theses/companies/{missing}/update", json={"rationale": "x"}
        )
    ).status_code == 404


async def test_get_unassessed_returns_null_assessment(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "THNOASSESS")
    data = (await client.get(f"/api/theses/companies/{company.id}")).json()
    assert data["company_id"] == str(company.id)
    assert data["ticker"] == "THNOASSESS"
    assert data["assessment"] is None
    assert data["methodology_version"] == THESIS_METHODOLOGY_VERSION


async def test_happy_path_assess(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "THHAPPY")
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("30"))
    await _add_metric(db_session, company, "revenue_growth_yoy", Decimal("8.00"))
    await _add_metric(db_session, company, "operating_margin", Decimal("15.00"))
    await _add_metric(db_session, company, "roe", Decimal("25.00"))
    await _add_score_row(db_session, company)

    response = await client.post(
        f"/api/theses/companies/{company.id}/assess", json=_body()
    )
    assert response.status_code == 200
    data = response.json()

    assert data["company_id"] == str(company.id)
    assert data["ticker"] == "THHAPPY"
    assert data["methodology_version"] == THESIS_METHODOLOGY_VERSION
    assert data["valuation_methodology_version"] == "1.0"
    assert data["header"]["horizon_years"] == 5
    assert data["header"]["is_shareholder"] is True
    assert data["header"]["fair_value"]["status"] == "AVAILABLE"
    assert Decimal(data["header"]["fair_value"]["value"]) > 0

    scenarios = data["scenarios"]
    for name in ("bear", "base", "bull"):
        assert scenarios[name]["status"] == "AVAILABLE"
        assert set(scenarios[name]["inputs"]) == {
            "revenue_growth",
            "operating_margin",
            "exit_multiple",
        }
        assert Decimal(scenarios[name]["value"]) > 0
    assert "range" in scenarios["note"]
    assert scenarios["prefill_source"]["revenue_growth"] == "caller"
    assert scenarios["methodology_version"] == "1.0"

    sensitivity = data["sensitivity"]
    for name in ("bear", "base", "bull"):
        entry = sensitivity[name]
        assert entry["status"] == "AVAILABLE"
        assert len(entry["rows"]) == 8
        discount_fvs = [
            Decimal(row["fair_value"])
            for row in entry["rows"]
            if row["parameter"] == "discount_rate"
        ]
        growth_fvs = [
            Decimal(row["fair_value"])
            for row in entry["rows"]
            if row["parameter"] == "revenue_growth"
        ]
        assert len(discount_fvs) == 4 and len(growth_fvs) == 4
        assert all(fv > 0 for fv in discount_fvs + growth_fvs)
        # 1-D monotonicity within one scenario: dearer discount lowers FV,
        # richer growth raises it (Phase-3 pipeline property, reused).
        assert discount_fvs == sorted(discount_fvs, reverse=True)
        assert growth_fvs == sorted(growth_fvs)

    assert len(data["invalidations"]) == 2
    for inv in data["invalidations"]:
        assert inv["status"] == "Active"
        assert inv["action"] == "documented_reassessment"
        assert inv["methodology_version"] == THESIS_METHODOLOGY_VERSION
        assert inv["extraction_confidence"] == "High"
        assert inv["version"] == 1

    assert len(data["ledger"]) >= 1
    assert data["ledger"][0]["classification"] == "New"
    assert data["ledger"][0]["action"] == "assessed"
    assert data["ledger"][0]["methodology_version"] == THESIS_METHODOLOGY_VERSION

    assert len(data["catalysts"]) == 6
    for cat in data["catalysts"]:
        assert cat["provenance"].startswith("http")
        assert cat["label"] in ("Confirmed", "Tentative")
        assert cat["methodology_version"] == THESIS_METHODOLOGY_VERSION
    caller_rows = [c for c in data["catalysts"] if c["event"] == "Q2 2026 results release"]
    assert len(caller_rows) == 1 and caller_rows[0]["label"] == "Confirmed"
    skeleton_rows = [c for c in data["catalysts"] if c["event"] != "Q2 2026 results release"]
    assert all(c["label"] == "Tentative" for c in skeleton_rows)

    assert data["needs_reassessment"] is False
    assert data["confidence"]["level"] == "VeryHigh"
    assert data["score"]["headline"]["value"] == 80.0
    assert data["dq"]["financial_statements"]["score"] == 85.0
    assert "Investment thesis for THHAPPY" in data["narrative"]
    assert "documented_reassessment" in data["narrative"]
    assert "not a recommendation" in data["disclaimer"]
    assert len(data["assumptions"]) == 2

    row = (
        await db_session.execute(
            select(InvestmentThesis).where(InvestmentThesis.company_id == company.id)
        )
    ).scalar_one()
    assert row.methodology_version == THESIS_METHODOLOGY_VERSION
    assert row.needs_reassessment is False


async def test_history_anchored_scenarios_without_caller_tikr(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "THHIST")
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("30"))
    await _add_metric(db_session, company, "revenue_growth_yoy", Decimal("8.00"))
    await _add_metric(db_session, company, "operating_margin", Decimal("15.00"))

    body = _body(
        assumptions=[],
        bulls=[],
        bears=[],
        invalidations=[],
        catalysts=[],
    )
    for key in ("revenue_growth", "operating_margin"):
        body.pop(key)
    data = (
        await client.post(f"/api/theses/companies/{company.id}/assess", json=body)
    ).json()

    scenarios = data["scenarios"]
    for name in ("bear", "base", "bull"):
        assert scenarios[name]["status"] == "AVAILABLE"
    assert scenarios["prefill_source"]["revenue_growth"] == "metric:revenue_growth_yoy"
    assert scenarios["prefill_source"]["operating_margin"] == "metric:operating_margin"
    # No caller invalidations: methodology defaults pad to the 2-minimum.
    assert len(data["invalidations"]) == 2
    # No caller catalysts: skeleton only.
    assert len(data["catalysts"]) == 5
    # Missing bull/bear slots stay explicit.
    assert "INSUFFICIENT_DATA: no case supplied" in data["narrative"]


async def test_missing_dq_degrades_honestly(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "THMISSING")
    await _add_assessment(
        db_session, company, "financial_statements", Decimal("0"), DataQualityStatusDB.MISSING
    )
    await _add_assessment(
        db_session, company, "price_history", Decimal("80"), DataQualityStatusDB.OK
    )
    await _add_price(db_session, company, Decimal("30"))

    data = (
        await client.post(f"/api/theses/companies/{company.id}/assess", json={})
    ).json()

    assert data["header"]["fair_value"] == {"value": None, "status": "INSUFFICIENT_DATA"}
    for name in ("bear", "base", "bull"):
        assert data["scenarios"][name]["status"] == "INSUFFICIENT_DATA"
        assert data["sensitivity"][name]["status"] == "INSUFFICIENT_DATA"
    assert data["confidence"]["level"] == "MISSING"
    assert data["score"] is None
    assert len(data["catalysts"]) == 5
    for inv in data["invalidations"]:
        assert inv["status"] == "Active"
        assert inv["extraction_confidence"] == "Low"
    assert "INSUFFICIENT_DATA" in data["narrative"]
    assert data["needs_reassessment"] is False


async def test_trigger_marks_triggered_and_appends_ledger(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "THTRIG")
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("30"))
    await _add_metric(db_session, company, "revenue_growth_yoy", Decimal("-5.00"))

    data = (
        await client.post(
            f"/api/theses/companies/{company.id}/assess",
            json=_body(invalidations=[], catalysts=[]),
        )
    ).json()

    by_metric = {inv["metric"]: inv for inv in data["invalidations"]}
    assert by_metric["revenue_growth_yoy"]["status"] == "Triggered"
    assert data["needs_reassessment"] is True
    challenged = [r for r in data["ledger"] if r["classification"] == "Challenged"]
    assert len(challenged) == 1
    assert challenged[0]["action"] == "documented_reassessment"
    assert challenged[0]["evidence"]["latest_value"] == "-5.0000"
    assert "status: Triggered" in data["narrative"]

    raw = str(data)
    assert "auto_sell" not in raw and "sell_order" not in raw
    assert data["needs_reassessment"] is True


async def test_update_marks_reassessed_and_records_outcome(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "THUPDATE")
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("30"))
    await _add_metric(db_session, company, "revenue_growth_yoy", Decimal("-5.00"))

    assessed = (
        await client.post(
            f"/api/theses/companies/{company.id}/assess",
            json=_body(invalidations=[], catalysts=[CALLER_CATALYST]),
        )
    ).json()
    catalyst_id = next(
        c["id"] for c in assessed["catalysts"] if c["event"] == "Q2 2026 results release"
    )
    ledger_before = len(assessed["ledger"])

    updated = (
        await client.post(
            f"/api/theses/companies/{company.id}/update",
            json={
                "rationale": "Reviewed Q2 filing; miss was one-off logistics.",
                "classification": "Confirmed",
                "invalidations": [
                    {"metric": "revenue_growth_yoy", "status": "Reassessed"}
                ],
                "catalysts": [{"catalyst_id": catalyst_id, "outcome": "Miss"}],
            },
        )
    ).json()

    by_metric = {inv["metric"]: inv for inv in updated["invalidations"]}
    assert by_metric["revenue_growth_yoy"]["status"] == "Reassessed"
    assert updated["needs_reassessment"] is False
    assert len(updated["ledger"]) == ledger_before + 2
    assert "status: Reassessed" in updated["narrative"]
    by_event = {c["event"]: c for c in updated["catalysts"]}
    assert by_event["Q2 2026 results release"]["outcome"] == "Miss"
    assert "outcome Miss" in updated["narrative"]

    # Re-assess preserves the Reassessed state when the spec is unchanged.
    reassessed = (
        await client.post(
            f"/api/theses/companies/{company.id}/assess",
            json=_body(invalidations=[], catalysts=[]),
        )
    ).json()
    keep = {inv["metric"]: inv for inv in reassessed["invalidations"]}
    assert keep["revenue_growth_yoy"]["status"] == "Reassessed"


async def test_update_validation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "THUPDVAL")
    await _good_dq(db_session, company)
    await client.post(f"/api/theses/companies/{company.id}/assess", json=_body())

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

    bad_status = await client.post(
        f"/api/theses/companies/{company.id}/update",
        json={
            "rationale": "documented",
            "invalidations": [{"metric": "roe", "status": "Sold"}],
        },
    )
    assert bad_status.status_code == 400

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


async def test_assess_validation(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "THVAL")
    await _good_dq(db_session, company)

    too_many = await client.post(
        f"/api/theses/companies/{company.id}/assess",
        json=_body(
            invalidations=[
                {
                    "metric": f"m{i}",
                    "threshold": 0.0,
                    "direction": "below",
                    "period": "annual",
                    "evidence_source": "annual_financial_statements",
                }
                for i in range(5)
            ]
        ),
    )
    assert too_many.status_code == 400

    bad_source = await client.post(
        f"/api/theses/companies/{company.id}/assess",
        json=_body(
            invalidations=[
                {
                    "metric": "roe",
                    "threshold": 0.0,
                    "direction": "below",
                    "period": "annual",
                    "evidence_source": "analyst_note",
                }
            ]
        ),
    )
    assert bad_source.status_code == 400

    bad_direction = await client.post(
        f"/api/theses/companies/{company.id}/assess",
        json=_body(
            invalidations=[
                {
                    "metric": "roe",
                    "threshold": 0.0,
                    "direction": "sideways",
                    "period": "annual",
                    "evidence_source": "annual_financial_statements",
                }
            ]
        ),
    )
    assert bad_direction.status_code == 400

    shariah_confirmed = await client.post(
        f"/api/theses/companies/{company.id}/assess",
        json=_body(
            catalysts=[
                {
                    "event": "Shariah33 index inclusion",
                    "provenance": "https://www.egx.com.eg/shariah.pdf",
                    "label": "Confirmed",
                }
            ]
        ),
    )
    assert shariah_confirmed.status_code == 400

    shariah_tentative = await client.post(
        f"/api/theses/companies/{company.id}/assess",
        json=_body(
            catalysts=[
                {
                    "event": "Shariah33 index inclusion",
                    "provenance": "https://www.egx.com.eg/shariah.pdf",
                    "label": "Tentative",
                }
            ]
        ),
    )
    assert shariah_tentative.status_code == 200

    no_url = await client.post(
        f"/api/theses/companies/{company.id}/assess",
        json=_body(
            catalysts=[{"event": "AGM", "provenance": "word of mouth"}]
        ),
    )
    assert no_url.status_code == 400

    bad_horizon = await client.post(
        f"/api/theses/companies/{company.id}/assess", json=_body(horizon_years=0)
    )
    assert bad_horizon.status_code == 400

    too_many_bulls = await client.post(
        f"/api/theses/companies/{company.id}/assess",
        json=_body(bulls=["a", "b", "c", "d"]),
    )
    assert too_many_bulls.status_code == 400


async def test_snapshot_last_writer_wins_ledger_append_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "THPIN")
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("30"))
    url = f"/api/theses/companies/{company.id}/assess"

    first = (await client.post(url, json=_body())).json()
    assert len(first["ledger"]) == 1
    second = (await client.post(url, json=_body(bulls=["Only one bull"]))).json()
    assert second["bulls"] == ["Only one bull"]
    assert len(second["ledger"]) == 2

    rows = (
        await db_session.execute(
            select(InvestmentThesis)
            .where(InvestmentThesis.company_id == company.id)
            .where(
                InvestmentThesis.methodology_version == THESIS_METHODOLOGY_VERSION
            )
            .execution_options(populate_existing=True)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].bulls == ["Only one bull"]


async def test_reads_filter_by_methodology_version(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "THVERSION")
    db_session.add(
        InvestmentThesis(
            id=uuid.uuid4(),
            company_id=company.id,
            methodology_version="0.9",
            horizon_years=5,
            is_shareholder=None,
            fair_value=None,
            fair_value_status="INSUFFICIENT_DATA",
            assumptions=[],
            bulls=[],
            bears=[],
            scenarios={},
            sensitivity={},
            narrative="stale",
            confidence={},
            dq={},
            score=None,
            needs_reassessment=False,
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    got = (await client.get(f"/api/theses/companies/{company.id}")).json()
    assert got["assessment"] is None

    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("30"))
    await client.post(f"/api/theses/companies/{company.id}/assess", json=_body())
    versions = (
        await db_session.execute(
            select(InvestmentThesis.methodology_version).where(
                InvestmentThesis.company_id == company.id
            )
        )
    ).scalars().all()
    assert sorted(versions) == ["0.9", THESIS_METHODOLOGY_VERSION]


async def test_post_get_round_trip_parity(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "THROUNDTRIP")
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("30"))
    await _add_metric(db_session, company, "revenue_growth_yoy", Decimal("8.00"))
    await _add_metric(db_session, company, "operating_margin", Decimal("15.00"))
    await _add_metric(db_session, company, "roe", Decimal("25.00"))

    post = (
        await client.post(f"/api/theses/companies/{company.id}/assess", json=_body())
    ).json()
    assessment = (
        await client.get(f"/api/theses/companies/{company.id}")
    ).json()["assessment"]
    assert assessment is not None
    assert assessment["ticker"] == post["ticker"] == "THROUNDTRIP"
    assert assessment["narrative"] == post["narrative"]
    assert assessment["header"] == post["header"]
    assert assessment["invalidations"] == post["invalidations"]
    assert assessment["needs_reassessment"] == post["needs_reassessment"]
    assert isinstance(assessment["header"]["fair_value"]["value"], str)


async def test_get_is_read_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed(db_session)
    company = await _make_company(db_session, "THREADONLY")
    await _good_dq(db_session, company)
    await _add_price(db_session, company, Decimal("30"))
    await client.post(f"/api/theses/companies/{company.id}/assess", json=_body())

    async def counts() -> tuple[int, int, int, int]:
        thesis_id = (
            await db_session.execute(
                select(InvestmentThesis.id).where(
                    InvestmentThesis.company_id == company.id
                )
            )
        ).scalar_one()
        results = []
        for model in (
            InvestmentThesis,
            ThesisInvalidation,
            ThesisLedger,
            ThesisCatalyst,
        ):
            column = (
                model.company_id if model is InvestmentThesis else model.thesis_id
            )
            value = company.id if model is InvestmentThesis else thesis_id
            results.append(
                (
                    await db_session.execute(
                        select(func.count()).select_from(model).where(column == value)
                    )
                ).scalar_one()
            )
        return (results[0], results[1], results[2], results[3])

    before = await counts()
    await client.get(f"/api/theses/companies/{company.id}")
    await client.get(f"/api/theses/companies/{company.id}")
    assert await counts() == before
