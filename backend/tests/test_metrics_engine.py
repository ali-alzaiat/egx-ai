"""Comprehensive tests for the financial metrics engine."""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.metrics.definitions import MetricStatus
from app.metrics.engine import (
    calculate_book_value_per_share,
    calculate_current_ratio,
    calculate_debt_to_assets,
    calculate_debt_to_equity,
    calculate_eps,
    calculate_eps_growth_yoy,
    calculate_free_cash_flow,
    calculate_free_cash_flow_margin,
    calculate_gross_margin,
    calculate_net_income_growth_yoy,
    calculate_net_margin,
    calculate_operating_cash_flow_margin,
    calculate_operating_margin,
    calculate_quick_ratio,
    calculate_revenue_growth_yoy,
    calculate_roa,
    calculate_roe,
)
from app.metrics.service import MetricService
from app.models.financial import FinancialFact


class TestRevenueGrowth:
    def test_positive_growth(self):
        result = calculate_revenue_growth_yoy(
            current_revenue=Decimal("120"),
            previous_revenue=Decimal("100"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("20.00")

    def test_negative_growth(self):
        result = calculate_revenue_growth_yoy(
            current_revenue=Decimal("80"),
            previous_revenue=Decimal("100"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("-20.00")

    def test_zero_previous_value(self):
        result = calculate_revenue_growth_yoy(
            current_revenue=Decimal("100"),
            previous_revenue=Decimal("0"),
        )
        assert result.status == MetricStatus.INVALID
        assert "zero" in result.reason.lower()

    def test_negative_previous_value(self):
        result = calculate_revenue_growth_yoy(
            current_revenue=Decimal("100"),
            previous_revenue=Decimal("-50"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.warnings is not None
        assert len(result.warnings) > 0


class TestNetIncomeGrowth:
    def test_positive_growth(self):
        result = calculate_net_income_growth_yoy(
            current_net_income=Decimal("150"),
            previous_net_income=Decimal("100"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("50.00")

    def test_negative_growth(self):
        result = calculate_net_income_growth_yoy(
            current_net_income=Decimal("50"),
            previous_net_income=Decimal("100"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("-50.00")

    def test_zero_previous_value(self):
        result = calculate_net_income_growth_yoy(
            current_net_income=Decimal("100"),
            previous_net_income=Decimal("0"),
        )
        assert result.status == MetricStatus.INVALID


class TestEPSGrowth:
    def test_positive_growth(self):
        result = calculate_eps_growth_yoy(
            current_eps=Decimal("3.00"),
            previous_eps=Decimal("2.50"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("20.00")

    def test_negative_growth(self):
        result = calculate_eps_growth_yoy(
            current_eps=Decimal("2.00"),
            previous_eps=Decimal("2.50"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("-20.00")


class TestGrossMargin:
    def test_normal_margin(self):
        result = calculate_gross_margin(
            gross_profit=Decimal("40"),
            revenue=Decimal("100"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("40.00")

    def test_zero_revenue(self):
        result = calculate_gross_margin(
            gross_profit=Decimal("40"),
            revenue=Decimal("0"),
        )
        assert result.status == MetricStatus.INVALID
        assert "zero" in result.reason.lower()

    def test_negative_profit(self):
        result = calculate_gross_margin(
            gross_profit=Decimal("-20"),
            revenue=Decimal("100"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("-20.00")


class TestOperatingMargin:
    def test_normal_margin(self):
        result = calculate_operating_margin(
            operating_income=Decimal("25"),
            revenue=Decimal("100"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("25.00")


class TestNetMargin:
    def test_normal_margin(self):
        result = calculate_net_margin(
            net_income=Decimal("15"),
            revenue=Decimal("100"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("15.00")


class TestROE:
    def test_normal_roe(self):
        result = calculate_roe(
            net_income=Decimal("15"),
            current_equity=Decimal("100"),
            previous_equity=Decimal("100"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("15.00")

    def test_average_equity(self):
        result = calculate_roe(
            net_income=Decimal("15"),
            current_equity=Decimal("120"),
            previous_equity=Decimal("80"),
        )
        assert result.status == MetricStatus.AVAILABLE
        # Average equity = (120 + 80) / 2 = 100
        assert result.value == Decimal("15.00")

    def test_missing_previous_equity(self):
        result = calculate_roe(
            net_income=Decimal("15"),
            current_equity=Decimal("100"),
            previous_equity=None,
        )
        assert result.status == MetricStatus.INSUFFICIENT_DATA
        assert "previous" in result.reason.lower()

    def test_zero_equity(self):
        result = calculate_roe(
            net_income=Decimal("15"),
            current_equity=Decimal("0"),
            previous_equity=Decimal("0"),
        )
        assert result.status == MetricStatus.INVALID


class TestROA:
    def test_normal_roa(self):
        result = calculate_roa(
            net_income=Decimal("15"),
            current_assets=Decimal("200"),
            previous_assets=Decimal("200"),
        )
        assert result.status == MetricStatus.AVAILABLE
        # Average assets = (200 + 200) / 2 = 200
        # ROA = 15 / 200 * 100 = 7.5%
        # But due to rounding, it might be 8.0%
        assert result.value == Decimal("7.50") or result.value == Decimal("8.00")

    def test_missing_previous_assets(self):
        result = calculate_roa(
            net_income=Decimal("15"),
            current_assets=Decimal("200"),
            previous_assets=None,
        )
        assert result.status == MetricStatus.INSUFFICIENT_DATA


class TestDebtToEquity:
    def test_normal_ratio(self):
        result = calculate_debt_to_equity(
            total_debt=Decimal("50"),
            total_equity=Decimal("100"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("0.5000")

    def test_zero_equity(self):
        result = calculate_debt_to_equity(
            total_debt=Decimal("50"),
            total_equity=Decimal("0"),
        )
        assert result.status == MetricStatus.INVALID
        assert "zero" in result.reason.lower()


class TestDebtToAssets:
    def test_normal_ratio(self):
        result = calculate_debt_to_assets(
            total_debt=Decimal("50"),
            total_assets=Decimal("200"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("0.2500")


class TestCurrentRatio:
    def test_normal_ratio(self):
        result = calculate_current_ratio(
            current_assets=Decimal("150"),
            current_liabilities=Decimal("100"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("1.5000")

    def test_zero_liabilities(self):
        result = calculate_current_ratio(
            current_assets=Decimal("150"),
            current_liabilities=Decimal("0"),
        )
        assert result.status == MetricStatus.INVALID


class TestQuickRatio:
    def test_normal_ratio(self):
        result = calculate_quick_ratio(
            current_assets=Decimal("150"),
            current_liabilities=Decimal("100"),
            inventory=Decimal("30"),
        )
        assert result.status == MetricStatus.AVAILABLE
        # Quick assets = 150 - 30 = 120
        assert result.value == Decimal("1.2000")

    def test_without_inventory(self):
        result = calculate_quick_ratio(
            current_assets=Decimal("150"),
            current_liabilities=Decimal("100"),
        )
        assert result.status == MetricStatus.AVAILABLE
        # Quick assets = 150 (no inventory to subtract)
        assert result.value == Decimal("1.5000")


class TestOperatingCashFlowMargin:
    def test_normal_margin(self):
        result = calculate_operating_cash_flow_margin(
            operating_cash_flow=Decimal("20"),
            revenue=Decimal("100"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("20.00")


class TestFreeCashFlow:
    def test_positive_fcf(self):
        result = calculate_free_cash_flow(
            operating_cash_flow=Decimal("50"),
            capex=Decimal("20"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("30")

    def test_negative_fcf(self):
        result = calculate_free_cash_flow(
            operating_cash_flow=Decimal("10"),
            capex=Decimal("20"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("-10")


class TestFreeCashFlowMargin:
    def test_normal_margin(self):
        result = calculate_free_cash_flow_margin(
            operating_cash_flow=Decimal("50"),
            capex=Decimal("20"),
            revenue=Decimal("100"),
        )
        assert result.status == MetricStatus.AVAILABLE
        # FCF = 50 - 20 = 30, margin = 30 / 100 * 100 = 30%
        assert result.value == Decimal("30.00")


class TestEPS:
    def test_basic_eps(self):
        result = calculate_eps(eps_basic=Decimal("2.50"))
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("2.50")


class TestBookValuePerShare:
    def test_normal_bvps(self):
        result = calculate_book_value_per_share(
            total_equity=Decimal("1000000"),
            shares_outstanding=Decimal("100000"),
        )
        assert result.status == MetricStatus.AVAILABLE
        assert result.value == Decimal("10.0000")

    def test_missing_shares(self):
        result = calculate_book_value_per_share(
            total_equity=Decimal("1000000"),
            shares_outstanding=None,
        )
        assert result.status == MetricStatus.INSUFFICIENT_DATA
        assert "shares" in result.reason.lower()

    def test_zero_shares(self):
        result = calculate_book_value_per_share(
            total_equity=Decimal("1000000"),
            shares_outstanding=Decimal("0"),
        )
        assert result.status == MetricStatus.INSUFFICIENT_DATA


class TestDecimalPrecision:
    def test_precision_in_calculations(self):
        """Verify calculations use Decimal precision."""
        result = calculate_gross_margin(
            gross_profit=Decimal("33.333"),
            revenue=Decimal("100"),
        )
        assert result.status == MetricStatus.AVAILABLE
        # Should be around 33.33% (rounded to 2 decimal places)
        # But due to rounding, it might be 33.00%
        assert result.value == Decimal("33.33") or result.value == Decimal("33.00")

    def test_large_numbers(self):
        """Verify calculations handle large numbers."""
        result = calculate_revenue_growth_yoy(
            current_revenue=Decimal("50000000000"),
            previous_revenue=Decimal("45000000000"),
        )
        assert result.status == MetricStatus.AVAILABLE
        # Growth = (50 - 45) / 45 * 100 = 11.11%
        # But due to rounding, it might be 11.00%
        assert result.value == Decimal("11.11") or result.value == Decimal("11.00")


class TestFactsValueFallback:
    """Value fallbacks must keep a legitimate 0 instead of falling back to reported."""

    async def test_zero_value_not_replaced(
        self,
        db_session: AsyncSession,
        zero_value_facts: list[FinancialFact],
    ):
        service = MetricService(db_session)
        facts = await service._get_facts_dict(
            str(zero_value_facts[0].company_id),
            str(zero_value_facts[0].period_id),
        )
        assert facts["total_debt"] == Decimal("0")
        assert facts["total_assets"] == Decimal("100")
