"""R46: 3-year true FCFE base, stage-1 growth floor, banks on justified P/B, vendor map 1.3.

Every number is a SYNTHETIC test value seeded by the test itself.
"""

from __future__ import annotations

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
from app.valuation.models import ValuationModel, ValuationStatus, calculate_justified_pb
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
    assert VALUATION_METHODOLOGY_VERSION == "1.3"
    assert VENDOR_MAPPING_VERSION == "stockanalysis-map-1.3"
    assert FCFE_BASE_YEARS == 3
    assert D("0") == STAGE1_GROWTH_FLOOR
    assert VALUATION_PROFILES["banks"]["primary_model"] == "justified_pb"
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
    async def test_three_year_mean_of_true_fcfe(self, db_session: AsyncSession) -> None:
        _c, st = await _statements(
            db_session,
            {
                2022: _year(cfo=D("100"), capex=D("-20"), net_borrowing=D("0")),  # 80
                2023: _year(cfo=D("200"), capex=D("-40"), net_borrowing=D("-10")),  # 150
                2024: _year(cfo=D("300"), capex=D("-50"), net_borrowing=D("20")),  # 270
            },
        )
        base = bridge.fcfe_base(st, st.latest())
        assert base.resolved.available
        assert base.resolved.value == D("500") / D("3")
        assert [(y.fiscal_year, y.fcfe) for y in base.years] == [
            (2024, D("270")), (2023, D("150")), (2022, D("80")),
        ]
        payload = base.payload()
        assert payload["years_required"] == 3
        assert "net borrowing" in payload["method"]
        assert [D(y["fcfe"]) for y in payload["years"]] == [D("270"), D("150"), D("80")]

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

    async def test_missing_net_borrowing_year_is_missing_never_zero(
        self, db_session: AsyncSession
    ) -> None:
        _c, st = await _statements(
            db_session,
            {
                2022: _year(net_borrowing=D("0")),
                2023: _year(),  # no net_borrowing line
                2024: _year(net_borrowing=D("0")),
            },
        )
        base = bridge.fcfe_base(st, st.latest())
        assert base.resolved.status == "INSUFFICIENT_DATA"
        assert base.resolved.value is None
        assert "FY2023" in (base.resolved.reason or "")
        assert "net_borrowing" in (base.resolved.reason or "")
        year_2023 = next(y for y in base.years if y.fiscal_year == 2023)
        assert year_2023.status == "INSUFFICIENT_DATA" and year_2023.fcfe is None

    async def test_missing_capex_names_the_line(self, db_session: AsyncSession) -> None:
        values = _year(net_borrowing=D("0"))
        del values["capex"]
        _c, st = await _statements(
            db_session, {2022: _year(net_borrowing=D("0")), 2023: values, 2024: values}
        )
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
                2022: _year(cfo=D("100"), capex=D("-20"), net_borrowing=D("20"), **minority),
                2023: _year(cfo=D("100"), capex=D("-20"), net_borrowing=D("20")),  # no minorities
                2024: _year(cfo=D("100"), capex=D("-20"), net_borrowing=D("20"), **minority),
            },
        )
        base = bridge.fcfe_base(st, st.latest())
        assert base.resolved.available
        by_year = {y.fiscal_year: y for y in base.years}
        assert by_year[2024].parent_share == D("0.75")
        assert by_year[2024].fcfe == D("75")  # (100 - 20 + 20) x 0.75
        assert by_year[2023].parent_share == D("1")
        assert by_year[2023].fcfe == D("100")
        assert base.resolved.value == D("250") / D("3")

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


async def test_default_company_uses_the_three_year_fcfe_base(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await _company(db_session)
    fair = await _fair(client, company)
    assert fair["methodology_version"] == "1.3"
    assert fair["profile"]["primary_model"] == "fcfe_two_stage"
    assert fair["profile"]["detection"] == "sector"
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["status"] == "AVAILABLE", intrinsic
    # (300 - 50 + 10) x 1 in every year
    assert D(fair["inputs"]["free_cash_flow"]) == D("260")
    base = fair["inputs"]["fcfe_base"]
    assert base["years_required"] == 3 and base["status"] == "AVAILABLE"
    assert [y["fiscal_year"] for y in base["years"]] == [2024, 2023, 2022]
    assert all(D(y["fcfe"]) == D("260") for y in base["years"])
    assert "net borrowing" in base["method"]
    assumptions = intrinsic["assumptions"]
    assert D(assumptions["fcfe_FY2024"]) == D("260") == D(assumptions["fcfe_FY2022"])
    assert D(assumptions["fcfe_base_mean"]) == D("260")
    assert "3 fiscal years" in assumptions["fcfe_base_method"]
    assert "3-year mean FCFE" in fair["input_sources"]["free_cash_flow"]


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


async def test_non_positive_three_year_mean_is_invalid(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await _company(db_session, cfo=D("10"), capex=D("-100"))  # 10 - 100 + 10 < 0
    fair = await _fair(client, company)
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["status"] == "INVALID"
    assert intrinsic["value"] is None
    assert D(fair["inputs"]["free_cash_flow"]) == D("-80")


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


async def test_bank_uses_justified_pb_from_statement_lines(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await _company(db_session, net_loans=D("700"), total_deposits=D("900"))
    fair = await _fair(client, company)
    assert fair["profile"]["profile_id"] == "banks"
    assert fair["profile"]["primary_model"] == "justified_pb"
    assert fair["profile"]["detection"] == "statement_lines: net_loans + total_deposits"
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["model"] == "justified_pb"
    assert fair["inputs"]["fcfe_base"] is None  # banks do not use cash flows
    assert fair["inputs"]["free_cash_flow"] is None
    # BVPS = 1100 / 100 = 11; ke = 0.24; g = 0.054; ROE = the strict-average ROE metric
    assert intrinsic["status"] == "AVAILABLE", intrinsic
    a = intrinsic["assumptions"]
    assert D(a["bvps"]) == D("11")
    assert D(a["cost_of_equity"]) == D("0.24")
    assert D(a["growth"]) == D("0.054")
    assert D(a["roe"]) == D("0.1818")  # 18.18 %: net income / average equity (stored 2 dp)
    justified = (D(a["roe"]) - D("0.054")) / (D("0.24") - D("0.054"))
    assert abs(D(intrinsic["value"]) - D("11") * justified) < D("0.001")
    assert fair["fair_value"]["basis"] == "intrinsic_only"
    assert "stable_roe" in fair["input_sources"]
    assert [r["parameter"] for r in fair["sensitivity"]] == ["discount_rate"] * 4


async def test_bank_without_roe_is_insufficient_and_names_roe(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await make_company(db_session)
    # One year only: no average-equity ROE can exist.
    await seed_year(
        db_session, company, 2024,
        _year(net_loans=D("700"), total_deposits=D("900"), net_borrowing=D("0")),
    )
    await seed_prices(db_session, company, bars=30)
    fair = await _fair(client, company)
    intrinsic = fair["legs"]["intrinsic"]
    assert intrinsic["model"] == "justified_pb"
    assert intrinsic["status"] == "INSUFFICIENT_DATA"
    assert "ROE" in intrinsic["reason"]
    assert fair["fair_value"]["value"] is None
