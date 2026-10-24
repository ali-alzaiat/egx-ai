"""Centralized metric definitions for the financial metrics engine.

Each metric definition contains metadata describing:
- metric name and code
- display name and description
- category
- formula (as a callable)
- required facts
- required periods
- unit
- applicability rules
- calculation rules
- handling of missing data
- version

All formulas are deterministic and versioned.
"""

from dataclasses import dataclass
from enum import Enum


class MetricCategory(Enum):
    GROWTH = "growth"
    MARGIN = "margin"
    PROFITABILITY = "profitability"
    LEVERAGE = "leverage"
    LIQUIDITY = "liquidity"
    CASH_FLOW = "cash_flow"
    PER_SHARE = "per_share"


class MetricStatus(Enum):
    AVAILABLE = "AVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    INVALID = "INVALID"


class PeriodRequirement(Enum):
    SINGLE = "SINGLE"
    COMPARABLE = "COMPARABLE"
    ANY = "ANY"


@dataclass(frozen=True)
class MetricDefinition:
    """Definition of a financial metric."""

    code: str
    display_name: str
    description: str
    category: MetricCategory
    formula_version: int
    required_fact_labels: tuple[str, ...]
    period_requirement: PeriodRequirement
    unit: str
    denominator_label: str | None = None
    is_applicable_to_sector: tuple[str, ...] | None = None
    notes: str = ""

    def __hash__(self) -> int:
        return hash((self.code, self.formula_version))


# Growth Metrics
REVENUE_GROWTH_YOY = MetricDefinition(
    code="revenue_growth_yoy",
    display_name="Revenue Growth (YoY)",
    description="Year-over-year revenue growth percentage",
    category=MetricCategory.GROWTH,
    formula_version=2,
    required_fact_labels=("revenue",),
    period_requirement=PeriodRequirement.COMPARABLE,
    unit="%",
    notes="Requires current and previous comparable period revenue",
)

NET_INCOME_GROWTH_YOY = MetricDefinition(
    code="net_income_growth_yoy",
    display_name="Net Income Growth (YoY)",
    description="Year-over-year net income growth percentage",
    category=MetricCategory.GROWTH,
    formula_version=2,
    required_fact_labels=("net_income",),
    period_requirement=PeriodRequirement.COMPARABLE,
    unit="%",
    notes="Requires current and previous comparable period net income",
)

EPS_GROWTH_YOY = MetricDefinition(
    code="eps_growth_yoy",
    display_name="EPS Growth (YoY)",
    description="Year-over-year earnings per share growth percentage",
    category=MetricCategory.GROWTH,
    formula_version=2,
    required_fact_labels=("eps_basic",),
    period_requirement=PeriodRequirement.COMPARABLE,
    unit="%",
    notes="Requires current and previous comparable period basic EPS",
)

# Margin Metrics
GROSS_MARGIN = MetricDefinition(
    code="gross_margin",
    display_name="Gross Margin",
    description="Gross profit as a percentage of revenue",
    category=MetricCategory.MARGIN,
    formula_version=2,
    required_fact_labels=("gross_profit", "revenue"),
    period_requirement=PeriodRequirement.SINGLE,
    unit="%",
)

OPERATING_MARGIN = MetricDefinition(
    code="operating_margin",
    display_name="Operating Margin",
    description="Operating income as a percentage of revenue",
    category=MetricCategory.MARGIN,
    formula_version=2,
    required_fact_labels=("operating_income", "revenue"),
    period_requirement=PeriodRequirement.SINGLE,
    unit="%",
)

NET_MARGIN = MetricDefinition(
    code="net_margin",
    display_name="Net Profit Margin",
    description="Net income as a percentage of revenue",
    category=MetricCategory.MARGIN,
    formula_version=2,
    required_fact_labels=("net_income", "revenue"),
    period_requirement=PeriodRequirement.SINGLE,
    unit="%",
)

# Profitability Metrics
ROE = MetricDefinition(
    code="roe",
    display_name="Return on Equity",
    description="Net income divided by average shareholders' equity",
    category=MetricCategory.PROFITABILITY,
    formula_version=2,
    required_fact_labels=("net_income", "total_equity"),
    period_requirement=PeriodRequirement.COMPARABLE,
    unit="%",
    notes=(
        "Strict average of current and previous comparable equity; no prior period or "
        "negative average equity is INSUFFICIENT_DATA (no spot-equity fallback). v2: "
        "percent rounded after x100"
    ),
)

ROA = MetricDefinition(
    code="roa",
    display_name="Return on Assets",
    description="Net income divided by average total assets",
    category=MetricCategory.PROFITABILITY,
    formula_version=2,
    required_fact_labels=("net_income", "total_assets"),
    period_requirement=PeriodRequirement.COMPARABLE,
    unit="%",
    notes=(
        "Strict average of current and previous comparable total assets; no prior period "
        "is INSUFFICIENT_DATA (no spot fallback). v2: percent rounded after x100"
    ),
)

