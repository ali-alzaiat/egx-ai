"""R43 review fixes (analyst F1-F14, qa-api F1-F4) and owner rulings M3-M5.

Every number is a SYNTHETIC value seeded by the test or an exact arithmetic
identity; nothing touches the dev database.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.metrics.definitions import ALL_METRICS, MetricStatus
from app.metrics.engine import (
    calculate_debt_to_equity,
    calculate_eps_growth_yoy,
    calculate_free_cash_flow_margin,
    calculate_gross_margin,
    calculate_net_income_growth_yoy,
    calculate_net_margin,
    calculate_operating_margin,
    calculate_revenue_growth_yoy,
    calculate_roa,
    calculate_roe,
)
from app.metrics.service import MetricService
from app.models.statements import FinancialStatementLine
from app.repositories.industry import IndustryRepository
from app.statements.bridge import load_company_statements
from app.statements.vendor_import import (
    VENDOR_MAPPING_VERSION,
    ImportSummary,
    import_payload,
    vendor_periods,
)
from app.valuation.assumption_snapshot import SNAPSHOT, load_snapshot
from app.valuation.assumptions import MARKET_SCOPE, record_assumption, resolve_assumptions
from app.valuation.constants import VALUATION_METHODOLOGY_VERSION
from app.valuation.models import (
    ValuationStatus,
    calculate_affo_2stage,
    calculate_fcfe_2stage,
)
from statement_seed import FULL_YEAR, make_company, seed_prices, seed_year

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

D = Decimal


# --- F1 / F2: percent metrics are rounded after x100 -----------------------------------


class TestPercentRounding:
    def test_margins_keep_two_decimals(self) -> None:
        # SWDY FY2025 (vendor): 15,257,140,146 / 281,049,081,719 = 5.4286 %
        assert calculate_net_margin(D("15257140146"), D("281049081719")).value == D("5.43")
        assert calculate_gross_margin(D("40762108187"), D("281049081719")).value == D("14.50")
        assert calculate_operating_margin(D("25207312588"), D("281049081719")).value == D("8.97")

    def test_fcf_margin_keeps_two_decimals(self) -> None:
        # (15,456,338,832 - 13,112,049,791) / 281,049,081,719 = 0.8341 %
        result = calculate_free_cash_flow_margin(
            D("15456338832"), D("13112049791"), D("281049081719")
        )
        assert result.value == D("0.83")

    def test_growth_keeps_two_decimals(self) -> None:
        assert calculate_revenue_growth_yoy(D("200"), D("190")).value == D("5.26")
        assert calculate_net_income_growth_yoy(D("128541616"), D("114754320")).value == D("12.01")
        assert calculate_eps_growth_yoy(D("2"), D("1.6")).value == D("25.00")

    def test_roa_roe_use_average_and_two_decimals(self) -> None:
        # COMI FY2025 (vendor): ROA 61.634bn / avg(1,442.494bn; 1,214.973bn) = 4.6386 %
        roa = calculate_roa(
            D("61634295000"), D("1442494120000"), D("1214973261000")
        )
        assert roa.value == D("4.64")
        roe = calculate_roe(D("61634295000"), D("231486342000"), D("152636277000"))
        assert roe.value == D("32.09")
        assert calculate_roa(D("200"), D("2000"), D("1800")).value == D("10.53")

    def test_rounding_is_half_up_on_the_percentage(self) -> None:
        # 1.005 % -> 1.01 (half up), not banker's rounding and not pre-rounded
        assert calculate_net_margin(D("1.005"), D("100")).value == D("1.01")

    def test_zero_and_negative_inputs(self) -> None:
        assert calculate_net_margin(D("0"), D("100")).value == D("0.00")
        assert calculate_net_margin(D("-10"), D("100")).value == D("-10.00")
        assert calculate_net_margin(D("10"), D("0")).status == MetricStatus.INVALID
        assert calculate_revenue_growth_yoy(D("10"), D("0")).status == MetricStatus.INVALID
        assert calculate_revenue_growth_yoy(D("0"), D("100")).value == D("-100.00")


# --- M3 / F10: strict average, no negative capital ---------------------------------------


class TestAverageReturns:
    def test_no_prior_period_is_insufficient_not_spot(self) -> None:
        for result in (
            calculate_roe(D("100"), D("1000"), None),
            calculate_roa(D("100"), D("1000"), None),
        ):
            assert result.status == MetricStatus.INSUFFICIENT_DATA
            assert result.value is None
            assert "Previous comparable period" in (result.reason or "")

    def test_negative_average_equity_is_insufficient_with_reason(self) -> None:
        # A loss on negative equity would otherwise print a positive ROE.
        result = calculate_roe(D("-50"), D("-100"), D("-300"))
        assert result.status == MetricStatus.INSUFFICIENT_DATA
        assert result.value is None
        assert "negative" in (result.reason or "")

    def test_zero_average_is_invalid_and_positive_average_with_one_negative_year_works(
        self,
    ) -> None:
        assert calculate_roe(D("10"), D("100"), D("-100")).status == MetricStatus.INVALID
        assert calculate_roe(D("10"), D("300"), D("-100")).value == D("10.00")

    def test_debt_to_equity_with_negative_equity_is_insufficient(self) -> None:
        result = calculate_debt_to_equity(D("500"), D("-100"))
        assert result.status == MetricStatus.INSUFFICIENT_DATA
        assert result.value is None
        assert "negative" in (result.reason or "")
        assert calculate_debt_to_equity(D("500"), D("0")).status == MetricStatus.INVALID
        assert calculate_debt_to_equity(D("500"), D("1000")).value == D("0.5000")

    def test_changed_formulas_bumped_their_versions(self) -> None:
        for code in (
            "revenue_growth_yoy", "net_income_growth_yoy", "eps_growth_yoy", "gross_margin",
            "operating_margin", "net_margin", "roe", "roa", "debt_to_equity", "quick_ratio",
            "operating_cash_flow_margin", "free_cash_flow_margin",
        ):
            assert ALL_METRICS[code].formula_version == 2, code
        assert ALL_METRICS["current_ratio"].formula_version == 1


# --- F11: quick ratio needs the inventory line ---------------------------------------------


async def test_quick_ratio_without_inventory_line_is_insufficient_naming_it(
    db_session: AsyncSession,
) -> None:
    company = await make_company(db_session)
    values = dict(FULL_YEAR)
    values.pop("inventory")
    await seed_year(db_session, company, 2024, values)
    st = await load_company_statements(db_session, company.id)
    out = {o.metric_code: o for o in MetricService(db_session).calculate_from_statements(st)}
    quick = out["quick_ratio"]
    assert quick.status == MetricStatus.INSUFFICIENT_DATA
    assert quick.value is None
    assert "inventory" in (quick.reason or "")
    # current ratio is unaffected: 800 / 400
    assert out["current_ratio"].value == D("2.0000")


async def test_quick_ratio_with_inventory_subtracts_it(db_session: AsyncSession) -> None:
    company = await make_company(db_session)
    await seed_year(db_session, company, 2024, FULL_YEAR)
    st = await load_company_statements(db_session, company.id)
    out = {o.metric_code: o for o in MetricService(db_session).calculate_from_statements(st)}
    assert out["quick_ratio"].value == D("1.7500")  # (800 - 100) / 400


# --- F9: the latest period never falls back to an older one -------------------------------


async def test_latest_metric_values_never_borrow_an_older_period(
    db_session: AsyncSession,
) -> None:
    company = await make_company(db_session)
    older = dict(FULL_YEAR)
    latest = dict(FULL_YEAR)
    latest.pop("gross_profit")
    await seed_year(db_session, company, 2023, older)
    await seed_year(db_session, company, 2024, latest)
    st = await load_company_statements(db_session, company.id)
    await MetricService(db_session).compute_and_persist(st)

    repo = IndustryRepository(db_session)
    gross = await repo.latest_metric_values([company.id], "gross_margin")
    assert company.id not in gross  # FY2024 has no gross profit; FY2023's 40.00 is not used
    net = await repo.latest_metric_values([company.id], "net_margin")
    assert D(net[company.id][0] or "0") == D("20")


# --- F12: vendor equity fallback --------------------------------------------------------------


class TestVendorEquityFallback:
    @staticmethod
    def _total_equity(payload: dict[str, Any]) -> dict[int, Decimal]:
        return {
            p.fiscal_year: next(
                c.value for c in p.candidates if c.ontology_code == "total_equity"
            )
            for p in vendor_periods(payload)
            if any(c.ontology_code == "total_equity" for c in p.candidates)
        }

    def test_equity_maps_when_common_equity_and_minority_are_absent(
        self, vendor_payload: Any
    ) -> None:
        payload = vendor_payload("R45EQ")
        data = payload["statements"]["balance"]["financialData"]
        del data["totalCommonEquity"]
        del data["minorityInterestBS"]
        assert self._total_equity(payload) == {2025: D("600"), 2024: D("500")}

    def test_zero_minority_counts_as_none(self, vendor_payload: Any) -> None:
        payload = vendor_payload("R45EQ")
        data = payload["statements"]["balance"]["financialData"]
        del data["totalCommonEquity"]
        data["minorityInterestBS"] = [0, 0, None]
        assert self._total_equity(payload) == {2025: D("600"), 2024: D("500")}

    def test_non_zero_minority_leaves_equity_unmapped(self, vendor_payload: Any) -> None:
        payload = vendor_payload("R45EQ")
        data = payload["statements"]["balance"]["financialData"]
        del data["totalCommonEquity"]
        assert self._total_equity(payload) == {}  # minority 20 in both years

    def test_common_equity_still_wins(self, vendor_payload: Any) -> None:
        payload = vendor_payload("R45EQ")
        assert self._total_equity(payload) == {2025: D("580"), 2024: D("480")}

    def test_mapping_version_bumped(self) -> None:
        assert VENDOR_MAPPING_VERSION == "stockanalysis-map-1.2"


# --- QA F4: an identical re-import changes nothing ---------------------------------------------


async def test_identical_reimport_keeps_line_ids(
    db_session: AsyncSession, vendor_payload: Any
) -> None:
    company = await make_company(db_session)
    payload = vendor_payload(company.ticker)
    await import_payload(db_session, payload, ImportSummary())
    first = {
        (r.id, r.created_at)
        for r in (
            await db_session.execute(
                select(FinancialStatementLine).where(
                    FinancialStatementLine.company_id == company.id
                )
            )
        ).scalars()
    }
    assert first
    await import_payload(db_session, payload, ImportSummary())
    second = {
        (r.id, r.created_at)
        for r in (
            await db_session.execute(
                select(FinancialStatementLine).where(
                    FinancialStatementLine.company_id == company.id
                )
            )
        ).scalars()
    }
    assert second == first


async def test_changed_reimport_replaces_only_changed_lines(
    db_session: AsyncSession, vendor_payload: Any
) -> None:
    company = await make_company(db_session)
    payload = vendor_payload(company.ticker)
    await import_payload(db_session, payload, ImportSummary())

    async def lines() -> dict[tuple[str, date], Any]:
        rows = (
            await db_session.execute(
                select(FinancialStatementLine).where(
                    FinancialStatementLine.company_id == company.id
                )
            )
        ).scalars().all()
        return {(r.ontology_code, r.published_date or date.min): r for r in rows}

    before = {k: (v.id, v.value) for k, v in (await lines()).items()}
    payload["statements"]["income"]["financialData"]["revenue"] = [999, 1001, 800]
    await import_payload(db_session, payload, ImportSummary())
    after = {k: (v.id, v.value) for k, v in (await lines()).items()}
    changed = {k for k in before if before[k] != after.get(k)}
    revenue_rows = {k for k in changed if k[0] == "revenue"}
    assert revenue_rows, "the edited revenue value must be stored"
    unchanged = [k for k in before if k not in changed and k in after]
    assert unchanged, "untouched lines keep their ids"
    assert all(k[0] == "revenue" for k in changed)


# --- QA F3: the fair-value leg names the missing statement line --------------------------------


# (covered end to end by test_r43_qa_api.py, test_missing_cfo_with_sourced_assumptions_*)


# --- R44 (b) / R45 M5: sourced assumptions, computed rates, staleness ------------------------


async def _record(
    db: AsyncSession, key: str, value: str, *, age_days: int = 1, scope: str = MARKET_SCOPE
) -> None:
    await record_assumption(
        db,
        key=key,
        scope=scope,
        value=D(value),
        source_url="https://example.test/assumption",
        source_title="SYNTHETIC test assumption",
        as_of=date.today() - timedelta(days=age_days),
    )


async def test_discount_and_terminal_rates_are_computed_from_sourced_rows(
    db_session: AsyncSession,
) -> None:
    await _record(db_session, "risk_free_rate", "0.20")
    await _record(db_session, "equity_risk_premium", "0.04")
    await _record(db_session, "long_run_inflation", "0.05")
    resolved = await resolve_assumptions(db_session, "default")
    assert resolved.discount_rate == D("0.24")
    assert resolved.terminal_growth_rate == D("0.05")
    assert resolved.long_run_cost_of_equity is None
    assert "long_run_cost_of_equity" in resolved.missing
    computed = resolved.payload()["computed"]
    assert isinstance(computed, dict)
    assert D(computed["discount_rate"]) == D("0.24")
    assert resolved.provenance_of("discount_rate") is not None
    assert "risk_free_rate" in (resolved.provenance_of("discount_rate") or "")


async def test_a_missing_component_leaves_the_computed_rate_none(
    db_session: AsyncSession,
) -> None:
    await _record(db_session, "risk_free_rate", "0.20")
    resolved = await resolve_assumptions(db_session, "default")
    assert resolved.discount_rate is None
    assert resolved.provenance_of("discount_rate") is None
    assert resolved.terminal_growth_rate is None
    assert resolved.gap(["equity_risk_premium"]) == (
        f"no sourced equity_risk_premium in valuation assumptions {VALUATION_METHODOLOGY_VERSION}"
    )


async def test_yield_rows_go_stale_after_120_days_others_after_400(
    db_session: AsyncSession,
) -> None:
    await _record(db_session, "risk_free_rate", "0.20", age_days=121)
    await _record(db_session, "equity_risk_premium", "0.04", age_days=399)
    await _record(db_session, "long_run_inflation", "0.05", age_days=401)
    await _record(db_session, "long_run_cost_of_equity", "0.15", age_days=400)
    resolved = await resolve_assumptions(db_session, "default")
    assert set(resolved.stale) == {"risk_free_rate", "long_run_inflation"}
    assert resolved.stale["risk_free_rate"].startswith("stale assumption: risk_free_rate")
    assert resolved.discount_rate is None  # a stale yield is missing, not used
    assert resolved.terminal_growth_rate is None
    assert resolved.value("equity_risk_premium") == D("0.04")
    assert resolved.value("long_run_cost_of_equity") == D("0.15")  # exactly 400 days is fresh
    assert "stale assumption" in resolved.gap(["risk_free_rate"])
    stale_keys = [s["key"] for s in resolved.payload()["stale"]]  # type: ignore[attr-defined]
    assert stale_keys == ["risk_free_rate", "long_run_inflation"]


async def test_snapshot_loads_the_owner_ruled_values_idempotently(
    db_session: AsyncSession,
) -> None:
    assert await load_snapshot(db_session) == len(SNAPSHOT) == 5
    assert await load_snapshot(db_session) == 5  # idempotent
    resolved = await resolve_assumptions(db_session, "default", today=date(2026, 10, 24))
    assert resolved.value("risk_free_rate") == D("0.24128")
    assert resolved.value("equity_risk_premium") == D("0.0420")
    assert resolved.discount_rate == D("0.28328")  # 24.128 % + 4.20 %
    assert resolved.terminal_growth_rate == D("0.054")
    assert resolved.long_run_cost_of_equity == D("0.1751")
    assert resolved.value("nominal_gdp_growth") == D("0.1359")
    assert resolved.stale == {}
    assert all(
        item.source_url.startswith("http") and item.source_title and item.as_of
        for item in resolved.items.values()
    )
    # no relative-multiple targets: those legs stay INSUFFICIENT_DATA
    assert {"target_pe", "target_pb", "target_ps"} <= set(resolved.missing)


async def test_snapshot_rows_are_stale_a_year_later(db_session: AsyncSession) -> None:
    await load_snapshot(db_session)
    resolved = await resolve_assumptions(db_session, "default", today=date(2027, 12, 31))
    assert resolved.discount_rate is None
    assert set(resolved.stale) == {
        "risk_free_rate", "equity_risk_premium", "long_run_inflation",
        "long_run_cost_of_equity", "nominal_gdp_growth",
    }


# --- M5: faded terminal discount rate (pure) ------------------------------------------------


class TestFadedDiscountRate:
    ARGS: dict[str, Any] = {
        "growth_high": D("0"), "growth_stable": D("0"), "discount_rate": D("0.10"),
        "terminal_growth_rate": D("0"), "years_high": 1, "years_stable": 1,
        "shares_outstanding": D("1"),
    }

    def test_no_terminal_rate_keeps_a_single_rate(self) -> None:
        result = calculate_fcfe_2stage(D("100"), **self.ARGS)
        # 100/1.1 + 100/1.21 + (100/0.10)/1.21 = 1000.0000
        assert result.status == ValuationStatus.AVAILABLE
        assert abs(result.value - D("1000")) < D("0.001")  # type: ignore[operator]
        assert result.assumptions["terminal_discount_rate"] is None

    def test_terminal_value_uses_the_long_run_rate(self) -> None:
        result = calculate_fcfe_2stage(
            D("100"), terminal_discount_rate=D("0.05"), **self.ARGS
        )
        # year 1 at 10 %: 90.90909091; year 2 (stable stage) at 1.10 * 1.05: 86.58008658
        # terminal value 100 / 0.05 = 2000, discounted by 1.155: 1731.60173160
        assert result.status == ValuationStatus.AVAILABLE
        assert abs(result.value - D("1909.0909")) < D("0.001")  # type: ignore[operator]
        assert result.assumptions["terminal_discount_rate"] == "0.05"
        assert result.assumptions["discount_rate"] == "0.10"

    def test_affo_uses_the_same_fade(self) -> None:
        result = calculate_affo_2stage(
            D("100"), terminal_discount_rate=D("0.05"), **self.ARGS
        )
        assert result.status == ValuationStatus.AVAILABLE
        assert abs(result.value - D("1909.0909")) < D("0.001")  # type: ignore[operator]

    def test_long_run_rate_must_exceed_terminal_growth(self) -> None:
        args = dict(self.ARGS, terminal_growth_rate=D("0.06"))
        result = calculate_fcfe_2stage(
            D("100"), terminal_discount_rate=D("0.06"), **args
        )
        assert result.status == ValuationStatus.INVALID
        assert result.value is None
        assert "Long-run cost of equity" in (result.reason or "")

    def test_negative_fcf_stays_invalid(self) -> None:
        result = calculate_fcfe_2stage(
            D("-100"), terminal_discount_rate=D("0.05"), **self.ARGS
        )
        assert result.status == ValuationStatus.INVALID
        assert result.value is None


# --- M5 end to end: the intrinsic leg needs every sourced key ---------------------------------


async def _fair_value(client: AsyncClient, company_id: Any) -> dict[str, Any]:
    response = await client.get(f"/api/valuation/companies/{company_id}/fair-value")
    assert response.status_code == 200, response.text[:300]
    body: dict[str, Any] = response.json()
    return body


async def _fv_company(
    db: AsyncSession, *, years: tuple[int, ...] = (2021, 2022, 2023, 2024),
    start_revenue: str = "1000",
) -> Any:
    """Flat FULL_YEAR statements; the first year's revenue sets the 3-year CAGR."""
    company = await make_company(db, industry="Software")
    for year in years:
        values = dict(FULL_YEAR)
        if year == years[0]:
            values["revenue"] = D(start_revenue)
        await seed_year(db, company, year, values)
    await seed_prices(db, company, bars=30)
    return company


