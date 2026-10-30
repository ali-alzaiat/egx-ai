"""Dividend safety (R47 Q2): payout ratio and cash coverage from cash dividends paid.

Pure and deterministic: no database, clock or I/O. Shown only; it never feeds the investment
score, whose dividend checks stay NOT_RUN (earlier owner ruling).

* payout ratio   = abs(dividends_paid) / net_income (to common holders)
* cash coverage  = (cfo - abs(capex)) / abs(dividends_paid)

Both are labelled ``LABEL`` ("from dividends paid (derived)") because the statement line is the
cash actually paid in the fiscal year, not the dividend declared for it (R44 D-6): timing and
bonus-share years make it noisy. Nothing is substituted for a missing input:

* no ``dividends_paid`` line -> INSUFFICIENT_DATA (never "no dividend");
* a ``dividends_paid`` line equal to 0 is a real "no dividend" (payout 0, coverage not meaningful);
* net income <= 0 -> the payout ratio is NOT_MEANINGFUL (reason given);
* a bank's operating cash flow includes deposit and loan flows -> coverage NOT_MEANINGFUL.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

DIVIDEND_SAFETY_VERSION = "dividend-safety-1.0"
LABEL = "from dividends paid (derived)"
PAYOUT_FORMULA = "abs(dividends_paid) / net_income"
COVERAGE_FORMULA = "(cfo - abs(capex)) / abs(dividends_paid)"
HISTORY_YEARS = 3  # the latest fiscal year plus the prior two, for context

#: Statement-line codes read per fiscal year.
DIVIDEND_LINE_CODES: tuple[str, ...] = ("dividends_paid", "net_income", "cfo", "capex")

MetricStatus = Literal["AVAILABLE", "NOT_MEANINGFUL", "INSUFFICIENT_DATA"]
YearStatus = Literal["PAID", "NO_DIVIDEND", "INSUFFICIENT_DATA"]

Values = Mapping[str, Decimal]
_Q = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class DividendMetric:
    value: str | None
    status: MetricStatus
    reason: str | None


@dataclass(frozen=True, slots=True)
class DividendYear:
    fiscal_year: int
    status: YearStatus
    reason: str | None
    #: Stored values as strings, None where the line is missing.
    inputs: dict[str, str | None]
    payout_ratio: DividendMetric
    cash_coverage: DividendMetric


@dataclass(frozen=True, slots=True)
class DividendSafetyResult:
    version: str
    label: str
    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    reason: str | None
    latest: DividendYear | None
    years: tuple[DividendYear, ...]
    payout_formula: str = PAYOUT_FORMULA
    coverage_formula: str = COVERAGE_FORMULA


def _s(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _insufficient(reason: str) -> DividendMetric:
    return DividendMetric(None, "INSUFFICIENT_DATA", reason)


def _not_meaningful(reason: str) -> DividendMetric:
    return DividendMetric(None, "NOT_MEANINGFUL", reason)


def evaluate_year(fiscal_year: int, vals: Values | None, *, is_bank: bool = False) -> DividendYear:
    """One fiscal year's payout ratio and cash coverage."""
    if vals is None:
        reason = f"no approved annual statements for FY{fiscal_year}"
        return DividendYear(
            fiscal_year, "INSUFFICIENT_DATA", reason,
            {code: None for code in DIVIDEND_LINE_CODES},
            _insufficient(reason), _insufficient(reason),
        )
    div = vals.get("dividends_paid")
    ni = vals.get("net_income")
    cfo = vals.get("cfo")
    capex = vals.get("capex")
    inputs = {code: _s(vals.get(code)) for code in DIVIDEND_LINE_CODES}

    if div is None:
        reason = (
            f"missing statement line: dividends_paid (FY{fiscal_year}); "
            "not read as no dividend"
        )
        return DividendYear(
            fiscal_year, "INSUFFICIENT_DATA", reason, inputs,
            _insufficient(reason), _insufficient(reason),
        )

    paid = abs(div)
    status: YearStatus = "NO_DIVIDEND" if paid == 0 else "PAID"

    # Payout ratio
    if ni is None:
        payout = _insufficient(f"missing statement line: net_income (FY{fiscal_year})")
    elif ni <= 0:
        payout = _not_meaningful(
            f"net income to common holders is not positive (FY{fiscal_year}): "
            "payout ratio not meaningful"
        )
    else:
        payout = DividendMetric(str((paid / ni).quantize(_Q)), "AVAILABLE", None)

    # Cash coverage
    if paid == 0:
        coverage = _not_meaningful(f"no dividends paid in FY{fiscal_year}: nothing to cover")
    elif is_bank:
        coverage = _not_meaningful(
            "operating cash flow of a bank includes deposit and loan flows: "
            "cash coverage not meaningful"
        )
    elif cfo is None:
        coverage = _insufficient(f"missing statement line: cfo (FY{fiscal_year})")
    elif capex is None:
        coverage = _insufficient(f"missing statement line: capex (FY{fiscal_year})")
    else:
        coverage = DividendMetric(str(((cfo - abs(capex)) / paid).quantize(_Q)), "AVAILABLE", None)

    note = "no dividends paid in the year (the line exists and is zero)" if paid == 0 else None
    return DividendYear(fiscal_year, status, note, inputs, payout, coverage)


def evaluate_dividend_safety(
    years: Mapping[int, Values],
    latest_year: int | None,
    *,
    is_bank: bool = False,
) -> DividendSafetyResult:
    """Latest fiscal year plus the prior two; ``years`` maps fiscal year to line values."""
    if latest_year is None:
        return DividendSafetyResult(
            version=DIVIDEND_SAFETY_VERSION,
            label=LABEL,
            status="INSUFFICIENT_DATA",
            reason="no approved annual statement lines",
            latest=None,
            years=(),
        )
    rows = tuple(
        evaluate_year(latest_year - back, years.get(latest_year - back), is_bank=is_bank)
        for back in range(HISTORY_YEARS)
    )
    latest = rows[0]
    available = latest.status != "INSUFFICIENT_DATA"
    return DividendSafetyResult(
        version=DIVIDEND_SAFETY_VERSION,
        label=LABEL,
        status="AVAILABLE" if available else "INSUFFICIENT_DATA",
        reason=None if available else latest.reason,
        latest=latest,
        years=rows,
    )
