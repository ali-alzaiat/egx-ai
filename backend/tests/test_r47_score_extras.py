"""R47 Q1 Piotroski F-Score and Q2 dividend safety: pure maths plus the score payload."""

from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.statement_seed import make_company, seed_year

from app.scores.constants import SCORE_METHODOLOGY_VERSION
from app.scores.dividend_safety import LABEL, evaluate_dividend_safety, evaluate_year
from app.scores.piotroski import (
    CHECKS_TOTAL,
    PIOTROSKI_METHODOLOGY_VERSION,
    evaluate_piotroski,
)

D = Decimal

# A company that improves on every dimension in FY2024 vs FY2023.
PRIOR = {
    "net_income": D("5"),
    "total_assets": D("100"),
    "cfo": D("6"),
    "interest_bearing_debt": D("40"),
    "current_assets": D("50"),
    "current_liabilities": D("40"),
    "shares_outstanding": D("100"),
    "gross_profit": D("30"),
    "revenue": D("100"),
}
LATEST = {
    "net_income": D("10"),
    "total_assets": D("110"),
    "cfo": D("15"),
    "interest_bearing_debt": D("30"),
    "current_assets": D("66"),
    "current_liabilities": D("40"),
    "shares_outstanding": D("100"),
    "gross_profit": D("45"),
    "revenue": D("130"),
}


def _run(  # type: ignore[no-untyped-def]
    latest: dict[str, Decimal] | None = None, prior: dict[str, Decimal] | None = None
):
    return evaluate_piotroski(
        LATEST if latest is None else latest,
        PRIOR if prior is None else prior,
        fiscal_year=2024,
        prior_fiscal_year=2023,
    )


def _status(result, key: str) -> str:  # type: ignore[no-untyped-def]
    return next(c.status for c in result.checks if c.key == key)


# --- Piotroski ------------------------------------------------------------------------------


def test_all_nine_pass() -> None:
    r = _run()
    assert r.version == PIOTROSKI_METHODOLOGY_VERSION
    assert (r.status, r.passes, r.checks_run, r.checks_total) == ("AVAILABLE", 9, 9, 9)
    assert len(r.checks) == CHECKS_TOTAL
    assert [c.status for c in r.checks] == ["PASS"] * 9


def test_hand_calculated_ratios() -> None:
    r = _run()
    roa = next(c for c in r.checks if c.key == "roa_improving")
    assert D(roa.inputs["ratio_now"] or "") == D("10") / D("110")
    assert D(roa.inputs["ratio_prior"] or "") == D("5") / D("100")
    cr = next(c for c in r.checks if c.key == "current_ratio_improving")
    assert D(cr.inputs["ratio_now"] or "") == D("1.65")


def test_each_check_can_fail_alone() -> None:
    cases = {
        "roa_positive": {"net_income": D("-1")},
        "cfo_positive": {"cfo": D("-1")},
        "roa_improving": {"net_income": D("5")},  # 5/110 < 5/100
        "accruals_cash_backed": {"cfo": D("9")},  # cfo 9 < net income 10 (still > 0)
        "leverage_falling": {"interest_bearing_debt": D("50")},
        "current_ratio_improving": {"current_assets": D("40")},
        "no_new_shares": {"shares_outstanding": D("120")},
        "gross_margin_improving": {"gross_profit": D("30")},  # 30/130 < 30/100
        "asset_turnover_improving": {"revenue": D("100")},  # 100/110 < 100/100
    }
    for key, change in cases.items():
        r = _run(latest={**LATEST, **change})
        assert _status(r, key) == "FAIL", key
        assert r.checks_run == 9, key


def test_zero_values_are_values_not_missing() -> None:
    # Zero debt both years: leverage equal, not improved -> FAIL (a real 0, not missing).
    r = _run(
        latest={**LATEST, "interest_bearing_debt": D("0")},
        prior={**PRIOR, "interest_bearing_debt": D("0")},
    )
    assert _status(r, "leverage_falling") == "FAIL"
    # Zero net income is not a positive ROA.
    r2 = _run(latest={**LATEST, "net_income": D("0")})
    assert _status(r2, "roa_positive") == "FAIL"


def test_missing_input_is_insufficient_never_fail() -> None:
    latest = {k: v for k, v in LATEST.items() if k != "interest_bearing_debt"}
    r = _run(latest=latest)
    leverage = next(c for c in r.checks if c.key == "leverage_falling")
    assert leverage.status == "INSUFFICIENT_DATA"
    assert leverage.reason is not None and "interest_bearing_debt" in leverage.reason
    assert r.checks_run == 8 and r.passes == 8


