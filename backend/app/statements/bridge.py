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
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import select

from app.models.financial import FinancialDocument, FinancialPeriod, ReportingPeriodType
from app.models.statements import ExtractionMethod
from app.repositories.statements import StatementLineRepository
from app.valuation.constants import FCFE_BASE_YEARS

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable, Mapping
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession

BRIDGE_VERSION = "stmt-bridge-1.0"
SourceTier = Literal["filing", "vendor"]
ResolvedStatus = Literal["AVAILABLE", "INSUFFICIENT_DATA"]

#: The shape of one cash-flow base year (R46 V7); the years averaged are ``FCFE_BASE_YEARS``.
FCFE_DERIVATION = "(cfo - abs(capex)) x parent_share"
FCFE_BASE_METHOD = (
    f"mean of the last {FCFE_BASE_YEARS} fiscal years of "
    "(operating cash flow - capex) x parent share; debt grows with the firm"
)
DEBT_METHOD = "latest-year interest-bearing debt x parent share"
PARENT_SHARE_DERIVATION = "net_income / (net_income_to_parent - minority_income)"

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
    #: Currency the line is reported in (statement currency, R46 C1); None when unknown.
    currency: str | None = None


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

    def currency(self) -> str | None:
        """The one currency every line of the period is reported in; None if unknown/mixed."""
        currencies = {lv.currency for lv in self.lines.values()}
        return next(iter(currencies)) if len(currencies) == 1 and None not in currencies else None


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
            currency=row.currency,
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


@dataclass(frozen=True, slots=True)
class FcfeYear:
    """One fiscal year of the cash-flow base (R46 V7); a gap names its line.

    ``flow`` is ``(cfo - abs(capex)) x parent_share``, the value averaged into the base.
    ``net_borrowing`` is information only: it no longer enters the base.
    """

    fiscal_year: int
    status: ResolvedStatus
    reason: str | None
    cfo: Decimal | None = None
    capex: Decimal | None = None
    pre_financing: Decimal | None = None
    net_borrowing: Decimal | None = None
    parent_share: Decimal | None = None
    flow: Decimal | None = None
    sources: tuple[LineValue, ...] = field(default=())

    def payload(self) -> dict[str, str | int | None]:
        def opt(v: Decimal | None) -> str | None:
            return str(v) if v is not None else None

        return {
            "fiscal_year": self.fiscal_year,
            "status": self.status,
            "reason": self.reason,
            "cfo": opt(self.cfo),
            "capex": opt(self.capex),
            "pre_financing": opt(self.pre_financing),
            "net_borrowing": opt(self.net_borrowing),
            "parent_share": opt(self.parent_share),
            "flow": opt(self.flow),
        }


@dataclass(frozen=True, slots=True)
class FcfeBase:
    """The cash-flow valuation base: ``resolved`` is the mean, ``years`` the evidence."""

    resolved: Resolved
    years: tuple[FcfeYear, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "method": FCFE_BASE_METHOD,
            "years_required": FCFE_BASE_YEARS,
            "status": self.resolved.status,
            "reason": self.resolved.reason,
            "mean": str(self.resolved.value) if self.resolved.value is not None else None,
            "years": [y.payload() for y in self.years],
        }


@dataclass(frozen=True, slots=True)
class DebtBase:
    """Interest-bearing debt that grows with the firm (R46 V7): latest year x parent share."""

    resolved: Resolved
    fiscal_year: int | None = None
    reported: Decimal | None = None
    parent_share: Decimal | None = None
    #: "reported" (a debt line exists) or "vendor_omitted_zero" (no-debt evidence, see below).
    basis: str | None = None

    def payload(self) -> dict[str, Any]:
        def opt(v: Decimal | None) -> str | None:
            return str(v) if v is not None else None

        return {
            "method": DEBT_METHOD,
            "value": opt(self.resolved.value),
            "fiscal_year": self.fiscal_year,
            "reported_value": opt(self.reported),
            "parent_share": opt(self.parent_share),
            "basis": self.basis,
            "status": self.resolved.status,
            "reason": self.resolved.reason,
        }


