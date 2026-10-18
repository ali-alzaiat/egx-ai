"""Build a ScreeningInput from approved statement lines (zborsa Task 8).

The existing Shariah methodology (versioned record, unchanged) is reused
verbatim. Only the *inputs* change: interest-bearing debt, total assets,
cash & equivalents and revenue are read from the approved stream of
``FinancialStatementLine`` rows instead of legacy ``FinancialFact`` rows.
Interest income is not part of the statement ontology v1, so it stays
``None`` and the corresponding rule reports ``INSUFFICIENT_DATA`` rather
than a synthetic pass/fail (no fabricated data).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from app.screening.service import ScreeningInput

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from app.models.market import Company
    from app.models.statements import FinancialStatementLine

_REQUIRED_CODES: tuple[str, ...] = (
    "interest_bearing_debt",
    "total_assets",
    "cash_and_equivalents",
    "revenue",
)


def _latest_period_lines(
    lines: Sequence[FinancialStatementLine],
) -> list[FinancialStatementLine]:
    """Pick the statement period with the newest publication date.

    All approved lines for a company span multiple periods; screening uses
    one coherent period. When publication dates are missing we fall back to
    the largest group (most lines) so the result is still deterministic.
    """
    if not lines:
        return []
    groups: dict[uuid.UUID, list[FinancialStatementLine]] = defaultdict(list)
    for line in lines:
        groups[line.period_id].append(line)
    if len(groups) == 1:
        return list(next(iter(groups.values())))
    # Prefer the period whose newest published_date is greatest.
    def period_key(period_lines: list[FinancialStatementLine]) -> tuple[int, int]:
        dates = [pl.published_date for pl in period_lines if pl.published_date is not None]
        latest = max(dates) if dates else date.min
        # Encode date as ordinal; missing dates sort last via 0 sentinel handled above.
        return (latest.toordinal() if latest != date.min else 0, len(period_lines))

    best = max(groups.values(), key=period_key)
    return list(best)


def build_screening_input_from_statements(
    company_id: uuid.UUID,
    company: Company,
    lines: Sequence[FinancialStatementLine],
    market_cap: Decimal | None,
) -> tuple[ScreeningInput | None, str | None]:
    """Map approved statement lines onto a ``ScreeningInput``.

    Returns ``(None, reason)`` when any required ontology code is absent so
    the caller can surface ``INSUFFICIENT_DATA`` instead of a verdict.
    ``market_cap`` is accepted for the market-side inputs future rules may
    need; v1 rules do not consume it (never invent a value).
    """
    del market_cap  # accepted for contract parity; no v1 rule consumes it
    period_lines = _latest_period_lines(lines)
    by_code: dict[str, Decimal | None] = {}
    for line in period_lines:
        if line.value is not None:
            by_code[line.ontology_code] = Decimal(str(line.value))
        else:
            by_code.setdefault(line.ontology_code, None)

    # A code present with a None value counts as missing too.
    missing = [
        code for code in _REQUIRED_CODES
        if by_code.get(code) is None
    ]
    # But a code that is genuinely absent from by_code is also missing (already covered).
    if missing:
        return None, "missing required statement lines: " + ", ".join(missing)

    total_debt = by_code.get("interest_bearing_debt")
    total_assets = by_code.get("total_assets")
    cash_and_securities = by_code.get("cash_and_equivalents")
    total_revenue = by_code.get("revenue")

    return ScreeningInput(
        company_id=str(company_id),
        ticker=company.ticker,
        industry=company.industry,
        total_debt=total_debt,
        total_assets=total_assets,
        interest_income=None,
        total_revenue=total_revenue,
        cash_and_securities=cash_and_securities,
        provenance=None,
    ), None
