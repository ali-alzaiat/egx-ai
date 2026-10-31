"""Pure data cross-checks (R50 B11): provenance, cross-source, identities, prices, freshness.

No database, clock or I/O: the caller passes the lines, closes and dates. Every check returns a
``CheckResult`` with a status of pass / warn / fail / insufficient_data. Missing inputs give
``insufficient_data`` with a reason, never a pass and never a zero.

The cross-source check compares our filing-backed value with a vendor value. Its result (detail
and evidence) carries only the agreement band and OUR value, never the vendor value or the exact
difference (either would let a reader reconstruct the vendor figure).
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, NamedTuple

from app.dataquality.constants import (
    BAND_FAIL,
    BAND_WARN,
    BAND_WITHIN,
    CHECK_ACCOUNTING_IDENTITY,
    CHECK_CROSS_SOURCE,
    CHECK_FRESHNESS,
    CHECK_PRICE_SANITY,
    CHECK_PROVENANCE,
    CROSS_SOURCE_FAIL,
    CROSS_SOURCE_WARN,
    EGX_DAILY_LIMIT,
    EGX_TRADING_WEEKDAYS,
    FRESH_PERIOD_FAIL_QUARTERS,
    FRESH_PERIOD_WARN_QUARTERS,
    FRESH_PRICE_FAIL_DAYS,
    FRESH_PRICE_WARN_DAYS,
    GAP_TRADING_DAYS,
    IDENTITY_FAIL,
    IDENTITY_WARN,
    LIMIT_TOLERANCE,
    MAX_EVIDENCE_ITEMS,
    PRICE_LOOKBACK_DAYS,
    PROVENANCE_WARN_SHARE,
    SPLIT_FACTORS,
    SPLIT_TOLERANCE,
    STATUS_FAIL,
    STATUS_INSUFFICIENT,
    STATUS_PASS,
    STATUS_SEVERITY,
    STATUS_WARN,
)
from app.statements.ontology import STATEMENT_LINES

_ONE = Decimal(1)
_RATIO_QUANT = Decimal("0.0001")


@dataclass(frozen=True)
class CheckResult:
    code: str
    status: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "status": self.status,
            "detail": self.detail,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class LineInfo:
    """One approved statement line, reduced to what the checks read."""

    period: str  # label, e.g. "ANNUAL-2025"
    period_end: date
    code: str
    value: Decimal | None
    vendor: bool  # extraction method is vendor_aggregator
    has_document: bool
    has_page: bool
    xbrl: bool = False

    @property
    def filing_backed(self) -> bool:
        """A filing document and a page (or an XBRL tag) behind the value; never a vendor."""
        return not self.vendor and self.has_document and (self.has_page or self.xbrl)


def worst_status(statuses: Sequence[str]) -> str:
    """The most severe status (fail > warn > insufficient_data > pass); no checks = pass."""
    return max(statuses, key=lambda s: STATUS_SEVERITY[s], default=STATUS_PASS)


def relative_difference(reference: Decimal, other: Decimal) -> Decimal:
    """``|reference - other| / |reference|``; a zero reference differs fully unless both are 0."""
    if reference == 0:
        return Decimal(0) if other == 0 else _ONE
    return abs(reference - other) / abs(reference)


def _insufficient(code: str, reason: str) -> CheckResult:
    return CheckResult(code, STATUS_INSUFFICIENT, reason)


# --- provenance --------------------------------------------------------------------------------


def check_provenance(lines: Sequence[LineInfo]) -> CheckResult:
    """Share of the latest approved lines backed by a filing (document + page)."""
    valued = [line for line in lines if line.value is not None]
    if not valued:
        return _insufficient(CHECK_PROVENANCE, "No approved statement lines for this company.")
    backed = sum(1 for line in valued if line.filing_backed)
    vendor = sum(1 for line in valued if line.vendor)
    share = (Decimal(backed) / Decimal(len(valued))).quantize(_RATIO_QUANT)
    evidence = {
        "lines": len(valued),
        "filing_backed": backed,
        "vendor_only": vendor,
        "other": len(valued) - backed - vendor,
        "filing_backed_share": str(share),
    }
    if backed == 0 and vendor == 0:
        return CheckResult(
            CHECK_PROVENANCE,
            STATUS_FAIL,
            "No approved line has a source: none is backed by a filing or a vendor file.",
            evidence,
        )
    if backed == 0:
        # Owner ruling (R50 B12): vendor-only data is unconfirmed, not shown to be wrong.
        return CheckResult(
            CHECK_PROVENANCE,
            STATUS_WARN,
            "No approved line is confirmed by a filing yet; the figures come from vendor files.",
            evidence,
        )
    if share < PROVENANCE_WARN_SHARE:
        return CheckResult(
            CHECK_PROVENANCE,
            STATUS_WARN,
            f"{backed} of {len(valued)} approved lines are filing-backed "
            f"(below {PROVENANCE_WARN_SHARE:.0%}).",
            evidence,
        )
    return CheckResult(
        CHECK_PROVENANCE,
        STATUS_PASS,
        f"{backed} of {len(valued)} approved lines are filing-backed.",
        evidence,
    )


# --- cross-source ------------------------------------------------------------------------------


def _band(diff: Decimal) -> tuple[str, str]:
    if diff > CROSS_SOURCE_FAIL:
        return BAND_FAIL, STATUS_FAIL
    if diff >= CROSS_SOURCE_WARN:
        return BAND_WARN, STATUS_WARN
    return BAND_WITHIN, STATUS_PASS


def check_cross_source(ours: Sequence[LineInfo], vendor: Sequence[LineInfo]) -> CheckResult:
    """Our filing-backed value against the vendor value of the same period and code.

    ``ours`` are filing-backed lines (non-filing ones are ignored), ``vendor`` the
    ``vendor_aggregator`` lines. Evidence lists only the band and our value.
    """
    vendor_by_key = {(v.period, v.code): v for v in vendor if v.value is not None}
    compared = 0
    counts = {STATUS_PASS: 0, STATUS_WARN: 0, STATUS_FAIL: 0}
    items: list[dict[str, Any]] = []
    statuses: list[str] = []
    for line in ours:
        if line.value is None or not line.filing_backed:
            continue
        other = vendor_by_key.get((line.period, line.code))
        if other is None or other.value is None:
            continue
        compared += 1
        band, status = _band(relative_difference(line.value, other.value))
        counts[status] += 1
        statuses.append(status)
        if status != STATUS_PASS:
            items.append(
                {
                    "period": line.period,
                    "ontology_code": line.code,
                    "band": band,
                    "our_value": str(line.value),
                }
            )
    if compared == 0:
        return _insufficient(
            CHECK_CROSS_SOURCE,
            "No period and line has both a filing-backed value and a vendor value.",
        )
    status = worst_status(statuses)
    evidence: dict[str, Any] = {
        "compared": compared,
        "within_1_percent": counts[STATUS_PASS],
        "from_1_to_5_percent": counts[STATUS_WARN],
        "over_5_percent": counts[STATUS_FAIL],
        "items": items[:MAX_EVIDENCE_ITEMS],
    }
    if status == STATUS_PASS:
        detail = f"All {compared} compared figures agree with the vendor within 1%."
    else:
        off = counts[STATUS_WARN] + counts[STATUS_FAIL]
        detail = f"{off} of {compared} compared figures differ from the vendor by 1% or more."
    return CheckResult(CHECK_CROSS_SOURCE, status, detail, evidence)


# --- accounting identities ---------------------------------------------------------------------


class Identity(NamedTuple):
    """``lhs`` should equal the signed sum of ``required`` (plus ``optional`` when reported)."""

    name: str
    lhs: str
    required: tuple[tuple[str, int], ...]
    optional: tuple[tuple[str, int], ...] = ()


#: The balance identity mirrors the statement validator (minority interests add when reported).
IDENTITIES: tuple[Identity, ...] = (
    Identity(
        "assets = liabilities + equity",
        "total_assets",
        (("total_liabilities", 1), ("total_equity", 1)),
        (("minority_interests", 1),),
    ),
    Identity(
        "assets = current + non-current assets",
        "total_assets",
        (("current_assets", 1), ("non_current_assets", 1)),
    ),
    Identity(
        "gross profit = revenue - cost of revenue",
        "gross_profit",
        (("revenue", 1), ("cost_of_revenue", -1)),
    ),
)


def available_identities() -> tuple[Identity, ...]:
    """Identities whose ontology codes all exist; the others are skipped, never guessed."""
    out: list[Identity] = []
    for identity in IDENTITIES:
        parts = (*identity.required, *identity.optional)
        codes = [identity.lhs, *(code for code, _ in parts)]
        if all(code in STATEMENT_LINES for code in codes):
            out.append(identity)
    return tuple(out)


def _identity_status(diff: Decimal) -> str:
    if diff > IDENTITY_FAIL:
        return STATUS_FAIL
    if diff >= IDENTITY_WARN:
        return STATUS_WARN
    return STATUS_PASS


def check_accounting_identities(lines: Sequence[LineInfo]) -> CheckResult:
    """Each identity per period, when every required line is present.

    Both sides are shown only when every line involved is non-vendor; a vendor-backed identity
    shows the relative difference alone (a vendor figure is never displayed).
    """
    by_period: dict[str, dict[str, LineInfo]] = {}
    for line in lines:
        if line.value is not None:
            by_period.setdefault(line.period, {})[line.code] = line
    evaluated = 0
    statuses: list[str] = []
    items: list[dict[str, Any]] = []
    for period in sorted(by_period):
        row = by_period[period]
        for identity in available_identities():
            if identity.lhs not in row or any(code not in row for code, _ in identity.required):
                continue
            used = [identity.lhs, *(c for c, _ in identity.required)]
            used += [c for c, _ in identity.optional if c in row]
            signed = [*identity.required, *((c, s) for c, s in identity.optional if c in row)]
            left = _value(row[identity.lhs])
            right = sum((_value(row[code]) * sign for code, sign in signed), Decimal(0))
            diff = relative_difference(left, right)
            status = _identity_status(diff)
            evaluated += 1
            statuses.append(status)
            if status != STATUS_PASS:
                item: dict[str, Any] = {
                    "period": period,
                    "identity": identity.name,
                    "relative_difference": str(diff.quantize(_RATIO_QUANT)),
                }
                if not any(row[code].vendor for code in used):
                    item["left"] = str(left)
                    item["right"] = str(right)
                items.append(item)
    if evaluated == 0:
        return _insufficient(
            CHECK_ACCOUNTING_IDENTITY,
            "No period has all the lines needed for an accounting identity.",
        )
    status = worst_status(statuses)
    off = len(items)
    detail = (
        f"All {evaluated} identity checks hold within {IDENTITY_WARN:.1%}."
        if status == STATUS_PASS
        else f"{off} of {evaluated} identity checks are off by {IDENTITY_WARN:.1%} or more."
    )
    return CheckResult(
        CHECK_ACCOUNTING_IDENTITY,
        status,
        detail,
        {"evaluated": evaluated, "off": off, "items": items[:MAX_EVIDENCE_ITEMS]},
    )


def _value(line: LineInfo) -> Decimal:
    assert line.value is not None  # callers keep valued lines only
    return line.value


# --- price sanity ------------------------------------------------------------------------------


def trading_days_between(start: date, end: date) -> int:
    """EGX trading weekdays in ``(start, end]``; zero when ``end <= start``."""
    days = 0
    current = start + timedelta(days=1)
    while current <= end:
        if current.weekday() in EGX_TRADING_WEEKDAYS:
            days += 1
        current += timedelta(days=1)
    return days


def _is_possible_split(ratio: Decimal) -> bool:
    """True when the close ratio is near n:1 or 1:n for a common split factor."""
    for n in SPLIT_FACTORS:
        factor = Decimal(n)
        if abs(ratio * factor - 1) <= SPLIT_TOLERANCE or abs(ratio / factor - 1) <= SPLIT_TOLERANCE:
            return True
    return False


def check_price_sanity(closes: Sequence[tuple[date, Decimal]], as_of: date) -> CheckResult:
    """Non-positive closes, one-day moves past the EGX limit, and gaps in the last year."""
    start = as_of - timedelta(days=PRICE_LOOKBACK_DAYS)
    series = sorted((d, c) for d, c in closes if start <= d <= as_of)
    if len(series) < 2:
        return _insufficient(CHECK_PRICE_SANITY, "Fewer than two closes in the last year.")
    non_positive = [d for d, c in series if c <= 0]
    breaches: list[dict[str, Any]] = []
    splits: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    limit = EGX_DAILY_LIMIT + LIMIT_TOLERANCE
    for (prev_date, prev_close), (day, close) in zip(series, series[1:], strict=False):
        missing = trading_days_between(prev_date, day) - 1
        if missing > GAP_TRADING_DAYS:
            gaps.append(
                {"from": prev_date.isoformat(), "to": day.isoformat(), "missing_days": missing}
            )
            continue  # the limit does not apply across a suspension-length gap
        if prev_close <= 0 or close <= 0:
            continue
        ratio = close / prev_close
        if abs(ratio - 1) > limit:
            entry = {"date": day.isoformat(), "change": str((ratio - 1).quantize(_RATIO_QUANT))}
            (splits if _is_possible_split(ratio) else breaches).append(entry)
    evidence: dict[str, Any] = {
        "closes_checked": len(series),
        "non_positive_closes": [d.isoformat() for d in non_positive[:MAX_EVIDENCE_ITEMS]],
        "limit_breaches": breaches[:MAX_EVIDENCE_ITEMS],
        "possible_splits": splits[:MAX_EVIDENCE_ITEMS],
        "gaps": gaps[:MAX_EVIDENCE_ITEMS],
    }
    if non_positive or breaches:
        parts = []
        if non_positive:
            parts.append(f"{len(non_positive)} non-positive close(s)")
        if breaches:
            parts.append(f"{len(breaches)} one-day move(s) beyond the EGX limit without a split")
        return CheckResult(CHECK_PRICE_SANITY, STATUS_FAIL, "; ".join(parts) + ".", evidence)
    if gaps:
        return CheckResult(
            CHECK_PRICE_SANITY,
            STATUS_WARN,
            f"{len(gaps)} gap(s) of more than {GAP_TRADING_DAYS} trading days in the last year.",
            evidence,
        )
    return CheckResult(
        CHECK_PRICE_SANITY,
        STATUS_PASS,
        f"{len(series)} closes in the last year are positive, within the daily limit and gap-free.",
        evidence,
    )


# --- freshness ---------------------------------------------------------------------------------


def quarters_behind(period_end: date, as_of: date) -> int:
    """Whole quarters between a period end and ``as_of`` (never negative)."""
    months = (as_of.year * 12 + as_of.month) - (period_end.year * 12 + period_end.month)
    return max(months, 0) // 3


def check_freshness(
    last_close: date | None, latest_period_end: date | None, as_of: date
) -> CheckResult:
    """Age of the last close (trading days) and of the latest reported period (quarters)."""
    statuses: list[str] = []
    parts: list[str] = []
    evidence: dict[str, Any] = {}
    if last_close is None:
        statuses.append(STATUS_INSUFFICIENT)
        parts.append("no stored price")
        evidence["last_close"] = None
    else:
        age = trading_days_between(last_close, as_of)
        evidence.update({"last_close": last_close.isoformat(), "price_age_trading_days": age})
        if age > FRESH_PRICE_FAIL_DAYS:
            statuses.append(STATUS_FAIL)
        elif age > FRESH_PRICE_WARN_DAYS:
            statuses.append(STATUS_WARN)
        else:
            statuses.append(STATUS_PASS)
        parts.append(f"last close {age} trading day(s) old")
    if latest_period_end is None:
        statuses.append(STATUS_INSUFFICIENT)
        parts.append("no reported period")
        evidence["latest_period_end"] = None
    else:
        behind = quarters_behind(latest_period_end, as_of)
        evidence.update(
            {"latest_period_end": latest_period_end.isoformat(), "quarters_behind": behind}
        )
        if behind > FRESH_PERIOD_FAIL_QUARTERS:
            statuses.append(STATUS_FAIL)
        elif behind > FRESH_PERIOD_WARN_QUARTERS:
            statuses.append(STATUS_WARN)
        else:
            statuses.append(STATUS_PASS)
        parts.append(f"latest period {behind} quarter(s) behind")
    evidence["as_of"] = as_of.isoformat()
    return CheckResult(
        CHECK_FRESHNESS, worst_status(statuses), "; ".join(parts).capitalize() + ".", evidence
    )


def run_all(
    *,
    latest_lines: Sequence[LineInfo],
    all_lines: Sequence[LineInfo],
    closes: Sequence[tuple[date, Decimal]],
    as_of: date,
) -> list[CheckResult]:
    """The five checks in display order.

    ``latest_lines`` are the winners the app shows; ``all_lines`` every approved line (for the
    cross-source pairing of a filing line with a vendor line of the same period and code).
    """
    filing = [line for line in all_lines if line.filing_backed]
    vendor = [line for line in all_lines if line.vendor]
    valued = [line for line in latest_lines if line.value is not None]
    last_close = max((d for d, _ in closes if d <= as_of), default=None)
    latest_period = max((line.period_end for line in valued), default=None)
    return [
        check_provenance(latest_lines),
        check_cross_source(filing, vendor),
        check_accounting_identities(latest_lines),
        check_price_sanity(closes, as_of),
        check_freshness(last_close, latest_period, as_of),
    ]
