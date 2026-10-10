"""Unit tests for Phase-3 valuation models (SWS 4-model engine + PS + router).

Every formula ships edge-case coverage per AGENTS.md rule 7:
zero, negative, and missing inputs — plus the invalid-parameter guards.
"""

from decimal import Decimal

import pytest

from app.valuation.fairvalue import (
    TikrInputs,
    confidence_for_dq,
    scenario_inputs,
    verdict_for,
    weighted_fair_value,
)
from app.valuation.models import (
    ValuationModel,
    ValuationStatus,
    calculate_affo_2stage,
    calculate_ddm,
    calculate_excess_returns,
    calculate_fcfe_2stage,
    calculate_ps_valuation,
    select_preferred_multiple,
)


def D(value: str) -> Decimal:
    return Decimal(value)


FCFE_KWARGS = {
    "free_cash_flow": D("100"),
    "growth_high": D("0.10"),
    "growth_stable": D("0.04"),
    "discount_rate": D("0.12"),
    "terminal_growth_rate": D("0.03"),
    "shares_outstanding": D("50"),
}


class TestPSValuation:
    def test_basic(self) -> None:
        result = calculate_ps_valuation(D("4"), D("3"))
        assert result.status == ValuationStatus.AVAILABLE
        assert result.value == D("12")
        assert result.model == ValuationModel.PS

    def test_zero_rps_invalid(self) -> None:
        result = calculate_ps_valuation(D("0"), D("3"))
        assert result.status == ValuationStatus.INVALID
        assert result.value is None

    def test_negative_rps_invalid(self) -> None:
        result = calculate_ps_valuation(D("-4"), D("3"))
        assert result.status == ValuationStatus.INVALID

    def test_missing(self) -> None:
        assert (
            calculate_ps_valuation(None, D("3")).status
            == ValuationStatus.INSUFFICIENT_DATA
        )
        assert (
            calculate_ps_valuation(D("4"), None).status
            == ValuationStatus.INSUFFICIENT_DATA
        )


class TestFcfe2Stage:
    def test_basic_positive(self) -> None:
        result = calculate_fcfe_2stage(**FCFE_KWARGS)
        assert result.status == ValuationStatus.AVAILABLE
        assert result.value is not None and result.value > 0
        assert result.assumptions["formula"] == "2-stage FCFE with Gordon terminal value"

    def test_missing_inputs(self) -> None:
        kwargs = dict(FCFE_KWARGS, growth_high=None)
        assert calculate_fcfe_2stage(**kwargs).status == ValuationStatus.INSUFFICIENT_DATA

    def test_zero_fcf_invalid(self) -> None:
        kwargs = dict(FCFE_KWARGS, free_cash_flow=D("0"))
        result = calculate_fcfe_2stage(**kwargs)
        assert result.status == ValuationStatus.INVALID
        assert result.value is None

    def test_negative_fcf_invalid(self) -> None:
        kwargs = dict(FCFE_KWARGS, free_cash_flow=D("-100"))
        assert calculate_fcfe_2stage(**kwargs).status == ValuationStatus.INVALID

    def test_discount_below_terminal_invalid(self) -> None:
        kwargs = dict(FCFE_KWARGS, discount_rate=D("0.02"))
        result = calculate_fcfe_2stage(**kwargs)
        assert result.status == ValuationStatus.INVALID

    def test_zero_discount_invalid(self) -> None:
        kwargs = dict(FCFE_KWARGS, discount_rate=D("0"))
        assert calculate_fcfe_2stage(**kwargs).status == ValuationStatus.INVALID

    def test_zero_horizon_invalid(self) -> None:
        kwargs = dict(FCFE_KWARGS, years_high=0)
        assert calculate_fcfe_2stage(**kwargs).status == ValuationStatus.INVALID

    def test_higher_discount_lowers_value(self) -> None:
        low = calculate_fcfe_2stage(**FCFE_KWARGS)
        high = calculate_fcfe_2stage(
            **{**FCFE_KWARGS, "discount_rate": D("0.15")}
        )
        assert low.value is not None and high.value is not None
        assert high.value < low.value

    def test_higher_growth_raises_value(self) -> None:
        low = calculate_fcfe_2stage(**FCFE_KWARGS)
        high = calculate_fcfe_2stage(**{**FCFE_KWARGS, "growth_high": D("0.15")})
        assert low.value is not None and high.value is not None
        assert high.value > low.value


