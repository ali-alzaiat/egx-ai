"""R46: 3-year true FCFE base, stage-1 growth floor, banks on justified P/B, vendor map 1.3.

Every number is a SYNTHETIC test value seeded by the test itself.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest

from app.statements import bridge
from app.statements.bridge import load_company_statements
from app.statements.vendor_import import VENDOR_MAPPING_VERSION, vendor_periods
from app.valuation.assumptions import MARKET_SCOPE, record_assumption
from app.valuation.constants import (
    FCFE_BASE_YEARS,
    STAGE1_GROWTH_FLOOR,
    VALUATION_METHODOLOGY_VERSION,
    VALUATION_PROFILES,
)
from app.valuation.models import (
    ValuationModel,
    ValuationStatus,
    calculate_fcfe_2stage,
    calculate_justified_pb,
    calculate_residual_income_2stage,
    solve_implied_growth,
    solve_implied_roe_residual_income,
)
from statement_seed import FULL_YEAR, make_company, seed_prices, seed_year

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.market import Company

D = Decimal


def _year(**overrides: Decimal) -> dict[str, Decimal]:
    values = dict(FULL_YEAR)
    values.update(overrides)
    return values


async def _statements(
    db: AsyncSession, years: dict[int, dict[str, Decimal]]
) -> tuple[Company, bridge.CompanyStatements]:
    company = await make_company(db)
    for fiscal_year, values in years.items():
        await seed_year(db, company, fiscal_year, values)
    return company, await load_company_statements(db, company.id)


# --- versions ---------------------------------------------------------------------------------


def test_versions_and_profiles() -> None:
    assert VALUATION_METHODOLOGY_VERSION == "1.5"
    assert VENDOR_MAPPING_VERSION == "stockanalysis-map-1.3"
    assert FCFE_BASE_YEARS == 3
    assert D("0") == STAGE1_GROWTH_FLOOR
    assert VALUATION_PROFILES["banks"]["primary_model"] == "residual_income_2stage"
    assert VALUATION_PROFILES["default"]["primary_model"] == "fcfe_two_stage"


# --- V3: justified P/B ------------------------------------------------------------------------


class TestJustifiedPb:
    def test_hand_checked_value(self) -> None:
        # P/B = (0.098 - 0.02) / (0.0761 - 0.02) = 1.39037...; x 35.38 = 49.1912...
        result = calculate_justified_pb(D("35.38"), D("0.098"), D("0.0761"), D("0.02"))
        assert result.status == ValuationStatus.AVAILABLE
        assert result.model == ValuationModel.JUSTIFIED_PB
        assert result.value is not None
        assert abs(result.value - D("49.1912")) < D("0.001")
        assert result.assumptions["formula"] == "FV = BVPS x (ROE - g) / (ke - g)"

    def test_roe_equal_to_ke_gives_book_value(self) -> None:
        result = calculate_justified_pb(D("20"), D("0.15"), D("0.15"), D("0.05"))
        assert result.value == D("20.0000")

    @pytest.mark.parametrize(
        ("bvps", "roe", "ke", "g", "missing"),
        [
            (None, D("0.1"), D("0.2"), D("0.05"), "BVPS"),
            (D("10"), None, D("0.2"), D("0.05"), "ROE"),
            (D("10"), D("0.1"), None, D("0.05"), "cost of equity"),
            (D("10"), D("0.1"), D("0.2"), None, "growth"),
        ],
    )
    def test_missing_input_is_insufficient_and_named(
        self, bvps: Decimal | None, roe: Decimal | None, ke: Decimal | None,
        g: Decimal | None, missing: str,
    ) -> None:
        result = calculate_justified_pb(bvps, roe, ke, g)
        assert result.status == ValuationStatus.INSUFFICIENT_DATA
        assert result.value is None
        assert missing in (result.reason or "")

    @pytest.mark.parametrize("ke", [D("0.05"), D("0.04")])
    def test_cost_of_equity_not_above_growth_is_invalid(self, ke: Decimal) -> None:
        result = calculate_justified_pb(D("10"), D("0.2"), ke, D("0.05"))
        assert result.status == ValuationStatus.INVALID
        assert result.value is None
        assert "greater than growth" in (result.reason or "")

    def test_non_positive_bvps_is_invalid(self) -> None:
        for bvps in (D("0"), D("-5")):
            result = calculate_justified_pb(bvps, D("0.2"), D("0.25"), D("0.05"))
            assert result.status == ValuationStatus.INVALID

    def test_roe_not_above_growth_is_invalid_never_negative_value(self) -> None:
        for roe in (D("0.05"), D("-0.10")):
            result = calculate_justified_pb(D("10"), roe, D("0.25"), D("0.05"))
            assert result.status == ValuationStatus.INVALID
            assert result.value is None


# --- vendor map 1.3 ---------------------------------------------------------------------------


def test_vendor_map_13_maps_new_lines(vendor_payload: Any) -> None:
    payload = vendor_payload("R46V")
    income = payload["statements"]["income"]["financialData"]
    income["netinc"] = [None, 150, 140]
    income["minorityInterest"] = [None, -50, -40]
    payload["statements"]["balance"]["financialData"]["netLoans"] = [None, 700, 650]
    payload["statements"]["balance"]["financialData"]["totalDeposits"] = [None, 900, 800]
    payload["statements"]["cash_flow"]["financialData"]["netDebtIssued"] = [None, -30, 25]
    by_code = {
        p.fiscal_year: {c.ontology_code: c.value for c in p.candidates}
        for p in vendor_periods(payload)
    }
    assert by_code[2025]["net_income_to_parent"] == D("150")
    assert by_code[2025]["minority_income"] == D("-50")  # vendor sign kept
    assert by_code[2025]["net_loans"] == D("700")
    assert by_code[2025]["total_deposits"] == D("900")
    assert by_code[2025]["net_borrowing"] == D("-30")  # negative = net repayment, kept
    assert by_code[2024]["net_borrowing"] == D("25")


def test_vendor_map_13_absent_fields_stay_absent(vendor_payload: Any) -> None:
    by_code = {
        p.fiscal_year: {c.ontology_code for c in p.candidates}
        for p in vendor_periods(vendor_payload("R46V2"))
    }
    for codes in by_code.values():
        assert not codes & {"net_borrowing", "net_loans", "total_deposits", "minority_income"}


# --- V1 + V2: 3-year true FCFE ----------------------------------------------------------------


class TestFcfeBase:
    async def test_three_year_mean_of_pre_financing_flow(self, db_session: AsyncSession) -> None:
        # Past net borrowing (+20 / -10 / 0) must not change the base (R46 V7).
        _c, st = await _statements(
            db_session,
            {
                2022: _year(cfo=D("100"), capex=D("-20"), net_borrowing=D("0")),  # 80
                2023: _year(cfo=D("200"), capex=D("-40"), net_borrowing=D("-10")),  # 160
                2024: _year(cfo=D("300"), capex=D("-50"), net_borrowing=D("20")),  # 250
            },
        )
        base = bridge.fcfe_base(st, st.latest())
        assert base.resolved.available
        assert base.resolved.value == D("490") / D("3")
        assert [(y.fiscal_year, y.pre_financing, y.flow) for y in base.years] == [
            (2024, D("250"), D("250")), (2023, D("160"), D("160")), (2022, D("80"), D("80")),
        ]
        payload = base.payload()
        assert payload["years_required"] == 3
        assert "debt grows with the firm" in payload["method"]
        assert [D(y["flow"]) for y in payload["years"]] == [D("250"), D("160"), D("80")]
        assert [D(y["net_borrowing"]) for y in payload["years"]] == [D("20"), D("-10"), D("0")]
        assert "fcfe" not in payload["years"][0]

    async def test_repayer_base_is_independent_of_past_repayment(
        self, db_session: AsyncSession
    ) -> None:
        # RACC-like: repays a lot every year. The base is the same as for a no-repayment twin.
        def years(borrowing: str) -> dict[int, dict[str, Decimal]]:
            return {
                y: _year(cfo=D("500"), capex=D("-100"), net_borrowing=D(borrowing))
                for y in (2022, 2023, 2024)
            }

        _c, repayer = await _statements(db_session, years("-250"))
        _c, steady = await _statements(db_session, years("0"))
        assert bridge.fcfe_base(repayer, repayer.latest()).resolved.value == D("400")
        assert bridge.fcfe_base(steady, steady.latest()).resolved.value == D("400")

    async def test_older_years_beyond_three_are_ignored(self, db_session: AsyncSession) -> None:
        _c, st = await _statements(
            db_session,
            {
                2021: _year(cfo=D("9999"), net_borrowing=D("0")),
                2022: _year(cfo=D("100"), capex=D("-20"), net_borrowing=D("0")),
                2023: _year(cfo=D("100"), capex=D("-20"), net_borrowing=D("0")),
                2024: _year(cfo=D("100"), capex=D("-20"), net_borrowing=D("0")),
            },
        )
        assert bridge.fcfe_base(st, st.latest()).resolved.value == D("80")

    async def test_fewer_than_three_years_is_insufficient(
        self, db_session: AsyncSession
    ) -> None:
        _c, st = await _statements(
            db_session,
            {
                2023: _year(net_borrowing=D("0")),
                2024: _year(net_borrowing=D("0")),
            },
        )
        base = bridge.fcfe_base(st, st.latest())
        assert base.resolved.status == "INSUFFICIENT_DATA"
        assert base.resolved.value is None
        assert "needs 3 fiscal years" in (base.resolved.reason or "")
        assert "FY2022" in (base.resolved.reason or "")

    async def test_gap_year_is_not_skipped(self, db_session: AsyncSession) -> None:
        _c, st = await _statements(
            db_session,
            {y: _year(net_borrowing=D("0")) for y in (2021, 2022, 2024)},
        )
        base = bridge.fcfe_base(st, st.latest())
        assert base.resolved.value is None
        assert "FY2023" in (base.resolved.reason or "")

    async def test_missing_net_borrowing_no_longer_blocks_the_base(
        self, db_session: AsyncSession
    ) -> None:
        # R46 V7: net borrowing is information only; a company missing it regains a base.
        _c, st = await _statements(db_session, {y: _year() for y in (2022, 2023, 2024)})
        base = bridge.fcfe_base(st, st.latest())
        assert base.resolved.available
        assert base.resolved.value == D("250")  # 300 - 50
        assert all(y.net_borrowing is None for y in base.years)

    async def test_missing_capex_names_the_line(self, db_session: AsyncSession) -> None:
        values = _year()
        del values["capex"]
        _c, st = await _statements(db_session, {2022: _year(), 2023: values, 2024: values})
        base = bridge.fcfe_base(st, st.latest())
        assert base.resolved.value is None
        assert "capex" in (base.resolved.reason or "")

    async def test_minorities_scale_the_year(self, db_session: AsyncSession) -> None:
        # Net income to common 150, parent (after minorities) 150, minorities earn 50 more:
        # incl. minorities = 150 - (-50) = 200; parent share = 150 / 200 = 0.75.
        minority = {
            "net_income": D("150"),
            "net_income_to_parent": D("150"),
            "minority_income": D("-50"),
        }
        _c, st = await _statements(
            db_session,
            {
                2022: _year(cfo=D("100"), capex=D("-20"), **minority),
                2023: _year(cfo=D("100"), capex=D("-20")),  # no minorities
                2024: _year(cfo=D("100"), capex=D("-20"), **minority),
            },
        )
        base = bridge.fcfe_base(st, st.latest())
        assert base.resolved.available
        by_year = {y.fiscal_year: y for y in base.years}
        assert by_year[2024].parent_share == D("0.75")
        assert by_year[2024].flow == D("60")  # (100 - 20) x 0.75
        assert by_year[2023].parent_share == D("1")
        assert by_year[2023].flow == D("80")
        assert base.resolved.value == D("200") / D("3")

    async def test_zero_minority_income_means_share_one(self, db_session: AsyncSession) -> None:
        _c, st = await _statements(db_session, {2024: _year(minority_income=D("0"))})
        share = bridge.parent_share(st.latest())
        assert share.available and share.value == D("1")

    async def test_balance_sheet_minority_without_income_line_is_unresolved(
        self, db_session: AsyncSession
    ) -> None:
        _c, st = await _statements(db_session, {2024: _year(minority_interests=D("40"))})
        share = bridge.parent_share(st.latest())
        assert share.status == "INSUFFICIENT_DATA" and share.value is None
        assert "minority_income" in (share.reason or "")

    async def test_minority_income_without_parent_income_line_is_unresolved(
        self, db_session: AsyncSession
    ) -> None:
        _c, st = await _statements(db_session, {2024: _year(minority_income=D("-5"))})
        share = bridge.parent_share(st.latest())
        assert share.status == "INSUFFICIENT_DATA" and share.value is None
        assert "net_income_to_parent" in (share.reason or "")

    async def test_non_positive_total_income_is_unresolved(
        self, db_session: AsyncSession
    ) -> None:
        _c, st = await _statements(
            db_session,
            {2024: _year(net_income_to_parent=D("10"), minority_income=D("20"))},
        )
        share = bridge.parent_share(st.latest())
        assert share.status == "INSUFFICIENT_DATA" and share.value is None

    async def test_negative_common_income_is_unresolved(self, db_session: AsyncSession) -> None:
        # Parent loses money, minorities earn: a negative share would flip FCFE's sign.
        _c, st = await _statements(
            db_session,
            {
                2024: _year(
                    net_income=D("-30"), net_income_to_parent=D("-30"), minority_income=D("-50")
                )
            },
        )
        share = bridge.parent_share(st.latest())
        assert share.status == "INSUFFICIENT_DATA" and share.value is None

    async def test_share_above_one_is_capped(self, db_session: AsyncSession) -> None:
        # Loss-making minorities: 200 / (200 - 50) = 1.33 -> capped at 1.
        _c, st = await _statements(
            db_session,
            {2024: _year(net_income_to_parent=D("200"), minority_income=D("50"))},
        )
        assert bridge.parent_share(st.latest()).value == D("1")

    async def test_negative_mean_is_returned_for_the_model_to_mark_invalid(
        self, db_session: AsyncSession
    ) -> None:
        _c, st = await _statements(
            db_session,
            {
                y: _year(cfo=D("10"), capex=D("-50"), net_borrowing=D("0"))
                for y in (2022, 2023, 2024)
            },
        )
        base = bridge.fcfe_base(st, st.latest())
        assert base.resolved.available
        assert base.resolved.value == D("-40")


class TestBankDetection:
    async def test_needs_both_net_loans_and_deposits(self, db_session: AsyncSession) -> None:
        _c, both = await _statements(
            db_session, {2024: _year(net_loans=D("700"), total_deposits=D("900"))}
        )
        _c, loans_only = await _statements(db_session, {2024: _year(net_loans=D("700"))})
        _c, deposits_only = await _statements(db_session, {2024: _year(total_deposits=D("9"))})
        _c, neither = await _statements(db_session, {2024: _year()})
        assert bridge.is_bank(both.latest())
        assert not bridge.is_bank(loans_only.latest())
        assert not bridge.is_bank(deposits_only.latest())
        assert not bridge.is_bank(neither.latest())
        assert not bridge.is_bank(None)


# --- end to end through the fair-value endpoint ------------------------------------------------


async def _record(db: AsyncSession, key: str, value: str) -> None:
    await record_assumption(
        db,
        key=key,
        scope=MARKET_SCOPE,
        value=D(value),
        source_url="https://example.test/assumption",
        source_title="SYNTHETIC test assumption",
        as_of=date.today() - timedelta(days=1),
    )


async def _assumptions(db: AsyncSession) -> None:
    await _record(db, "risk_free_rate", "0.20")
    await _record(db, "equity_risk_premium", "0.04")
    await _record(db, "long_run_inflation", "0.054")
    await _record(db, "long_run_cost_of_equity", "0.15")
    await _record(db, "nominal_gdp_growth", "0.1359")


async def _company(
    db: AsyncSession, revenues: tuple[str, ...] = ("1000", "1000", "1000", "1000"),
    **extra: Decimal,
) -> Company:
    company = await make_company(db)
    for fiscal_year, revenue in zip((2021, 2022, 2023, 2024), revenues, strict=True):
        await seed_year(
            db, company, fiscal_year,
            _year(revenue=D(revenue), net_borrowing=D("10"), **extra),
        )
    await seed_prices(db, company, bars=30)
    return company


async def _fair(client: AsyncClient, company: Company) -> dict[str, Any]:
    response = await client.get(f"/api/valuation/companies/{company.id}/fair-value")
    assert response.status_code == 200, response.text[:300]
    body: dict[str, Any] = response.json()
    return body


async def test_default_company_uses_the_three_year_flow_base_and_debt(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await _company(db_session)
    fair = await _fair(client, company)
    assert fair["methodology_version"] == "1.5"
    assert fair["profile"]["primary_model"] == "fcfe_two_stage"
    assert fair["profile"]["detection"] == "sector"
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["status"] == "AVAILABLE", intrinsic
    # no fallback was needed: the fields exist and are empty
    assert intrinsic["fallback_from"] is None and intrinsic["fallback_reason"] is None
    assert intrinsic["fallback_attempt"] is None
    # cfo 300 - capex 50 in every year; net borrowing (10) is information only
    assert D(fair["inputs"]["free_cash_flow"]) == D("250")
    base = fair["inputs"]["fcfe_base"]
    assert base["years_required"] == 3 and base["status"] == "AVAILABLE"
    assert [y["fiscal_year"] for y in base["years"]] == [2024, 2023, 2022]
    assert all(D(y["flow"]) == D("250") == D(y["pre_financing"]) for y in base["years"])
    assert all(D(y["net_borrowing"]) == D("10") for y in base["years"])
    assert "debt grows with the firm" in base["method"]
    debt = fair["inputs"]["debt"]
    assert debt["status"] == "AVAILABLE" and debt["basis"] == "reported"
    assert D(debt["value"]) == D("500") and debt["fiscal_year"] == 2024
    assert D(debt["parent_share"]) == D("1")
    assumptions = intrinsic["assumptions"]
    assert D(assumptions["flow_FY2024"]) == D("250") == D(assumptions["flow_FY2022"])
    assert D(assumptions["flow_base_mean"]) == D("250")
    assert "3 fiscal years" in assumptions["flow_base_method"]
    assert D(assumptions["debt"]) == D("500")
    assert "3-year mean pre-financing flow" in fair["input_sources"]["free_cash_flow"]
    assert "interest_bearing_debt FY2024" in fair["input_sources"]["debt"]


async def test_past_repayment_does_not_change_the_value(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    steady = await _company(db_session)
    repayer = await make_company(db_session)
    for fiscal_year in (2021, 2022, 2023, 2024):
        await seed_year(
            db_session, repayer, fiscal_year,
            _year(net_borrowing=D("-300"), debt_repayment=D("300")),
        )
    await seed_prices(db_session, repayer, bars=30)
    a, b = await _fair(client, steady), await _fair(client, repayer)
    assert a["legs"]["intrinsic"]["status"] == "AVAILABLE"
    assert a["legs"]["intrinsic"]["value"] == b["legs"]["intrinsic"]["value"]


async def test_missing_debt_makes_the_leg_insufficient_and_names_it(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await make_company(db_session)
    for fiscal_year in (2021, 2022, 2023, 2024):
        values = _year(finance_costs=D("40"))  # interest paid but no debt line: ambiguous
        del values["interest_bearing_debt"]
        await seed_year(db_session, company, fiscal_year, values)
    await seed_prices(db_session, company, bars=30)
    fair = await _fair(client, company)
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["status"] == "INSUFFICIENT_DATA"
    assert intrinsic["value"] is None
    assert "interest-bearing debt" in intrinsic["reason"]
    assert "finance_costs" in intrinsic["reason"]
    assert fair["inputs"]["debt"]["status"] == "INSUFFICIENT_DATA"
    assert fair["inputs"]["debt"]["value"] is None
    assert fair["fair_value"]["value"] is None


async def test_fair_value_is_the_intrinsic_leg_alone_and_says_so(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await _company(db_session)
    fair = await _fair(client, company)
    assert fair["legs"]["relative"]["status"] == "INSUFFICIENT_DATA"
    assert fair["legs"]["relative"]["value"] is None
    assert fair["fair_value"]["value"] == fair["legs"]["intrinsic"]["value"]
    assert fair["fair_value"]["basis"] == "intrinsic_only"
    assert "intrinsic model alone" in fair["fair_value"]["basis_note"]
    assert fair["n_with_data"] == 1


async def test_two_years_of_statements_make_fcfe_insufficient(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await make_company(db_session)
    for fiscal_year in (2023, 2024):
        await seed_year(db_session, company, fiscal_year, _year(net_borrowing=D("10")))
    await seed_prices(db_session, company, bars=30)
    fair = await _fair(client, company)
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["status"] == "INSUFFICIENT_DATA"
    assert intrinsic["value"] is None
    assert fair["fair_value"]["value"] is None
    # growth needs 4 revenue points too, so either honest reason may lead; FCFE names itself
    assert fair["inputs"]["fcfe_base"]["status"] == "INSUFFICIENT_DATA"
    assert "FY2022" in fair["inputs"]["fcfe_base"]["reason"]


async def test_non_positive_flow_falls_back_to_residual_income(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """SWDY-like (R46 V9): 3-year pre-financing flow < 0, positive ROE -> residual income."""
    await _assumptions(db_session)
    company = await _company(db_session, cfo=D("10"), capex=D("-100"))  # 10 - 100 < 0
    fair = await _fair(client, company)
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["status"] == "AVAILABLE", intrinsic
    assert intrinsic["model"] == "residual_income_2stage"
    assert intrinsic["fallback_from"] == "fcfe_two_stage"
    assert "Free cash flow must be positive" in intrinsic["fallback_reason"]
    assert intrinsic["fallback_attempt"] is None
    # the cash-flow evidence (and its negative mean) stays visible
    assert D(fair["inputs"]["free_cash_flow"]) == D("-90")
    assert fair["inputs"]["fcfe_base"]["status"] == "AVAILABLE"
    # profile still names the company's own model; the leg says what ran
    assert fair["profile"]["primary_model"] == "fcfe_two_stage"
    # value = the bank model on the 3-year mean ROE (net income 200 / equity 1100 = 18.18 %)
    assert D(fair["inputs"]["roe_base"]["mean"]) == D("0.1818")
    expected = calculate_residual_income_2stage(
        D("11"), D("0.1818"), D("0.24"), D("0"), D("0.054"), D("0.054"),
        terminal_discount_rate=D("0.15"),
    )
    assert expected.value is not None
    assert intrinsic["value"] == str(expected.value)
    assert fair["fair_value"]["value"] == intrinsic["value"]
    assert fair["fair_value"]["basis"] == "intrinsic_only"
    # the reverse calculation follows the model that produced the value
    implied = fair["implied"]
    assert implied["model"] == "residual_income_2stage"  # the model that produced the value
    assert implied["metric"] == "roe"
    assert implied["compare_to"]["key"] == "roe"
    assert D(implied["compare_to"]["value"]) == D("0.1818")
    assert implied["status"] == "AVAILABLE", implied


async def test_fallback_flows_into_scenarios_and_sensitivity(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await _company(db_session, cfo=D("10"), capex=D("-100"))
    fair = await _fair(client, company)
    rows = {r["parameter"] for r in fair["sensitivity"]}
    assert rows == {"discount_rate", "revenue_growth"}
    assert all(r["fair_value"] is not None for r in fair["sensitivity"])


async def test_negative_roe_gives_no_fallback_value(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await _company(
        db_session, cfo=D("10"), capex=D("-100"), net_income=D("-200")
    )
    fair = await _fair(client, company)
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["model"] == "fcfe_two_stage"
    assert intrinsic["status"] == "INVALID" and intrinsic["value"] is None
    assert intrinsic["fallback_from"] is None
    attempt = intrinsic["fallback_attempt"]
    assert attempt["model"] == "residual_income_2stage"
    assert attempt["status"] == "INSUFFICIENT_DATA"
    assert "not positive" in attempt["reason"]
    assert fair["fair_value"]["value"] is None
    assert fair["implied"]["status"] == "INSUFFICIENT_DATA"


async def test_missing_roe_gives_no_fallback_value(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await make_company(db_session)
    for fiscal_year in (2021, 2022, 2023, 2024):
        values = _year(cfo=D("10"), capex=D("-100"), net_borrowing=D("10"))
        if fiscal_year == 2021:
            del values["total_equity"]  # FY2022 ROE needs the prior year's equity
        await seed_year(db_session, company, fiscal_year, values)
    await seed_prices(db_session, company, bars=30)
    fair = await _fair(client, company)
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["status"] == "INVALID" and intrinsic["value"] is None
    attempt = intrinsic["fallback_attempt"]
    assert attempt["status"] == "INSUFFICIENT_DATA"
    assert "Missing ROE" in attempt["reason"] and "FY2022" in attempt["reason"]
    assert fair["inputs"]["roe_base"]["mean"] is None


async def test_insufficient_cash_flow_data_does_not_fall_back(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Missing data stays missing: an unresolved debt is INSUFFICIENT, not INVALID."""
    await _assumptions(db_session)
    company = await make_company(db_session)
    for fiscal_year in (2021, 2022, 2023, 2024):
        values = _year(cfo=D("10"), capex=D("-100"), finance_costs=D("40"))
        del values["interest_bearing_debt"]
        await seed_year(db_session, company, fiscal_year, values)
    await seed_prices(db_session, company, bars=30)
    fair = await _fair(client, company)
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["model"] == "fcfe_two_stage"
    assert intrinsic["status"] == "INSUFFICIENT_DATA" and intrinsic["value"] is None
    assert intrinsic["fallback_from"] is None and intrinsic["fallback_attempt"] is None
    assert D(fair["inputs"]["roe_base"]["mean"]) == D("0.1818")  # ROE was available
    assert fair["fair_value"]["value"] is None