# Leverage Metrics
DEBT_TO_EQUITY = MetricDefinition(
    code="debt_to_equity",
    display_name="Debt-to-Equity Ratio",
    description="Total debt divided by shareholders' equity",
    category=MetricCategory.LEVERAGE,
    formula_version=2,
    required_fact_labels=("total_debt", "total_equity"),
    period_requirement=PeriodRequirement.SINGLE,
    unit="ratio",
    notes=(
        "Requires explicit debt fact, not total liabilities; negative equity is "
        "INSUFFICIENT_DATA (v2)"
    ),
)

DEBT_TO_ASSETS = MetricDefinition(
    code="debt_to_assets",
    display_name="Debt-to-Assets Ratio",
    description="Total debt divided by total assets",
    category=MetricCategory.LEVERAGE,
    formula_version=1,
    required_fact_labels=("total_debt", "total_assets"),
    period_requirement=PeriodRequirement.SINGLE,
    unit="ratio",
    notes="Requires explicit debt fact, not total liabilities",
)

# Liquidity Metrics
CURRENT_RATIO = MetricDefinition(
    code="current_ratio",
    display_name="Current Ratio",
    description="Current assets divided by current liabilities",
    category=MetricCategory.LIQUIDITY,
    formula_version=1,
    required_fact_labels=("current_assets", "current_liabilities"),
    period_requirement=PeriodRequirement.SINGLE,
    unit="ratio",
)

QUICK_RATIO = MetricDefinition(
    code="quick_ratio",
    display_name="Quick Ratio",
    description="Quick assets divided by current liabilities",
    category=MetricCategory.LIQUIDITY,
    formula_version=2,
    required_fact_labels=("current_assets", "current_liabilities"),
    period_requirement=PeriodRequirement.SINGLE,
    unit="ratio",
    notes=(
        "Current assets minus inventory over current liabilities; a missing inventory "
        "line is INSUFFICIENT_DATA (v2, was silently the current ratio)"
    ),
)

# Cash Flow Metrics
OPERATING_CASH_FLOW_MARGIN = MetricDefinition(
    code="operating_cash_flow_margin",
    display_name="Operating Cash Flow Margin",
    description="Operating cash flow as a percentage of revenue",
    category=MetricCategory.CASH_FLOW,
    formula_version=2,
    required_fact_labels=("operating_cash_flow", "revenue"),
    period_requirement=PeriodRequirement.SINGLE,
    unit="%",
)

FREE_CASH_FLOW = MetricDefinition(
    code="free_cash_flow",
    display_name="Free Cash Flow",
    description="Operating cash flow minus capital expenditures",
    category=MetricCategory.CASH_FLOW,
    formula_version=1,
    required_fact_labels=("operating_cash_flow", "capex"),
    period_requirement=PeriodRequirement.SINGLE,
    unit="currency",
    notes="Capex is subtracted as a positive expenditure amount",
)

FREE_CASH_FLOW_MARGIN = MetricDefinition(
    code="free_cash_flow_margin",
    display_name="Free Cash Flow Margin",
    description="Free cash flow as a percentage of revenue",
    category=MetricCategory.CASH_FLOW,
    formula_version=2,
    required_fact_labels=("operating_cash_flow", "capex", "revenue"),
    period_requirement=PeriodRequirement.SINGLE,
    unit="%",
)

# Per-Share Metrics
EPS = MetricDefinition(
    code="eps",
    display_name="Earnings Per Share",
    description="Basic earnings per share",
    category=MetricCategory.PER_SHARE,
    formula_version=1,
    required_fact_labels=("eps_basic",),
    period_requirement=PeriodRequirement.SINGLE,
    unit="currency per share",
    notes="Uses reported basic EPS",
)

BOOK_VALUE_PER_SHARE = MetricDefinition(
    code="book_value_per_share",
    display_name="Book Value Per Share",
    description="Shareholders' equity divided by shares outstanding",
    category=MetricCategory.PER_SHARE,
    formula_version=1,
    required_fact_labels=("total_equity",),
    period_requirement=PeriodRequirement.SINGLE,
    unit="currency per share",
    notes="Requires shares_outstanding from company record",
)


# Metric Registry
ALL_METRICS: dict[str, MetricDefinition] = {
    metric.code: metric
    for metric in [
        REVENUE_GROWTH_YOY,
        NET_INCOME_GROWTH_YOY,
        EPS_GROWTH_YOY,
        GROSS_MARGIN,
        OPERATING_MARGIN,
        NET_MARGIN,
        ROE,
        ROA,
        DEBT_TO_EQUITY,
        DEBT_TO_ASSETS,
        CURRENT_RATIO,
        QUICK_RATIO,
        OPERATING_CASH_FLOW_MARGIN,
        FREE_CASH_FLOW,
        FREE_CASH_FLOW_MARGIN,
        EPS,
        BOOK_VALUE_PER_SHARE,
    ]
}


def get_metric(code: str) -> MetricDefinition | None:
    """Get a metric definition by code."""
    return ALL_METRICS.get(code)


def get_metrics_by_category(category: MetricCategory) -> list[MetricDefinition]:
    """Get all metrics in a category."""
    return [m for m in ALL_METRICS.values() if m.category == category]