async def _record_all(db: AsyncSession, *, gdp: str | None = "0.1359") -> None:
    await _record(db, "risk_free_rate", "0.20")
    await _record(db, "equity_risk_premium", "0.04")
    await _record(db, "long_run_inflation", "0.05")
    await _record(db, "long_run_cost_of_equity", "0.15")
    if gdp is not None:
        await _record(db, "nominal_gdp_growth", gdp)


async def test_intrinsic_leg_names_the_missing_long_run_assumption(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _record(db_session, "risk_free_rate", "0.20")
    await _record(db_session, "equity_risk_premium", "0.04")
    await _record(db_session, "long_run_inflation", "0.05")
    await _record(db_session, "nominal_gdp_growth", "0.1359")
    company = await _fv_company(db_session)
    fair = await _fair_value(client, company.id)
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["value"] is None
    assert intrinsic["status"] == "INSUFFICIENT_DATA"
    assert intrinsic["reason"] == (
        f"no sourced long_run_cost_of_equity in valuation assumptions "
        f"{VALUATION_METHODOLOGY_VERSION}"
    )
    assert D(fair["assumptions"]["computed"]["discount_rate"]) == D("0.24")


async def test_stale_yield_names_the_stale_assumption(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _record(db_session, "risk_free_rate", "0.20", age_days=200)
    await _record(db_session, "equity_risk_premium", "0.04")
    await _record(db_session, "long_run_inflation", "0.05")
    await _record(db_session, "long_run_cost_of_equity", "0.15")
    await _record(db_session, "nominal_gdp_growth", "0.1359")
    company = await _fv_company(db_session)
    fair = await _fair_value(client, company.id)
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["value"] is None
    assert "stale assumption: risk_free_rate" in intrinsic["reason"]
    assert [s["key"] for s in fair["assumptions"]["stale"]] == ["risk_free_rate"]


async def test_full_assumption_set_gives_a_faded_intrinsic_value(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _record(db_session, "risk_free_rate", "0.20")
    await _record(db_session, "equity_risk_premium", "0.04")
    await _record(db_session, "long_run_inflation", "0.05")
    await _record(db_session, "long_run_cost_of_equity", "0.15")
    await _record(db_session, "nominal_gdp_growth", "0.1359")
    company = await _fv_company(db_session)
    fair = await _fair_value(client, company.id)
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["status"] == "AVAILABLE", intrinsic
    assumptions = intrinsic["assumptions"]
    assert D(assumptions["discount_rate"]) == D("0.24")
    assert D(assumptions["terminal_discount_rate"]) == D("0.15")
    assert D(assumptions["terminal_growth_rate"]) == D("0.05")
    assert fair["methodology_version"] == VALUATION_METHODOLOGY_VERSION == "1.2"
    assert fair["input_sources"]["discount_rate"].count("assumption:") == 2
    assert fair["input_sources"]["long_run_cost_of_equity"].startswith(
        "assumption:long_run_cost_of_equity"
    )


# --- M4: dividend history checks are NOT_RUN ----------------------------------------------------
# (covered through the API in test_scores_api.py::test_statement_inputs_resolve_and_are_cited)


# --- F13: stage-1 growth = 3-year revenue CAGR capped at nominal GDP growth ---------------------


class TestRevenueCagr:
    async def test_cagr_from_four_annual_points(self, db_session: AsyncSession) -> None:
        from app.statements import bridge

        company = await make_company(db_session)
        for year, revenue in ((2021, "800"), (2022, "900"), (2023, "1000"), (2024, "1600")):
            values = dict(FULL_YEAR)
            values["revenue"] = D(revenue)
            await seed_year(db_session, company, year, values)
        st = await load_company_statements(db_session, company.id)
        cagr = bridge.revenue_cagr_3y(st, st.latest())
        assert cagr.available
        # (1600 / 800) ** (1/3) - 1 = 25.992...%
        assert cagr.value is not None
        assert abs(cagr.value - D("0.259921")) < D("0.000001")
        assert [lv.fiscal_year for lv in cagr.sources] == [2021, 2024]

    async def test_fewer_than_four_points_names_the_missing_year(
        self, db_session: AsyncSession
    ) -> None:
        from app.statements import bridge

        company = await make_company(db_session)
        for year in (2022, 2023, 2024):
            await seed_year(db_session, company, year, dict(FULL_YEAR))
        st = await load_company_statements(db_session, company.id)
        cagr = bridge.revenue_cagr_3y(st, st.latest())
        assert cagr.status == "INSUFFICIENT_DATA"
        assert cagr.value is None
        assert cagr.reason == "revenue CAGR needs 4 annual revenue points: missing revenue FY2021"

    async def test_gap_year_is_not_interpolated(self, db_session: AsyncSession) -> None:
        from app.statements import bridge

        company = await make_company(db_session)
        for year in (2020, 2022, 2023, 2024):  # FY2021 missing: not 4 consecutive points
            await seed_year(db_session, company, year, dict(FULL_YEAR))
        st = await load_company_statements(db_session, company.id)
        cagr = bridge.revenue_cagr_3y(st, st.latest())
        assert cagr.status == "INSUFFICIENT_DATA"
        assert "FY2021" in (cagr.reason or "")

    async def test_non_positive_revenue_is_insufficient_not_zero(
        self, db_session: AsyncSession
    ) -> None:
        from app.statements import bridge

        company = await make_company(db_session)
        for year in (2021, 2022, 2023, 2024):
            values = dict(FULL_YEAR)
            if year == 2021:
                values["revenue"] = D("0")
            await seed_year(db_session, company, year, values)
        st = await load_company_statements(db_session, company.id)
        cagr = bridge.revenue_cagr_3y(st, st.latest())
        assert cagr.status == "INSUFFICIENT_DATA"
        assert cagr.value is None
        assert "non-positive" in (cagr.reason or "")

    async def test_declining_revenue_gives_a_negative_cagr(self, db_session: AsyncSession) -> None:
        from app.statements import bridge

        company = await make_company(db_session)
        for year, revenue in ((2021, "1000"), (2022, "900"), (2023, "800"), (2024, "512")):
            values = dict(FULL_YEAR)
            values["revenue"] = D(revenue)
            await seed_year(db_session, company, year, values)
        st = await load_company_statements(db_session, company.id)
        cagr = bridge.revenue_cagr_3y(st, st.latest())
        assert cagr.value is not None
        assert abs(cagr.value - D("-0.200")) < D("0.0001")  # (0.512) ** (1/3) = 0.8


async def test_growth_high_is_the_capped_cagr(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _record_all(db_session, gdp="0.1359")
    company = await _fv_company(db_session, start_revenue="500")  # CAGR = 25.99 %
    fair = await _fair_value(client, company.id)
    assert fair["legs"]["intrinsic"]["status"] == "AVAILABLE", fair["legs"]["intrinsic"]
    assert D(fair["inputs"]["resolved_growth_high"]) == D("0.1359")  # capped
    source = fair["input_sources"]["revenue_growth"]
    assert source.startswith("statement:revenue 3y CAGR FY2021-FY2024")
    assert "capped at assumption:nominal_gdp_growth" in source
    assert fair["input_sources"]["growth_high"] == source


async def test_growth_high_below_the_cap_is_the_cagr_itself(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _record_all(db_session, gdp="0.1359")
    company = await _fv_company(db_session, start_revenue="1000")  # CAGR = 0
    fair = await _fair_value(client, company.id)
    assert D(fair["inputs"]["resolved_growth_high"]) == D("0")
    assert "below cap" in fair["input_sources"]["revenue_growth"]


async def test_missing_cap_assumption_makes_the_intrinsic_leg_name_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _record_all(db_session, gdp=None)
    company = await _fv_company(db_session)
    fair = await _fair_value(client, company.id)
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["value"] is None
    assert intrinsic["reason"] == (
        f"no sourced nominal_gdp_growth in valuation assumptions {VALUATION_METHODOLOGY_VERSION}"
    )
    assert fair["inputs"]["resolved_growth_high"] is None


async def test_three_annual_points_name_the_missing_revenue_year(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _record_all(db_session)
    company = await _fv_company(db_session, years=(2022, 2023, 2024))
    fair = await _fair_value(client, company.id)
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["status"] == "INSUFFICIENT_DATA"
    assert intrinsic["value"] is None
    assert intrinsic["reason"] == (
        "Missing stage-1 growth: revenue CAGR needs 4 annual revenue points: "
        "missing revenue FY2021"
    )


async def test_single_year_growth_metric_is_never_a_fallback(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _record_all(db_session)
    company = await _fv_company(db_session, years=(2023, 2024))
    fair = await _fair_value(client, company.id)
    assert fair["inputs"]["resolved_growth_high"] is None
    assert fair["legs"]["intrinsic"]["value"] is None


# --- router ruling: excess returns and DDM fade the terminal rate too ---------------------------


class TestFadedPerpetuities:
    def test_excess_returns_equal_rates_reproduce_the_closed_form(self) -> None:
        from app.valuation.models import calculate_excess_returns

        closed = calculate_excess_returns(D("35.38"), D("0.098"), D("0.0761"), D("0.02"))
        faded = calculate_excess_returns(
            D("35.38"), D("0.098"), D("0.0761"), D("0.02"), terminal_discount_rate=D("0.0761")
        )
        assert closed.value is not None and faded.value is not None
        assert abs(closed.value - faded.value) < D("0.001")
        assert faded.assumptions["terminal_discount_rate"] == "0.0761"

    def test_excess_returns_lower_long_run_rate_raises_the_value(self) -> None:
        from app.valuation.models import calculate_excess_returns

        same = calculate_excess_returns(
            D("100"), D("0.30"), D("0.25"), D("0.05"), terminal_discount_rate=D("0.25")
        )
        faded = calculate_excess_returns(
            D("100"), D("0.30"), D("0.25"), D("0.05"), terminal_discount_rate=D("0.15")
        )
        assert same.value is not None and faded.value is not None
        assert faded.value > same.value
        # hand check, 1 explicit year: excess 5 -> PV 4; terminal excess (0.30-0.15)*100*1.05
        # = 15.75 at 0.15-0.05 -> 157.5, back one year at 25 % -> 126; FV = 100 + 4 + 126
        one_year = calculate_excess_returns(
            D("100"), D("0.30"), D("0.25"), D("0.05"), terminal_discount_rate=D("0.15"),
            explicit_years=1,
        )
        assert one_year.value is not None
        assert abs(one_year.value - D("230")) < D("0.001")

    def test_one_shared_five_year_explicit_stage(self) -> None:
        from app.valuation.constants import EXPLICIT_STAGE_YEARS
        from app.valuation.models import calculate_ddm, calculate_excess_returns

        assert EXPLICIT_STAGE_YEARS == 5
        er_default = calculate_excess_returns(
            D("100"), D("0.30"), D("0.25"), D("0.05"), terminal_discount_rate=D("0.15")
        )
        er_five = calculate_excess_returns(
            D("100"), D("0.30"), D("0.25"), D("0.05"), terminal_discount_rate=D("0.15"),
            explicit_years=5,
        )
        er_ten = calculate_excess_returns(
            D("100"), D("0.30"), D("0.25"), D("0.05"), terminal_discount_rate=D("0.15"),
            explicit_years=10,
        )
        assert er_default.value == er_five.value != er_ten.value
        ddm_default = calculate_ddm(D("2"), D("0.20"), D("0.02"), terminal_discount_rate=D("0.10"))
        ddm_five = calculate_ddm(
            D("2"), D("0.20"), D("0.02"), terminal_discount_rate=D("0.10"), explicit_years=5
        )
        assert ddm_default.value == ddm_five.value
        fcfe = calculate_fcfe_2stage(
            D("100"), D("0.05"), D("0.05"), D("0.20"), D("0.05"), shares_outstanding=D("1"),
            terminal_discount_rate=D("0.15"),
        )
        assert fcfe.assumptions["years_high"] == "5"

    def test_excess_returns_long_run_rate_must_exceed_growth(self) -> None:
        from app.valuation.models import calculate_excess_returns

        result = calculate_excess_returns(
            D("100"), D("0.30"), D("0.25"), D("0.05"), terminal_discount_rate=D("0.05")
        )
        assert result.status == ValuationStatus.INVALID
        assert result.value is None

    def test_ddm_equal_rates_reproduce_the_closed_form(self) -> None:
        from app.valuation.models import calculate_ddm

        closed = calculate_ddm(D("2"), D("0.12"), D("0.02"))
        faded = calculate_ddm(D("2"), D("0.12"), D("0.02"), terminal_discount_rate=D("0.12"))
        assert closed.value == D("20.0000")
        assert faded.value is not None
        assert abs(faded.value - D("20")) < D("0.001")

    def test_ddm_hand_checked_fade(self) -> None:
        from app.valuation.models import calculate_ddm

        # 1 explicit year: 2 / 1.20 = 1.6667; terminal DPS 2 x 1.02 = 2.04 at 0.10 - 0.02
        # = 25.5, back one year at 20 %: 21.25; total 22.9167
        result = calculate_ddm(
            D("2"), D("0.20"), D("0.02"), terminal_discount_rate=D("0.10"), explicit_years=1
        )
        assert result.value is not None
        assert abs(result.value - D("22.9167")) < D("0.001")

    def test_ddm_long_run_rate_must_exceed_growth(self) -> None:
        from app.valuation.models import calculate_ddm

        result = calculate_ddm(D("2"), D("0.20"), D("0.02"), terminal_discount_rate=D("0.02"))
        assert result.status == ValuationStatus.INVALID

    async def test_bank_intrinsic_needs_the_long_run_assumption(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        from app.valuation.assumptions import resolve_assumptions

        await _record(db_session, "risk_free_rate", "0.20")
        await _record(db_session, "equity_risk_premium", "0.04")
        await _record(db_session, "long_run_inflation", "0.05")
        resolved = await resolve_assumptions(db_session, "banks")
        from app.valuation.service import _INTRINSIC_KEYS

        needed = [k for k in _INTRINSIC_KEYS["excess_returns"] if k in resolved.missing]
        assert needed == ["long_run_cost_of_equity"]  # no GDP cap: no growth stage


def test_fade_switches_to_long_run_rate_after_explicit_stage() -> None:
    """Owner fade horizon: years 1-5 at the first-stage rate, years 6+ and the
    terminal value at the long-run rate, with factors compounding across the switch."""
    from app.valuation.models import _two_stage_present_value

    result = _two_stage_present_value(
        base_cash_flow=Decimal("100"),
        growth_high=Decimal("0"),
        years_high=5,
        growth_stable=Decimal("0"),
        years_stable=5,
        discount_rate=Decimal("0.25"),
        terminal_growth_rate=Decimal("0"),
        terminal_discount_rate=Decimal("0.10"),
    )
    assert result is not None
    pv_flows, terminal_value, pv_terminal, _ = result
    high = sum(Decimal(100) / Decimal("1.25") ** t for t in range(1, 6))
    f5 = Decimal("1.25") ** 5
    stable = sum(Decimal(100) / (f5 * Decimal("1.10") ** t) for t in range(1, 6))
    assert abs(pv_flows - (high + stable)) < Decimal("0.0001")
    assert terminal_value == Decimal("1000")
    assert abs(pv_terminal - Decimal(1000) / (f5 * Decimal("1.10") ** 5)) < Decimal("0.0001")
