"""Individual Shariah screening rules.

Each rule is a pure function that takes financial data and returns
a screening result. No AI is involved in rule evaluation.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class ScreeningVerdict(Enum):
    """Result of a screening rule."""
    PASS = "PASS"
    FAIL = "FAIL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class ScreeningRuleResult:
    """Result of evaluating a single screening rule."""
    rule_name: str
    verdict: ScreeningVerdict
    value: Decimal | None
    threshold: Decimal | None
    reason: str | None = None


def screen_debt_ratio(
    total_debt: Decimal | None,
    total_assets: Decimal | None,
    threshold: Decimal = Decimal("0.33"),
) -> ScreeningRuleResult:
    """Screen based on total debt to total assets ratio.

    AAOIFI guideline: Total debt / Total assets < 33%

    Args:
        total_debt: Total debt of the company
        total_assets: Total assets of the company
        threshold: Maximum allowed ratio (default 33%)

    Returns:
        ScreeningRuleResult with PASS, FAIL, or INSUFFICIENT_DATA
    """
    if total_debt is None or total_assets is None:
        return ScreeningRuleResult(
            rule_name="debt_ratio",
            verdict=ScreeningVerdict.INSUFFICIENT_DATA,
            value=None,
            threshold=threshold,
            reason="Missing debt or assets data",
        )

    if total_assets == 0:
        return ScreeningRuleResult(
            rule_name="debt_ratio",
            verdict=ScreeningVerdict.INSUFFICIENT_DATA,
            value=None,
            threshold=threshold,
            reason="Total assets is zero",
        )

    ratio = total_debt / total_assets
    verdict = ScreeningVerdict.PASS if ratio < threshold else ScreeningVerdict.FAIL
    comparison = "<" if verdict == ScreeningVerdict.PASS else ">="

    return ScreeningRuleResult(
        rule_name="debt_ratio",
        verdict=verdict,
        value=ratio,
        threshold=threshold,
        reason=f"Debt ratio {ratio:.2%} {comparison} threshold {threshold:.2%}",
    )


def screen_interest_income(
    interest_income: Decimal | None,
    total_revenue: Decimal | None,
    threshold: Decimal = Decimal("0.05"),
) -> ScreeningRuleResult:
    """Screen based on interest income to total revenue ratio.

    AAOIFI guideline: Interest income / Total revenue < 5%

    Args:
        interest_income: Interest income of the company
        total_revenue: Total revenue of the company
        threshold: Maximum allowed ratio (default 5%)

    Returns:
        ScreeningRuleResult with PASS, FAIL, or INSUFFICIENT_DATA
    """
    if interest_income is None or total_revenue is None:
        return ScreeningRuleResult(
            rule_name="interest_income_ratio",
            verdict=ScreeningVerdict.INSUFFICIENT_DATA,
            value=None,
            threshold=threshold,
            reason="Missing interest income or revenue data",
        )

    if total_revenue == 0:
        return ScreeningRuleResult(
            rule_name="interest_income_ratio",
            verdict=ScreeningVerdict.INSUFFICIENT_DATA,
            value=None,
            threshold=threshold,
            reason="Total revenue is zero",
        )

    ratio = interest_income / total_revenue
    verdict = ScreeningVerdict.PASS if ratio < threshold else ScreeningVerdict.FAIL
    comparison = "<" if verdict == ScreeningVerdict.PASS else ">="

    return ScreeningRuleResult(
        rule_name="interest_income_ratio",
        verdict=verdict,
        value=ratio,
        threshold=threshold,
        reason=f"Interest income ratio {ratio:.2%} {comparison} threshold {threshold:.2%}",
    )


def screen_cash_and_securities(
    cash_and_securities: Decimal | None,
    total_assets: Decimal | None,
    threshold: Decimal = Decimal("0.33"),
) -> ScreeningRuleResult:
    """Screen based on cash and interest-bearing securities to total assets.

    AAOIFI guideline: Cash & interest-bearing securities / Total assets < 33%

    Args:
        cash_and_securities: Cash and interest-bearing securities
        total_assets: Total assets of the company
        threshold: Maximum allowed ratio (default 33%)

    Returns:
        ScreeningRuleResult with PASS, FAIL, or INSUFFICIENT_DATA
    """
    if cash_and_securities is None or total_assets is None:
        return ScreeningRuleResult(
            rule_name="cash_securities_ratio",
            verdict=ScreeningVerdict.INSUFFICIENT_DATA,
            value=None,
            threshold=threshold,
            reason="Missing cash/securities or assets data",
        )

    if total_assets == 0:
        return ScreeningRuleResult(
            rule_name="cash_securities_ratio",
            verdict=ScreeningVerdict.INSUFFICIENT_DATA,
            value=None,
            threshold=threshold,
            reason="Total assets is zero",
        )

    ratio = cash_and_securities / total_assets
    verdict = ScreeningVerdict.PASS if ratio < threshold else ScreeningVerdict.FAIL
    comparison = "<" if verdict == ScreeningVerdict.PASS else ">="

    return ScreeningRuleResult(
        rule_name="cash_securities_ratio",
        verdict=verdict,
        value=ratio,
        threshold=threshold,
        reason=f"Cash/securities ratio {ratio:.2%} {comparison} threshold {threshold:.2%}",
    )


def screen_industry(
    industry: str | None,
    prohibited_industries: tuple[str, ...] = (),
) -> ScreeningRuleResult:
    """Screen based on industry/sector.

    Companies in prohibited industries fail screening.

    Args:
        industry: Company industry/sector
        prohibited_industries: List of prohibited industry keywords

    Returns:
        ScreeningRuleResult with PASS, FAIL, or INSUFFICIENT_DATA
    """
    if industry is None:
        return ScreeningRuleResult(
            rule_name="industry_screen",
            verdict=ScreeningVerdict.INSUFFICIENT_DATA,
            value=None,
            threshold=None,
            reason="Industry information not available",
        )

    industry_lower = industry.lower()
    is_prohibited = any(
        prohibited.lower() in industry_lower
        for prohibited in prohibited_industries
    )

    verdict = ScreeningVerdict.FAIL if is_prohibited else ScreeningVerdict.PASS

    return ScreeningRuleResult(
        rule_name="industry_screen",
        verdict=verdict,
        value=None,
        threshold=None,
        reason=f"Industry '{industry}' is {'prohibited' if is_prohibited else 'permitted'}",
    )