def parent_share(p: PeriodLines | None) -> Resolved:
    """Share of consolidated earnings that belongs to the parent's common holders.

    ``net_income / (net_income_to_parent - minority_income)``: net income to common over
    net income including minorities (``minority_income`` keeps the vendor sign, negative
    = earnings attributed to minorities). Exactly 1 when minorities are absent: a zero
    income minority line, or no income line and no balance-sheet minority interests.
    Balance-sheet minorities without the income line, or a non-positive net income
    incl. minorities, leave the share unresolved (INSUFFICIENT_DATA), never 1. A share
    above 1 (loss-making minorities) is capped at 1 so FCFE is never inflated.
    """
    if p is None:
        return _missing("net_income", None, PARENT_SHARE_DERIVATION)
    mi = line(p, "minority_income")
    if mi.available and mi.value == 0:
        return Resolved(
            Decimal(1), "AVAILABLE", None, None, mi.sources, "no minority earnings: share 1"
        )
    if not mi.available:
        bs_minority = line(p, "minority_interests")
        if bs_minority.available and bs_minority.value not in (None, Decimal(0)):
            return Resolved(
                None, "INSUFFICIENT_DATA",
                f"parent share unresolved: balance-sheet minority interests present but "
                f"minority_income missing (FY{p.fiscal_year})",
                "minority_income", (), PARENT_SHARE_DERIVATION,
            )
        return Resolved(
            Decimal(1), "AVAILABLE", None, None, bs_minority.sources,
            "no minority interests: share 1",
        )
    parent = line(p, "net_income_to_parent")
    common = line(p, "net_income")
    for part in (parent, common):
        if not part.available or part.value is None:
            return Resolved(
                None, "INSUFFICIENT_DATA", part.reason, part.missing_input, (),
                PARENT_SHARE_DERIVATION,
            )
    assert parent.value is not None and common.value is not None and mi.value is not None
    total = parent.value - mi.value
    if total <= 0:
        return Resolved(
            None, "INSUFFICIENT_DATA",
            f"parent share undefined: net income incl. minorities is not positive "
            f"(FY{p.fiscal_year})",
            "net_income_to_parent", (), PARENT_SHARE_DERIVATION,
        )
    if common.value < 0:
        return Resolved(
            None, "INSUFFICIENT_DATA",
            f"parent share undefined: net income to common is negative while net income "
            f"incl. minorities is positive (FY{p.fiscal_year})",
            "net_income", (), PARENT_SHARE_DERIVATION,
        )
    share = min(Decimal(1), common.value / total)
    return Resolved(
        share, "AVAILABLE", None, None, mi.sources + parent.sources + common.sources,
        PARENT_SHARE_DERIVATION,
    )


def fcfe_year(p: PeriodLines) -> FcfeYear:
    """Pre-financing cash flow of one fiscal year x parent share; a missing line = missing year.

    Net borrowing is carried for information only (R46 V7): the projection grows the
    latest debt with the firm instead of repeating past repayments.
    """
    fy = p.fiscal_year
    cfo = line(p, "cfo")
    capex = capex_magnitude(p)
    borrowing = line(p, "net_borrowing")
    for part in (cfo, capex):
        if not part.available or part.value is None:
            return FcfeYear(
                fy, "INSUFFICIENT_DATA", part.reason, cfo.value, capex.value,
                net_borrowing=borrowing.value,
            )
    assert cfo.value is not None and capex.value is not None
    pre_financing = cfo.value - capex.value
    share = parent_share(p)
    if not share.available or share.value is None:
        return FcfeYear(
            fy, "INSUFFICIENT_DATA", share.reason, cfo.value, capex.value, pre_financing,
            borrowing.value,
        )
    return FcfeYear(
        fy, "AVAILABLE", None, cfo.value, capex.value, pre_financing, borrowing.value,
        share.value, pre_financing * share.value,
        cfo.sources + capex.sources + share.sources,
    )


