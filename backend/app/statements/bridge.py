"""Bridge: approved statement lines -> engine inputs (R43 M1, stmt-bridge-1.0).

Single owner of "ontology code -> engine input". Engines (metrics, data
quality, Shariah, purification, fair value, score, thesis) read fundamentals
only through this module, which reads only
``StatementLineRepository.latest_approved`` (filing beats vendor).

Rules:
- One coherent period per computation: a code missing in a period is
  INSUFFICIENT_DATA, never borrowed from an older period.
- ANNUAL periods only (v1).
- Derived values are exact Decimal arithmetic; a missing, zero or negative
  denominator yields INSUFFICIENT_DATA naming the line, never a zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from sqlalchemy import select

from app.models.financial import FinancialDocument, FinancialPeriod, ReportingPeriodType
from app.models.statements import ExtractionMethod
from app.repositories.statements import StatementLineRepository

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable, Mapping
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession

BRIDGE_VERSION = "stmt-bridge-1.0"
SourceTier = Literal["filing", "vendor"]
ResolvedStatus = Literal["AVAILABLE", "INSUFFICIENT_DATA"]

DPS_DERIVATION = "abs(dividends_paid) / shares_outstanding"
#: How a derived DPS is named everywhere; it is never a *declared* DPS (analyst D-6/M4).
DPS_LABEL = "cash dividends paid per share (derived)"


@dataclass(frozen=True, slots=True)
class LineValue:
    """One winning approved statement line with its provenance."""

    code: str
    value: Decimal
    line_id: uuid.UUID
    period_id: uuid.UUID
    fiscal_year: int
    period_end: date
    source_tier: SourceTier
    document_id: uuid.UUID | None
    document_type: str | None
    document_url: str | None
    source_label_reported: str | None
    source_page: str | None
    published_date: date | None


@dataclass(frozen=True, slots=True)
class PeriodLines:
    """All winning lines of one reporting period."""

    period_id: uuid.UUID
    fiscal_year: int
    period_type: str
    period_end: date
    lines: Mapping[str, LineValue]

    def get(self, code: str) -> LineValue | None:
        return self.lines.get(code)


@dataclass(frozen=True, slots=True)
class Resolved:
    """An engine input: a value with its sources, or an honest gap."""

    value: Decimal | None
    status: ResolvedStatus
    reason: str | None
    missing_input: str | None
    sources: tuple[LineValue, ...] = field(default=())
    derivation: str | None = None

    @property
    def available(self) -> bool:
        return self.status == "AVAILABLE"


@dataclass(frozen=True, slots=True)
class CompanyStatements:
    """ANNUAL periods with winner lines, newest ``period_end`` first."""

    company_id: uuid.UUID
    periods: tuple[PeriodLines, ...]

    def latest(self) -> PeriodLines | None:
        return self.periods[0] if self.periods else None

    def prior(self, p: PeriodLines) -> PeriodLines | None:
        """Same period type, ``fiscal_year - 1``; None when absent."""
        return self._by_year(p, p.fiscal_year - 1)

    def years_back(self, p: PeriodLines, n: int) -> PeriodLines | None:
        return self._by_year(p, p.fiscal_year - n)

    def _by_year(self, p: PeriodLines, year: int) -> PeriodLines | None:
        for other in self.periods:
            if other.period_type == p.period_type and other.fiscal_year == year:
                return other
        return None

    def series(self, code: str) -> list[LineValue]:
        """Every period's value of ``code``, oldest -> newest."""
        out = [p.lines[code] for p in self.periods if code in p.lines]
        return list(reversed(out))

    def all_lines(self) -> list[LineValue]:
        return [lv for p in self.periods for lv in p.lines.values()]


def _period_type_value(period: FinancialPeriod) -> str:
    raw = period.period_type
    return raw.value if hasattr(raw, "value") else str(raw)


