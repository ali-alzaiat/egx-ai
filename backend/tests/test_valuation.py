"""Tests for valuation models."""

import pytest
from decimal import Decimal

from app.valuation.models import (
    ValuationModel,
    ValuationStatus,
    calculate_dcf_valuation,
    calculate_ev_ebitda_valuation,
    calculate_pb_valuation,
    calculate_pe_valuation,
)


class TestPEValuation:
    def test_basic_pe(self):
        result = calculate_pe_valuation(
            earnings_per_share=Decimal("2.50"),
            pe_ratio=Decimal("15"),
        )
        assert result.status == ValuationStatus.AVAILABLE
        assert result.value == Decimal("37.5000")

    def test_negative_eps(self):
        result = calculate_pe_valuation(
            earnings_per_share=Decimal("-2.50"),
            pe_ratio=Decimal("15"),
        )
        assert result.status == ValuationStatus.INVALID

    def test_missing_data(self):
        result = calculate_pe_valuation(
            earnings_per_share=None,
            pe_ratio=Decimal("15"),
        )
        assert result.status == ValuationStatus.INSUFFICIENT_DATA


class TestPBValuation:
    def test_basic_pb(self):
        result = calculate_pb_valuation(
            book_value_per_share=Decimal("10"),
            pb_ratio=Decimal("2"),
        )
        assert result.status == ValuationStatus.AVAILABLE
        assert result.value == Decimal("20.0000")

    def test_negative_bvps(self):
        result = calculate_pb_valuation(
            book_value_per_share=Decimal("-10"),
            pb_ratio=Decimal("2"),
        )
        assert result.status == ValuationStatus.INVALID


class TestEVEBITDAValuation:
    def test_basic_ev_ebitda(self):
        result = calculate_ev_ebitda_valuation(
            ebitda=Decimal("100"),
            ev_ebitda_ratio=Decimal("8"),
            net_debt=Decimal("200"),
            shares_outstanding=Decimal("50"),
        )
        assert result.status == ValuationStatus.AVAILABLE
        # EV = 100 * 8 = 800
        # Equity = 800 - 200 = 600
        # Price = 600 / 50 = 12
        assert result.value == Decimal("12.0000")

    def test_negative_ebitda(self):
        result = calculate_ev_ebitda_valuation(
            ebitda=Decimal("-100"),
            ev_ebitda_ratio=Decimal("8"),
            net_debt=Decimal("200"),
            shares_outstanding=Decimal("50"),
        )
        assert result.status == ValuationStatus.INVALID


class TestDCFValuation:
    def test_basic_dcf(self):
        result = calculate_dcf_valuation(
            free_cash_flow=Decimal("100"),
            growth_rate=Decimal("0.05"),
            discount_rate=Decimal("0.10"),
            terminal_growth_rate=Decimal("0.02"),
            projection_years=5,
            shares_outstanding=Decimal("50"),
        )
        assert result.status == ValuationStatus.AVAILABLE
        assert result.value is not None
        assert result.value > 0

    def test_negative_fcf(self):
        result = calculate_dcf_valuation(
            free_cash_flow=Decimal("-100"),
            growth_rate=Decimal("0.05"),
            discount_rate=Decimal("0.10"),
            terminal_growth_rate=Decimal("0.02"),
        )
        assert result.status == ValuationStatus.INVALID

    def test_discount_rate_less_than_terminal(self):
        result = calculate_dcf_valuation(
            free_cash_flow=Decimal("100"),
            growth_rate=Decimal("0.05"),
            discount_rate=Decimal("0.01"),
            terminal_growth_rate=Decimal("0.02"),
        )
        assert result.status == ValuationStatus.INVALID


class TestAssumptions:
    def test_pe_assumptions(self):
        result = calculate_pe_valuation(
            earnings_per_share=Decimal("2.50"),
            pe_ratio=Decimal("15"),
        )
        assert "eps" in result.assumptions
        assert "pe_ratio" in result.assumptions
        assert "formula" in result.assumptions

    def test_dcf_assumptions(self):
        result = calculate_dcf_valuation(
            free_cash_flow=Decimal("100"),
            growth_rate=Decimal("0.05"),
            discount_rate=Decimal("0.10"),
            terminal_growth_rate=Decimal("0.02"),
        )
        assert "fcf" in result.assumptions
        assert "growth_rate" in result.assumptions
        assert "discount_rate" in result.assumptions
        assert "terminal_growth_rate" in result.assumptions
