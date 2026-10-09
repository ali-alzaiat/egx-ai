"""Validation service for financial facts.

Provides ERROR/WARNING distinction for data quality issues.
Errors indicate critical problems that prevent data use.
Warnings indicate potential issues that should be reviewed.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

from app.models.financial import FinancialFact

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass
class ValidationIssue:
    """A single validation issue."""
    severity: ValidationSeverity
    field: str
    message: str
    fact_id: str | None = None


@dataclass
class ValidationResult:
    """Result of validating a financial fact."""
    fact_id: str
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]


class FinancialFactValidator:
    """Validates financial facts for data quality issues."""

    def validate(self, fact: FinancialFact) -> ValidationResult:
        """Validate a single financial fact."""
        issues: list[ValidationIssue] = []

        # Check required fields
        if not fact.reported_label:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                field="reported_label",
                message="Reported label is required",
                fact_id=str(fact.id),
            ))

        if fact.reported_value is None:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                field="reported_value",
                message="Reported value is missing",
                fact_id=str(fact.id),
            ))

        # Check value ranges
        if fact.reported_value is not None:
            if (
                fact.reported_value < 0
                and fact.fact_type == "INCOME_STATEMENT"
                and (
                    "revenue" in fact.reported_label.lower()
                    or "sales" in fact.reported_label.lower()
                )
            ):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    field="reported_value",
                    message=f"Negative revenue detected: {fact.reported_value}",
                    fact_id=str(fact.id),
                ))

            # Check for extremely large values (potential unit errors)
            if abs(fact.reported_value) > Decimal("1000000000000"):  # > 1 trillion
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    field="reported_value",
                    message=f"Extremely large value detected: {fact.reported_value}",
                    fact_id=str(fact.id),
                ))

        # Check currency
        if fact.currency and len(fact.currency) != 3:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                field="currency",
                message=f"Invalid currency code: {fact.currency}",
                fact_id=str(fact.id),
            ))

        # Check period
        if fact.period_id is None:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                field="period_id",
                message="Period is required",
                fact_id=str(fact.id),
            ))

        # Check document
        if fact.document_id is None:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                field="document_id",
                message="Document is required",
                fact_id=str(fact.id),
            ))

        # Check company
        if fact.company_id is None:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                field="company_id",
                message="Company is required",
                fact_id=str(fact.id),
            ))

        # Determine validity
        has_errors = any(i.severity == ValidationSeverity.ERROR for i in issues)

        return ValidationResult(
            fact_id=str(fact.id),
            is_valid=not has_errors,
            issues=issues,
        )

    def validate_facts(self, facts: list[FinancialFact]) -> list[ValidationResult]:
        """Validate multiple financial facts."""
        return [self.validate(fact) for fact in facts]

    def get_summary(self, results: list[ValidationResult]) -> dict[str, Any]:
        """Get a summary of validation results."""
        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        invalid = total - valid
        total_errors = sum(len(r.errors) for r in results)
        total_warnings = sum(len(r.warnings) for r in results)

        return {
            "total": total,
            "valid": valid,
            "invalid": invalid,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
        }


def validate_financial_facts(facts: list[FinancialFact]) -> dict[str, Any]:
    """Convenience function to validate financial facts and get summary."""
    validator = FinancialFactValidator()
    results = validator.validate_facts(facts)
    summary = validator.get_summary(results)
    return {
        "results": results,
        "summary": summary,
    }
