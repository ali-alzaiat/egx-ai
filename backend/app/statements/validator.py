"""StatementValidator: deterministic identity gates before anything is shown.

Version stmt-validator-1.0 (tolerance 1% relative). v1 identities:
- assets = liabilities + equity (+ minority_interests when present)
- gross_profit = revenue - cost_of_revenue
- currency uniformity per candidate set; sign rules; null values rejected.
v1 limitation (R41): the CFO+CFI+CFF net-movement identity cannot run —
the ontology v1 code list has no net-cash-movement code; lines pass without it.
"""

from collections.abc import Sequence
from decimal import Decimal

from app.models.statements import ExtStatus
from app.statements.extractor import LineCandidate

VALIDATOR_VERSION = "stmt-validator-1.0"
VALIDATION_TOLERANCE = Decimal("0.01")

_PASSTHRU_CODES = frozenset(
    {
        "eps",  # share-count-based identity: runs only when shares are known (v1: never)
    }
)


class ValidatedLine:
    """A candidate after its gates ran (defaults preserve the input)."""

    def __init__(self, candidate: LineCandidate) -> None:
        self.candidate = candidate

    @property
    def ext_status(self) -> str:
        return self.candidate.ext_status

    @property
    def failure(self) -> str | None:
        return self.candidate.ext_reason


class ValidationSummary:
    def __init__(self, lines: list[ValidatedLine]) -> None:
        self.lines = lines

    @property
    def auto_validated_count(self) -> int:
        return sum(1 for v in self.lines if v.ext_status == ExtStatus.auto_validated.value)

    @property
    def rejected_count(self) -> int:
        return sum(1 for v in self.lines if v.ext_status == ExtStatus.rejected.value)


def _within_tolerance(value: Decimal, expected: Decimal) -> bool:
    if expected == 0:
        return value == 0
    deviation = abs(value - expected) / abs(expected)
    return deviation <= VALIDATION_TOLERANCE


def _by_code(candidates: Sequence[LineCandidate]) -> dict[str, LineCandidate]:
    return {c.ontology_code: c for c in candidates}


def _reject(candidate: LineCandidate, failure: str) -> ValidatedLine:
    candidate.ext_status = ExtStatus.rejected.value
    candidate.ext_reason = failure
    return ValidatedLine(candidate)


def _pass(candidate: LineCandidate, status: str) -> ValidatedLine:
    candidate.ext_status = status
    return ValidatedLine(candidate)


class StatementValidator:
    def validate(self, candidates: Sequence[LineCandidate]) -> ValidationSummary:
        results: list[ValidatedLine] = []
        lines = _by_code(candidates)

        # Gate 0: uniform currency per document.
        currencies = {c.currency for c in candidates if c.value is not None}
        if len(currencies) > 1:
            for candidate in candidates:
                results.append(
                    _reject(candidate, f"CURRENCY_MISMATCH: {sorted(currencies)}")
                )
            return ValidationSummary(results)

        # Gate 1: sign conventions (revenue and expenses stay non-negative).
        sign_links: dict[str, tuple[str, bool]] = {
            "revenue": ("revenue", False),
            "cost_of_revenue": ("cost_of_revenue", True),
            "finance_costs": ("finance_costs", True),
            "income_tax": ("income_tax", True),
        }

        # Gate 2: balance identity.
        assets = lines.get("total_assets")
        if assets is not None and assets.value is not None:
            parts: list[Decimal] = []
            for key in ("total_liabilities", "total_equity", "minority_interests"):
                row = lines.get(key)
                if row is not None and row.value is not None:
                    parts.append(row.value)
            if len(parts) >= 2:
                expected = sum(parts, Decimal("0"))
                if not _within_tolerance(assets.value, expected):
                    results.append(
                        _reject(
                            assets,
                            f"ASSETS_IDENTITY: assets {assets.value} != "
                            f"liabilities+equity {expected} (tolerance {VALIDATION_TOLERANCE})",
                        )
                    )
            # else: not enough inputs -> no identity ran.

        # Gate 3: gross profit identity.
        gross_row = lines.get("gross_profit")
        revenue_row = lines.get("revenue")
        cost_row = lines.get("cost_of_revenue")
        if (
            gross_row is not None
            and gross_row.value is not None
            and revenue_row is not None
            and revenue_row.value is not None
            and cost_row is not None
            and cost_row.value is not None
        ):
            revenue_value = revenue_row.value
            cost_value = cost_row.value
            expected = revenue_value - cost_value
            if not _within_tolerance(gross_row.value, expected):
                results.append(
                    _reject(
                        gross_row,
                        f"GROSS_PROFIT_IDENTITY: gross_profit {gross_row.value} != "
                        f"revenue({revenue_value}) - cost_of_revenue({cost_value})"
                        f" = {expected} (tolerance {VALIDATION_TOLERANCE})",
                    )
                )

        for candidate in candidates:
            if any(v.candidate is candidate for v in results):
                continue
            code = candidate.ontology_code
            if candidate.value is None:
                results.append(_reject(candidate, "NULL_VALUE: no numeric value extracted"))
                continue
            sign_rule = sign_links.get(code)
            if sign_rule is not None and candidate.value < 0:
                results.append(
                    _reject(candidate, f"SIGN_RULE: {code} must be non-negative")
                )
                continue
            status = (
                ExtStatus.auto_validated.value
                if code not in _PASSTHRU_CODES
                else ExtStatus.extraction_candidate.value
            )
            results.append(_pass(candidate, status))
        return ValidationSummary(results)
