"""Deterministic metric calculation engine.

All calculations use Decimal for precision.
No LLM or AI is used for calculations.
Each function is pure and independently testable.
"""

from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import NamedTuple

from app.metrics.definitions import MetricStatus


class MetricResult(NamedTuple):
    """Result of a metric calculation."""
    value: Decimal | None
    status: MetricStatus
    reason: str | None = None
    warnings: list[str] | None = None


def _safe_divide(
    numerator: Decimal,
    denominator: Decimal,
    precision: int = 4,
) -> Decimal | None:
    """Safely divide two Decimals, returning None if denominator is zero."""
    if denominator == 0:
        return None
    try:
        result = numerator / denominator
        return result.quantize(Decimal(10) ** -precision, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def _calculate_growth(
    current: Decimal,
    previous: Decimal,
    precision: int = 2,
) -> MetricResult:
    """Calculate growth percentage."""
    if previous == 0:
        return MetricResult(
            value=None,
            status=MetricStatus.INVALID,
            reason="Previous period value is zero, growth undefined",
        )

    growth = _safe_divide(current - previous, abs(previous), precision)
    if growth is None:
        return MetricResult(
            value=None,
            status=MetricStatus.INVALID,
            reason="Division by zero in growth calculation",
        )

    warnings = []
    if previous < 0:
        warnings.append(
            f"Previous period value is negative ({previous}), "
            "growth interpretation may be misleading"
        )

    return MetricResult(
        value=growth * Decimal("100"),
        status=MetricStatus.AVAILABLE,
        warnings=warnings if warnings else None,
    )


def _calculate_margin(
    numerator: Decimal,
    denominator: Decimal,
    precision: int = 2,
) -> MetricResult:
    """Calculate margin percentage."""
    if denominator == 0:
        return MetricResult(
            value=None,
            status=MetricStatus.INVALID,
            reason="Revenue is zero, margin undefined",
        )

    margin = _safe_divide(numerator, denominator, precision)
    if margin is None:
        return MetricResult(
            value=None,
            status=MetricStatus.INVALID,
            reason="Division by zero in margin calculation",
        )

    return MetricResult(
        value=margin * Decimal("100"),
        status=MetricStatus.AVAILABLE,
    )


def _calculate_ratio(
    numerator: Decimal,
    denominator: Decimal,
    precision: int = 4,
) -> MetricResult:
    """Calculate a simple ratio."""
    if denominator == 0:
        return MetricResult(
            value=None,
            status=MetricStatus.INVALID,
            reason="Denominator is zero, ratio undefined",
        )

    ratio = _safe_divide(numerator, denominator, precision)
    if ratio is None:
        return MetricResult(
            value=None,
            status=MetricStatus.INVALID,
            reason="Division by zero in ratio calculation",
        )

    return MetricResult(
        value=ratio,
        status=MetricStatus.AVAILABLE,
    )


def _calculate_average_ratio(
    numerator: Decimal,
    current_value: Decimal,
    previous_value: Decimal | None,
    precision: int = 2,
    as_percentage: bool = True,
) -> MetricResult:
    """Calculate a ratio using average of current and previous values."""
    if previous_value is not None:
        average = (current_value + previous_value) / Decimal("2")
    else:
        return MetricResult(
            value=None,
            status=MetricStatus.INSUFFICIENT_DATA,
            reason="Previous comparable period value is unavailable, "
                   "cannot calculate average",
        )

    if average == 0:
        return MetricResult(
            value=None,
            status=MetricStatus.INVALID,
            reason="Average denominator is zero, ratio undefined",
        )

    result = _safe_divide(numerator, average, precision)
    if result is None:
        return MetricResult(
            value=None,
            status=MetricStatus.INVALID,
            reason="Division by zero in ratio calculation",
        )

    if as_percentage:
        result = result * Decimal("100")

    return MetricResult(
        value=result,
        status=MetricStatus.AVAILABLE,
    )


# Metric calculation functions

def calculate_revenue_growth_yoy(
    current_revenue: Decimal,
    previous_revenue: Decimal,
) -> MetricResult:
    """Calculate year-over-year revenue growth."""
    return _calculate_growth(current_revenue, previous_revenue)


def calculate_net_income_growth_yoy(
    current_net_income: Decimal,
    previous_net_income: Decimal,
) -> MetricResult:
    """Calculate year-over-year net income growth."""
    return _calculate_growth(current_net_income, previous_net_income)


def calculate_eps_growth_yoy(
    current_eps: Decimal,
    previous_eps: Decimal,
) -> MetricResult:
    """Calculate year-over-year EPS growth."""
    return _calculate_growth(current_eps, previous_eps)


def calculate_gross_margin(
    gross_profit: Decimal,
    revenue: Decimal,
) -> MetricResult:
    """Calculate gross margin percentage."""
    return _calculate_margin(gross_profit, revenue)


def calculate_operating_margin(
    operating_income: Decimal,
    revenue: Decimal,
) -> MetricResult:
    """Calculate operating margin percentage."""
    return _calculate_margin(operating_income, revenue)


def calculate_net_margin(
    net_income: Decimal,
    revenue: Decimal,
) -> MetricResult:
    """Calculate net profit margin percentage."""
    return _calculate_margin(net_income, revenue)


def calculate_roe(
    net_income: Decimal,
    current_equity: Decimal,
    previous_equity: Decimal | None,
) -> MetricResult:
    """Calculate return on equity using average equity."""
    return _calculate_average_ratio(
        net_income, current_equity, previous_equity,
        precision=2, as_percentage=True,
    )


def calculate_roa(
    net_income: Decimal,
    current_assets: Decimal,
    previous_assets: Decimal | None,
) -> MetricResult:
    """Calculate return on assets using average assets."""
    return _calculate_average_ratio(
        net_income, current_assets, previous_assets,
        precision=2, as_percentage=True,
    )


def calculate_debt_to_equity(
    total_debt: Decimal,
    total_equity: Decimal,
) -> MetricResult:
    """Calculate debt-to-equity ratio."""
    return _calculate_ratio(total_debt, total_equity)


def calculate_debt_to_assets(
    total_debt: Decimal,
    total_assets: Decimal,
) -> MetricResult:
    """Calculate debt-to-assets ratio."""
    return _calculate_ratio(total_debt, total_assets)


def calculate_current_ratio(
    current_assets: Decimal,
    current_liabilities: Decimal,
) -> MetricResult:
    """Calculate current ratio."""
    return _calculate_ratio(current_assets, current_liabilities)


def calculate_quick_ratio(
    current_assets: Decimal,
    current_liabilities: Decimal,
    inventory: Decimal | None = None,
    prepaid_expenses: Decimal | None = None,
) -> MetricResult:
    """Calculate quick ratio.

    Quick Ratio = (Current Assets - Inventory - Prepaid Expenses) / Current Liabilities
    """
    quick_assets = current_assets
    if inventory is not None:
        quick_assets = quick_assets - inventory
    if prepaid_expenses is not None:
        quick_assets = quick_assets - prepaid_expenses

    return _calculate_ratio(quick_assets, current_liabilities)


def calculate_operating_cash_flow_margin(
    operating_cash_flow: Decimal,
    revenue: Decimal,
) -> MetricResult:
    """Calculate operating cash flow margin percentage."""
    return _calculate_margin(operating_cash_flow, revenue)


def calculate_free_cash_flow(
    operating_cash_flow: Decimal,
    capex: Decimal,
) -> MetricResult:
    """Calculate free cash flow.

    FCF = Operating Cash Flow - Capital Expenditures
    Capex is assumed to be stored as a positive expenditure amount.
    """
    fcf = operating_cash_flow - capex
    return MetricResult(
        value=fcf,
        status=MetricStatus.AVAILABLE,
    )


def calculate_free_cash_flow_margin(
    operating_cash_flow: Decimal,
    capex: Decimal,
    revenue: Decimal,
) -> MetricResult:
    """Calculate free cash flow margin percentage."""
    fcf = operating_cash_flow - capex
    return _calculate_margin(fcf, revenue)


def calculate_eps(
    eps_basic: Decimal,
) -> MetricResult:
    """Calculate earnings per share (uses reported basic EPS)."""
    return MetricResult(
        value=eps_basic,
        status=MetricStatus.AVAILABLE,
    )


def calculate_book_value_per_share(
    total_equity: Decimal,
    shares_outstanding: Decimal | None,
) -> MetricResult:
    """Calculate book value per share."""
    if shares_outstanding is None or shares_outstanding == 0:
        return MetricResult(
            value=None,
            status=MetricStatus.INSUFFICIENT_DATA,
            reason="Shares outstanding is unavailable or zero",
        )

    bvps = _safe_divide(total_equity, shares_outstanding, precision=4)
    if bvps is None:
        return MetricResult(
            value=None,
            status=MetricStatus.INVALID,
            reason="Division by zero in book value per share calculation",
        )

    return MetricResult(
        value=bvps,
        status=MetricStatus.AVAILABLE,
    )


# Metric function registry
METRIC_CALCULATORS: dict[str, Callable[..., MetricResult]] = {
    "revenue_growth_yoy": calculate_revenue_growth_yoy,
    "net_income_growth_yoy": calculate_net_income_growth_yoy,
    "eps_growth_yoy": calculate_eps_growth_yoy,
    "gross_margin": calculate_gross_margin,
    "operating_margin": calculate_operating_margin,
    "net_margin": calculate_net_margin,
    "roe": calculate_roe,
    "roa": calculate_roa,
    "debt_to_equity": calculate_debt_to_equity,
    "debt_to_assets": calculate_debt_to_assets,
    "current_ratio": calculate_current_ratio,
    "quick_ratio": calculate_quick_ratio,
    "operating_cash_flow_margin": calculate_operating_cash_flow_margin,
    "free_cash_flow": calculate_free_cash_flow,
    "free_cash_flow_margin": calculate_free_cash_flow_margin,
    "eps": calculate_eps,
    "book_value_per_share": calculate_book_value_per_share,
}