class TestDDM:
    def test_basic_matches_gordon(self) -> None:
        # 2 / (0.10 - 0.03) = 28.5714
        result = calculate_ddm(D("2"), D("0.10"), D("0.03"))
        assert result.status == ValuationStatus.AVAILABLE
        assert result.value == D("28.5714")

    def test_missing(self) -> None:
        assert calculate_ddm(None, D("0.10"), D("0.03")).status == (
            ValuationStatus.INSUFFICIENT_DATA
        )

    def test_zero_dps_invalid(self) -> None:
        result = calculate_ddm(D("0"), D("0.10"), D("0.03"))
        assert result.status == ValuationStatus.INVALID
        assert result.value is None

    def test_negative_dps_invalid(self) -> None:
        assert calculate_ddm(D("-1"), D("0.10"), D("0.03")).status == (
            ValuationStatus.INVALID
        )

    def test_discount_below_growth_invalid(self) -> None:
        assert calculate_ddm(D("2"), D("0.02"), D("0.03")).status == (
            ValuationStatus.INVALID
        )


class TestExcessReturns:
    def test_basic_matches_sws_mechanics(self) -> None:
        # Excess = (0.098 - 0.0761) × 35.38 = 0.7748;
        # terminal = 0.7748 / (0.0761 - 0.02); FV = 35.38 + terminal.
        result = calculate_excess_returns(D("35.38"), D("0.098"), D("0.0761"), D("0.02"))
        assert result.status == ValuationStatus.AVAILABLE
        assert result.value is not None
        assert result.value > D("35.38")

    def test_missing(self) -> None:
        assert calculate_excess_returns(None, D("0.10"), D("0.08"), D("0.02")).status == (
            ValuationStatus.INSUFFICIENT_DATA
        )

    def test_zero_bvps_invalid(self) -> None:
        result = calculate_excess_returns(D("0"), D("0.10"), D("0.08"), D("0.02"))
        assert result.status == ValuationStatus.INVALID
        assert result.value is None

    def test_negative_bvps_invalid(self) -> None:
        assert calculate_excess_returns(D("-5"), D("0.10"), D("0.08"), D("0.02")).status == (
            ValuationStatus.INVALID
        )

    def test_coe_below_growth_invalid(self) -> None:
        assert calculate_excess_returns(D("10"), D("0.10"), D("0.02"), D("0.03")).status == (
            ValuationStatus.INVALID
        )

    def test_deeply_negative_excess_invalid(self) -> None:
        # ROE far below CoE drives fair value non-positive: honest INVALID.
        result = calculate_excess_returns(D("10"), D("-5"), D("0.10"), D("0.02"))
        assert result.status == ValuationStatus.INVALID
        assert result.value is None


class TestAffo2Stage:
    def test_basic_positive(self) -> None:
        result = calculate_affo_2stage(
            D("80"), D("0.08"), D("0.03"), D("0.11"), D("0.02"), shares_outstanding=D("40")
        )
        assert result.status == ValuationStatus.AVAILABLE
        assert result.value is not None and result.value > 0
        assert result.assumptions["cash_flow_source"] == "affo"

    def test_ffo_source_recorded(self) -> None:
        result = calculate_affo_2stage(
            D("80"), D("0.08"), D("0.03"), D("0.11"), D("0.02"), cash_flow_source="ffo"
        )
        assert result.status == ValuationStatus.AVAILABLE
        assert result.assumptions["cash_flow_source"] == "ffo"

    def test_unknown_source_invalid(self) -> None:
        result = calculate_affo_2stage(
            D("80"), D("0.08"), D("0.03"), D("0.11"), D("0.02"), cash_flow_source="ebitda"
        )
        assert result.status == ValuationStatus.INVALID

    def test_missing(self) -> None:
        assert calculate_affo_2stage(
            None, D("0.08"), D("0.03"), D("0.11"), D("0.02")
        ).status == ValuationStatus.INSUFFICIENT_DATA

    def test_zero_cash_flow_invalid(self) -> None:
        assert calculate_affo_2stage(
            D("0"), D("0.08"), D("0.03"), D("0.11"), D("0.02")
        ).status == ValuationStatus.INVALID

    def test_negative_cash_flow_invalid(self) -> None:
        assert calculate_affo_2stage(
            D("-80"), D("0.08"), D("0.03"), D("0.11"), D("0.02")
        ).status == ValuationStatus.INVALID