def fcfe_base(bundle: CompanyStatements, p: PeriodLines | None) -> FcfeBase:
    """Mean pre-financing flow (x parent share) of the last ``FCFE_BASE_YEARS`` years.

    Needs every one of the consecutive years t, t-1, t-2; a missing period or a year
    missing any component is INSUFFICIENT_DATA naming it (no shorter average, no
    interpolation). The mean may be <= 0: the valuation model marks that INVALID.
    """
    if p is None:
        return FcfeBase(_missing("cfo", None, FCFE_DERIVATION), ())
    years: list[FcfeYear] = []
    for back in range(FCFE_BASE_YEARS):
        period = bundle.years_back(p, back)
        if period is None:
            years.append(
                FcfeYear(
                    p.fiscal_year - back,
                    "INSUFFICIENT_DATA",
                    f"no approved annual period FY{p.fiscal_year - back}",
                )
            )
        else:
            years.append(fcfe_year(period))
    gaps = [f"FY{y.fiscal_year}: {y.reason}" for y in years if y.status != "AVAILABLE"]
    if gaps:
        return FcfeBase(
            Resolved(
                None, "INSUFFICIENT_DATA",
                f"FCFE needs {FCFE_BASE_YEARS} fiscal years; " + "; ".join(gaps),
                "fcfe", (), FCFE_DERIVATION,
            ),
            tuple(years),
        )
    total = sum((y.flow for y in years if y.flow is not None), Decimal(0))
    sources = tuple(lv for y in years for lv in y.sources)
    return FcfeBase(
        Resolved(
            total / Decimal(FCFE_BASE_YEARS), "AVAILABLE", None, None, sources, FCFE_DERIVATION
        ),
        tuple(years),
    )


def debt_base(bundle: CompanyStatements, p: PeriodLines | None) -> DebtBase:
    """Latest-year interest-bearing debt x the same year's parent share (R46 V7).

    Scaled by the parent share because the flow base is: minorities' part of the group's
    debt is not the parent's to grow or repay. A reported ``interest_bearing_debt`` line is
    used as is. When the line is absent, zero debt is only concluded from evidence, never
    assumed: the vendor omits zero-valued rows (a company repaying to nil, or with none,
    has no ``debt`` row), so all of these must hold - every line of the period is
    vendor-sourced, the balance sheet is present (``total_liabilities``), the period has no
    finance costs, net borrowing or debt repayment, and the prior year has no debt. Any
    other absence is INSUFFICIENT_DATA naming what contradicts it.
    """
    if p is None:
        return DebtBase(_missing("interest_bearing_debt", None, DEBT_METHOD))
    share = parent_share(p)
    if not share.available or share.value is None:
        return DebtBase(
            Resolved(None, "INSUFFICIENT_DATA", share.reason, share.missing_input, (), DEBT_METHOD),
            p.fiscal_year,
        )

    def done(value: Decimal, reported: Decimal, basis: str, src: tuple[LineValue, ...]) -> DebtBase:
        return DebtBase(
            Resolved(value, "AVAILABLE", None, None, src + share.sources, DEBT_METHOD),
            p.fiscal_year, reported, share.value, basis,
        )

    def unresolved(reason: str) -> DebtBase:
        return DebtBase(
            Resolved(None, "INSUFFICIENT_DATA", reason, "interest_bearing_debt", (), DEBT_METHOD),
            p.fiscal_year, None, share.value,
        )

    debt = line(p, "interest_bearing_debt")
    if debt.available and debt.value is not None:
        if debt.value < 0:
            return unresolved(f"negative interest_bearing_debt (FY{p.fiscal_year})")
        return done(debt.value * share.value, debt.value, "reported", debt.sources)

    base = f"interest_bearing_debt missing (FY{p.fiscal_year}) and not evidenced as nil"
    if any(lv.source_tier != "vendor" for lv in p.lines.values()):
        return unresolved(f"{base}: the period is not vendor-sourced")
    balance = line(p, "total_liabilities")
    if not balance.available:
        return unresolved(f"{base}: no balance sheet (total_liabilities) in the period")
    for code in ("finance_costs", "net_borrowing", "debt_repayment"):
        lv = p.get(code)
        if lv is not None and lv.value != 0:
            return unresolved(f"{base}: {code} {lv.value} is non-zero")
    prior = bundle.prior(p)
    prior_debt = prior.get("interest_bearing_debt") if prior is not None else None
    if prior_debt is not None and prior_debt.value != 0:
        return unresolved(
            f"{base}: FY{prior_debt.fiscal_year} debt {prior_debt.value} has no recorded "
            f"repayment"
        )
    return done(Decimal(0), Decimal(0), "vendor_omitted_zero", balance.sources)


def is_bank(p: PeriodLines | None) -> bool:
    """A bank reports both net loans and customer deposits (R46 V3); sector is not used."""
    return p is not None and p.get("net_loans") is not None and p.get("total_deposits") is not None


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
