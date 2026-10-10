"""Unit tests for the pure investment-score check engine."""

from decimal import Decimal

from app.scores.checks import (
    COMPONENT_ORDER,
    CheckStatus,
    ComponentStatus,
    ScoreInputs,
    buy_zone,
    confidence_for,
    headline_label,
    headline_score,
    run_checks,
    score_all_components,
    score_component,
)

D = Decimal


def test_value_fv_discount_bands() -> None:
    from app.scores.checks import check_value_fv_discount

    assert check_value_fv_discount(
        ScoreInputs(current_price=D("75"), fair_value=D("100"))
    ).status is CheckStatus.PASS
    assert check_value_fv_discount(
        ScoreInputs(current_price=D("90"), fair_value=D("100"))
    ).status is CheckStatus.FAIL
    # Missing never fails and never zeroes: NOT_RUN, not FAIL.
    assert check_value_fv_discount(ScoreInputs(fair_value=D("100"))).status is (
        CheckStatus.NOT_RUN
    )
    assert check_value_fv_discount(ScoreInputs(current_price=D("75"))).status is (
        CheckStatus.NOT_RUN
    )
    # Zero / non-positive denominators are undefined, not failures.
    assert check_value_fv_discount(
        ScoreInputs(current_price=D("75"), fair_value=D("0"))
    ).status is CheckStatus.NOT_RUN
    assert check_value_fv_discount(
        ScoreInputs(current_price=D("0"), fair_value=D("100"))
    ).status is CheckStatus.NOT_RUN


def test_value_pe_pb_edge_cases() -> None:
    from app.scores.checks import (
        check_value_pb_vs_industry,
        check_value_pe_vs_industry,
        check_value_pe_vs_market,
    )

    assert check_value_pe_vs_market(
        ScoreInputs(pe_ratio=D("12"), market_pe_avg=D("18"))
    ).status is CheckStatus.PASS
    assert check_value_pe_vs_industry(
        ScoreInputs(pe_ratio=D("20"), industry_pe_avg=D("15"))
    ).status is CheckStatus.FAIL
    # Negative PE fails the 0 < PE leg (ranks naturally, never skipped).
    assert check_value_pe_vs_market(
        ScoreInputs(pe_ratio=D("-5"), market_pe_avg=D("18"))
    ).status is CheckStatus.FAIL
    # Zero PE likewise fails, it is not treated as missing.
    assert check_value_pe_vs_market(
        ScoreInputs(pe_ratio=D("0"), market_pe_avg=D("18"))
    ).status is CheckStatus.FAIL
    # Missing either side is NOT_RUN.
    assert check_value_pe_vs_market(ScoreInputs(pe_ratio=D("12"))).status is (
        CheckStatus.NOT_RUN
    )
    assert check_value_pb_vs_industry(
        ScoreInputs(pb_ratio=D("1.2"), industry_pb_avg=D("1.8"))
    ).status is CheckStatus.PASS
    assert check_value_pb_vs_industry(
        ScoreInputs(pb_ratio=D("-1"), industry_pb_avg=D("1.8"))
    ).status is CheckStatus.FAIL
    assert check_value_pb_vs_industry(ScoreInputs()).status is CheckStatus.NOT_RUN


def test_past_checks_zero_negative_missing() -> None:
    from app.scores.checks import (
        check_past_eps_growth_vs_industry,
        check_past_eps_vs_5y,
        check_past_roa_vs_industry,
        check_past_roce_trend,
        check_past_roe_level,
    )

    assert check_past_roe_level(ScoreInputs(roe_now=D("0.25"))).status is CheckStatus.PASS
    assert check_past_roe_level(ScoreInputs(roe_now=D("0.05"))).status is CheckStatus.FAIL
    # Negative ROE fails the level; it still ran.
    assert check_past_roe_level(ScoreInputs(roe_now=D("-0.1"))).status is CheckStatus.FAIL
    assert check_past_roe_level(ScoreInputs()).status is CheckStatus.NOT_RUN
    assert check_past_eps_vs_5y(
        ScoreInputs(eps_now=D("5"), eps_5y_ago=D("3"))
    ).status is CheckStatus.PASS
    assert check_past_eps_vs_5y(
        ScoreInputs(eps_now=D("-1"), eps_5y_ago=D("3"))
    ).status is CheckStatus.FAIL
    assert check_past_eps_growth_vs_industry(
        ScoreInputs(eps_growth_1y=D("0.15"), industry_eps_growth_avg=D("0.10"))
    ).status is CheckStatus.PASS
    assert check_past_roce_trend(
        ScoreInputs(roce_now=D("0.10"), roce_3y_ago=D("0.12"))
    ).status is CheckStatus.FAIL
    assert check_past_roa_vs_industry(
        ScoreInputs(roa_now=D("0.06"), industry_roa_avg=D("0.04"))
    ).status is CheckStatus.PASS
    assert check_past_roa_vs_industry(ScoreInputs(roa_now=D("0.06"))).status is (
        CheckStatus.NOT_RUN
    )


