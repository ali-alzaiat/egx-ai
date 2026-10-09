"""Deterministic normalization service for financial facts.

This service normalizes reported financial data using rule-based transformations.
No LLM is involved — all transformations are deterministic and versioned.
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import NamedTuple

from app.models.financial import FactStatus, FinancialFact

logger = logging.getLogger(__name__)

# Version of the normalization rules below; stamp on derived data.
NORMALIZATION_VERSION = "1.0"


class NormalizationResult(NamedTuple):
    """Result of normalizing a financial fact."""
    fact_id: str
    normalized_label: str
    normalized_value: Decimal | None
    status: str
    warnings: list[str]


class NormalizationRule(NamedTuple):
    """A rule for normalizing financial facts."""
    source_label: str
    target_label: str
    fact_type: str
    transform: str | None = None


class NormalizationService:
    """Deterministic normalization service for financial facts.

    Normalization rules:
    1. Map reported labels to standardized labels
    2. Handle unit conversions (millions, billions, etc.)
    3. Handle currency conversions if needed
    4. Validate normalized values
    """

    # Standard normalization rules for Egyptian companies
    NORMALIZATION_RULES: list[NormalizationRule] = [
        # Income Statement
        NormalizationRule("Total Revenue", "revenue", "INCOME_STATEMENT"),
        NormalizationRule("Net Revenue", "revenue", "INCOME_STATEMENT"),
        NormalizationRule("Cost of Revenue", "cost_of_revenue", "INCOME_STATEMENT"),
        NormalizationRule("Cost of Goods Sold", "cost_of_revenue", "INCOME_STATEMENT"),
        NormalizationRule("Gross Profit", "gross_profit", "INCOME_STATEMENT"),
        NormalizationRule("Operating Expenses", "operating_expenses", "INCOME_STATEMENT"),
        NormalizationRule("Operating Income", "operating_income", "INCOME_STATEMENT"),
        NormalizationRule("Net Income", "net_income", "INCOME_STATEMENT"),
        NormalizationRule("Earnings Per Share", "eps", "INCOME_STATEMENT"),
        NormalizationRule("Basic EPS", "eps_basic", "INCOME_STATEMENT"),
        NormalizationRule("Diluted EPS", "eps_diluted", "INCOME_STATEMENT"),

        # Balance Sheet
        NormalizationRule("Total Assets", "total_assets", "BALANCE_SHEET"),
        NormalizationRule("Total Liabilities", "total_liabilities", "BALANCE_SHEET"),
        NormalizationRule("Total Equity", "total_equity", "BALANCE_SHEET"),
        NormalizationRule("Shareholders Equity", "total_equity", "BALANCE_SHEET"),
        NormalizationRule("Cash and Cash Equivalents", "cash", "BALANCE_SHEET"),
        NormalizationRule("Total Debt", "total_debt", "BALANCE_SHEET"),
        NormalizationRule("Current Assets", "current_assets", "BALANCE_SHEET"),
        NormalizationRule("Current Liabilities", "current_liabilities", "BALANCE_SHEET"),

        # Cash Flow
        NormalizationRule("Operating Cash Flow", "operating_cash_flow", "CASH_FLOW"),
        NormalizationRule("Cash Flow from Operations", "operating_cash_flow", "CASH_FLOW"),
        NormalizationRule("Capital Expenditures", "capex", "CASH_FLOW"),
        NormalizationRule("Free Cash Flow", "free_cash_flow", "CASH_FLOW"),
        NormalizationRule("Dividends Paid", "dividends_paid", "CASH_FLOW"),
    ]

    def normalize_fact(self, fact: FinancialFact) -> NormalizationResult:
        """Normalize a single financial fact deterministically."""
        warnings: list[str] = []
        normalized_label = fact.reported_label
        normalized_value = fact.reported_value
        status = FactStatus.REPORTED

        # Step 1: Apply normalization rules
        rule_match = self._find_matching_rule(fact.reported_label, fact.fact_type)
        if rule_match:
            normalized_label = rule_match.target_label

            # Step 2: Handle unit scaling
            if fact.scale and fact.scale != 1:
                try:
                    scale_factor = Decimal(str(fact.scale))
                    if normalized_value is not None:
                        normalized_value = normalized_value * scale_factor
                except (InvalidOperation, ValueError) as e:
                    warnings.append(f"Failed to apply scale {fact.scale}: {e}")
                    status = FactStatus.INSUFFICIENT_DATA
            else:
                # Step 3: Handle common unit suffixes
                normalized_value, scale_warnings = self._handle_unit_suffixes(
                    fact.reported_label, fact.reported_value
                )
                warnings.extend(scale_warnings)

        # Step 4: Validate normalized value
        if normalized_value is not None:
            if normalized_value < 0:
                # Negative values are valid for some items (e.g., losses)
                pass  # Don't warn for negative values

            if fact.fact_type == "INCOME_STATEMENT" and normalized_value == 0:
                warnings.append("Zero revenue/income may indicate missing data")

        # Step 5: Mark as normalized if changes were made
        if normalized_label != fact.reported_label or normalized_value != fact.reported_value:
            status = FactStatus.NORMALIZED

        return NormalizationResult(
            fact_id=str(fact.id),
            normalized_label=normalized_label,
            normalized_value=normalized_value,
            status=status,
            warnings=warnings,
        )

    def normalize_facts(self, facts: list[FinancialFact]) -> list[NormalizationResult]:
        """Normalize multiple financial facts."""
        return [self.normalize_fact(fact) for fact in facts]

    def _find_matching_rule(self, label: str, fact_type: str) -> NormalizationRule | None:
        """Find a normalization rule matching the reported label and fact type."""
        for rule in self.NORMALIZATION_RULES:
            if rule.source_label.lower() == label.lower() and rule.fact_type == fact_type:
                return rule
        return None

    def _handle_unit_suffixes(
        self, label: str, value: Decimal | None
    ) -> tuple[Decimal | None, list[str]]:
        """Handle common unit suffixes in reported labels."""
        warnings: list[str] = []

        if value is None:
            return value, warnings

        label_lower = label.lower()

        # Check for common Egyptian reporting units
        if "(in millions)" in label_lower or "(mn)" in label_lower:
            return value * Decimal("1000000"), warnings
        elif "(in thousands)" in label_lower or "(000s)" in label_lower:
            return value * Decimal("1000"), warnings
        elif "(in billions)" in label_lower or "(bn)" in label_lower:
            return value * Decimal("1000000000"), warnings

        return value, warnings


def normalize_financial_facts(facts: list[FinancialFact]) -> list[NormalizationResult]:
    """Convenience function to normalize financial facts."""
    service = NormalizationService()
    return service.normalize_facts(facts)