async def load_company_statements(
    session: AsyncSession,
    company_id: uuid.UUID,
    *,
    as_of: date | None = None,
) -> CompanyStatements:
    """Load winner lines grouped into ANNUAL periods (newest first).

    ``as_of`` (R14 bound) drops lines published after it; lines without a
    publication date are kept (vendor lines cannot be dated).
    """
    rows = await StatementLineRepository(session).latest_approved(company_id)
    rows = [
        r
        for r in rows
        if r.value is not None
        and (as_of is None or r.published_date is None or r.published_date <= as_of)
    ]
    if not rows:
        return CompanyStatements(company_id=company_id, periods=())

    period_ids = {r.period_id for r in rows}
    periods = {
        p.id: p
        for p in (
            await session.execute(
                select(FinancialPeriod).where(FinancialPeriod.id.in_(period_ids))
            )
        ).scalars().all()
    }
    doc_ids = {r.source_document_id for r in rows if r.source_document_id is not None}
    documents: dict[uuid.UUID, FinancialDocument] = {}
    if doc_ids:
        documents = {
            d.id: d
            for d in (
                await session.execute(
                    select(FinancialDocument).where(FinancialDocument.id.in_(doc_ids))
                )
            ).scalars().all()
        }

    grouped: dict[uuid.UUID, dict[str, LineValue]] = {}
    for row in rows:
        period = periods.get(row.period_id)
        if period is None or _period_type_value(period) != ReportingPeriodType.ANNUAL.value:
            continue
        doc = documents.get(row.source_document_id) if row.source_document_id else None
        assert row.value is not None
        grouped.setdefault(row.period_id, {})[row.ontology_code] = LineValue(
            code=row.ontology_code,
            value=Decimal(row.value),
            line_id=row.id,
            period_id=row.period_id,
            fiscal_year=int(period.fiscal_year),
            period_end=period.end_date,
            source_tier=(
                "vendor"
                if row.extraction_method == ExtractionMethod.vendor_aggregator
                else "filing"
            ),
            document_id=row.source_document_id,
            document_type=doc.document_type if doc is not None else None,
            document_url=doc.document_url if doc is not None else None,
            source_label_reported=row.source_label_reported,
            source_page=row.source_page,
            published_date=row.published_date,
        )

    out = [
        PeriodLines(
            period_id=pid,
            fiscal_year=int(periods[pid].fiscal_year),
            period_type=_period_type_value(periods[pid]),
            period_end=periods[pid].end_date,
            lines=lines,
        )
        for pid, lines in grouped.items()
    ]
    out.sort(key=lambda p: p.period_end, reverse=True)
    return CompanyStatements(company_id=company_id, periods=tuple(out))


# --- resolution -------------------------------------------------------------


def missing_reason(code: str, p: PeriodLines | None) -> str:
    if p is None:
        return f"no approved statement period: {code} unavailable"
    return f"missing statement line: {code} (FY{p.fiscal_year})"


def _missing(code: str, p: PeriodLines | None, derivation: str | None = None) -> Resolved:
    return Resolved(
        value=None,
        status="INSUFFICIENT_DATA",
        reason=missing_reason(code, p),
        missing_input=code,
        sources=(),
        derivation=derivation,
    )


def line(p: PeriodLines | None, code: str) -> Resolved:
    """Straight statement line from one period (never another period)."""
    lv = p.get(code) if p is not None else None
    if lv is None:
        return _missing(code, p)
    return Resolved(
        value=lv.value,
        status="AVAILABLE",
        reason=None,
        missing_input=None,
        sources=(lv,),
        derivation=None,
    )


def _divide(
    p: PeriodLines | None,
    num: Resolved,
    den_code: str,
    derivation: str,
    *,
    num_abs: bool = False,
) -> Resolved:
    if not num.available or num.value is None:
        return Resolved(None, "INSUFFICIENT_DATA", num.reason, num.missing_input, (), derivation)
    den = line(p, den_code)
    if not den.available or den.value is None:
        return Resolved(None, "INSUFFICIENT_DATA", den.reason, den.missing_input, (), derivation)
    fy = f" (FY{p.fiscal_year})" if p is not None else ""
    if den.value == 0:
        return Resolved(
            None, "INSUFFICIENT_DATA", f"zero denominator: {den_code}{fy}", den_code, (),
            derivation,
        )
    if den.value < 0:
        return Resolved(
            None, "INSUFFICIENT_DATA", f"negative denominator: {den_code}{fy}", den_code, (),
            derivation,
        )
    numerator = abs(num.value) if num_abs else num.value
    return Resolved(
        value=numerator / den.value,
        status="AVAILABLE",
        reason=None,
        missing_input=None,
        sources=num.sources + den.sources,
        derivation=derivation,
    )


def capex_magnitude(p: PeriodLines | None) -> Resolved:
    """``abs(capex)``: vendor stores capex negative; engines expect a spend."""
    capex = line(p, "capex")
    if not capex.available or capex.value is None:
        return capex
    return Resolved(abs(capex.value), "AVAILABLE", None, None, capex.sources, "abs(capex)")


def free_cash_flow(p: PeriodLines | None) -> Resolved:
    """``cfo - abs(capex)`` (same formula as the ``free_cash_flow`` metric)."""
    derivation = "cfo - abs(capex)"
    cfo = line(p, "cfo")
    if not cfo.available or cfo.value is None:
        return Resolved(None, "INSUFFICIENT_DATA", cfo.reason, cfo.missing_input, (), derivation)
    capex = capex_magnitude(p)
    if not capex.available or capex.value is None:
        return Resolved(
            None, "INSUFFICIENT_DATA", capex.reason, capex.missing_input, (), derivation
        )
    return Resolved(
        cfo.value - capex.value, "AVAILABLE", None, None, cfo.sources + capex.sources,
        derivation,
    )


