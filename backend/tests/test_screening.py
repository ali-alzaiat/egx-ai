"""Tests for Shariah screening rules and service."""

from decimal import Decimal

from app.screening.methodology import DEFAULT_METHODOLOGY
from app.screening.rules import (
    ScreeningVerdict,
    screen_cash_and_securities,
    screen_debt_ratio,
    screen_industry,
    screen_interest_income,
)


class TestDebtRatioScreening:
    def test_pass_under_threshold(self):
        result = screen_debt_ratio(
            total_debt=Decimal("25"),
            total_assets=Decimal("100"),
            threshold=Decimal("0.33"),
        )
        assert result.verdict == ScreeningVerdict.PASS
        assert result.value == Decimal("0.25")

    def test_fail_over_threshold(self):
        result = screen_debt_ratio(
            total_debt=Decimal("40"),
            total_assets=Decimal("100"),
            threshold=Decimal("0.33"),
        )
        assert result.verdict == ScreeningVerdict.FAIL
        assert result.value == Decimal("0.40")

    def test_fail_at_threshold(self):
        result = screen_debt_ratio(
            total_debt=Decimal("33"),
            total_assets=Decimal("100"),
            threshold=Decimal("0.33"),
        )
        assert result.verdict == ScreeningVerdict.FAIL

    def test_missing_data(self):
        result = screen_debt_ratio(
            total_debt=None,
            total_assets=Decimal("100"),
        )
        assert result.verdict == ScreeningVerdict.INSUFFICIENT_DATA

    def test_zero_assets(self):
        result = screen_debt_ratio(
            total_debt=Decimal("10"),
            total_assets=Decimal("0"),
        )
        assert result.verdict == ScreeningVerdict.INSUFFICIENT_DATA


class TestInterestIncomeScreening:
    def test_pass_under_threshold(self):
        result = screen_interest_income(
            interest_income=Decimal("3"),
            total_revenue=Decimal("100"),
            threshold=Decimal("0.05"),
        )
        assert result.verdict == ScreeningVerdict.PASS
        assert result.value == Decimal("0.03")

    def test_fail_over_threshold(self):
        result = screen_interest_income(
            interest_income=Decimal("6"),
            total_revenue=Decimal("100"),
            threshold=Decimal("0.05"),
        )
        assert result.verdict == ScreeningVerdict.FAIL
        assert result.value == Decimal("0.06")

    def test_missing_data(self):
        result = screen_interest_income(
            interest_income=None,
            total_revenue=Decimal("100"),
        )
        assert result.verdict == ScreeningVerdict.INSUFFICIENT_DATA


class TestCashAndSecuritiesScreening:
    def test_pass_under_threshold(self):
        result = screen_cash_and_securities(
            cash_and_securities=Decimal("20"),
            total_assets=Decimal("100"),
            threshold=Decimal("0.33"),
        )
        assert result.verdict == ScreeningVerdict.PASS
        assert result.value == Decimal("0.20")

    def test_fail_over_threshold(self):
        result = screen_cash_and_securities(
            cash_and_securities=Decimal("40"),
            total_assets=Decimal("100"),
            threshold=Decimal("0.33"),
        )
        assert result.verdict == ScreeningVerdict.FAIL
        assert result.value == Decimal("0.40")


class TestIndustryScreening:
    def test_pass_permitted_industry(self):
        result = screen_industry(
            industry="Technology",
            prohibited_industries=("alcohol", "gambling", "pork"),
        )
        assert result.verdict == ScreeningVerdict.PASS

    def test_fail_prohibited_industry(self):
        result = screen_industry(
            industry="Alcohol Production",
            prohibited_industries=("alcohol", "gambling", "pork"),
        )
        assert result.verdict == ScreeningVerdict.FAIL

    def test_missing_industry(self):
        result = screen_industry(
            industry=None,
            prohibited_industries=("alcohol", "gambling", "pork"),
        )
        assert result.verdict == ScreeningVerdict.INSUFFICIENT_DATA


class TestDefaultMethodology:
    def test_thresholds(self):
        assert DEFAULT_METHODOLOGY.debt_to_assets_threshold == Decimal("0.33")
        assert DEFAULT_METHODOLOGY.interest_income_to_revenue_threshold == Decimal("0.05")
        assert DEFAULT_METHODOLOGY.cash_and_securities_to_assets_threshold == Decimal("0.33")

    def test_version(self):
        assert DEFAULT_METHODOLOGY.version.value == "1.0"

    def test_source_reference(self):
        assert "AAOIFI" in DEFAULT_METHODOLOGY.source_reference
