"""Provenance record shape + EAS gotcha tags + basis comparator guard (R34 P0-3/P0-4).

Every parsed numeral becomes a full provenance record: metric, value payload
(OK, or UNKNOWN with a reason — missing numerals are never zero), currency,
period, source filing, cell locator, extraction report, accounting basis plus
gotcha tags, and methodology version. The comparator refuses to silently pool
EAS-family facts with IFRS facts: mixed series raise :class:`BasisMixError`.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from app.ingestion.disclosures.constants import (
    ACCOUNTING_BASES,
    DISCLOSURE_METHODOLOGY_VERSION,
    EAS_FAMILY,
    EAS_GOTCHA_TAGS,
)
from app.models.disclosure import DisclosureFiling
from app.models.financial import FactStatus, FinancialFact


class BasisMixError(ValueError):
    """Raised when a comparison would silently pool EAS with IFRS facts."""


def validate_eas_tags(tags: list[str] | None) -> list[str]:
    """Return the stored gotcha tags; unknown tags are rejected, not stored."""
    clean = list(tags or [])
    unknown = [tag for tag in clean if tag not in EAS_GOTCHA_TAGS]
    if unknown:
        raise ValueError(
            f"Unknown EAS gotcha tags {unknown}; expected subset of {EAS_GOTCHA_TAGS}"
        )
    return clean


def validate_basis_for_fact(accounting_basis: str | None) -> str | None:
    """Return the basis or raise on a value outside the known three."""
    if accounting_basis is None:
        return None
    if accounting_basis not in ACCOUNTING_BASES:
        raise ValueError(
            f"Unknown accounting_basis {accounting_basis!r}; expected one of {ACCOUNTING_BASES}"
        )
    return accounting_basis


def ensure_comparable_basis(bases: set[str | None]) -> None:
    """Refuse silent EAS/IFRS pooling across one comparison series.

    Unknown (None) bases are skipped — legacy rows that cannot prove their
    basis — but the moment both EAS-family and IFRS appear, the comparison
    is refused loudly. Same-family mixes (EAS with EAS+CBE) pass with the
    tags surfaced on each fact payload.
    """
    known = {basis for basis in bases if basis is not None}
    if not known:
        return
    unfamiliar = known - set(ACCOUNTING_BASES)
    if unfamiliar:
        raise BasisMixError(f"Unrecognized accounting bases pooled: {sorted(unfamiliar)}")
    has_eas = bool(known & set(EAS_FAMILY))
    if has_eas and "IFRS" in known:
        raise BasisMixError(
            f"Refusing to pool EAS-family {sorted(known & set(EAS_FAMILY))} "
            "with IFRS facts without surfaced gotcha tags"
        )


def reported_amount(fact: FinancialFact) -> Decimal | None:
    """Normalized wins when present; zero stays zero; None only when both missing."""
    if fact.normalized_value is not None:
        return fact.normalized_value
    return fact.reported_value


def value_payload(amount: Decimal | None, *, metric: str) -> dict[str, Any]:
    """``{"value", "status"}`` block: OK stringified numeral, or UNKNOWN."""
    if amount is None:
        return {
            "value": None,
            "status": "UNKNOWN",
            "reason": f"missing numeral for {metric}",
        }
    return {"value": str(amount), "status": "OK"}


def locator_payload(fact: FinancialFact) -> dict[str, Any]:
    """Cell locator; absent locator degrades to an empty dict, never a guess."""
    return dict(fact.locator or {})


def extraction_payload(fact: FinancialFact) -> dict[str, Any]:
    """Extraction report; absent report degrades to an empty dict."""
    return dict(fact.extraction or {})


def fact_payload(
    fact: FinancialFact,
    *,
    company_ticker: str,
    filing: DisclosureFiling | None,
    period_end: date | None,
    period_label: str | None,
) -> dict[str, Any]:
    """Full Phase-7 provenance record for one stored fact (R34 P0-4)."""
    metric = fact.normalized_label or fact.reported_label
    amount = reported_amount(fact)
    if fact.status == FactStatus.INSUFFICIENT_DATA or amount is None:
        status = "UNKNOWN"
        reason = fact.unknown_reason or f"missing numeral for {metric}"
    else:
        status = "OK"
        reason = None
    return {
        "id": str(fact.id),
        "metric": metric,
        "value": {
            "value": str(amount) if amount is not None else None,
            "status": status,
            "reason": reason,
        },
        "currency_unit": fact.currency,
        "period": {
            "end": period_end.isoformat() if period_end else None,
            "type": period_label,
            "audit_state": fact.audit_state,
        },
        "source": {
            "filing_url": filing.filing_url if filing else None,
            "bulletin_id": filing.bulletin_id if filing else None,
            "company": company_ticker,
            "report_date": filing.report_date.isoformat() if filing else None,
            "filing_type": filing.filing_type if filing else None,
        },
        "locator": locator_payload(fact),
        "extraction": extraction_payload(fact),
        "accounting_basis": fact.accounting_basis,
        "eas_tags": list(fact.eas_tags or []),
        "methodology_version": fact.methodology_version or DISCLOSURE_METHODOLOGY_VERSION,
        "status": status,
        "supersedes": str(fact.supersedes_id) if fact.supersedes_id else None,
        "is_restated": fact.is_restated,
        "created_at": fact.created_at.isoformat() if fact.created_at else None,
    }
