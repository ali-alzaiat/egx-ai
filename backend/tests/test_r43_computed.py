"""R43: statement-line bridge, computed-on-read engines and the recompute service.

Every number is a SYNTHETIC test value seeded by the test itself.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import func, select

from app.metrics.definitions import MetricStatus
from app.metrics.service import MetricService
from app.models.compute import ComputeState
from app.models.metrics import FinancialMetric, FinancialMetricInput
from app.models.screening import ScreeningRuleResultDB
from app.models.statements import ExtStatus
from app.services import recompute as rc
from app.services.recompute import Engine, RecomputeService, Trigger
from app.statements import bridge
from app.statements.bridge import load_company_statements
from app.statements.vendor_import import ImportSummary, import_payload, vendor_periods
from statement_seed import FULL_YEAR, make_company, seed_prices, seed_year

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.market import Company


async def _two_years(db: AsyncSession, company: Company, **overrides: Decimal) -> None:
    prior = dict(FULL_YEAR)
    prior.update(
        {"revenue": Decimal("800"), "net_income": Decimal("160"),
         "total_equity": Decimal("900"), "total_assets": Decimal("1800")}
    )
    latest = dict(FULL_YEAR)
    latest.update(overrides)
    await seed_year(db, company, 2023, prior)
    await seed_year(db, company, 2024, latest)


# --- M1a: vendor map 1.1 ------------------------------------------------------


class TestVendorMap11:
    def test_new_codes_and_bank_fallback_precedence(self, vendor_payload: Any) -> None:
        payload = vendor_payload("R43V")
        income = payload["statements"]["income"]["financialData"]
        income["interestIncome"] = [None, 5, None]
        income["interestIncomeTotalBank"] = [1, 7, 9]
        income["sharesBasic"] = [1, 100, 90]
        payload["statements"]["balance"]["financialData"]["sharesOutTotalCommon"] = [1, 110, 95]
        periods = {p.fiscal_year: p for p in vendor_periods(payload)}
        by_code = {
            fy: {c.ontology_code: c.value for c in p.candidates} for fy, p in periods.items()
        }
        # interestIncome wins when present; the bank field fills only its gaps.
        assert by_code[2025]["interest_income"] == Decimal("5")
        assert by_code[2024]["interest_income"] == Decimal("9")
        assert by_code[2025]["weighted_avg_shares_basic"] == Decimal("100")
        assert by_code[2025]["shares_outstanding"] == Decimal("110")
        codes_2025 = [c.ontology_code for c in periods[2025].candidates]
        assert codes_2025.count("interest_income") == 1

    async def test_negative_share_count_is_rejected(
        self, db_session: AsyncSession, vendor_payload: Any
    ) -> None:
        company = await make_company(db_session)
        payload = vendor_payload(company.ticker)
        payload["statements"]["income"]["financialData"]["sharesBasic"] = [1, -100, 90]
        summary = ImportSummary()
        await import_payload(db_session, payload, summary)
        assert summary.company_ids == [company.id]
        rows = await load_company_statements(db_session, company.id)
        fy2025 = next(p for p in rows.periods if p.fiscal_year == 2025)
        assert fy2025.get("weighted_avg_shares_basic") is None  # rejected, never used

    async def test_unit_served_on_statements(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        company = await make_company(db_session)
        await seed_year(db_session, company, 2024, FULL_YEAR)
        body = (
            await client.get(f"/api/statements/companies/{company.ticker}/statements")
        ).json()
        balance = {ln["ontology_code"]: ln for ln in body["periods"][0]["balance"]}
        income = {ln["ontology_code"]: ln for ln in body["periods"][0]["income"]}
        assert balance["shares_outstanding"]["unit"] == "shares"
        assert income["eps"]["unit"] == "currency_per_share"
        assert income["revenue"]["unit"] == "currency"


# --- M1b: bridge ---------------------------------------------------------------


class TestBridge:
    async def test_derived_values_and_denominator_gaps(self, db_session: AsyncSession) -> None:
        company = await make_company(db_session)
        await seed_year(db_session, company, 2024, FULL_YEAR)
        p = (await load_company_statements(db_session, company.id)).latest()
        assert bridge.eps(p).value == Decimal("2")
        assert bridge.eps(p).derivation == "net_income / weighted_avg_shares_basic"
        assert bridge.book_value_per_share(p).value == Decimal("11")
        assert bridge.revenue_per_share(p).value == Decimal("10")
        assert bridge.long_term_liabilities(p).value == Decimal("500")
        assert bridge.capex_magnitude(p).value == Decimal("50")
        assert bridge.free_cash_flow(p).value == Decimal("250")
        assert bridge.dps(p).value == Decimal("0.8")

    @pytest.mark.parametrize(
        ("shares", "reason"),
        [
            (Decimal("0"), "zero denominator: shares_outstanding (FY2024)"),
            (Decimal("-5"), "negative denominator: shares_outstanding (FY2024)"),
            (None, "missing statement line: shares_outstanding (FY2024)"),
        ],
    )
    async def test_bad_denominator_is_insufficient_never_zero(
        self, db_session: AsyncSession, shares: Decimal | None, reason: str
    ) -> None:
        company = await make_company(db_session)
        values = dict(FULL_YEAR)
        values.pop("shares_outstanding")
        if shares is not None:
            values["shares_outstanding"] = shares
        await seed_year(db_session, company, 2024, values)
        p = (await load_company_statements(db_session, company.id)).latest()
        for fn in (bridge.book_value_per_share, bridge.revenue_per_share, bridge.dps):
            resolved = fn(p)
            assert resolved.value is None
            assert resolved.status == "INSUFFICIENT_DATA"
            assert resolved.reason == reason
            assert resolved.missing_input == "shares_outstanding"

    async def test_missing_numerator_names_the_line(self, db_session: AsyncSession) -> None:
        company = await make_company(db_session)
        values = dict(FULL_YEAR)
        values.pop("dividends_paid")
        values.pop("capex")
        await seed_year(db_session, company, 2024, values)
        p = (await load_company_statements(db_session, company.id)).latest()
        assert bridge.dps(p).reason == "missing statement line: dividends_paid (FY2024)"
        assert bridge.free_cash_flow(p).missing_input == "capex"

    async def test_no_borrowing_from_older_period(self, db_session: AsyncSession) -> None:
        company = await make_company(db_session)
        await seed_year(db_session, company, 2023, {"revenue": Decimal("1"), "cfo": Decimal("9")})
        await seed_year(db_session, company, 2024, {"revenue": Decimal("2")})
        st = await load_company_statements(db_session, company.id)
        latest = st.latest()
        assert latest is not None and latest.fiscal_year == 2024
        assert bridge.line(latest, "cfo").value is None  # FY2023 cfo is not borrowed
        assert st.prior(latest) is not None
        assert [lv.value for lv in st.series("revenue")] == [Decimal("1"), Decimal("2")]

    async def test_filing_beats_vendor_and_tier(self, db_session: AsyncSession) -> None:
        company = await make_company(db_session)
        await seed_year(db_session, company, 2024, {"revenue": Decimal("100")})
        await seed_year(
            db_session, company, 2024, {"revenue": Decimal("120")}, tier="filing",
            published=date(2025, 3, 1),
        )
        p = (await load_company_statements(db_session, company.id)).latest()
        lv = p.get("revenue")
        assert lv is not None and lv.value == Decimal("120") and lv.source_tier == "filing"
        assert bridge.tier_of([lv]) == "filing"
        assert bridge.provenance(lv)["provisional"] is False
        vendor_only = p.get("revenue")
        assert bridge.tier_of([]) is None
        assert vendor_only is not None


# --- M1c: metrics ---------------------------------------------------------------


class TestMetricsFromStatements:
    async def _outputs(self, db: AsyncSession, company: Company) -> dict[tuple[int, str], Any]:
        st = await load_company_statements(db, company.id)
        return {
            (o.fiscal_year, o.metric_code): o
            for o in MetricService(db).calculate_from_statements(st)
        }

    async def test_growth_receives_current_year_value(self, db_session: AsyncSession) -> None:
        """Regression: growth metrics were always INVALID (no current-year kwarg)."""
        company = await make_company(db_session)
        await _two_years(db_session, company)
        out = await self._outputs(db_session, company)
        growth = out[(2024, "revenue_growth_yoy")]
        assert growth.status == MetricStatus.AVAILABLE
        assert growth.value == Decimal("25.00")  # 1000 vs 800
        assert out[(2024, "eps_growth_yoy")].value == Decimal("25.00")  # 2.0 vs 1.6
        assert out[(2023, "revenue_growth_yoy")].reason == (
            "no prior period: FY2022 has no revenue"
        )

    async def test_roa_uses_total_assets_and_averages(self, db_session: AsyncSession) -> None:
        """Regression: ROA read current assets and never averaged."""
        company = await make_company(db_session)
        await _two_years(db_session, company)
        out = await self._outputs(db_session, company)
        # 200 / ((2000 + 1800) / 2) = 10.526...% -> 10.53 (rounded after x100,
        # formula v2); spot current assets (800) would give 25.00.
        # ROE 200 / ((1100 + 900) / 2) = 20%.
        assert out[(2024, "roa")].value == Decimal("10.53")
        assert out[(2024, "roe")].value == Decimal("20.00")
        roles = {role for role, _ in out[(2024, "roa")].inputs}
        assert roles == {"net_income", "current_assets", "previous_assets"}

    async def test_missing_line_names_it_never_zero(self, db_session: AsyncSession) -> None:
        company = await make_company(db_session)
        values = dict(FULL_YEAR)
        values.pop("gross_profit")
        await seed_year(db_session, company, 2024, values)
        out = await self._outputs(db_session, company)
        gm = out[(2024, "gross_margin")]
        assert gm.value is None
        assert gm.status == MetricStatus.INSUFFICIENT_DATA
        assert gm.reason == "missing statement line: gross_profit (FY2024)"

    async def test_get_serves_provenance_and_persists_inputs(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        company = await make_company(db_session)
        await _two_years(db_session, company)
        rows = (await client.get(f"/api/metrics/companies/{company.id}")).json()
        roe = next(r for r in rows if r["metric_code"] == "roe" and r["fiscal_year"] == 2024)
        assert roe["period_end"] == "2024-12-31"
        assert roe["provisional"] is True
        assert roe["source_tier"] == "vendor"
        assert roe["methodology_version"] == "metrics-stmt-1.1"
        assert roe["compute_status"] == "ok"
        assert {i["input_role"] for i in roe["inputs"]} == {
            "net_income", "current_equity", "previous_equity",
        }
        assert all(i["provisional"] is True for i in roe["inputs"])
        count = (
            await db_session.execute(
                select(func.count())
                .select_from(FinancialMetricInput)
                .join(FinancialMetric, FinancialMetric.id == FinancialMetricInput.metric_id)
                .where(FinancialMetric.company_id == company.id)
                .where(FinancialMetricInput.statement_line_id.is_not(None))
            )
        ).scalar_one()
        assert count > 0


# --- Shariah rule replacement ------------------------------------------------------


async def test_rescreen_replaces_rule_rows(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session, industry="Software")
    await seed_year(db_session, company, 2024, FULL_YEAR)
    service = RecomputeService(db_session)
    await service.recompute_company(company.id, Trigger.BACKFILL, [Engine.SHARIAH], force=True)
    await service.recompute_company(company.id, Trigger.BACKFILL, [Engine.SHARIAH], force=True)
    body = (await client.get(f"/api/screening/companies/{company.id}")).json()
    assert len(body["rule_results"]) == 4
    count = (
        await db_session.execute(select(func.count()).select_from(ScreeningRuleResultDB).where(
            ScreeningRuleResultDB.screening_result_id == uuid.UUID(body["id"])
        ))
    ).scalar_one()
    assert count == 4


# --- AC-2: GETs alone produce computed payloads -------------------------------------


async def test_get_only_payloads_for_seeded_company(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session, industry="Software")
    await _two_years(db_session, company)
    last_bar = await seed_prices(db_session, company, bars=210)
    cid = company.id
    paths = {
        "metrics": f"/api/metrics/companies/{cid}",
        "fair_value": f"/api/valuation/companies/{cid}/fair-value",
        "score": f"/api/scores/companies/{cid}",
        "screening": f"/api/screening/companies/{cid}",
        "technical": f"/api/technical/companies/{cid}",
        "thesis": f"/api/theses/companies/{cid}",
    }
    for name, path in paths.items():
        response = await client.get(path)
        assert response.status_code == 200, name
        body = response.json()
        first = body[0] if isinstance(body, list) else body
        assert first["calculated_at"], name
        assert first["methodology_version"], name
        assert first["compute_status"] == "ok", name
    technical = (await client.get(paths["technical"])).json()
    assert len(technical) == len({r["indicator_type"] for r in technical})  # one set only
    assert technical[0]["price_as_of"] == last_bar.isoformat()
    assert technical[0]["methodology_version"] == "technical-1.0"
    available = [r for r in technical if r["status"] == "AVAILABLE"]
    assert available, "200+ bars give real indicators"
    score = (await client.get(paths["score"])).json()
    assert score["assessment"] is not None


# --- AC-5: statement hooks refresh only the affected company --------------------------


async def test_manual_filing_recomputes_that_company_only(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    target = await make_company(db_session)
    other = await make_company(db_session)
    response = await client.post(
        "/api/statements/manual-filings",
        json={
            "ticker": target.ticker,
            "fiscal_year": 2024,
            "period_end": "2024-12-31",
            "document_url": "https://www.egx.com.eg/test/filing.pdf",
            "publication_date": "2025-03-01",
            "lines": [
                {"code": "revenue", "value": "1000", "page": "4"},
                {"code": "net_income", "value": "200", "page": "4"},
            ],
        },
    )
    assert response.status_code == 200
    recompute = response.json()["recompute"]
    assert recompute["trigger"] == "statement_import"
    statuses = {o["engine"]: o["status"] for o in recompute["outcomes"]}
    for engine in ("metrics", "shariah", "fair_value", "score", "thesis"):
        assert statuses[engine] == "computed"
    assert "technical" not in statuses
    states = (
        await db_session.execute(
            select(ComputeState.engine, ComputeState.trigger).where(
                ComputeState.company_id == target.id
            )
        )
    ).all()
    assert ("metrics", "statement_import") in states
    others = (
        await db_session.execute(
            select(func.count()).select_from(ComputeState).where(
                ComputeState.company_id == other.id
            )
        )
    ).scalar_one()
    assert others == 0


async def test_approve_triggers_recompute(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session)
    rows = await seed_year(
        db_session, company, 2024, {"revenue": Decimal("10")},
        tier="filing", status=ExtStatus.extraction_candidate,
    )
    line_id = rows["revenue"].id
    response = await client.post(f"/api/statements/lines/{line_id}/approve")
    assert response.status_code == 200
    statuses = {o["engine"]: o["status"] for o in response.json()["recompute"]["outcomes"]}
    assert statuses["metrics"] == "computed"


async def test_after_statement_import_hook(db_session: AsyncSession) -> None:
    company = await make_company(db_session)
    await seed_year(db_session, company, 2024, FULL_YEAR)

    @asynccontextmanager
    async def factory() -> AsyncIterator[AsyncSession]:
        yield db_session

    report = await rc.after_statement_import([company.id], session_factory=factory)
    assert report.companies == 1
    assert report.computed["metrics"] == 1
    assert "technical" not in report.computed
    again = await rc.after_statement_import([company.id], session_factory=factory)
    assert again.computed == {}
    assert again.fresh >= 7


# --- AC-6: price-sync hook per-step counts -------------------------------------------


async def test_after_price_sync_reports_per_step_counts(db_session: AsyncSession) -> None:
    company = await make_company(db_session)
    await seed_year(db_session, company, 2024, FULL_YEAR)
    await seed_prices(db_session, company, bars=40)

    @asynccontextmanager
    async def factory() -> AsyncIterator[AsyncSession]:
        yield db_session

    result = (await rc.after_price_sync([company.id], session_factory=factory)).as_dict()
    assert result["technical"] == {"computed": 1, "fresh": 0, "failed": 0}
    for step in ("fair_value", "score", "thesis"):
        assert result[step]["computed"] == 1
    assert set(result["signals"]) == {"ran", "as_of", "scored", "error"}


# --- AC-7 / failure isolation --------------------------------------------------------


async def test_failed_engine_marks_dependents_and_is_not_retried(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    company = await make_company(db_session)
    calls = {"n": 0}

    async def boom(_ctx: Any) -> Any:
        calls["n"] += 1
        raise ValueError("simulated metrics failure")

    monkeypatch.setitem(rc.RUNNERS, Engine.METRICS, boom)
    service = RecomputeService(db_session)
    report = await service.recompute_company(company.id, Trigger.BACKFILL)
    outcome = {o.engine: o for o in report.outcomes}
    assert outcome[Engine.METRICS].error == "ValueError: simulated metrics failure"
    assert outcome[Engine.FAIR_VALUE].error == "upstream failed: metrics"
    assert outcome[Engine.SHARIAH].status == "computed"  # independent engine still runs
    # The failed fingerprint is stored: a second pass does not retry it.
    await service.ensure_fresh(company.id, Engine.METRICS)
    assert calls["n"] == 1
    state = await service.state(company.id, Engine.METRICS)
    assert state is not None and state.status == "failed"


async def test_concurrent_ensure_fresh_computes_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Advisory lock + re-check: two parallel first views run the engine once."""
    from sqlalchemy.ext.asyncio import AsyncSession as Session

    from app.db.session import engine as db_engine
    from app.models.market import Company as CompanyModel

    async with Session(db_engine, expire_on_commit=False) as setup:
        company = await make_company(setup)
        await setup.commit()
    calls = {"n": 0}
    original = rc.RUNNERS[Engine.DQ_PH]

    async def slow(ctx: Any) -> Any:
        calls["n"] += 1
        await asyncio.sleep(0.3)
        return await original(ctx)

    monkeypatch.setitem(rc.RUNNERS, Engine.DQ_PH, slow)

    async def view() -> None:
        async with Session(db_engine, expire_on_commit=False) as session:
            await RecomputeService(session).ensure_fresh(company.id, Engine.DQ_PH)
            await session.commit()

    try:
        await asyncio.gather(view(), view())
        assert calls["n"] == 1
    finally:
        async with Session(db_engine) as cleanup:
            row = await cleanup.get(CompanyModel, company.id)
            if row is not None:
                await cleanup.delete(row)
            await cleanup.commit()


async def test_upload_auto_parse_never_fails_upload(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session)
    response = await client.post(
        "/api/disclosures/upload",
        data={"company_id": str(company.id), "report_date": "2025-03-31", "filing_type": "Q"},
        files={"file": ("g.pdf", b"%PDF-1.4 garbage-body", "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert "parse" in body and body["parse"] is not None
    skipped = await client.post(
        "/api/disclosures/upload",
        data={
            "company_id": str(company.id), "report_date": "2025-06-30",
            "filing_type": "Q", "auto_parse": "false",
        },
        files={"file": ("h.pdf", b"%PDF-1.4 other-body", "application/pdf")},
    )
    assert skipped.json()["parse"] is None