async def test_negative_growth_is_floored_at_zero(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    shrinking = await _company(db_session, revenues=("1000", "900", "800", "512"))
    flat = await _company(db_session)
    fair = await _fair(client, shrinking)
    reference = await _fair(client, flat)
    assert D(fair["inputs"]["revenue_growth"]) == D("0")
    assert D(fair["inputs"]["resolved_growth_high"]) == D("0")
    assert "floored at 0%" in fair["input_sources"]["revenue_growth"]
    assert D(fair["legs"]["intrinsic"]["assumptions"]["growth_high"]) == D("0")
    # identical cash flows and a 0 % CAGR (flat) give the same intrinsic value
    assert fair["legs"]["intrinsic"]["value"] == reference["legs"]["intrinsic"]["value"]


async def test_growth_cap_is_unchanged_and_not_marked_floored(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await _company(db_session, revenues=("500", "700", "900", "1000"))
    fair = await _fair(client, company)
    assert D(fair["inputs"]["resolved_growth_high"]) == D("0.1359")
    assert "floored" not in fair["input_sources"]["revenue_growth"]


async def _bank(
    db: AsyncSession, *, net_income: dict[int, str] | None = None,
    years: tuple[int, ...] = (2021, 2022, 2023, 2024), drop: tuple[str, ...] = (),
) -> Company:
    company = await make_company(db)
    for fiscal_year in years:
        values = _year(net_loans=D("700"), total_deposits=D("900"))
        if net_income is not None:
            values["net_income"] = D(net_income[fiscal_year])
        for code in drop:
            values.pop(code, None)
        await seed_year(db, company, fiscal_year, values)
    await seed_prices(db, company, bars=30)
    return company


async def test_bank_uses_two_stage_residual_income_with_three_year_roe(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    # equity 1100 every year: ROE = net income / 1100 = 10 %, 20 %, 30 % -> mean 20 %
    company = await _bank(
        db_session, net_income={2021: "100", 2022: "110", 2023: "220", 2024: "330"}
    )
    fair = await _fair(client, company)
    assert fair["profile"]["profile_id"] == "banks"
    assert fair["profile"]["primary_model"] == "residual_income_2stage"
    assert fair["profile"]["detection"] == "statement_lines: net_loans + total_deposits"
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["model"] == "residual_income_2stage"
    assert fair["inputs"]["fcfe_base"] is None and fair["inputs"]["debt"] is None
    assert intrinsic["fallback_from"] is None and intrinsic["fallback_attempt"] is None
    assert fair["inputs"]["free_cash_flow"] is None
    assert intrinsic["status"] == "AVAILABLE", intrinsic
    roe = fair["inputs"]["roe_base"]
    assert roe["status"] == "AVAILABLE" and roe["years_required"] == 3
    assert [y["fiscal_year"] for y in roe["years"]] == [2024, 2023, 2022]
    assert [D(y["roe"]) for y in roe["years"]] == [D("0.3"), D("0.2"), D("0.1")]
    assert D(roe["mean"]) == D("0.2")
    a = intrinsic["assumptions"]
    assert D(a["roe"]) == D("0.2") and D(fair["inputs"]["stable_roe"]) == D("0.2")
    assert D(a["bvps"]) == D("11") and D(a["cost_of_equity"]) == D("0.24")
    assert D(a["terminal_discount_rate"]) == D("0.15")  # the fade: long-run rate after year 5
    assert D(a["terminal_growth_rate"]) == D("0.054") and D(a["growth_stable"]) == D("0.054")
    assert D(a["growth_high"]) == D("0")  # flat revenue
    expected = calculate_residual_income_2stage(
        D("11"), D("0.2"), D("0.24"), D("0"), D("0.054"), D("0.054"),
        terminal_discount_rate=D("0.15"),
    )
    assert intrinsic["value"] == str(expected.value)
    assert fair["fair_value"]["basis"] == "intrinsic_only"
    assert "metric:roe 3-year mean" in fair["input_sources"]["stable_roe"]
    # growth matters to this model now, so both sensitivity families are shown
    assert {r["parameter"] for r in fair["sensitivity"]} == {"discount_rate", "revenue_growth"}


async def test_bank_with_fewer_than_three_roe_years_is_insufficient(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    # 3 balance sheets give only 2 strict-average ROEs (FY2023, FY2024)
    company = await _bank(db_session, years=(2022, 2023, 2024))
    fair = await _fair(client, company)
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["model"] == "residual_income_2stage"
    assert intrinsic["status"] == "INSUFFICIENT_DATA"
    assert "ROE needs 3 fiscal years" in intrinsic["reason"] and "FY2022" in intrinsic["reason"]
    assert fair["inputs"]["roe_base"]["status"] == "INSUFFICIENT_DATA"
    assert fair["inputs"]["roe_base"]["mean"] is None
    assert fair["fair_value"]["value"] is None


async def test_bank_without_revenue_has_no_stage_one_growth_and_no_value(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await _bank(db_session, drop=("revenue",))
    fair = await _fair(client, company)
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["status"] == "INSUFFICIENT_DATA"
    assert "stage-1 growth" in intrinsic["reason"] and "revenue" in intrinsic["reason"]
    assert fair["fair_value"]["value"] is None


# --- V7: debt that grows with the firm ----------------------------------------------------------


def _debt_free(**extra: Decimal) -> dict[str, Decimal]:
    values = _year(**extra)
    del values["interest_bearing_debt"]
    return values


class TestDebtBase:
    async def test_reported_debt_is_scaled_by_the_parent_share(
        self, db_session: AsyncSession
    ) -> None:
        minority = {
            "net_income": D("150"), "net_income_to_parent": D("150"), "minority_income": D("-50"),
        }
        _c, st = await _statements(
            db_session, {2024: _year(interest_bearing_debt=D("400"), **minority)}
        )
        debt = bridge.debt_base(st, st.latest())
        assert debt.resolved.available and debt.basis == "reported"
        assert debt.reported == D("400") and debt.parent_share == D("0.75")
        assert debt.resolved.value == D("300")
        payload = debt.payload()
        assert payload["fiscal_year"] == 2024 and payload["status"] == "AVAILABLE"
        assert D(payload["value"]) == D("300") and D(payload["reported_value"]) == D("400")

    async def test_unresolved_parent_share_leaves_debt_unresolved(
        self, db_session: AsyncSession
    ) -> None:
        _c, st = await _statements(db_session, {2024: _year(minority_interests=D("40"))})
        debt = bridge.debt_base(st, st.latest())
        assert debt.resolved.status == "INSUFFICIENT_DATA" and debt.resolved.value is None
        assert "minority_income" in (debt.resolved.reason or "")

    async def test_vendor_omitted_row_with_no_activity_is_evidenced_as_nil(
        self, db_session: AsyncSession
    ) -> None:
        _c, st = await _statements(db_session, {2023: _debt_free(), 2024: _debt_free()})
        debt = bridge.debt_base(st, st.latest())
        assert debt.resolved.available and debt.resolved.value == D("0")
        assert debt.basis == "vendor_omitted_zero"

    async def test_zero_activity_lines_still_count_as_no_activity(
        self, db_session: AsyncSession
    ) -> None:
        zeros = {
            "finance_costs": D("0"), "net_borrowing": D("0"), "debt_repayment": D("0"),
        }
        _c, st = await _statements(db_session, {2024: _debt_free(**zeros)})
        assert bridge.debt_base(st, st.latest()).resolved.value == D("0")

    @pytest.mark.parametrize("code", ["finance_costs", "net_borrowing", "debt_repayment"])
    async def test_activity_contradicts_nil_debt(
        self, db_session: AsyncSession, code: str
    ) -> None:
        _c, st = await _statements(db_session, {2024: _debt_free(**{code: D("5")})})
        debt = bridge.debt_base(st, st.latest())
        assert debt.resolved.status == "INSUFFICIENT_DATA" and debt.resolved.value is None
        assert code in (debt.resolved.reason or "")

    async def test_prior_year_debt_without_a_repayment_record_is_ambiguous(
        self, db_session: AsyncSession
    ) -> None:
        _c, st = await _statements(
            db_session, {2023: _year(interest_bearing_debt=D("159")), 2024: _debt_free()}
        )
        debt = bridge.debt_base(st, st.latest())
        assert debt.resolved.value is None
        assert "FY2023 debt 159" in (debt.resolved.reason or "")

    async def test_filing_sourced_period_is_never_inferred(
        self, db_session: AsyncSession
    ) -> None:
        company = await make_company(db_session)
        await seed_year(db_session, company, 2024, _debt_free(), tier="filing")
        st = await load_company_statements(db_session, company.id)
        debt = bridge.debt_base(st, st.latest())
        assert debt.resolved.value is None
        assert "not vendor-sourced" in (debt.resolved.reason or "")

    async def test_no_balance_sheet_is_never_inferred(self, db_session: AsyncSession) -> None:
        values = _debt_free()
        del values["total_liabilities"]
        _c, st = await _statements(db_session, {2024: values})
        debt = bridge.debt_base(st, st.latest())
        assert debt.resolved.value is None
        assert "total_liabilities" in (debt.resolved.reason or "")

    async def test_negative_reported_debt_is_unresolved(self, db_session: AsyncSession) -> None:
        _c, st = await _statements(db_session, {2024: _year(interest_bearing_debt=D("-5"))})
        assert bridge.debt_base(st, st.latest()).resolved.value is None

    def test_no_period_at_all(self) -> None:
        empty = bridge.CompanyStatements(company_id=uuid.uuid4(), periods=())
        assert bridge.debt_base(empty, None).resolved.status == "INSUFFICIENT_DATA"


class TestDebtGrowthMath:
    """Hand calculation: flow 100, debt 50, 2 years at 10 %, 1 year at 5 %, terminal 3 %."""

    ARGS: dict[str, Any] = {
        "growth_high": D("0.10"), "growth_stable": D("0.05"), "discount_rate": D("0.20"),
        "terminal_growth_rate": D("0.03"), "years_high": 2, "years_stable": 1,
        "shares_outstanding": D("1"), "terminal_discount_rate": D("0.10"),
    }

    def test_matches_the_year_by_year_hand_calculation(self) -> None:
        # t1: flow 110, debt 55 (+5)            -> FCFE 115     discount 1.2
        # t2: flow 121, debt 60.5 (+5.5)        -> FCFE 126.5   discount 1.44
        # t3: flow 127.05, debt 63.525 (+3.025) -> FCFE 130.075 discount 1.44 x 1.1 = 1.584
        # terminal flow: 127.05 x 1.03 + 63.525 x 0.03 = 130.8615 + 1.90575 = 132.76725
        pv = D("115") / D("1.2") + D("126.5") / D("1.44") + D("130.075") / D("1.584")
        terminal = D("132.76725") / (D("0.10") - D("0.03")) / D("1.584")
        result = calculate_fcfe_2stage(D("100"), debt=D("50"), **self.ARGS)
        assert result.status == ValuationStatus.AVAILABLE
        assert result.value is not None
        assert abs(result.value - (pv + terminal)) < D("0.0005")
        assert result.assumptions["debt"] == "50"

    def test_zero_debt_is_the_plain_flow_stream(self) -> None:
        pv = D("110") / D("1.2") + D("121") / D("1.44") + D("127.05") / D("1.584")
        terminal = D("127.05") * D("1.03") / (D("0.10") - D("0.03")) / D("1.584")
        result = calculate_fcfe_2stage(D("100"), debt=D("0"), **self.ARGS)
        assert result.value is not None
        assert abs(result.value - (pv + terminal)) < D("0.0005")
        # the default (omitted) debt is the same stream
        assert calculate_fcfe_2stage(D("100"), **self.ARGS).value == result.value

    def test_more_debt_gives_more_value_when_growing(self) -> None:
        low = calculate_fcfe_2stage(D("100"), debt=D("0"), **self.ARGS).value
        high = calculate_fcfe_2stage(D("100"), debt=D("500"), **self.ARGS).value
        assert low is not None and high is not None and high > low

    def test_no_growth_means_debt_changes_nothing(self) -> None:
        flat = {**self.ARGS, "growth_high": D("0"), "growth_stable": D("0")}
        flat["terminal_growth_rate"] = D("0")
        a = calculate_fcfe_2stage(D("100"), debt=D("0"), **flat).value
        b = calculate_fcfe_2stage(D("100"), debt=D("900"), **flat).value
        assert a == b

    def test_negative_debt_is_invalid(self) -> None:
        result = calculate_fcfe_2stage(D("100"), debt=D("-1"), **self.ARGS)
        assert result.status == ValuationStatus.INVALID and result.value is None


# --- V8: two-stage residual income ---------------------------------------------------------------


class TestResidualIncome:
    ARGS: dict[str, Any] = {
        "growth_high": D("0.10"), "growth_stable": D("0.05"), "terminal_growth_rate": D("0.03"),
        "years_high": 2, "years_stable": 1, "terminal_discount_rate": D("0.10"),
    }

    def test_matches_the_hand_calculation_with_the_fade(self) -> None:
        # BV0 100, ROE 30 %, ke 20 % for 2 years then 10 %.
        # t1: RI (0.30-0.20) x 100   = 10    discount 1.2     (BV1 110)
        # t2: RI (0.30-0.20) x 110   = 11    discount 1.44    (BV2 121)
        # t3: RI (0.30-0.10) x 121   = 24.2  discount 1.584   (BV3 127.05)
        # terminal RI (0.30-0.10) x 127.05 = 25.41, / (0.10-0.03) = 363, / 1.584
        expected = (
            D("100") + D("10") / D("1.2") + D("11") / D("1.44") + D("24.2") / D("1.584")
            + D("25.41") / D("0.07") / D("1.584")
        )
        result = calculate_residual_income_2stage(D("100"), D("0.30"), D("0.20"), **self.ARGS)
        assert result.status == ValuationStatus.AVAILABLE
        assert result.model == ValuationModel.RESIDUAL_INCOME_2STAGE
        assert result.value is not None
        assert abs(result.value - expected) < D("0.0001")

    def test_roe_equal_to_cost_of_equity_gives_book_value(self) -> None:
        args = {**self.ARGS, "terminal_discount_rate": D("0.20")}
        result = calculate_residual_income_2stage(D("100"), D("0.20"), D("0.20"), **args)
        assert result.value == D("100.0000")

    def test_the_fade_raises_the_value_of_a_high_roe_bank(self) -> None:
        faded = calculate_residual_income_2stage(D("100"), D("0.30"), D("0.20"), **self.ARGS)
        single = calculate_residual_income_2stage(
            D("100"), D("0.30"), D("0.20"), **{**self.ARGS, "terminal_discount_rate": D("0.20")}
        )
        assert faded.value is not None and single.value is not None
        assert faded.value > single.value

    def test_value_rises_with_roe(self) -> None:
        values = [
            calculate_residual_income_2stage(D("100"), D(r), D("0.20"), **self.ARGS).value
            for r in ("0.10", "0.20", "0.30", "0.40")
        ]
        assert None not in values
        assert values == sorted(v for v in values if v is not None)

    @pytest.mark.parametrize(
        ("field", "missing"),
        [("bvps", "BVPS"), ("roe", "ROE"), ("ke", "cost of equity")],
    )
    def test_missing_inputs_are_named(self, field: str, missing: str) -> None:
        kw: dict[str, Decimal | None] = {"bvps": D("100"), "roe": D("0.3"), "ke": D("0.2")}
        kw[field] = None
        result = calculate_residual_income_2stage(kw["bvps"], kw["roe"], kw["ke"], **self.ARGS)
        assert result.status == ValuationStatus.INSUFFICIENT_DATA and result.value is None
        assert missing in (result.reason or "")

    def test_missing_growth_is_named(self) -> None:
        result = calculate_residual_income_2stage(
            D("100"), D("0.3"), D("0.2"), **{**self.ARGS, "growth_high": None}
        )
        assert result.status == ValuationStatus.INSUFFICIENT_DATA
        assert "stage-1 growth" in (result.reason or "")

    def test_invalid_inputs(self) -> None:
        for override in (
            {"book_value_per_share": D("0")},
            {"book_value_per_share": D("-5")},
            {"cost_of_equity": D("0")},
            {"terminal_discount_rate": D("0.03")},  # long-run rate not above terminal growth
        ):
            args: dict[str, Any] = {
                "book_value_per_share": D("100"), "roe": D("0.3"), "cost_of_equity": D("0.2"),
                **self.ARGS,
            }
            args.update(override)
            result = calculate_residual_income_2stage(**args)
            assert result.status == ValuationStatus.INVALID and result.value is None

    def test_deeply_negative_roe_is_invalid_not_a_negative_value(self) -> None:
        result = calculate_residual_income_2stage(D("100"), D("-3"), D("0.2"), **self.ARGS)
        assert result.status == ValuationStatus.INVALID and result.value is None


class TestImpliedUnderTheNewModels:
    FCFE_ARGS: dict[str, Any] = {
        "growth_stable": D("0.054"), "discount_rate": D("0.24"),
        "terminal_growth_rate": D("0.054"), "shares_outstanding": D("100"),
        "terminal_discount_rate": D("0.15"),
    }

    def test_implied_growth_uses_the_debt(self) -> None:
        target = calculate_fcfe_2stage(D("260"), D("0.07"), debt=D("800"), **self.FCFE_ARGS)
        assert target.value is not None
        with_debt = solve_implied_growth(target.value, D("260"), debt=D("800"), **self.FCFE_ARGS)
        without_debt = solve_implied_growth(target.value, D("260"), debt=D("0"), **self.FCFE_ARGS)
        assert with_debt.value is not None and without_debt.value is not None
        assert abs(with_debt.value - D("0.07")) < D("0.0005")
        assert without_debt.value != with_debt.value  # the debt matters to the inversion

    def test_implied_roe_round_trip(self) -> None:
        args: dict[str, Any] = {
            "book_value_per_share": D("11"), "cost_of_equity": D("0.24"),
            "growth_high": D("0.05"), "growth_stable": D("0.054"),
            "terminal_growth_rate": D("0.054"), "terminal_discount_rate": D("0.15"),
        }
        price = calculate_residual_income_2stage(roe=D("0.22"), **args).value
        result = solve_implied_roe_residual_income(
            price, args["book_value_per_share"], args["cost_of_equity"], args["growth_high"],
            args["growth_stable"], args["terminal_growth_rate"], args["terminal_discount_rate"],
        )
        assert result.status == ValuationStatus.AVAILABLE and result.metric == "roe"
        assert result.value is not None and abs(result.value - D("0.22")) < D("0.0005")

    def test_implied_roe_outside_bounds_and_no_price(self) -> None:
        common = (D("11"), D("0.24"), D("0.05"), D("0.054"), D("0.054"), D("0.15"))
        high = solve_implied_roe_residual_income(D("100000"), *common)
        assert high.status == ValuationStatus.INSUFFICIENT_DATA
        assert "over 100%" in (high.reason or "")
        # A tiny price needs a small ROE; the model value reaches zero before the lower bound.
        tiny = solve_implied_roe_residual_income(D("0.001"), *common)
        assert tiny.status == ValuationStatus.AVAILABLE
        assert tiny.value is not None and tiny.value < D("0.1")
        for price in (None, D("0"), D("-1")):
            none = solve_implied_roe_residual_income(price, *common)
            assert none.status == ValuationStatus.INSUFFICIENT_DATA and none.value is None

    def test_implied_roe_with_unusable_inputs(self) -> None:
        result = solve_implied_roe_residual_income(
            D("10"), None, D("0.24"), D("0.05"), D("0.054"), D("0.054"), D("0.15")
        )
        assert result.status == ValuationStatus.INSUFFICIENT_DATA