def test_unusable_denominators_are_insufficient() -> None:
    r = _run(latest={**LATEST, "total_assets": D("0")})
    for key in ("roa_positive", "roa_improving", "leverage_falling", "asset_turnover_improving"):
        assert _status(r, key) == "INSUFFICIENT_DATA", key
    r2 = _run(latest={**LATEST, "current_liabilities": D("0")})
    assert _status(r2, "current_ratio_improving") == "INSUFFICIENT_DATA"
    r3 = _run(latest={**LATEST, "revenue": D("-5")})
    assert _status(r3, "gross_margin_improving") == "INSUFFICIENT_DATA"


def test_no_prior_year_runs_only_level_checks() -> None:
    r = evaluate_piotroski(LATEST, None, fiscal_year=2024, prior_fiscal_year=2023)
    assert r.status == "AVAILABLE"
    assert r.checks_run == 3  # roa_positive, cfo_positive, accruals_cash_backed
    assert r.passes == 3
    assert _status(r, "no_new_shares") == "INSUFFICIENT_DATA"


def test_nothing_usable_is_insufficient_not_zero() -> None:
    r = evaluate_piotroski({}, None, fiscal_year=2024, prior_fiscal_year=2023)
    assert r.status == "INSUFFICIENT_DATA"
    assert r.passes is None and r.checks_run == 0
    none = evaluate_piotroski(None, None, fiscal_year=None, prior_fiscal_year=None)
    assert none.status == "INSUFFICIENT_DATA" and none.passes is None


def test_bank_is_not_run_with_reason() -> None:
    r = evaluate_piotroski(
        LATEST, PRIOR, fiscal_year=2024, prior_fiscal_year=2023, is_bank=True
    )
    assert r.status == "NOT_RUN"
    assert r.passes is None and r.checks_run == 0 and r.checks == ()
    assert r.reason is not None and "bank" in r.reason.lower()


def test_new_shares_flagged_with_bonus_caveat() -> None:
    r = _run(latest={**LATEST, "shares_outstanding": D("110")})
    check = next(c for c in r.checks if c.key == "no_new_shares")
    assert check.status == "FAIL"
    assert check.reason is not None and "bonus" in check.reason


# --- dividend safety -----------------------------------------------------------------------


def _year(**kw: str) -> dict[str, Decimal]:
    base = {
        "dividends_paid": D("-30"),
        "net_income": D("100"),
        "cfo": D("200"),
        "capex": D("-50"),
    }
    base.update({k: D(v) for k, v in kw.items()})
    return base


def test_payout_and_coverage_hand_calculation() -> None:
    y = evaluate_year(2024, _year())
    assert y.status == "PAID"
    assert y.payout_ratio.value == "0.3000"  # 30 / 100
    assert y.cash_coverage.value == "5.0000"  # (200 - 50) / 30


def test_dividend_sign_is_ignored_by_abs() -> None:
    assert evaluate_year(2024, _year(dividends_paid="30")).payout_ratio.value == "0.3000"


def test_loss_year_payout_not_meaningful_but_coverage_still_computed() -> None:
    y = evaluate_year(2024, _year(net_income="-10"))
    assert y.payout_ratio.status == "NOT_MEANINGFUL"
    assert y.payout_ratio.value is None and y.payout_ratio.reason is not None
    assert y.cash_coverage.status == "AVAILABLE"
    zero = evaluate_year(2024, _year(net_income="0"))
    assert zero.payout_ratio.status == "NOT_MEANINGFUL"


def test_no_dividends_line_is_insufficient_not_no_dividend() -> None:
    vals = _year()
    del vals["dividends_paid"]
    y = evaluate_year(2024, vals)
    assert y.status == "INSUFFICIENT_DATA"
    assert y.payout_ratio.status == "INSUFFICIENT_DATA" and y.payout_ratio.value is None
    assert y.cash_coverage.status == "INSUFFICIENT_DATA"
    assert "dividends_paid" in (y.reason or "")


def test_zero_dividends_line_is_a_real_no_dividend() -> None:
    y = evaluate_year(2024, _year(dividends_paid="0"))
    assert y.status == "NO_DIVIDEND"
    assert y.payout_ratio.status == "AVAILABLE" and y.payout_ratio.value == "0.0000"
    assert y.cash_coverage.status == "NOT_MEANINGFUL"