def test_health_standard_zero_denominators_not_run() -> None:
    from app.scores.checks import (
        check_health_cash_coverage,
        check_health_interest_cover,
        check_health_leverage_level,
        check_health_leverage_trend,
        check_health_liquidity_lt,
        check_health_liquidity_st,
    )

    assert check_health_liquidity_st(
        ScoreInputs(st_assets=D("100"), st_liabilities=D("60"))
    ).status is CheckStatus.PASS
    assert check_health_liquidity_lt(
        ScoreInputs(st_assets=D("100"), lt_liabilities=D("120"))
    ).status is CheckStatus.FAIL
    assert check_health_leverage_trend(
        ScoreInputs(de_ratio_now=D("0.3"), de_ratio_5y_ago=D("0.5"))
    ).status is CheckStatus.PASS
    assert check_health_leverage_level(ScoreInputs(de_ratio_now=D("0.9"))).status is (
        CheckStatus.FAIL
    )
    assert check_health_cash_coverage(
        ScoreInputs(operating_cash_flow=D("50"), total_debt=D("100"))
    ).status is CheckStatus.PASS
    # Zero debt: coverage undefined -> NOT_RUN, never PASS-by-default.
    assert check_health_cash_coverage(
        ScoreInputs(operating_cash_flow=D("50"), total_debt=D("0"))
    ).status is CheckStatus.NOT_RUN
    assert check_health_interest_cover(
        ScoreInputs(ebit=D("100"), net_interest_expense=D("10"))
    ).status is CheckStatus.PASS
    # Zero interest: cover undefined -> NOT_RUN.
    assert check_health_interest_cover(
        ScoreInputs(ebit=D("100"), net_interest_expense=D("0"))
    ).status is CheckStatus.NOT_RUN


def test_health_bank_track_individually_gated() -> None:
    from app.scores.checks import (
        check_bank_allowance,
        check_bank_capital,
        check_bank_charge_off,
        check_bank_funding,
        check_bank_loans_to_assets,
        check_bank_loans_to_deposits,
    )

    assert check_bank_capital(
        ScoreInputs(total_assets=D("1000"), total_equity=D("100"))
    ).status is CheckStatus.PASS
    assert check_bank_capital(
        ScoreInputs(total_assets=D("3000"), total_equity=D("100"))
    ).status is CheckStatus.FAIL
    assert check_bank_capital(ScoreInputs(total_assets=D("1000"))).status is (
        CheckStatus.NOT_RUN
    )
    assert check_bank_capital(
        ScoreInputs(total_assets=D("1000"), total_equity=D("0"))
    ).status is CheckStatus.NOT_RUN
    assert check_bank_allowance(
        ScoreInputs(bank_allowance=D("50"), bank_npl=D("30"))
    ).status is CheckStatus.PASS
    assert check_bank_allowance(ScoreInputs(bank_allowance=D("50"))).status is (
        CheckStatus.NOT_RUN
    )
    assert check_bank_funding(
        ScoreInputs(bank_deposits=D("700"), bank_total_liabilities=D("1200"))
    ).status is CheckStatus.PASS
    assert check_bank_loans_to_assets(
        ScoreInputs(bank_net_loans=D("800"), total_assets=D("1000"))
    ).status is CheckStatus.PASS
    assert check_bank_loans_to_deposits(
        ScoreInputs(bank_net_loans=D("900"), bank_deposits=D("700"))
    ).status is CheckStatus.FAIL
    assert check_bank_charge_off(
        ScoreInputs(bank_net_charge_offs=D("5"), bank_avg_loans=D("500"))
    ).status is CheckStatus.PASS
    assert check_bank_charge_off(
        ScoreInputs(bank_net_charge_offs=D("5"), bank_avg_loans=D("0"))
    ).status is CheckStatus.NOT_RUN


