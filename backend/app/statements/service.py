"""StatementService: assemble an approved-lines bundle per company.

Renders the FULL ontology per section (lines with no approved data carry
value None / INSUFFICIENT_DATA — never zero, never omitted) ordered
newest period first.
"""

import uuid
from datetime import date
from decimal import Decimal  # noqa: TC003 — kept local for clarity
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import FinancialDocument, FinancialPeriod, ReportingPeriodType
from app.repositories.statements import StatementLineRepository
from app.statements.ontology import STATEMENT_LINES, LineSection
from app.statements.ratios import RATIO_VERSION, RatioService

if TYPE_CHECKING:
    from app.models.statements import FinancialStatementLine

_PERIOD_TYPE_ORDER = {
    ReportingPeriodType.ANNUAL: 0,
    ReportingPeriodType.INTERIM: 1,
    ReportingPeriodType.SEMI_ANNUAL: 2,
    ReportingPeriodType.Q1: 3,
    ReportingPeriodType.Q2: 4,
    ReportingPeriodType.Q3: 5,
    ReportingPeriodType.Q4: 6,
}


class StatementLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ontology_code: str
    label_en: str
    label_ar: str
    value: str | None
    status: str
    currency: str
    source_label_reported: str | None
    source_page: str | None
    published_date: date | None
    document_url: str | None


class PeriodStatements(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_id: uuid.UUID
    fiscal_year: int
    period_type: str
    published_date: date | None
    income: list[StatementLineRead]
    balance: list[StatementLineRead]
    cash_flow: list[StatementLineRead]


class StatementBundle(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    periods: list[PeriodStatements]


class RatioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    value: str | None
    status: str
    reason: str | None


class RatioBundle(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fiscal_year: int | None
    ratios_version: str
    ratios: list[RatioRead]


class StatementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def company_statements(self, company_id: uuid.UUID) -> StatementBundle:
        repo = StatementLineRepository(self.session)
        lines = await repo.latest_approved(company_id)
        line_map: dict[uuid.UUID, list[FinancialStatementLine]] = {}
        for row in lines:
            line_map.setdefault(row.period_id, []).append(row)

        period_rows = (await self.session.execute(
            select(FinancialPeriod).where(FinancialPeriod.company_id == company_id)
        )).scalars().all()
        period_by_id = {p.id: p for p in period_rows if p.id in line_map}

        doc_ids = {
            row.source_document_id
            for rows in line_map.values()
            for row in rows
            if row.source_document_id
        }
        documents = {}
        if doc_ids:
            doc_rows = (await self.session.execute(
                select(FinancialDocument).where(FinancialDocument.id.in_(doc_ids))
            )).scalars().all()
            documents = {d.id: d for d in doc_rows}

        periods: list[PeriodStatements] = []
        for period_id, period_lines in line_map.items():
            fperiod = period_by_id[period_id]
            published = max(
                (row.published_date for row in period_lines if row.published_date),
                default=None,
            )
            income: list[StatementLineRead] = []
            balance: list[StatementLineRead] = []
            cash_flow: list[StatementLineRead] = []
            by_code_latest: dict[str, FinancialStatementLine] = {}
            for row in period_lines:
                prev = by_code_latest.get(row.ontology_code)
                prev_date = prev.published_date if prev else None
                if prev is None or (row.published_date or date.min) > (prev_date or date.min):
                    by_code_latest[row.ontology_code] = row
            for line in STATEMENT_LINES.values():
                table = (
                    income
                    if line.section == LineSection.INCOME
                    else balance
                    if line.section == LineSection.BALANCE
                    else cash_flow
                )
                line_row = by_code_latest.get(line.code)
                if line_row is None or line_row.value is None:
                    status = "INSUFFICIENT_DATA"
                    value: str | None = None
                else:
                    status = "AVAILABLE"
                    value = str(line_row.value)
                table.append(
                    StatementLineRead(
                        ontology_code=line.code,
                        label_en=line.label_en,
                        label_ar=line.label_ar,
                        value=value,
                        status=status,
                        currency=line_row.currency if line_row is not None else "EGP",
                        source_label_reported=line_row.source_label_reported if line_row else None,
                        source_page=line_row.source_page if line_row else None,
                        published_date=line_row.published_date if line_row else None,
                        document_url=(
                            documents[line_row.source_document_id].document_url
                            if (
                                line_row is not None
                                and line_row.source_document_id is not None
                                and line_row.source_document_id in documents
                            )
                            else None
                        ),
                    )
                )
            periods.append(
                PeriodStatements(
                    period_id=period_id,
                    fiscal_year=fperiod.fiscal_year,
                    period_type=(
                        fperiod.period_type.value
                        if hasattr(fperiod.period_type, "value")
                        else str(fperiod.period_type)
                    ),
                    published_date=published,
                    income=income,
                    balance=balance,
                    cash_flow=cash_flow,
                )
            )
        periods.sort(
            key=lambda p: (
                -p.fiscal_year,
                _PERIOD_TYPE_ORDER.get(ReportingPeriodType(p.period_type), 99),
                p.published_date or date.min,
            )
        )
        return StatementBundle(periods=periods)

    async def company_ratios(
        self, company_id: uuid.UUID, shared: RatioService | None = None
    ) -> RatioBundle:
        """Latest two approved periods feed the v1 ratio set."""
        repo = StatementLineRepository(self.session)
        bundle = await self.company_statements(company_id)
        if not bundle.periods:
            return RatioBundle(
                fiscal_year=None, ratios_version=RATIO_VERSION, ratios=[]
            )
        svc = shared or RatioService()
        by_code: dict[str, Decimal] = {}
        latest_rows = await repo.latest_approved(company_id)
        for row in latest_rows:
            if row.period_id == bundle.periods[0].period_id and row.value is not None:
                by_code[row.ontology_code] = row.value
        prior_by_code: dict[str, Decimal] | None = None
        if len(bundle.periods) > 1:
            prior_by_code = {}
            for row in latest_rows:
                if row.period_id == bundle.periods[1].period_id and row.value is not None:
                    prior_by_code[row.ontology_code] = row.value
        computed = svc.compute(by_code, prior_by_code, None)
        return RatioBundle(
            fiscal_year=bundle.periods[0].fiscal_year,
            ratios_version=RATIO_VERSION,
            ratios=[
                RatioRead(code=r.code, value=r.value, status=r.status, reason=r.reason)
                for r in computed
            ],
        )

