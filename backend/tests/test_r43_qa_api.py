"""R43 QA (qa-api): contract checks for computed company data, GET-only compute.

Covers AC-2..AC-7 end to end through the HTTP layer. Every number is a SYNTHETIC
value seeded by the test. These tests only add coverage; they sit beside
``test_r43_computed.py`` (engine-level) and never touch the dev database.
"""

from __future__ import annotations

import re
import uuid
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import event, func, select

from app.db.session import engine as db_engine
from app.models.compute import ComputeState
from app.models.metrics import FinancialMetric
from app.models.screening import ShariahScreeningResult
from app.models.signals import SignalRun
from app.models.statements import ExtStatus
from app.models.valuation import ValuationAssumption
from app.services import recompute as rc
from app.services.recompute import Engine
from app.valuation.constants import VALUATION_METHODOLOGY_VERSION
from statement_seed import FULL_YEAR, make_company, seed_prices, seed_year

if TYPE_CHECKING:
    from collections.abc import Iterator

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.market import Company

_WRITE = re.compile(r"^\s*(INSERT|UPDATE|DELETE)\b", re.IGNORECASE)


@contextmanager
def write_statements() -> Iterator[list[str]]:
    """Collect every INSERT/UPDATE/DELETE the engine executes inside the block."""
    seen: list[str] = []

    def _listener(
        _conn: Any, _cursor: Any, statement: str, _params: Any, _ctx: Any, _many: Any
    ) -> None:
        if _WRITE.match(statement):
            seen.append(" ".join(statement.split())[:90])

    event.listen(db_engine.sync_engine, "before_cursor_execute", _listener)
    try:
        yield seen
    finally:
        event.remove(db_engine.sync_engine, "before_cursor_execute", _listener)


def _paths(company: Company) -> dict[str, str]:
    cid = company.id
    return {
        "metrics": f"/api/metrics/companies/{cid}",
        "fair_value": f"/api/valuation/companies/{cid}/fair-value",
        "score": f"/api/scores/companies/{cid}",
        "screening": f"/api/screening/companies/{cid}",
        "purification": f"/api/screening/companies/{cid}/purification",
        "technical": f"/api/technical/companies/{cid}",
        "thesis": f"/api/theses/companies/{cid}",
        "stance": f"/api/stance/companies/{company.ticker}",
    }


async def _states(db: AsyncSession, company: Company) -> dict[str, Any]:
    rows = (
        await db.execute(
            select(ComputeState.engine, ComputeState.calculated_at, ComputeState.trigger).where(
                ComputeState.company_id == company.id
            )
        )
    ).all()
    return {r[0]: (r[1], r[2]) for r in rows}


async def _two_year_company(db: AsyncSession, bars: int = 60) -> Company:
    company = await make_company(db, industry="Software")
    prior = dict(FULL_YEAR)
    prior.update({"revenue": Decimal("800"), "net_income": Decimal("160")})
    await seed_year(db, company, 2023, prior)
    await seed_year(db, company, 2024, FULL_YEAR)
    if bars:
        await seed_prices(db, company, bars=bars)
    return company


async def _seed_assumptions(db: AsyncSession) -> None:
    for key, value in (
        ("risk_free_rate", "0.20"),
        ("equity_risk_premium", "0.04"),
        ("long_run_inflation", "0.05"),
        ("long_run_cost_of_equity", "0.15"),
        ("nominal_gdp_growth", "0.1359"),
        ("target_pe", "8"),
        ("target_pb", "1.2"),
        ("target_ps", "1.5"),
    ):
        db.add(
            ValuationAssumption(
                methodology_version=VALUATION_METHODOLOGY_VERSION,
                key=key,
                scope="market",
                value=Decimal(value),
                source_url="https://example.test/assumptions",
                source_title="SYNTHETIC test assumption",
                as_of=date.today() - timedelta(days=1),
            )
        )
    await db.flush()


# --- AC-7: GET-only compute, second GET is read-only ------------------------------------


