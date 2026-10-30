"""R46 round 2: implied growth / ROE (V6), trading currency (C1).

Every number is a SYNTHETIC test value seeded by the test itself.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest

from app.ingestion.egx.provider import normalize_currency
from app.ingestion.trading_currency import backfill_trading_currency
from app.statements.bridge import load_company_statements
from app.valuation.assumptions import MARKET_SCOPE, record_assumption
from app.valuation.fairvalue import currency_check
from app.valuation.models import (
    ValuationStatus,
    calculate_fcfe_2stage,
    calculate_residual_income_2stage,
    solve_implied_growth,
)
from statement_seed import FULL_YEAR, make_company, seed_prices, seed_year

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.market import Company

D = Decimal

# A representative model: cash flow base 260, 100 shares, ke 24 % then 15 %, g 5.4 %.
_FCF, _SHARES = D("260"), D("100")
_STABLE, _G = D("0.054"), D("0.054")
_KE, _LR = D("0.24"), D("0.15")


def _value(growth: Decimal) -> Decimal:
    result = calculate_fcfe_2stage(
        _FCF, growth, _STABLE, _KE, _G, shares_outstanding=_SHARES, terminal_discount_rate=_LR
    )
    assert result.value is not None
    return result.value


def _solve(price: Decimal | None, **overrides: Any) -> Any:
    args: dict[str, Any] = {
        "free_cash_flow": _FCF, "growth_stable": _STABLE, "discount_rate": _KE,
        "terminal_growth_rate": _G, "shares_outstanding": _SHARES,
        "terminal_discount_rate": _LR,
    }
    args.update(overrides)
    return solve_implied_growth(price, **args)


# --- V6: implied growth (pure) ----------------------------------------------------------------


class TestImpliedGrowth:
    @pytest.mark.parametrize("growth", [D("-0.2"), D("0"), D("0.07"), D("0.1359"), D("0.6")])
    def test_round_trip(self, growth: Decimal) -> None:
        result = _solve(_value(growth))
        assert result.status == ValuationStatus.AVAILABLE
        assert result.metric == "growth_high"
        assert abs(result.value - growth) < D("0.0005")

    def test_is_deterministic(self) -> None:
        assert _solve(D("12.5")).value == _solve(D("12.5")).value

    def test_higher_price_implies_higher_growth(self) -> None:
        low, high = _solve(D("10")), _solve(D("20"))
        assert low.value < high.value

    def test_price_below_the_lower_bound(self) -> None:
        result = _solve(D("0.01"))
        assert result.status == ValuationStatus.INSUFFICIENT_DATA
        assert result.value is None
        assert "under -50%" in result.reason

    def test_price_above_the_upper_bound(self) -> None:
        result = _solve(D("1000000"))
        assert result.status == ValuationStatus.INSUFFICIENT_DATA
        assert result.value is None
        assert "over 100%" in result.reason

    @pytest.mark.parametrize("price", [None, D("0"), D("-3")])
    def test_no_usable_price(self, price: Decimal | None) -> None:
        result = _solve(price)
        assert result.status == ValuationStatus.INSUFFICIENT_DATA
        assert "price" in result.reason

    def test_non_positive_cash_flow_has_nothing_to_invert(self) -> None:
        for fcf in (D("0"), D("-5")):
            result = _solve(D("12"), free_cash_flow=fcf)
            assert result.status == ValuationStatus.INSUFFICIENT_DATA
            assert result.value is None
            assert "no value to invert" in result.reason

    def test_missing_input_is_insufficient(self) -> None:
        result = _solve(D("12"), discount_rate=None)
        assert result.status == ValuationStatus.INSUFFICIENT_DATA

    def test_missing_shares_is_insufficient(self) -> None:
        result = _solve(D("12"), shares_outstanding=None)
        assert result.status == ValuationStatus.INSUFFICIENT_DATA
        assert "shares" in result.reason

    def test_custom_bounds_are_reported(self) -> None:
        result = _solve(D("12"), lower=D("-0.1"), upper=D("0.3"))
        assert result.bounds == (D("-0.1"), D("0.3"))


# --- C1: currency -----------------------------------------------------------------------------


class TestCurrency:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("EGP", "EGP"), ("USD", "USD"), (" USD ", "USD"), ("GBp", None), ("usd", None),
         ("", None), (None, None), (840, None), ("EGPP", None)],
    )
    def test_normalize_currency(self, raw: object, expected: str | None) -> None:
        assert normalize_currency(raw) == expected

    def test_check_states(self) -> None:
        assert currency_check("EGP", "EGP")["status"] == "MATCH"
        assert currency_check(None, "EGP")["status"] == "UNKNOWN"
        assert currency_check("USD", None)["status"] == "UNKNOWN"
        mismatch = currency_check("USD", "EGP")
        assert mismatch["status"] == "MISMATCH"
        assert mismatch["reason"] == "price in USD, statements in EGP"

    async def test_statements_currency_comes_from_the_lines(
        self, db_session: AsyncSession
    ) -> None:
        company = await make_company(db_session)
        await seed_year(db_session, company, 2024, dict(FULL_YEAR))
        st = await load_company_statements(db_session, company.id)
        latest = st.latest()
        assert latest is not None
        assert latest.currency() == "EGP"


class TestBackfill:
    async def test_stores_what_the_provider_reports_and_never_guesses(
        self, db_session: AsyncSession
    ) -> None:
        usd = await make_company(db_session)
        egp = await make_company(db_session)
        silent = await make_company(db_session)
        answers = {usd.ticker: "USD", egp.ticker: "EGP", silent.ticker: None}

        async def fetch(ticker: str) -> str | None:
            return answers[ticker]

        when = datetime(2026, 10, 30, tzinfo=UTC)
        summary = await backfill_trading_currency(
            db_session, fetch, [usd.ticker, egp.ticker, silent.ticker], now=when
        )
        assert summary.checked == 3 and summary.updated == 2
        assert summary.unreported == [silent.ticker]
        assert summary.by_currency == {"USD": 1, "EGP": 1}
        assert usd.trading_currency == "USD" and usd.trading_currency_checked_at == when
        assert egp.trading_currency == "EGP"
        assert silent.trading_currency is None  # NOT defaulted from companies.currency
        assert silent.trading_currency_checked_at is None
        assert any("USD" in line and usd.ticker in line for line in summary.lines())

    async def test_dry_run_writes_nothing(self, db_session: AsyncSession) -> None:
        company = await make_company(db_session)

        async def fetch(_ticker: str) -> str | None:
            return "USD"

        summary = await backfill_trading_currency(
            db_session, fetch, [company.ticker], dry_run=True
        )
        assert summary.updated == 0 and summary.by_currency == {"USD": 1}
        assert company.trading_currency is None


# --- end to end through the fair-value endpoint ------------------------------------------------


async def _record(db: AsyncSession, key: str, value: str) -> None:
    await record_assumption(
        db, key=key, scope=MARKET_SCOPE, value=D(value),
        source_url="https://example.test/assumption",
        source_title="SYNTHETIC test assumption", as_of=date.today() - timedelta(days=1),
    )


async def _assumptions(db: AsyncSession) -> None:
    await _record(db, "risk_free_rate", "0.20")
    await _record(db, "equity_risk_premium", "0.04")
    await _record(db, "long_run_inflation", "0.054")
    await _record(db, "long_run_cost_of_equity", "0.15")
    await _record(db, "nominal_gdp_growth", "0.1359")


async def _company(
    db: AsyncSession, *, trading_currency: str | None = None, **extra: Decimal
) -> Company:
    company = await make_company(db)
    company.trading_currency = trading_currency
    for fiscal_year in (2021, 2022, 2023, 2024):
        values = dict(FULL_YEAR)
        values["net_borrowing"] = D("10")
        values.update(extra)
        await seed_year(db, company, fiscal_year, values)
    await seed_prices(db, company, bars=30)
    await db.flush()
    return company


async def _fair(client: AsyncClient, company: Company) -> dict[str, Any]:
    response = await client.get(f"/api/valuation/companies/{company.id}/fair-value")
    assert response.status_code == 200, response.text[:300]
    body: dict[str, Any] = response.json()
    return body


async def test_implied_growth_block_for_an_fcfe_company(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await _company(db_session)
    fair = await _fair(client, company)
    implied = fair["implied"]
    assert implied["metric"] == "growth_high"
    assert implied["model"] == "fcfe_two_stage"
    assert implied["compare_to"]["key"] == "nominal_gdp_growth"
    assert D(implied["compare_to"]["value"]) == D("0.1359")
    assert implied["bounds"] == {"min": "-0.5", "max": "1.0"}
    assert implied["price"] == fair["current_price"]["value"]
    assert implied["status"] == "AVAILABLE", implied
    # plugging the implied growth back into the model reproduces the price
    a = fair["legs"]["intrinsic"]["assumptions"]
    back = calculate_fcfe_2stage(
        D(a["fcf"]), D(implied["value"]), D(a["growth_stable"]), D(a["discount_rate"]),
        D(a["terminal_growth_rate"]), shares_outstanding=D(a["shares_outstanding"]),
        terminal_discount_rate=D(a["terminal_discount_rate"]), debt=D(a["debt"]),
    )
    assert back.value is not None
    assert abs(back.value - D(implied["price"])) < D("0.05")
    # display only: the verdict is whatever it was without it
    assert fair["verdict"]["label"] in {
        "POTENTIALLY_UNDERVALUED", "POTENTIALLY_OVERVALUED", "AROUND_FAIR_VALUE",
    }


async def test_implied_is_insufficient_when_the_model_has_no_value(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await _company(  # negative flow base and no positive ROE: no fallback either
        db_session, cfo=D("10"), capex=D("-100"), net_income=D("-200")
    )
    implied = (await _fair(client, company))["implied"]
    assert implied["status"] == "INSUFFICIENT_DATA"
    assert implied["value"] is None
    assert "no value to invert" in implied["reason"]


async def test_implied_roe_block_for_a_bank(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await _company(db_session, net_loans=D("700"), total_deposits=D("900"))
    fair = await _fair(client, company)
    implied = fair["implied"]
    assert implied["metric"] == "roe" and implied["model"] == "residual_income_2stage"
    assert implied["status"] == "AVAILABLE", implied
    assert implied["bounds"] == {"min": "-0.5", "max": "1.0"}
    assert D(implied["compare_to"]["value"]) == D("0.1818")  # the computed 3-year ROE
    assert implied["compare_to"]["key"] == "roe"
    # plugging the implied ROE back into the residual income model reproduces the price
    a = fair["legs"]["intrinsic"]["assumptions"]
    back = calculate_residual_income_2stage(
        D(a["bvps"]), D(implied["value"]), D(a["cost_of_equity"]), D(a["growth_high"]),
        D(a["growth_stable"]), D(a["terminal_growth_rate"]),
        terminal_discount_rate=D(a["terminal_discount_rate"]),
    )
    assert back.value is not None
    assert abs(back.value - D(fair["current_price"]["value"])) < D("0.05")


async def test_currency_mismatch_blocks_verdict_and_implied(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await _assumptions(db_session)
    company = await _company(db_session, trading_currency="USD")
    fair = await _fair(client, company)
    assert fair["currency"] == {
        "status": "MISMATCH", "trading_currency": "USD", "statements_currency": "EGP",
        "reason": "price in USD, statements in EGP",
    }
    assert fair["verdict"]["label"] == "INSUFFICIENT_DATA"
    assert fair["verdict"]["discount"] is None
    assert "price in USD, statements in EGP" in fair["verdict"]["detail"]
    assert fair["implied"]["status"] == "INSUFFICIENT_DATA"
    assert fair["implied"]["reason"] == "price in USD, statements in EGP"
    # the fair value itself stays in statement currency, never converted
    assert fair["fair_value"]["value"] is not None


@pytest.mark.parametrize(("trading", "status"), [("EGP", "MATCH"), (None, "UNKNOWN")])
async def test_matching_or_unknown_currency_keeps_the_verdict(
    client: AsyncClient, db_session: AsyncSession, trading: str | None, status: str
) -> None:
    await _assumptions(db_session)
    company = await _company(db_session, trading_currency=trading)
    fair = await _fair(client, company)
    assert fair["currency"]["status"] == status
    assert fair["verdict"]["label"] != "INSUFFICIENT_DATA"
