"""Deterministic statement ratios (stmt-ratios-1.0).

Pure Decimal math over ontology codes — never delegated to an LLM. Missing
code, zero or negative denominator -> INSUFFICIENT_DATA with a reason, never
an exception and never a fabricated number.
"""

from decimal import Decimal
from typing import Literal, NamedTuple

RATIO_VERSION = "stmt-ratios-1.0"


class RatioResult(NamedTuple):
    code: str
    value: str | None
    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    reason: str | None


def _available(code: str, value: Decimal) -> RatioResult:
    return RatioResult(code, str(value), "AVAILABLE", None)


def _insufficient(code: str, reason: str) -> RatioResult:
    return RatioResult(code, None, "INSUFFICIENT_DATA", reason)


class RatioService:
    def compute(
        self,
        lines_by_code: dict[str, Decimal],
        prior_lines: dict[str, Decimal] | None,
        shares: Decimal | None,
    ) -> list[RatioResult]:
        """Ten v1 ratios; value strings are the exact Decimal division result."""
        by_code = lines_by_code
        revenue = by_code.get("revenue")
        net_income = by_code.get("net_income")
        gross_profit = by_code.get("gross_profit")
        operating_profit = by_code.get("operating_profit")
        total_equity = by_code.get("total_equity")
        total_assets = by_code.get("total_assets")
        debt = by_code.get("interest_bearing_debt")
        current_assets = by_code.get("current_assets")
        current_liabilities = by_code.get("current_liabilities")

        def ratio(
            code: str, num: Decimal | None, den: Decimal | None, den_code: str
        ) -> RatioResult:
            if den is None:
                return _insufficient(code, f"missing:{den_code}")
            if num is None:
                return _insufficient(code, "missing")
            if den == 0 or den < 0:
                return _insufficient(code, den_zero_reason(code, den_code, den))
            return _available(code, num / den)

        def den_zero_reason(code: str, den_code: str, den: Decimal) -> str:
            names = {
                "total_equity": "EQUITY",
                "total_assets": "ASSETS",
                "revenue": "REVENUE",
                "current_liabilities": "CURRENT_LIABILITIES",
            }
            kind = names.get(den_code, den_code.upper())
            return f"{'ZERO' if den == 0 else 'NEGATIVE'}_{kind}"

        results: list[RatioResult] = [
            ratio("gross_margin", gross_profit, revenue, "revenue"),
            ratio("operating_margin", operating_profit, revenue, "revenue"),
            ratio("net_margin", net_income, revenue, "revenue"),
            ratio("roe", net_income, total_equity, "total_equity"),
            ratio("roa", net_income, total_assets, "total_assets"),
            ratio("leverage", debt, total_equity, "total_equity"),
            ratio("current_ratio", current_assets, current_liabilities, "current_liabilities"),
        ]

        # EPS straight from the line when approved; else deterministic
        # net_income/shares when a share count is supplied (never guessed).
        if (eps_line := by_code.get("eps")) is not None:
            results.append(_available("eps", eps_line))
        elif shares is not None and shares > 0 and net_income is not None:
            results.append(_available("eps", net_income / shares))
        else:
            results.append(_insufficient("eps", "missing:eps"))

        for code, numerator, prior_code in (
            ("revenue_growth_yoy", revenue, "revenue"),
            ("net_income_growth_yoy", net_income, "net_income"),
        ):
            if numerator is None:
                results.append(_insufficient(code, "missing"))
                continue
            prior_val = None if prior_lines is None else prior_lines.get(prior_code)
            if prior_val is None:
                results.append(_insufficient(code, "prior"))
            elif prior_val <= 0:
                results.append(_insufficient(code, "PRIOR_NON_POSITIVE"))
            else:
                results.append(_available(code, numerator / prior_val - 1))
        return results