def eps(p: PeriodLines | None) -> Resolved:
    """Approved ``eps`` line when it is a winner, else net income / weighted shares."""
    direct = line(p, "eps")
    if direct.available:
        return direct
    return _divide(
        p, line(p, "net_income"), "weighted_avg_shares_basic",
        "net_income / weighted_avg_shares_basic",
    )


def book_value_per_share(p: PeriodLines | None) -> Resolved:
    return _divide(
        p, line(p, "total_equity"), "shares_outstanding", "total_equity / shares_outstanding"
    )


def revenue_per_share(p: PeriodLines | None) -> Resolved:
    return _divide(p, line(p, "revenue"), "shares_outstanding", "revenue / shares_outstanding")


def long_term_liabilities(p: PeriodLines | None) -> Resolved:
    derivation = "total_liabilities - current_liabilities"
    total = line(p, "total_liabilities")
    current = line(p, "current_liabilities")
    for part in (total, current):
        if not part.available:
            return Resolved(
                None, "INSUFFICIENT_DATA", part.reason, part.missing_input, (), derivation
            )
    assert total.value is not None and current.value is not None
    return Resolved(
        total.value - current.value, "AVAILABLE", None, None, total.sources + current.sources,
        derivation,
    )


def revenue_cagr_3y(bundle: CompanyStatements, p: PeriodLines | None) -> Resolved:
    """3-year revenue CAGR as a fraction: ``(revenue_t / revenue_t-3) ** (1/3) - 1``.

    Needs the four consecutive annual revenue points t, t-1, t-2, t-3 (owner ruling
    F13); a missing point is INSUFFICIENT_DATA naming the year, never an interpolation.
    A non-positive start or end revenue has no meaningful CAGR and is INSUFFICIENT too.
    """
    derivation = "(revenue_t / revenue_t-3) ** (1/3) - 1"
    if p is None:
        return _missing("revenue", None, derivation)
    points: list[LineValue] = []
    for back in range(4):
        period = bundle.years_back(p, back)
        lv = period.get("revenue") if period is not None else None
        if lv is None:
            return Resolved(
                None, "INSUFFICIENT_DATA",
                f"revenue CAGR needs 4 annual revenue points: missing revenue "
                f"FY{p.fiscal_year - back}",
                "revenue", (), derivation,
            )
        points.append(lv)
    latest, start = points[0], points[3]
    if latest.value <= 0 or start.value <= 0:
        return Resolved(
            None, "INSUFFICIENT_DATA",
            f"revenue CAGR undefined: non-positive revenue in FY{start.fiscal_year} "
            f"or FY{latest.fiscal_year}",
            "revenue", (), derivation,
        )
    cagr = (latest.value / start.value) ** (Decimal(1) / Decimal(3)) - 1
    return Resolved(cagr, "AVAILABLE", None, None, (start, latest), derivation)


def dps(p: PeriodLines | None) -> Resolved:
    """Cash dividends paid **in** the fiscal year per share outstanding (ANALYST GATE D-6).

    Label: ``DPS_LABEL``. Used for purification and the cash-paid / EPS payout
    only; it is timing-noisy, so it never feeds the dividend-history checks.
    """
    return _divide(
        p, line(p, "dividends_paid"), "shares_outstanding", DPS_DERIVATION, num_abs=True
    )


# --- provenance -------------------------------------------------------------


def provenance(lv: LineValue) -> dict[str, str | int | bool | None]:
    """The one provenance shape every statement-derived number carries (section 1.4)."""
    return {
        "code": lv.code,
        "value": str(lv.value),
        "line_id": str(lv.line_id),
        "fiscal_year": lv.fiscal_year,
        "period_end": lv.period_end.isoformat(),
        "source_tier": lv.source_tier,
        "provisional": lv.source_tier == "vendor",
        "document_type": lv.document_type,
        "document_url": lv.document_url,
        "source_label_reported": lv.source_label_reported,
        "source_page": lv.source_page,
        "published_date": lv.published_date.isoformat() if lv.published_date else None,
    }


def tier_of(sources: Iterable[LineValue]) -> SourceTier | None:
    """"vendor" if any vendor line, "filing" if all filing, None if empty."""
    tiers = {lv.source_tier for lv in sources}
    if not tiers:
        return None
    return "vendor" if "vendor" in tiers else "filing"


def unique_sources(sources: Iterable[LineValue]) -> list[LineValue]:
    seen: set[uuid.UUID] = set()
    out: list[LineValue] = []
    for lv in sources:
        if lv.line_id not in seen:
            seen.add(lv.line_id)
            out.append(lv)
    return out