class TestPreferredMultipleRouter:
    def test_profitable_picks_pe(self) -> None:
        result = select_preferred_multiple(D("5"), D("10"), D("20"), D("2"), D("30"), D("1.5"))
        assert result.status == ValuationStatus.AVAILABLE
        assert result.model == ValuationModel.PE
        assert result.value == D("50")
        assert result.assumptions["selected_multiple"] == "pe"

    def test_unprofitable_falls_to_ps(self) -> None:
        result = select_preferred_multiple(
            D("-5"), D("10"), D("20"), D("2"), D("30"), D("1.5")
        )
        assert result.model == ValuationModel.PS
        assert result.value == D("40")
        assert result.assumptions["selected_multiple"] == "ps"

    def test_no_eps_falls_to_pb(self) -> None:
        result = select_preferred_multiple(None, None, None, None, D("30"), D("1.5"))
        assert result.model == ValuationModel.PB
        assert result.value == D("45.0")
        assert result.assumptions["selected_multiple"] == "pb"

    def test_absurd_pe_skipped(self) -> None:
        result = select_preferred_multiple(D("5"), D("200"), D("20"), D("2"), None, None)
        assert result.model == ValuationModel.PS

    def test_nothing_usable_is_insufficient_never_zero(self) -> None:
        result = select_preferred_multiple(None, None, None, None, None, None)
        assert result.status == ValuationStatus.INSUFFICIENT_DATA
        assert result.value is None

    def test_zero_basis_inputs_skipped(self) -> None:
        result = select_preferred_multiple(D("0"), D("10"), D("0"), D("2"), D("0"), D("1.5"))
        assert result.status == ValuationStatus.INSUFFICIENT_DATA
        assert result.value is None


class TestWeightedFairValue:
    def test_weights_both_legs(self) -> None:
        value, n = weighted_fair_value(
            {"intrinsic": D("100"), "relative": D("50")},
            {"intrinsic": D("0.6"), "relative": D("0.4")},
        )
        assert value == D("80")
        assert n == 2

    def test_missing_leg_skipped_with_renormalization(self) -> None:
        value, n = weighted_fair_value(
            {"intrinsic": None, "relative": D("50")},
            {"intrinsic": D("0.6"), "relative": D("0.4")},
        )
        assert value == D("50")
        assert n == 1

    def test_all_missing_is_null_never_zero(self) -> None:
        value, n = weighted_fair_value(
            {"intrinsic": None, "relative": None},
            {"intrinsic": D("0.6"), "relative": D("0.4")},
        )
        assert value is None
        assert n == 0


class TestScenariosAndLadder:
    def test_scenario_deltas_bracket_base(self) -> None:
        base = TikrInputs(D("0.05"), D("0.15"), D("12"))
        assert scenario_inputs(base, 0) == base
        bull, bear = scenario_inputs(base, 1), scenario_inputs(base, -1)
        assert bull.revenue_growth > base.revenue_growth > bear.revenue_growth
        assert bull.operating_margin > base.operating_margin > bear.operating_margin
        assert bull.exit_multiple > base.exit_multiple > bear.exit_multiple

    @pytest.mark.parametrize(
        ("score", "level", "required"),
        [
            (95.0, "VeryHigh", "0.10"),
            (80.0, "VeryHigh", "0.10"),
            (70.0, "High", "0.15"),
            (50.0, "Medium", "0.20"),
            (10.0, "Low", "0.30"),
            (0.0, "POOR", "0.30"),
        ],
    )
    def test_confidence_ladder(self, score: float, level: str, required: str) -> None:
        confidence = confidence_for_dq(score, "OK")
        assert confidence.level == level
        assert confidence.required_discount == D(required)

    def test_confidence_missing_degrades(self) -> None:
        confidence = confidence_for_dq(0.0, "MISSING")
        assert confidence.level == "MISSING"

    def test_confidence_no_assessment_caps_poor(self) -> None:
        confidence = confidence_for_dq(None, None)
        assert confidence.level == "POOR"
        assert confidence.required_discount == D("0.30")

    def test_verdict_undervalued_language(self) -> None:
        verdict = verdict_for(D("100"), D("70"), D("0.20"))
        assert verdict["label"] == "POTENTIALLY_UNDERVALUED"
        assert "under these assumptions" in verdict["detail"]
        assert "BUY" not in verdict["detail"]

    def test_verdict_overvalued_language(self) -> None:
        verdict = verdict_for(D("100"), D("130"), D("0.20"))
        assert verdict["label"] == "POTENTIALLY_OVERVALUED"

    def test_verdict_around_fair_value(self) -> None:
        verdict = verdict_for(D("100"), D("95"), D("0.20"))
        assert verdict["label"] == "AROUND_FAIR_VALUE"

    def test_verdict_missing_inputs(self) -> None:
        assert verdict_for(None, D("70"), D("0.20"))["label"] == "INSUFFICIENT_DATA"
        assert verdict_for(D("100"), None, D("0.20"))["label"] == "INSUFFICIENT_DATA"
