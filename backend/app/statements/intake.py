"""Official-filings intake: priority checklist + assisted manual entry.

Priority set = official EGX33 Shariah members + the 30 most-traded companies
(by average value traded; a proxy for EGX30 until the official EGX30 list is
loaded). For each, the checklist shows which fiscal years are backed by an
official filing and which only have provisional vendor data.

Manual entry records numbers a person copies from an official filing: every
value needs the filing URL and a page reference, and the batch runs through the
same StatementValidator gates as automated extraction. Filing-backed lines
always outrank vendor lines for the same period and code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from sqlalchemy import select

from app.models.financial import FinancialPeriod, ReportingPeriodType
from app.models.market import Company, DataSourceType
from app.models.statements import ExtractionMethod, FinancialStatementLine
from app.repositories.data_source import DataSourceRepository
from app.repositories.financial import FinancialDocumentRepository, FinancialPeriodRepository
from app.repositories.price import PriceRepository
from app.repositories.screening import ScreeningRepository
from app.repositories.statements import CalculationStatuses, StatementLineRepository
from app.schemas.financial import FinancialDocumentCreate, FinancialPeriodCreate
from app.statements.extractor import LineCandidate
from app.statements.ontology import STATEMENT_LINES, STATEMENT_ONTOLOGY_VERSION
from app.statements.validator import StatementValidator
from app.statements.vendor_import import period_start

if TYPE_CHECKING:
    import uuid
    from decimal import Decimal

    from sqlalchemy.ext.asyncio import AsyncSession

MOST_TRADED_COUNT = 30
FILING_DOCUMENT_TYPE = "ANNUAL_REPORT"
EGX_DISCLOSURE_SEARCH = "https://www.egx.com.eg/en/NewsSearch.aspx?isin={isin}&sec_id=20"


@dataclass
class IntakeRow:
    company_id: uuid.UUID
    ticker: str
    name: str
    reasons: list[str]
    filing_years: list[int]
    vendor_years: list[int]
    target_year: int
    status: str  # filed | vendor_only | missing
    disclosure_url: str | None


@dataclass
class ManualLine:
    code: str
    value: Decimal
    page: str


@dataclass
class ManualFilingResult:
    document_id: uuid.UUID
    period_id: uuid.UUID
    lines: list[dict[str, str | None]] = field(default_factory=list)


async def priority_companies(session: AsyncSession) -> dict[uuid.UUID, list[str]]:
    """Company id -> why it is in the priority set."""
    reasons: dict[uuid.UUID, list[str]] = {}
    memberships = await ScreeningRepository(session).latest_egx_memberships()
    for company_id, row in memberships.items():
        if row.member:
            reasons.setdefault(company_id, []).append("egx33")
    for company_id in await PriceRepository(session).most_traded_company_ids(MOST_TRADED_COUNT):
        reasons.setdefault(company_id, []).append("most_traded")
    return reasons


async def _years_by_tier(
    session: AsyncSession, company_ids: list[uuid.UUID]
) -> tuple[dict[uuid.UUID, set[int]], dict[uuid.UUID, set[int]]]:
    rows = (
        await session.execute(
            select(
                FinancialStatementLine.company_id,
                FinancialStatementLine.extraction_method,
                FinancialPeriod.fiscal_year,
            )
            .join(FinancialPeriod, FinancialPeriod.id == FinancialStatementLine.period_id)
            .where(
                FinancialStatementLine.company_id.in_(company_ids),
                FinancialStatementLine.ext_status.in_(CalculationStatuses),
                FinancialPeriod.period_type == ReportingPeriodType.ANNUAL,
            )
            .distinct()
        )
    ).all()
    filing: dict[uuid.UUID, set[int]] = {}
    vendor: dict[uuid.UUID, set[int]] = {}
    for company_id, method, year in rows:
        target = vendor if method == ExtractionMethod.vendor_aggregator else filing
        target.setdefault(company_id, set()).add(year)
    return filing, vendor


async def intake_checklist(session: AsyncSession, today: date | None = None) -> list[IntakeRow]:
    """Priority companies with their filing coverage, missing work first."""
    reasons = await priority_companies(session)
    ids = list(reasons)
    if not ids:
        return []
    companies = (await session.execute(select(Company).where(Company.id.in_(ids)))).scalars()
    filing, vendor = await _years_by_tier(session, ids)
    default_target = (today or date.today()).year - 1
    rows: list[IntakeRow] = []
    for company in companies:
        filed = filing.get(company.id, set())
        vendor_years = vendor.get(company.id, set())
        target = max(vendor_years | filed, default=default_target)
        status = "filed" if target in filed else "vendor_only" if vendor_years else "missing"
        rows.append(
            IntakeRow(
                company_id=company.id,
                ticker=company.ticker,
                name=company.name,
                reasons=reasons[company.id],
                filing_years=sorted(filed, reverse=True),
                vendor_years=sorted(vendor_years, reverse=True),
                target_year=target,
                status=status,
                disclosure_url=(
                    EGX_DISCLOSURE_SEARCH.format(isin=company.isin) if company.isin else None
                ),
            )
        )
    order = {"missing": 0, "vendor_only": 1, "filed": 2}
    rows.sort(key=lambda r: (order[r.status], r.ticker))
    return rows


def _validate_inputs(document_url: str, lines: list[ManualLine]) -> None:
    parsed = urlparse(document_url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("document_url must be the http(s) address of the official filing")
    if not lines:
        raise ValueError("enter at least one statement line")
    seen: set[str] = set()
    for line in lines:
        if line.code not in STATEMENT_LINES:
            raise ValueError(f"unknown statement line {line.code!r}")
        if line.code in seen:
            raise ValueError(f"statement line {line.code!r} entered twice")
        if not line.page.strip():
            raise ValueError(f"{line.code}: a page reference in the filing is required")
        seen.add(line.code)


async def record_manual_filing(
    session: AsyncSession,
    *,
    ticker: str,
    fiscal_year: int,
    period_end: date,
    document_url: str,
    publication_date: date | None,
    currency: str,
    lines: list[ManualLine],
) -> ManualFilingResult:
    """Persist numbers copied from an official filing, validated like any filing."""
    _validate_inputs(document_url, lines)
    company = (
        await session.execute(select(Company).where(Company.ticker == ticker.upper()))
    ).scalar_one_or_none()
    if company is None:
        raise LookupError(f"company {ticker!r} not found")

    host = urlparse(document_url).netloc.lower()
    is_egx = host.endswith("egx.com.eg")
    source = await DataSourceRepository(session).get_or_create(
        name="EGX_DISCLOSURES" if is_egx else "COMPANY_IR",
        source_type=DataSourceType.EGX if is_egx else DataSourceType.COMPANY,
        base_url="https://www.egx.com.eg" if is_egx else None,
    )
    period = await FinancialPeriodRepository(session).upsert(
        FinancialPeriodCreate(
            company_id=company.id,
            period_type=ReportingPeriodType.ANNUAL,
            fiscal_year=fiscal_year,
            fiscal_quarter=None,
            start_date=period_start(period_end),
            end_date=period_end,
        )
    )
    document = await FinancialDocumentRepository(session).upsert(
        FinancialDocumentCreate(
            period_id=period.id,
            source_id=source.id,
            document_type=FILING_DOCUMENT_TYPE,
            document_url=document_url.strip()[:500],
            publication_date=publication_date,
            fiscal_year_end=period_end,
            notes="Entered manually from the official filing (values with page references).",
        )
    )
    document.source_kind = "EGX_DISCLOSURE" if is_egx else "IR"
    document.fetched_at = datetime.now(UTC)

    candidates = [
        LineCandidate(
            ontology_code=line.code,
            ontology_version=STATEMENT_ONTOLOGY_VERSION,
            value=line.value,
            currency=currency.upper(),
            source_label_reported=STATEMENT_LINES[line.code].label_en,
            source_label_en=STATEMENT_LINES[line.code].label_en,
            source_label_ar=STATEMENT_LINES[line.code].label_ar,
            source_page=line.page.strip()[:32],
            extraction_method=ExtractionMethod.manual_seed.value,
            published_date=publication_date,
        )
        for line in lines
    ]
    validated = StatementValidator().validate(candidates)
    await StatementLineRepository(session).upsert_candidates(
        document_id=document.id,
        company_id=company.id,
        period_id=period.id,
        lines=[v.candidate for v in validated.lines],
    )
    return ManualFilingResult(
        document_id=document.id,
        period_id=period.id,
        lines=[
            {
                "code": v.candidate.ontology_code,
                "status": v.candidate.ext_status,
                "reason": v.candidate.ext_reason,
            }
            for v in validated.lines
        ],
    )