async def test_second_get_with_no_new_inputs_writes_nothing(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await _two_year_company(db_session)
    paths = _paths(company)
    first: dict[str, Any] = {}
    for name, path in paths.items():
        response = await client.get(path)
        assert response.status_code == 200, (name, response.text[:200])
        first[name] = response.json()
    before = await _states(db_session, company)
    assert {Engine.METRICS, Engine.SCORE, Engine.THESIS, Engine.TECHNICAL} <= {
        Engine(e) for e in before
    }
    metric_ids = {r["id"] for r in first["metrics"]}
    with write_statements() as writes:
        for name, path in paths.items():
            response = await client.get(path)
            assert response.status_code == 200, name
            second = response.json()
            if name in ("metrics", "technical"):
                assert {r["id"] for r in second} == {r["id"] for r in first[name]}, name
                assert {r["calculated_at"] for r in second} == {
                    r["calculated_at"] for r in first[name]
                }, name
            elif name != "stance":
                assert second["calculated_at"] == first[name]["calculated_at"], name
    assert writes == [], f"second GET wrote: {writes[:5]}"
    assert await _states(db_session, company) == before
    assert metric_ids  # the first GET really produced metrics


async def test_new_input_makes_only_dependent_engines_stale(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await _two_year_company(db_session)
    paths = _paths(company)
    for path in paths.values():
        assert (await client.get(path)).status_code == 200
    before = await _states(db_session, company)

    # A new price bar only: technical, price DQ, fair value, score, thesis are stale;
    # statement-only engines (metrics, shariah, purification) are not.
    day = date.today() + timedelta(days=1)
    from app.models.market import DailyPrice

    existing = (
        await db_session.execute(
            select(DailyPrice).where(DailyPrice.company_id == company.id).limit(1)
        )
    ).scalar_one()
    db_session.add(
        DailyPrice(
            id=uuid.uuid4(),
            company_id=company.id,
            date=day,
            open=Decimal("30"),
            high=Decimal("31"),
            low=Decimal("29"),
            close=Decimal("30"),
            volume=1000,
            source_id=existing.source_id,
        )
    )
    await db_session.flush()
    for name in ("metrics", "screening", "purification", "technical", "score", "fair_value"):
        assert (await client.get(paths[name])).status_code == 200
    after = await _states(db_session, company)
    for engine in ("technical", "data_quality_ph", "fair_value", "score"):
        assert after[engine][0] > before[engine][0], engine
        assert after[engine][1] == "first_view"
    for engine in ("metrics", "shariah", "purification", "data_quality_fs"):
        assert after[engine] == before[engine], engine

    # A new statement line (filing): statement-fed engines recompute, technical does not.
    await seed_year(
        db_session,
        company,
        2024,
        {"revenue": Decimal("1100")},
        tier="filing",
        published=date(2025, 3, 1),
    )
    for name in ("metrics", "screening", "technical", "score"):
        assert (await client.get(paths[name])).status_code == 200
    again = await _states(db_session, company)
    assert again["metrics"][0] > after["metrics"][0]
    assert again["shariah"][0] > after["shariah"][0]
    assert again["technical"] == after["technical"]
    rows = (await client.get(f"{paths['metrics']}?metric_code=net_margin&fiscal_year=2024")).json()
    assert Decimal(rows[0]["value"]) == Decimal("18.18")  # 200 / filing revenue 1100 = 18.1818 %


async def test_unknown_inputs_company_is_never_unassessed(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """AC-7: a known company with no statements and no prices still gets payloads."""
    company = await make_company(db_session)
    paths = _paths(company)
    score = (await client.get(paths["score"])).json()
    assert score["assessment"] is not None
    assert score["assessment"]["headline"]["value"] is None
    assert score["assessment"]["headline"]["status"] == "INSUFFICIENT_DATA"
    thesis = (await client.get(paths["thesis"])).json()
    assert thesis["assessment"] is not None
    screening = await client.get(paths["screening"])
    assert screening.status_code == 200
    assert screening.json()["is_compliant"] is None
    assert screening.json()["overall_reason"] == "no approved statement lines"
    purification = await client.get(paths["purification"])
    assert purification.status_code == 200
    assert purification.json()["status"] == "INSUFFICIENT_DATA"
    assert purification.json()["amount_egp"] is None
    fair = (await client.get(paths["fair_value"])).json()
    assert fair["fair_value"]["value"] is None
    assert fair["fair_value"]["status"] == "INSUFFICIENT_DATA"
    assert (await client.get(paths["metrics"])).json() == []
    technical = (await client.get(paths["technical"])).json()
    assert all(r["value"] is None and r["status"] == "INSUFFICIENT_DATA" for r in technical)
    assert all(r["reason"] for r in technical)


@pytest.mark.parametrize(
    "name", ["metrics", "fair_value", "score", "screening", "purification", "technical", "thesis"]
)
async def test_unknown_company_is_404_not_500(
    client: AsyncClient, db_session: AsyncSession, name: str
) -> None:
    ghost = await make_company(db_session)
    path = _paths(ghost)[name].replace(str(ghost.id), str(uuid.uuid4()))
    response = await client.get(path)
    assert response.status_code == 404, response.text[:200]
    assert (await client.get("/api/stance/companies/NOPE_NOT_A_TICKER")).status_code in (404, 200)


# --- AC-3: INSUFFICIENT_DATA names the missing line, never 0 ---------------------------------


async def test_missing_line_is_null_and_named_in_every_engine(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session, industry="Software")
    values = dict(FULL_YEAR)
    for code in ("interest_income", "dividends_paid", "cfo", "gross_profit"):
        values.pop(code)
    await seed_year(db_session, company, 2023, dict(FULL_YEAR))
    await seed_year(db_session, company, 2024, values)
    paths = _paths(company)

    metrics = (await client.get(f"{paths['metrics']}?fiscal_year=2024")).json()
    by_code = {r["metric_code"]: r for r in metrics}
    for code, line in (
        ("gross_margin", "gross_profit"),
        ("operating_cash_flow_margin", "cfo"),
        ("free_cash_flow", "cfo"),
    ):
        row = by_code[code]
        assert row["value"] is None, code
        assert row["status"] == "INSUFFICIENT_DATA", code
        assert line in row["reason"], (code, row["reason"])
    assert all(
        r["value"] != "0" and r["value"] != "0.00" for r in metrics if r["status"] != "AVAILABLE"
    )

    screening = (await client.get(paths["screening"])).json()
    assert screening["is_compliant"] is None
    rule = next(r for r in screening["rule_results"] if r["rule_name"] == "interest_income_ratio")
    assert rule["value"] is None
    assert rule["verdict"] == "INSUFFICIENT_DATA"
    assert rule["missing_input"] == "interest_income"
    assert "interest_income" in rule["reason"]

    purification = (await client.get(paths["purification"])).json()
    assert purification["status"] == "INSUFFICIENT_DATA"
    assert purification["amount_egp"] is None and purification["dividend_egp"] is None
    assert purification["dps"] is None
    assert purification["missing_input"] == "dividends_paid"
    assert "dividends_paid" in purification["reason"]

    fair = (await client.get(paths["fair_value"])).json()
    assert fair["fair_value"]["value"] is None
    assert fair["fair_value"]["status"] == "INSUFFICIENT_DATA"
    assert fair["inputs"]["free_cash_flow"] is None  # cfo missing: not 0

    score = (await client.get(paths["score"])).json()["assessment"]
    assert score["headline"]["value"] is None or score["headline"]["status"] != "INSUFFICIENT_DATA"
    thesis = (await client.get(paths["thesis"])).json()["assessment"]
    assert thesis["header"]["fair_value"]["value"] is None
    assert thesis["header"]["fair_value"]["status"] == "INSUFFICIENT_DATA"


async def test_missing_cfo_with_sourced_assumptions_names_the_line(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Assumptions exist, so the only gap is the statement line: it must be named."""
    await _seed_assumptions(db_session)
    company = await make_company(db_session, industry="Software")
    values = dict(FULL_YEAR)
    values.pop("cfo")
    await seed_year(db_session, company, 2023, dict(FULL_YEAR))
    await seed_year(db_session, company, 2024, values)
    await seed_prices(db_session, company, bars=40)
    fair = (await client.get(_paths(company)["fair_value"])).json()
    assert fair["assumptions"]["missing"] == []
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["value"] is None
    assert intrinsic["status"] == "INSUFFICIENT_DATA"
    assert (
        "cfo" in (intrinsic["reason"] or "")
        or "free cash flow" in (intrinsic["reason"] or "").lower()
    ), intrinsic["reason"]
    assert fair["fair_value"]["value"] != "0"


async def test_technical_with_few_bars_is_insufficient_never_zero(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session)
    await seed_prices(db_session, company, bars=5)
    rows = (await client.get(_paths(company)["technical"])).json()
    assert rows
    insufficient = [r for r in rows if r["status"] == "INSUFFICIENT_DATA"]
    assert insufficient, "5 bars cannot support SMA20/RSI14"
    for row in insufficient:
        assert row["value"] is None
        assert row["reason"]


# --- AC-4: filing beats vendor; provenance + provisional flag ---------------------------------


async def test_filing_beats_vendor_everywhere_and_flags_provisional(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_assumptions(db_session)
    filing = await make_company(db_session, industry="Software")
    vendor = await make_company(db_session, industry="Software")
    filing_year = dict(FULL_YEAR)
    for company, tier, published in (
        (filing, "filing", date(2025, 3, 1)),
        (vendor, "vendor", None),
    ):
        await seed_year(db_session, company, 2023, dict(FULL_YEAR), tier=tier, published=published)
        await seed_year(db_session, company, 2024, filing_year, tier=tier, published=published)
        await seed_prices(db_session, company, bars=40)
    # The vendor company also gets a filing for revenue only: the filing value must win,
    # but the snapshots stay provisional because other inputs are still vendor lines.
    await seed_year(
        db_session,
        vendor,
        2024,
        {"revenue": Decimal("2000")},
        tier="filing",
        published=date(2025, 3, 1),
    )

    for name, path in _paths(filing).items():
        if name in ("technical", "stance"):
            continue
        body = (await client.get(path)).json()
        rows = body if isinstance(body, list) else [body]
        assert rows, name
        for row in rows:
            assert row["provisional"] is False, (name, row.get("metric_code"))
            assert row["source_tier"] in ("filing", None), name
            if name != "metrics":
                assert row["period_end"] in ("2024-12-31", None), name
        if name == "metrics":
            assert {r["period_end"] for r in rows} == {"2023-12-31", "2024-12-31"}

    for name, path in _paths(vendor).items():
        if name in ("technical", "stance"):
            continue
        body = (await client.get(path)).json()
        rows = body if isinstance(body, list) else [body]
        assert any(r["provisional"] is True and r["source_tier"] == "vendor" for r in rows), name

    margin = (
        await client.get(f"{_paths(vendor)['metrics']}?metric_code=net_margin&fiscal_year=2024")
    ).json()[0]
    assert Decimal(margin["value"]) == Decimal("10.00")  # 200 / filing revenue 2000
    by_role = {i["input_role"]: i for i in margin["inputs"]}
    assert by_role["revenue"]["source_tier"] == "filing"
    assert by_role["revenue"]["provisional"] is False
    assert by_role["revenue"]["value"].startswith("2000")
    assert by_role["net_income"]["source_tier"] == "vendor"
    assert by_role["net_income"]["provisional"] is True
    assert margin["source_tier"] == "vendor" and margin["provisional"] is True
    for item in margin["inputs"]:
        assert item["period_end"] == "2024-12-31"
        assert item["document_url"] and item["document_type"] and item["line_id"]

    shariah = (await client.get(_paths(vendor)["screening"])).json()
    assert shariah["provisional"] is True
    revenue_rules = [
        r for r in shariah["rule_results"] if r["rule_name"] == "interest_income_ratio"
    ]
    assert revenue_rules and revenue_rules[0]["source"]
    fv = (await client.get(_paths(vendor)["fair_value"])).json()
    assert fv["provisional"] is True
    statements = fv["statement_sources"]
    assert any(s["code"] == "revenue" and s["source_tier"] == "filing" for s in statements)
    assert all(
        {"line_id", "period_end", "source_tier", "provisional"} <= set(s) for s in statements
    )
    score = (await client.get(_paths(vendor)["score"])).json()
    sources = score["assessment"]["inputs_echo"]["sources"]["statements"]
    assert sources and all(s["period_end"] and "provisional" in s for s in sources)


# --- AC-5: statement writers recompute only the affected company ------------------------------


async def test_reject_and_approve_recompute_only_that_company(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    target = await _two_year_company(db_session, bars=0)
    other = await _two_year_company(db_session, bars=0)
    for company in (target, other):
        for name in ("metrics", "screening", "score", "thesis", "fair_value"):
            assert (await client.get(_paths(company)[name])).status_code == 200
    other_before = await _states(db_session, other)
    target_before = await _states(db_session, target)

    # Reject the auto_validated vendor revenue line of FY2024: the approved set changes.
    from app.models.statements import FinancialStatementLine

    line = (
        await db_session.execute(
            select(FinancialStatementLine)
            .where(FinancialStatementLine.company_id == target.id)
            .where(FinancialStatementLine.ontology_code == "revenue")
            .where(FinancialStatementLine.value == Decimal("1000"))
        )
    ).scalar_one()
    response = await client.post(
        f"/api/statements/lines/{line.id}/reject", json={"reason": "QA reject"}
    )
    assert response.status_code == 200
    recompute = response.json()["recompute"]
    assert recompute["company_id"] == str(target.id)
    statuses = {o["engine"]: o["status"] for o in recompute["outcomes"]}
    for engine in ("metrics", "shariah", "fair_value", "score", "thesis"):
        assert statuses[engine] == "computed", engine
    assert "technical" not in statuses
    after = await _states(db_session, target)
    for engine in ("metrics", "shariah", "fair_value", "score", "thesis"):
        assert after[engine][0] > target_before[engine][0]
        assert after[engine][1] == "statement_import"
    assert await _states(db_session, other) == other_before

    rows = (
        await client.get(f"{_paths(target)['metrics']}?metric_code=net_margin&fiscal_year=2024")
    ).json()
    assert rows[0]["status"] == "INSUFFICIENT_DATA"
    assert "revenue" in rows[0]["reason"]
    assert rows[0]["trigger"] == "statement_import"  # GET did not recompute again

    # Approving a held candidate brings the number back through the same hook.
    held = await seed_year(
        db_session,
        target,
        2024,
        {"revenue": Decimal("1500")},
        tier="filing",
        published=date(2025, 3, 1),
        status=ExtStatus.extraction_candidate,
    )
    approve = await client.post(f"/api/statements/lines/{held['revenue'].id}/approve")
    assert approve.status_code == 200
    assert {o["engine"]: o["status"] for o in approve.json()["recompute"]["outcomes"]}[
        "metrics"
    ] == "computed"
    rows = (
        await client.get(f"{_paths(target)['metrics']}?metric_code=net_margin&fiscal_year=2024")
    ).json()
    assert rows[0]["status"] == "AVAILABLE"
    assert rows[0]["trigger"] == "statement_import"
    assert await _states(db_session, other) == other_before


async def test_hook_failure_does_not_fail_the_statement_write(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    company = await make_company(db_session)

    async def boom(_ctx: Any) -> Any:
        raise RuntimeError("engine exploded")

    for engine in rc.ENGINE_ORDER:
        monkeypatch.setitem(rc.RUNNERS, engine, boom)
    response = await client.post(
        "/api/statements/manual-filings",
        json={
            "ticker": company.ticker,
            "fiscal_year": 2024,
            "period_end": "2024-12-31",
            "document_url": "https://www.egx.com.eg/test/f.pdf",
            "publication_date": "2025-03-01",
            "lines": [{"code": "revenue", "value": "1000", "page": "4"}],
        },
    )
    assert response.status_code == 200
    outcomes = response.json()["recompute"]["outcomes"]
    assert outcomes and all(o["status"] == "failed" for o in outcomes)
    assert any(o["error"] == "RuntimeError: engine exploded" for o in outcomes)


# --- (8) a compute error never 500s a request --------------------------------------------------


@pytest.mark.parametrize(
    ("name", "engine"),
    [
        ("metrics", Engine.METRICS),
        ("fair_value", Engine.FAIR_VALUE),
        ("score", Engine.SCORE),
        ("screening", Engine.SHARIAH),
        ("purification", Engine.PURIFICATION),
        ("technical", Engine.TECHNICAL),
        ("thesis", Engine.THESIS),
    ],
)
async def test_compute_error_is_200_with_failed_status(
    client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    engine: Engine,
) -> None:
    company = await _two_year_company(db_session)

    async def boom(_ctx: Any) -> Any:
        raise ValueError("simulated engine failure")

    monkeypatch.setitem(rc.RUNNERS, engine, boom)
    response = await client.get(_paths(company)[name])
    assert response.status_code == 200, response.text[:300]
    body = response.json()
    rows = body if isinstance(body, list) else [body]
    if rows:
        assert rows[0]["compute_status"] == "failed"
        assert "simulated engine failure" in rows[0]["compute_error"]
    else:
        pytest.fail(f"{name}: failed compute returned an empty list with no status")


async def test_failed_dependent_serves_upstream_failed_not_500(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    company = await _two_year_company(db_session)

    async def boom(_ctx: Any) -> Any:
        raise ValueError("metrics down")

    monkeypatch.setitem(rc.RUNNERS, Engine.METRICS, boom)
    paths = _paths(company)
    for name in ("fair_value", "score", "thesis", "stance"):
        response = await client.get(paths[name])
        assert response.status_code == 200, (name, response.text[:300])
    fair = (await client.get(paths["fair_value"])).json()
    assert fair["compute_status"] == "failed"
    assert fair["compute_error"] == "upstream failed: metrics"
    assert fair["fair_value"]["value"] is None
    # A failed compute is not retried on every GET: no writes on the repeat.
    with write_statements() as writes:
        assert (await client.get(paths["fair_value"])).status_code == 200
    assert writes == []


async def test_dependent_of_an_already_failed_engine_is_marked_failed(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    company = await _two_year_company(db_session)

    async def boom(_ctx: Any) -> Any:
        raise ValueError("score down")

    monkeypatch.setitem(rc.RUNNERS, Engine.SCORE, boom)
    paths = _paths(company)
    assert (await client.get(paths["score"])).json()["compute_status"] == "failed"
    thesis = (await client.get(paths["thesis"])).json()  # score failed on the earlier GET
    assert thesis["compute_status"] == "failed"
    assert thesis["compute_error"] == "upstream failed: score"


async def test_last_good_snapshot_is_served_when_a_later_compute_fails(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    company = await _two_year_company(db_session)
    path = _paths(company)["score"]
    good = (await client.get(path)).json()
    assert good["compute_status"] == "ok" and good["assessment"] is not None

    async def boom(_ctx: Any) -> Any:
        raise ValueError("score blew up")

    monkeypatch.setitem(rc.RUNNERS, Engine.SCORE, boom)
    await seed_year(
        db_session,
        company,
        2024,
        {"revenue": Decimal("1300")},
        tier="filing",
        published=date(2025, 3, 1),
    )
    stale = await client.get(path)
    assert stale.status_code == 200
    body = stale.json()
    assert body["compute_status"] == "failed"
    assert "score blew up" in body["compute_error"]
    assert body["assessment"] is not None  # the last good snapshot, not null
    assert body["assessment"]["computed_at"] == good["assessment"]["computed_at"]


async def test_failed_engine_rolls_back_its_partial_writes(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    company = await _two_year_company(db_session, bars=0)
    original = rc.RUNNERS[Engine.SHARIAH]

    async def write_then_fail(ctx: Any) -> Any:
        await original(ctx)
        raise ValueError("late failure")

    monkeypatch.setitem(rc.RUNNERS, Engine.SHARIAH, write_then_fail)
    body = (await client.get(_paths(company)["screening"])).json()
    assert body["compute_status"] == "failed"
    count = (
        await db_session.execute(
            select(func.count())
            .select_from(ShariahScreeningResult)
            .where(ShariahScreeningResult.company_id == company.id)
        )
    ).scalar_one()
    assert count == 0  # SAVEPOINT rolled the engine's rows back
    assert body["id"] is None
    assert body["is_compliant"] is None


async def test_database_error_inside_an_engine_does_not_poison_the_request(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import text

    company = await _two_year_company(db_session, bars=0)

    async def db_boom(ctx: Any) -> Any:
        await ctx.session.execute(text("SELECT 1/0"))

    monkeypatch.setitem(rc.RUNNERS, Engine.TECHNICAL, db_boom)
    paths = _paths(company)
    technical = await client.get(paths["technical"])
    assert technical.status_code == 200
    assert technical.json() == [] or technical.json()[0]["compute_status"] == "failed"
    # The same session keeps serving other engines afterwards.
    metrics = await client.get(paths["metrics"])
    assert metrics.status_code == 200 and metrics.json()
    state = (await _states(db_session, company))["technical"]
    assert state[0] is not None


# --- (5) removed routes are gone, kept routes still exist --------------------------------------

_REMOVED: tuple[tuple[str, str], ...] = (
    ("POST", "/api/technical/companies/{id}/calculate"),
    ("POST", "/api/valuation/companies/{id}/calculate"),
    ("GET", "/api/valuation/companies/{id}"),
    ("POST", "/api/metrics/companies/{id}/calculate"),
    ("POST", "/api/metrics/companies/{id}/periods/{id}/calculate"),
    ("POST", "/api/scores/companies/{id}/assess"),
    ("POST", "/api/theses/companies/{id}/assess"),
    ("POST", "/api/screening/companies/{id}/screen"),
    ("POST", "/api/screening/companies/{id}/screen-statements"),
    ("POST", "/api/screening/companies/{id}/purification"),
    ("PUT", "/api/scores/companies/{id}"),
    ("DELETE", "/api/metrics/companies/{id}"),
)


@pytest.mark.parametrize(("method", "template"), _REMOVED)
async def test_removed_routes_are_404_or_405(
    client: AsyncClient, method: str, template: str
) -> None:
    path = template.replace("{id}", str(uuid.uuid4()))
    response = await client.request(method, path, json={})
    assert response.status_code in (404, 405), (method, path, response.status_code)
    if response.status_code == 404:
        assert response.json() == {"detail": "Not Found"}  # router-level miss, not a handler


async def test_openapi_has_no_removed_or_caller_input_routes() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    for method, template in _REMOVED:
        normalized = re.sub(r"\{id\}", "{company_id}", template, count=1)
        normalized = normalized.replace("{id}", "{period_id}")
        item = paths.get(normalized)
        if item is not None:
            assert method.lower() not in item, (method, normalized)
    fair = paths["/api/valuation/companies/{company_id}/fair-value"]["get"]
    assert [p["name"] for p in fair.get("parameters", [])] == ["company_id"]
    for kept in (
        ("get", "/api/statements/intake"),
        ("post", "/api/statements/manual-filings"),
        ("post", "/api/disclosures/register"),
        ("post", "/api/disclosures/upload"),
        ("post", "/api/disclosures/filings/{filing_id}/parse"),
        ("put", "/api/industry/companies/{company_id}/peers"),
        ("post", "/api/theses/companies/{company_id}/update"),
        ("post", "/api/ingestion/sync"),
        ("get", "/api/ingestion/sync/status"),
        ("post", "/api/screening/companies/{company_id}/egx-membership"),
        ("post", "/api/signals/run"),
        ("post", "/api/disclosures/facts"),
    ):
        assert kept[0] in paths[kept[1]], kept


async def test_kept_admin_routes_still_work(client: AsyncClient, db_session: AsyncSession) -> None:
    company = await make_company(db_session)
    assert (await client.get("/api/statements/intake")).status_code == 200
    assert (await client.get("/api/ingestion/sync/status")).status_code == 200
    # Validation, not a missing route.
    for method, path in (
        ("POST", "/api/disclosures/register"),
        ("POST", "/api/disclosures/upload"),
        ("POST", "/api/statements/manual-filings"),
    ):
        response = await client.request(method, path, json={})
        assert response.status_code == 422, (method, path, response.status_code)
    peers = await client.put(f"/api/industry/companies/{company.id}/peers", json={})
    assert peers.status_code not in (404, 405)
    # Thesis documented update works after the GET auto-assessed.
    assert (await client.get(_paths(company)["thesis"])).json()["assessment"] is not None
    update = await client.post(
        f"/api/theses/companies/{company.id}/update",
        json={"rationale": "QA documented update", "classification": "Pending"},
    )
    assert update.status_code == 200, update.text[:200]
    # ...and a later GET with unchanged inputs does not erase it (no auto re-assess).
    with write_statements() as writes:
        assert (await client.get(_paths(company)["thesis"])).status_code == 200
    assert writes == []


async def test_legacy_query_overrides_on_fair_value_are_ignored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await _two_year_company(db_session, bars=30)
    path = _paths(company)["fair_value"]
    plain = (await client.get(path)).json()
    with write_statements() as writes:
        forced = (
            await client.get(
                path,
                params={
                    "discount_rate": "0.99",
                    "terminal_growth_rate": "0.5",
                    "growth_rate": "9",
                    "earnings_per_share": "1000",
                    "pe_ratio": "50",
                    "exit_multiple": "50",
                },
            )
        ).json()
    assert writes == []
    assert forced["fair_value"] == plain["fair_value"]
    assert forced["inputs"] == plain["inputs"]
    assert forced["calculated_at"] == plain["calculated_at"]


# --- AC-6: price sync recompute scope -------------------------------------------------------


async def test_after_price_sync_touches_only_synced_tickers_and_runs_signals(
    db_session: AsyncSession,
) -> None:
    from contextlib import asynccontextmanager

    synced = await _two_year_company(db_session, bars=40)
    untouched = await _two_year_company(db_session, bars=40)

    @asynccontextmanager
    async def factory() -> Any:
        yield db_session

    runs_before = (
        await db_session.execute(select(func.count()).select_from(SignalRun))
    ).scalar_one()
    result = (await rc.after_price_sync([synced.id], session_factory=factory)).as_dict()
    runs_after = (
        await db_session.execute(select(func.count()).select_from(SignalRun))
    ).scalar_one()
    assert result["signals"]["ran"] is True and result["signals"]["error"] is None
    assert runs_after == runs_before + 1
    assert result["technical"] == {"computed": 1, "fresh": 0, "failed": 0}
    for step in ("fair_value", "score", "thesis"):
        assert result[step] == {"computed": 1, "fresh": 0, "failed": 0}
    assert result["failed_companies"] == []
    states = await _states(db_session, synced)
    assert states["technical"][1] == "price_sync"
    assert states["score"][1] == "price_sync"
    assert "metrics" in states  # pulled in as upstream of fair value
    assert await _states(db_session, untouched) == {}

    # Idempotent: a repeat without new prices recomputes nothing.
    again = (await rc.after_price_sync([synced.id], session_factory=factory)).as_dict()
    assert again["technical"] == {"computed": 0, "fresh": 1, "failed": 0}
    for step in ("fair_value", "score", "thesis"):
        assert again[step] == {"computed": 0, "fresh": 1, "failed": 0}


async def test_price_sync_failure_is_reported_per_step_not_raised(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from contextlib import asynccontextmanager

    company = await _two_year_company(db_session, bars=40)

    @asynccontextmanager
    async def factory() -> Any:
        yield db_session

    async def boom(_ctx: Any) -> Any:
        raise ValueError("score broke")

    monkeypatch.setitem(rc.RUNNERS, Engine.SCORE, boom)
    result = (await rc.after_price_sync([company.id], session_factory=factory)).as_dict()
    assert result["score"] == {"computed": 0, "fresh": 0, "failed": 1}
    assert result["thesis"]["failed"] == 1  # dependent of score
    assert result["fair_value"]["computed"] == 1  # independent branch still ran
    assert result["failed_companies"]
    assert {f["engine"] for f in result["failed_companies"]} >= {"score"}


# --- (7) concurrency: parallel first views on a stale company ---------------------------------


async def _purge_committed(company_ids: list[uuid.UUID]) -> None:
    """Remove committed seed rows (the concurrency tests cannot use the rolled-back session)."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession as Session

    async with Session(db_engine) as s:
        for cid in company_ids:
            await s.execute(text("DELETE FROM companies WHERE id = :i"), {"i": cid})
        await s.execute(text("DELETE FROM data_sources WHERE name LIKE 'R43 %'"))
        await s.commit()


async def test_parallel_first_views_compute_each_engine_once(
    monkeypatch: pytest.MonkeyPatch, api_token: str
) -> None:
    import asyncio

    from httpx import ASGITransport
    from httpx import AsyncClient as Client
    from sqlalchemy.ext.asyncio import AsyncSession as Session

    from app.main import app
    from app.models.thesis import ThesisLedger

    async with Session(db_engine, expire_on_commit=False) as setup:
        company = await _two_year_company(setup, bars=60)
        await setup.commit()
    cid = company.id
    calls: dict[str, int] = {}

    def wrap(engine: Engine) -> None:
        original = rc.RUNNERS[engine]

        async def counted(ctx: Any) -> Any:
            calls[engine.value] = calls.get(engine.value, 0) + 1
            await asyncio.sleep(0.05)  # widen the race window
            return await original(ctx)

        monkeypatch.setitem(rc.RUNNERS, engine, counted)

    for engine in rc.ENGINE_ORDER:
        wrap(engine)
    try:
        app.dependency_overrides.clear()
        transport = ASGITransport(app=app)
        async with Client(
            transport=transport,
            base_url="http://test",
            headers={"Authorization": f"Bearer {api_token}"},
        ) as ac:
            paths = _paths(company)
            batch = [
                paths[k]
                for k in (
                    "metrics",
                    "metrics",
                    "score",
                    "score",
                    "thesis",
                    "fair_value",
                    "screening",
                    "purification",
                    "technical",
                    "stance",
                )
            ]
            responses = await asyncio.gather(*(ac.get(p) for p in batch))
            assert [r.status_code for r in responses] == [200] * len(batch), [
                (p, r.status_code, r.text[:120])
                for p, r in zip(batch, responses, strict=True)
                if r.status_code != 200
            ]
            first_calls = dict(calls)
            assert all(n == 1 for n in first_calls.values()), first_calls
            assert set(first_calls) == {e.value for e in rc.ENGINE_ORDER}

            # A second parallel burst computes nothing and writes nothing.
            with write_statements() as writes:
                again = await asyncio.gather(*(ac.get(p) for p in batch))
            assert [r.status_code for r in again] == [200] * len(batch)
            assert calls == first_calls
            assert writes == []

        async with Session(db_engine) as check:
            states = (
                await check.execute(
                    select(ComputeState.engine, func.count())
                    .where(ComputeState.company_id == cid)
                    .group_by(ComputeState.engine)
                )
            ).all()
            assert all(n == 1 for _e, n in states) and len(states) == len(rc.ENGINE_ORDER)
            dup_metrics = (
                await check.execute(
                    select(
                        FinancialMetric.period_id,
                        FinancialMetric.metric_code,
                        FinancialMetric.formula_version,
                        func.count(),
                    )
                    .where(FinancialMetric.company_id == cid)
                    .group_by(
                        FinancialMetric.period_id,
                        FinancialMetric.metric_code,
                        FinancialMetric.formula_version,
                    )
                    .having(func.count() > 1)
                )
            ).all()
            assert dup_metrics == []
            results = (
                await check.execute(
                    select(func.count())
                    .select_from(ShariahScreeningResult)
                    .where(ShariahScreeningResult.company_id == cid)
                )
            ).scalar_one()
            assert results == 1
            ledger = (
                await check.execute(select(func.count()).select_from(ThesisLedger))
            ).scalar_one()
            assert ledger >= 1
    finally:
        app.dependency_overrides.clear()
        await _purge_committed([cid])


async def test_parallel_requests_on_a_failing_engine_do_not_500_or_double_write(
    monkeypatch: pytest.MonkeyPatch, api_token: str
) -> None:
    import asyncio

    from httpx import ASGITransport
    from httpx import AsyncClient as Client
    from sqlalchemy.ext.asyncio import AsyncSession as Session

    from app.main import app

    async with Session(db_engine, expire_on_commit=False) as setup:
        company = await _two_year_company(setup, bars=30)
        await setup.commit()
    runs = {"n": 0}

    async def boom(_ctx: Any) -> Any:
        runs["n"] += 1
        await asyncio.sleep(0.05)
        raise ValueError("parallel failure")

    monkeypatch.setitem(rc.RUNNERS, Engine.SCORE, boom)
    try:
        app.dependency_overrides.clear()
        async with Client(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {api_token}"},
        ) as ac:
            paths = _paths(company)
            responses = await asyncio.gather(
                ac.get(paths["score"]),
                ac.get(paths["score"]),
                ac.get(paths["thesis"]),
                ac.get(paths["thesis"]),
            )
        assert [r.status_code for r in responses] == [200, 200, 200, 200]
        assert runs["n"] == 1  # the failed fingerprint is stored; nobody retries it
        assert [r.json()["compute_status"] for r in responses[:2]] == ["failed"] * 2
    finally:
        await _purge_committed([company.id])


# --- AC-6 through the refresh job --------------------------------------------------------------


@pytest.fixture
def refresh_env(monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession) -> Iterator[None]:
    from contextlib import asynccontextmanager

    from app.ingestion import jobs
    from test_ingestion_jobs import _StubUniverseSource

    jobs.reset_job()

    @asynccontextmanager
    async def session_factory() -> Any:
        yield db_session

    monkeypatch.setattr(jobs, "_session_factory", session_factory)
    monkeypatch.setattr(
        jobs, "create_universe_source", lambda: _StubUniverseSource(["COMI", "HRHO"])
    )
    yield
    jobs.reset_job()


async def test_refresh_job_recomputes_only_synced_tickers(
    client: AsyncClient,
    db_session: AsyncSession,
    refresh_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ingestion import jobs
    from app.models.market import Company
    from test_ingestion_jobs import _StubProvider

    monkeypatch.setattr(jobs, "create_price_provider", lambda: _StubProvider(fail={"HRHO"}))
    bystander = await _two_year_company(db_session, bars=40)
    runs_before = (
        await db_session.execute(select(func.count()).select_from(SignalRun))
    ).scalar_one()

    response = await client.post("/api/ingestion/sync", params={"tickers": "COMI,HRHO"})
    assert response.status_code == 202
    task = jobs.current_job().task
    assert task is not None
    await task
    done = jobs.current_job().to_dict()

    assert done["status"] == "partial"  # HRHO price fetch failed, the job still finished
    assert done["prices"]["failed_count"] == 1
    recompute = done["recompute"]
    assert recompute is not None
    assert recompute["technical"] == {"computed": 1, "fresh": 0, "failed": 0}  # COMI only
    for step in ("fair_value", "score", "thesis"):
        assert recompute[step] == {"computed": 1, "fresh": 0, "failed": 0}, step
    assert recompute["signals"]["ran"] is True
    assert recompute["signals"]["error"] is None
    assert recompute["failed_companies"] == []
    runs_after = (
        await db_session.execute(select(func.count()).select_from(SignalRun))
    ).scalar_one()
    assert runs_after == runs_before + 1

    comi = (await db_session.execute(select(Company).where(Company.ticker == "COMI"))).scalar_one()
    hrho = (await db_session.execute(select(Company).where(Company.ticker == "HRHO"))).scalar_one()
    comi_states = await _states(db_session, comi)
    assert comi_states["technical"][1] == "price_sync"
    assert await _states(db_session, hrho) == {}  # failed fetch: not recomputed
    assert await _states(db_session, bystander) == {}  # not synced: untouched


async def test_refresh_job_survives_a_failing_engine(
    client: AsyncClient,
    db_session: AsyncSession,
    refresh_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.ingestion import jobs
    from test_ingestion_jobs import _StubProvider

    monkeypatch.setattr(jobs, "create_price_provider", lambda: _StubProvider())

    async def boom(_ctx: Any) -> Any:
        raise ValueError("fair value broke")

    monkeypatch.setitem(rc.RUNNERS, Engine.FAIR_VALUE, boom)
    assert (
        await client.post("/api/ingestion/sync", params={"tickers": "COMI,HRHO"})
    ).status_code == 202
    task = jobs.current_job().task
    assert task is not None
    await task
    done = jobs.current_job().to_dict()
    assert done["status"] == "done"
    recompute = done["recompute"]
    assert recompute["fair_value"]["failed"] == 2
    assert recompute["score"]["failed"] == 2 and recompute["thesis"]["failed"] == 2
    assert recompute["technical"]["computed"] == 2
    assert {f["engine"] for f in recompute["failed_companies"]} >= {"fair_value"}
    assert len(recompute["failed_companies"]) <= 20


# --- migration 023 with data, constraint and drift --------------------------------------------


async def test_migration_023_has_no_model_drift_and_single_head() -> None:
    import asyncio

    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config("alembic.ini")
    assert ScriptDirectory.from_config(cfg).get_heads() == ["023"]
    await asyncio.to_thread(command.check, cfg)  # raises when models and migrations differ


async def test_migration_023_downgrade_keeps_fact_inputs_and_drops_line_inputs() -> None:
    import asyncio

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import AsyncSession as Session

    from app.models.financial import FinancialFact
    from app.models.metrics import FinancialMetricInput
    from app.services.recompute import RecomputeService, Trigger

    async with Session(db_engine, expire_on_commit=False) as s:
        company = await _two_year_company(s, bars=0)
        company_id = company.id
        await RecomputeService(s).recompute_company(company_id, Trigger.BACKFILL, [Engine.METRICS])
        await s.commit()
        metric = (
            (
                await s.execute(
                    select(FinancialMetric)
                    .where(FinancialMetric.company_id == company.id)
                    .where(FinancialMetric.metric_code == "net_margin")
                )
            )
            .scalars()
            .first()
        )
        assert metric is not None
        from app.models.financial import FinancialDocument

        doc = (await s.execute(select(FinancialDocument).limit(1))).scalars().first()
        assert doc is not None
        fact = FinancialFact(
            id=uuid.uuid4(),
            period_id=metric.period_id,
            document_id=doc.id,
            company_id=company.id,
            fact_type="INCOME_STATEMENT",
            reported_label="revenue",
            normalized_label="revenue",
            reported_value=Decimal("1"),
            normalized_value=Decimal("1"),
            currency="EGP",
        )
        s.add(fact)
        await s.flush()
        s.add(FinancialMetricInput(metric_id=metric.id, fact_id=fact.id, input_role="legacy"))
        await s.commit()
        metric_id = metric.id

        # the XOR check: neither source, or both sources, are refused
        line_input = (
            (
                await s.execute(
                    select(FinancialMetricInput.statement_line_id)
                    .where(FinancialMetricInput.metric_id == metric_id)
                    .where(FinancialMetricInput.statement_line_id.is_not(None))
                )
            )
            .scalars()
            .first()
        )
        assert line_input is not None
        for fact_id, line_id in ((None, None), (fact.id, line_input)):
            s.add(
                FinancialMetricInput(
                    metric_id=metric_id,
                    fact_id=fact_id,
                    statement_line_id=line_id,
                    input_role=f"bad-{uuid.uuid4().hex[:6]}",
                )
            )
            with pytest.raises(IntegrityError):
                await s.flush()
            await s.rollback()

    cfg = Config("alembic.ini")
    try:
        await asyncio.to_thread(command.downgrade, cfg, "022")
        async with db_engine.connect() as conn:
            roles = (
                await conn.execute(
                    text(
                        "SELECT input_role, fact_id FROM financial_metric_inputs "
                        "WHERE metric_id = :m"
                    ),
                    {"m": metric_id},
                )
            ).all()
            nullable = (
                await conn.execute(
                    text(
                        "SELECT is_nullable FROM information_schema.columns "
                        "WHERE table_name = 'financial_metric_inputs' AND column_name = 'fact_id'"
                    )
                )
            ).scalar_one()
        assert [r[0] for r in roles] == ["legacy"]  # statement-line-only inputs were dropped
        assert roles[0][1] is not None
        assert nullable == "NO"
    finally:
        await asyncio.to_thread(command.upgrade, cfg, "head")
        await _purge_committed([company_id])


# --- robustness: degenerate inputs, batch surfaces, auth, replacement semantics ---------------


async def test_degenerate_statement_values_never_500_or_zero_fill(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session, industry="Software")
    degenerate = dict(FULL_YEAR)
    degenerate.update(
        {
            "revenue": Decimal("0"),
            "total_equity": Decimal("-100"),
            "shares_outstanding": Decimal("0"),
            "weighted_avg_shares_basic": Decimal("0"),
            "total_assets": Decimal("0"),
            "current_liabilities": Decimal("0"),
        }
    )
    await seed_year(db_session, company, 2023, dict(FULL_YEAR))
    await seed_year(db_session, company, 2024, degenerate)
    await seed_prices(db_session, company, bars=30)
    paths = _paths(company)
    for name, path in paths.items():
        response = await client.get(path)
        assert response.status_code == 200, (name, response.text[:200])
    metrics = {
        r["metric_code"]: r
        for r in (await client.get(f"{paths['metrics']}?fiscal_year=2024")).json()
    }
    for code in (
        "gross_margin",
        "net_margin",
        "operating_margin",
        "operating_cash_flow_margin",
        "book_value_per_share",
        "eps",
        "current_ratio",
        "debt_to_assets",
    ):
        row = metrics[code]
        assert row["status"] != "AVAILABLE" or row["value"] is not None, code
        if row["status"] != "AVAILABLE":
            assert row["value"] is None, (code, row["value"])
            assert row["reason"], code
    shariah = (await client.get(paths["screening"])).json()
    ratio_rules = [r for r in shariah["rule_results"] if r["rule_name"].endswith("_ratio")]
    assert all(r["value"] is None for r in ratio_rules if r["verdict"] == "INSUFFICIENT_DATA")
    fair = (await client.get(paths["fair_value"])).json()
    assert fair["fair_value"]["value"] is None or Decimal(fair["fair_value"]["value"]) > 0


async def test_batch_surfaces_never_compute(client: AsyncClient, db_session: AsyncSession) -> None:
    company = await _two_year_company(db_session)
    with write_statements() as writes:
        for path in (
            "/api/screening/companies",
            "/api/stance/radar",
            f"/api/companies/overview?tickers={company.ticker}",
            "/api/signals",
            "/api/signals/coverage",
            f"/api/data-quality/companies/{company.id}",
            f"/api/statements/companies/{company.ticker}/statements",
        ):
            response = await client.get(path)
            assert response.status_code in (200, 404), (path, response.status_code)
    compute_writes = [w for w in writes if "company_compute_state" in w]
    assert compute_writes == []
    assert await _states(db_session, company) == {}


async def test_computed_gets_require_the_token_and_do_not_compute_anonymously(
    anon_client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await _two_year_company(db_session)
    for name, path in _paths(company).items():
        response = await anon_client.get(path)
        assert response.status_code in (401, 403), (name, response.status_code)
    assert await _states(db_session, company) == {}


async def test_period_detail_serves_statement_line_provenance(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await _two_year_company(db_session, bars=0)
    rows = (
        await client.get(f"{_paths(company)['metrics']}?metric_code=roe&fiscal_year=2024")
    ).json()
    period_id = rows[0]["period_id"]
    listing = await client.get(f"{_paths(company)['metrics']}/periods/{period_id}")
    assert listing.status_code == 200 and listing.json()
    detail = await client.get(f"{_paths(company)['metrics']}/periods/{period_id}/roe")
    assert detail.status_code == 200
    body = detail.json()
    assert body["provenance"] and all("statement_line_id" in p for p in body["provenance"])
    assert all("fact_id" not in p for p in body["provenance"])
    missing = await client.get(f"{_paths(company)['metrics']}/periods/{period_id}/not_a_metric")
    assert missing.status_code == 404
    bad = await client.get(f"{_paths(company)['metrics']}?fiscal_year=abc")
    assert bad.status_code == 422


async def test_recompute_replaces_rows_instead_of_accumulating(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from app.models.technical import TechnicalIndicator

    company = await _two_year_company(db_session)
    paths = _paths(company)
    for name in ("metrics", "technical"):
        assert (await client.get(paths[name])).status_code == 200

    async def counts() -> tuple[int, int, int]:
        metrics = (
            await db_session.execute(
                select(func.count())
                .select_from(FinancialMetric)
                .where(FinancialMetric.company_id == company.id)
            )
        ).scalar_one()
        distinct = (
            await db_session.execute(
                select(
                    func.count(
                        func.distinct(
                            FinancialMetric.period_id.op("||")(FinancialMetric.metric_code)
                        )
                    )
                ).where(FinancialMetric.company_id == company.id)
            )
        ).scalar_one()
        technical = (
            await db_session.execute(
                select(func.count())
                .select_from(TechnicalIndicator)
                .where(TechnicalIndicator.company_id == company.id)
            )
        ).scalar_one()
        return metrics, distinct, technical

    first = await counts()
    for _ in range(3):  # three further input changes, each forcing a recompute
        await seed_year(
            db_session,
            company,
            2024,
            {"revenue": Decimal(str(1000 + _ + 1))},
            tier="filing",
            published=date(2025, 3, 1 + _),
        )
        existing = (
            await db_session.execute(
                select(func.max(rc.DailyPrice.date)).where(rc.DailyPrice.company_id == company.id)
            )
        ).scalar_one()
        source_id = (
            await db_session.execute(
                select(rc.DailyPrice.source_id)
                .where(rc.DailyPrice.company_id == company.id)
                .limit(1)
            )
        ).scalar_one()
        db_session.add(
            rc.DailyPrice(
                id=uuid.uuid4(),
                company_id=company.id,
                date=existing + timedelta(days=1),
                open=Decimal("40"),
                high=Decimal("41"),
                low=Decimal("39"),
                close=Decimal("40"),
                volume=10,
                source_id=source_id,
            )
        )
        await db_session.flush()
        for name in ("metrics", "technical"):
            assert (await client.get(paths[name])).status_code == 200
        assert await counts() == first


async def test_fair_value_snapshot_is_not_overwritten_by_thesis_or_stance_reads(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_assumptions(db_session)
    company = await _two_year_company(db_session)
    paths = _paths(company)
    before = (await client.get(paths["fair_value"])).json()
    assert before["fair_value"]["status"] == "AVAILABLE"
    for name in ("thesis", "stance", "score"):
        assert (await client.get(paths[name])).status_code == 200
    after = (await client.get(paths["fair_value"])).json()
    assert after == before