def test_dividend_narrowed_and_fails_open() -> None:
    from app.scores.checks import (
        check_dividend_earnings_coverage,
        check_dividend_growing,
        check_dividend_stability,
    )

    hist = (D("1.0"), D("1.1"), D("1.2"), D("1.3"))
    assert check_dividend_stability(ScoreInputs(dps_history=hist)).status is (
        CheckStatus.PASS
    )
    assert check_dividend_stability(
        ScoreInputs(dps_history=(D("1.0"), D("0.5")))
    ).status is CheckStatus.FAIL
    assert check_dividend_stability(ScoreInputs(dps_history=(D("1.0"),))).status is (
        CheckStatus.NOT_RUN
    )
    assert check_dividend_stability(ScoreInputs()).status is CheckStatus.NOT_RUN
    # Non-positive base DPS: drop ratio undefined, not a failure.
    assert check_dividend_stability(
        ScoreInputs(dps_history=(D("0"), D("1.0")))
    ).status is CheckStatus.NOT_RUN

    assert check_dividend_earnings_coverage(
        ScoreInputs(earnings_payout=D("0.5"))
    ).status is CheckStatus.PASS
    assert check_dividend_earnings_coverage(
        ScoreInputs(earnings_payout=D("0.95"))
    ).status is CheckStatus.FAIL
    assert check_dividend_earnings_coverage(
        ScoreInputs(earnings_payout=D("-0.2"))
    ).status is CheckStatus.FAIL
    assert check_dividend_earnings_coverage(ScoreInputs()).status is (
        CheckStatus.NOT_RUN
    )

    ten = tuple(D(str(v)) for v in (1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.0))
    assert check_dividend_growing(ScoreInputs(dps_history=ten)).status is (
        CheckStatus.PASS
    )
    # Short pay-history fails OPEN to not-run even when the trend is up.
    assert check_dividend_growing(ScoreInputs(dps_history=hist)).status is (
        CheckStatus.NOT_RUN
    )
    falling = tuple(D(str(v)) for v in (2.0, 1.9, 1.8, 1.7, 1.6, 1.5, 1.4, 1.3, 1.2, 1.0))
    assert check_dividend_growing(ScoreInputs(dps_history=falling)).status is (
        CheckStatus.FAIL
    )


def test_growth_honest_degrade() -> None:
    from app.scores.checks import (
        check_growth_earnings_hist,
        check_growth_revenue_hist,
        check_growth_roe_proxy,
    )

    assert check_growth_earnings_hist(
        ScoreInputs(hist_earnings_growth=D("0.25"))
    ).status is CheckStatus.PASS
    assert check_growth_earnings_hist(
        ScoreInputs(hist_earnings_growth=D("0.05"))
    ).status is CheckStatus.FAIL
    assert check_growth_earnings_hist(ScoreInputs()).status is CheckStatus.NOT_RUN
    assert check_growth_revenue_hist(
        ScoreInputs(hist_revenue_growth=D("0.30"))
    ).status is CheckStatus.PASS
    assert check_growth_revenue_hist(ScoreInputs()).status is CheckStatus.NOT_RUN
    # Disclosed historical proxy for forecast ROE: shares the past input,
    # carries its own forward semantic and threshold citation.
    assert check_growth_roe_proxy(ScoreInputs(roe_now=D("0.25"))).status is (
        CheckStatus.PASS
    )
    assert check_growth_roe_proxy(ScoreInputs(roe_now=D("0.10"))).status is (
        CheckStatus.FAIL
    )
    assert check_growth_roe_proxy(ScoreInputs()).status is CheckStatus.NOT_RUN
    assert "proxy" in check_growth_roe_proxy(ScoreInputs()).threshold


def test_check_result_carries_threshold_and_inputs() -> None:
    from app.scores.checks import check_past_roe_level

    result = check_past_roe_level(ScoreInputs(roe_now=D("0.25")))
    payload = result.as_dict()
    assert payload["status"] == "PASS"
    assert "20%" in payload["threshold"]
    assert payload["inputs"] == {"roe_now": "0.25"}
    assert payload["reason"] != ""


def test_run_checks_routing_and_counts() -> None:
    standard = run_checks(ScoreInputs(), health_track="standard")
    banks = run_checks(ScoreInputs(), health_track="banks")
    # 5 value + 6 past + 6 health + 3 dividend + 3 growth ~= 20 per brief.
    assert len(standard) == 23
    assert len(banks) == 23
    assert {c.check_key for c in standard} - {c.check_key for c in banks} == {
        "health_liquidity_st",
        "health_liquidity_lt",
        "health_leverage_trend",
        "health_leverage_level",
        "health_cash_coverage",
        "health_interest_cover",
    }
    assert {c.check_key for c in banks} - {c.check_key for c in standard} == {
        "bank_capital",
        "bank_allowance",
        "bank_funding",
        "bank_loans_to_assets",
        "bank_loans_to_deposits",
        "bank_charge_off",
    }
    assert all(c.status is CheckStatus.NOT_RUN for c in standard)