def test_negative_coverage_is_a_value() -> None:
    y = evaluate_year(2024, _year(cfo="10"))  # (10 - 50) / 30
    assert y.cash_coverage.status == "AVAILABLE"
    assert y.cash_coverage.value == "-1.3333"


def test_missing_cash_flow_lines_name_the_gap() -> None:
    vals = _year()
    del vals["capex"]
    y = evaluate_year(2024, vals)
    assert y.cash_coverage.status == "INSUFFICIENT_DATA"
    assert "capex" in (y.cash_coverage.reason or "")
    assert y.payout_ratio.status == "AVAILABLE"
    no_ni = _year()
    del no_ni["net_income"]
    assert evaluate_year(2024, no_ni).payout_ratio.status == "INSUFFICIENT_DATA"


def test_bank_coverage_not_meaningful() -> None:
    y = evaluate_year(2024, _year(), is_bank=True)
    assert y.cash_coverage.status == "NOT_MEANINGFUL"
    assert y.payout_ratio.status == "AVAILABLE"


def test_three_year_context_and_missing_year() -> None:
    result = evaluate_dividend_safety({2024: _year(), 2022: _year()}, 2024)
    assert result.label == LABEL == "from dividends paid (derived)"
    assert [y.fiscal_year for y in result.years] == [2024, 2023, 2022]
    assert result.years[1].status == "INSUFFICIENT_DATA"
    assert result.status == "AVAILABLE" and result.latest is result.years[0]


def test_no_statements_is_insufficient() -> None:
    result = evaluate_dividend_safety({}, None)
    assert result.status == "INSUFFICIENT_DATA" and result.latest is None and result.years == ()


# --- API payload ---------------------------------------------------------------------------


async def test_score_payload_carries_both_blocks(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session, industry="Software")
    prior = {**PRIOR, "dividends_paid": D("-3"), "capex": D("-4")}
    latest = {**LATEST, "dividends_paid": D("-5"), "capex": D("-6")}
    await seed_year(db_session, company, 2023, prior)
    await seed_year(db_session, company, 2024, latest)
    body = (await client.get(f"/api/scores/companies/{company.id}")).json()

    assert body["methodology_version"] == SCORE_METHODOLOGY_VERSION  # unchanged
    pio = body["piotroski"]
    assert pio["status"] == "AVAILABLE" and pio["passes"] == 9 and pio["checks_run"] == 9
    assert pio["checks_total"] == 9 and pio["fiscal_year"] == 2024
    assert pio["version"] == PIOTROSKI_METHODOLOGY_VERSION
    assert pio["source_tier"] == "vendor" and pio["provisional"] is True
    assert {c["key"] for c in pio["checks"]} >= {"roa_positive", "no_new_shares"}

    div = body["dividend_safety"]
    assert div["status"] == "AVAILABLE" and div["label"] == LABEL
    assert div["latest"]["fiscal_year"] == 2024
    assert div["latest"]["payout_ratio"]["value"] == "0.5000"  # 5 / 10
    assert div["latest"]["cash_coverage"]["value"] == "1.8000"  # (15 - 6) / 5
    assert [y["fiscal_year"] for y in div["years"]] == [2024, 2023, 2022]
    assert div["years"][2]["status"] == "INSUFFICIENT_DATA"
    assert div["source_tier"] == "vendor"


async def test_score_payload_blocks_without_statements(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session)
    body = (await client.get(f"/api/scores/companies/{company.id}")).json()
    assert body["piotroski"]["status"] == "INSUFFICIENT_DATA"
    assert body["piotroski"]["passes"] is None
    assert body["dividend_safety"]["status"] == "INSUFFICIENT_DATA"
    assert body["dividend_safety"]["latest"] is None


async def test_bank_detected_from_lines_is_not_run(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    company = await make_company(db_session)
    bank = {**LATEST, "net_loans": D("500"), "total_deposits": D("900")}
    await seed_year(db_session, company, 2024, {**bank, "dividends_paid": D("-5")})
    body = (await client.get(f"/api/scores/companies/{company.id}")).json()
    assert body["piotroski"]["status"] == "NOT_RUN"
    assert "net loans" in body["piotroski"]["reason"]
    assert body["dividend_safety"]["latest"]["cash_coverage"]["status"] == "NOT_MEANINGFUL"