def test_component_floor() -> None:
    results = run_checks(ScoreInputs(), health_track="standard")
    components = score_all_components(results)
    assert set(components) == set(COMPONENT_ORDER)
    for comp in components.values():
        assert comp.status is ComponentStatus.INSUFFICIENT_DATA
        assert comp.score is None

    # Exactly at the floor (3 of 6 run) the component is valid.
    from app.scores.checks import check_past_roe_level

    passed = check_past_roe_level(ScoreInputs(roe_now=D("0.5")))
    failed = check_past_roe_level(ScoreInputs(roe_now=D("0.01")))
    missing = check_past_roe_level(ScoreInputs())
    comp = score_component("past", (passed, passed, failed, missing, missing, missing))
    assert comp.status is ComponentStatus.AVAILABLE
    assert comp.score == round(2 / 3 * 100, 1)
    assert comp.passes == 2 and comp.ran == 3 and comp.total == 6


def test_headline_equal_weight_and_floor() -> None:
    from app.scores.checks import ComponentResult

    def valid(score: float) -> ComponentResult:
        return ComponentResult(
            key="x", status=ComponentStatus.AVAILABLE, score=score,
            passes=1, ran=1, total=1, reason="",
        )

    def invalid() -> ComponentResult:
        return ComponentResult(
            key="x", status=ComponentStatus.INSUFFICIENT_DATA, score=None,
            passes=0, ran=0, total=1, reason="",
        )

    comps = {
        "value": valid(100.0), "past": valid(50.0), "health": valid(0.0),
        "dividend": invalid(), "growth": invalid(),
    }
    headline, _reason = headline_score(comps)
    assert headline == round((100.0 + 50.0 + 0.0) / 3, 1)

    thin = {"value": valid(100.0), "past": valid(50.0), **{
        k: invalid() for k in ("health", "dividend", "growth")}}
    headline_none, reason = headline_score(thin)
    assert headline_none is None
    assert "INSUFFICIENT_DATA" in reason


def test_confidence_ladder_display_only() -> None:
    assert confidence_for(85.0, False, 21, 21).level == "VeryHigh"
    assert confidence_for(65.0, False, 15, 21).level == "High"
    assert confidence_for(45.0, False, 11, 21).level == "Medium"
    assert confidence_for(10.0, False, 21, 21).level == "Low"
    # Strong checks cannot outrun weak data quality.
    assert confidence_for(85.0, False, 5, 21).level == "Low"
    # MISSING or unassessed scope caps at Low, score value unknown or not.
    assert confidence_for(None, True, 21, 21).level == "Low"
    assert confidence_for(90.0, True, 21, 21).level == "Low"
    assert "MISSING" in confidence_for(None, True, 21, 21).reason
    # Bands are published on the payload.
    assert len(confidence_for(85.0, False, 21, 21).as_dict()["bands"]) == 4


def test_headline_copy_hedged_never_buy() -> None:
    assert headline_label(None)["label"] == "INSUFFICIENT_DATA"
    for score in (0.0, 10.0, 30.0, 60.0, 90.0):
        copy = headline_label(score)
        assert "BUY" not in copy["detail"].upper()
        assert "potentially" in copy["detail"]


def test_buy_zone_display_only() -> None:
    zone = buy_zone(D("100"), D("70"), D("0.20"))
    assert zone["status"] == "AVAILABLE"
    assert zone["buy_zone_price"] == str(D("80.00"))
    assert zone["in_buy_zone"] is True
    out = buy_zone(D("100"), D("90"), D("0.20"))
    assert out["in_buy_zone"] is False
    missing = buy_zone(None, D("90"), D("0.20"))
    assert missing["status"] == "INSUFFICIENT_DATA"
    assert missing["buy_zone_price"] is None
    zero_fv = buy_zone(D("0"), D("90"), D("0.20"))
    assert zero_fv["status"] == "INSUFFICIENT_DATA"


def test_value_fv_deep_discount_second_tier() -> None:
    from app.scores.checks import check_value_fv_deep_discount

    assert check_value_fv_deep_discount(
        ScoreInputs(current_price=D("55"), fair_value=D("100"))
    ).status is CheckStatus.PASS
    # 25% clears the first tier but not the deep tier.
    assert check_value_fv_deep_discount(
        ScoreInputs(current_price=D("75"), fair_value=D("100"))
    ).status is CheckStatus.FAIL
    assert check_value_fv_deep_discount(ScoreInputs()).status is CheckStatus.NOT_RUN
