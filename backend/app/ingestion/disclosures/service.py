"""Disclosure service: registry I/O, parse persistence, comparison, diffs (R34 P0-1–P0-6).

Facts live on the Phase-1 ``financial_facts`` surface (extended with Phase-7
provenance columns in migration 017): recording a parsed cell provisions the
Phase-1 period + document rows via the existing upserts, then stores the fact
with its locator, extraction report, basis, and tags. Restatements never
delete: the new row supersedes the old one and the diff ledger records the
link, so ``as_of`` reads keep returning the pre-restatement value.

Deterministic throughout: no fetching (intake is explicit registration +
upload only), no invented numerals (missing stays UNKNOWN), no silent
EAS/IFRS pooling (mixed series raise).
"""

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.disclosures import parse as parse_mod
from app.ingestion.disclosures.comparison import (
    compute_ttm,
    margin_vs_prior_year,
    quantize4,
    ttm_margin,
    yoy_delta,
)
from app.ingestion.disclosures.constants import (
    AUDIT_STATES,
    DIFF_KINDS,
    DISCLOSURE_DATA_SOURCE_NAME,
    DISCLOSURE_METHODOLOGY_VERSION,
    MARGIN_INCOME_METRIC,
    MARGIN_REVENUE_METRIC,
    PARSE_ENGINES,
    PARSE_METHODS,
    QUARTER_PERIOD_TYPES,
)
from app.ingestion.disclosures.diffs import (
    FactVersion,
    build_diff_row,
    restatement_decision,
    select_as_of,
)
from app.ingestion.disclosures.facts import (
    BasisMixError,
    ensure_comparable_basis,
    fact_payload,
    reported_amount,
    validate_basis_for_fact,
    validate_eas_tags,
)
from app.ingestion.disclosures.intake import (
    check_upload_bytes,
    compute_content_hash,
    downloaded_now,
    filing_period_bounds,
    new_filing_id,
    registration_hash_for_url,
    validate_accounting_basis,
    validate_filing_type,
    validate_filing_url,
)
from app.models.disclosure import DisclosureFactDiff, DisclosureFiling
from app.models.financial import (
    FactStatus,
    FactType,
    FinancialDocument,
    FinancialFact,
    FinancialPeriod,
    ReportingPeriodType,
)
from app.models.market import Company, DataSource, DataSourceType
from app.repositories.company import CompanyRepository
from app.repositories.disclosure import (
    DisclosureFactDiffRepository,
    DisclosureFilingRepository,
)
from app.repositories.financial import (
    FinancialDocumentRepository,
    FinancialPeriodRepository,
)
from app.schemas.financial import FinancialDocumentCreate, FinancialPeriodCreate

_PERIOD_LABELS: dict[str, str] = {
    "ANNUAL": "FY",
    "SEMI_ANNUAL": "H1",
    "INTERIM": "9M",
}

#: Grouped fact versions keyed by (metric, period_id) for as-of reads.
_VersionGroup = dict[
    tuple[str, uuid.UUID], list[tuple[FinancialFact, DisclosureFiling | None]]
]


class DisclosureService:
    """Phase-7 disclosure intake, parse persistence, comparison, and diffs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.filings = DisclosureFilingRepository(session)
        self.diffs = DisclosureFactDiffRepository(session)
        self.companies = CompanyRepository(session)
        self.periods = FinancialPeriodRepository(session)
        self.documents = FinancialDocumentRepository(session)

    async def _require_company(self, company_id: uuid.UUID) -> Company:
        company = await self.companies.get_by_id(company_id)
        if company is None:
            raise LookupError(f"Company {company_id} not found")
        return company

    async def register_url(
        self,
        *,
        company_id: uuid.UUID,
        filing_url: str,
        bulletin_id: str | None,
        report_date: date,
        filing_type: str,
        accounting_basis: str = "EAS",
        content_hash: str | None = None,
    ) -> tuple[DisclosureFiling, bool]:
        """Explicit URL registration (no fetch, no crawl). Same hash twice → one row."""
        await self._require_company(company_id)
        validate_filing_type(filing_type)
        validate_accounting_basis(accounting_basis)
        filing_url = validate_filing_url(filing_url)
        key = content_hash or registration_hash_for_url(filing_url)
        existing = await self.filings.get_by_hash(key)
        if existing is not None:
            return existing, False
        filing = DisclosureFiling(
            id=new_filing_id(),
            company_id=company_id,
            filing_url=filing_url,
            bulletin_id=bulletin_id,
            report_date=report_date,
            filing_type=filing_type,
            accounting_basis=accounting_basis,
            content_hash=key,
            byte_size=None,
            storage_path=None,
            pdf_bytes=None,
            downloaded_at=downloaded_now(),
        )
        await self.filings.create(filing)
        await self.session.commit()
        return filing, True

    async def upload(
        self,
        *,
        company_id: uuid.UUID,
        filename: str,
        data: bytes,
        bulletin_id: str | None,
        report_date: date,
        filing_type: str,
        accounting_basis: str = "EAS",
    ) -> tuple[DisclosureFiling, bool]:
        """File upload registration. Same bytes twice → the single stored row."""
        await self._require_company(company_id)
        validate_filing_type(filing_type)
        validate_accounting_basis(accounting_basis)
        blob = check_upload_bytes(data, filename=filename)
        key = compute_content_hash(blob)
        existing = await self.filings.get_by_hash(key)
        if existing is not None:
            return existing, False
        filing = DisclosureFiling(
            id=new_filing_id(),
            company_id=company_id,
            filing_url=None,
            bulletin_id=bulletin_id,
            report_date=report_date,
            filing_type=filing_type,
            accounting_basis=accounting_basis,
            content_hash=key,
            byte_size=len(blob),
            storage_path=filename,
            pdf_bytes=blob,
            downloaded_at=downloaded_now(),
        )
        await self.filings.create(filing)
        await self.session.commit()
        return filing, True

    async def _ensure_source(self) -> DataSource:
        result = await self.session.execute(
            select(DataSource).where(DataSource.name == DISCLOSURE_DATA_SOURCE_NAME)
        )
        source = result.scalar_one_or_none()
        if source is None:
            source = DataSource(
                id=uuid.uuid4(),
                name=DISCLOSURE_DATA_SOURCE_NAME,
                source_type=DataSourceType.MANUAL,
                base_url="https://www.egx.com.eg",
            )
            self.session.add(source)
            await self.session.flush()
        return source

    async def _ensure_period_document(
        self, filing: DisclosureFiling
    ) -> tuple[FinancialPeriod, FinancialDocument]:
        """Provision the Phase-1 grouping rows for a filing (upserts, no invented facts)."""
        period_type_value, fiscal_year, quarter, start, end = filing_period_bounds(
            filing.report_date, filing.filing_type
        )
        period = await self.periods.upsert(
            FinancialPeriodCreate(
                company_id=filing.company_id,
                period_type=ReportingPeriodType(period_type_value),
                fiscal_year=fiscal_year,
                fiscal_quarter=quarter,
                start_date=start,
                end_date=end,
            )
        )
        source = await self._ensure_source()
        if filing.filing_url is not None and len(filing.filing_url) > 500:
            raise ValueError("filing_url exceeds the 500-char document URL cap")
        # Last-writer-wins on the Phase-1 document row (mirrors thesis/score
        # snapshot semantics); fact-level provenance + the supersede chain keep
        # the full restatement history regardless.
        document = await self.documents.upsert(
            FinancialDocumentCreate(
                period_id=period.id,
                source_id=source.id,
                document_type=filing.filing_type,
                document_url=filing.filing_url,
                filing_date=filing.report_date,
                publication_date=filing.report_date,
            )
        )
        return period, document

    async def _facts_for_label(
        self, company_id: uuid.UUID, metric: str
    ) -> Sequence[FinancialFact]:
        result = await self.session.execute(
            select(FinancialFact)
            .where(FinancialFact.company_id == company_id)
            .where(
                (FinancialFact.normalized_label == metric)
                | (FinancialFact.reported_label == metric)
            )
        )
        return result.scalars().all()

    async def record_fact(
        self,
        *,
        filing_id: uuid.UUID,
        metric: str,
        value: Decimal | None,
        statement_name: str,
        page: int | None = None,
        table_id: int | None = None,
        row: int | None = None,
        col: int | None = None,
        fact_type: str = "INCOME_STATEMENT",
        currency: str = "EGP",
        audit_state: str = "unaudited",
        eas_tags: list[str] | None = None,
        estimate: Decimal | None = None,
        extraction: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> tuple[FinancialFact, bool, DisclosureFactDiff | None]:
        """Store one parsed cell as a provenance fact; returns (fact, created, diff).

        Missing numerals persist as UNKNOWN rows (never zero). Republishing the
        same (metric, period) with a different value supersedes the old row and
        writes a restatement diff; an identical republish returns the existing
        row untouched.
        """
        filing = await self.filings.get_by_id(filing_id)
        if filing is None:
            raise LookupError(f"Disclosure filing {filing_id} not found")
        if not metric.strip():
            raise ValueError("metric is required")
        try:
            fact_type_enum = FactType(fact_type)
        except ValueError:
            raise ValueError(
                f"Unknown fact_type {fact_type!r}"
            ) from None
        if audit_state not in AUDIT_STATES:
            raise ValueError(f"Unknown audit_state {audit_state!r}; expected {AUDIT_STATES}")
        tags = validate_eas_tags(eas_tags)
        basis = validate_basis_for_fact(filing.accounting_basis)
        # Quantize at the record boundary: Numeric(20, 4) columns would round
        # on write anyway; doing it here keeps in-memory and DB-read rows
        # serializing identically.
        amount = quantize4(value) if value is not None else None
        estimate_amount = quantize4(estimate) if estimate is not None else None
        period, document = await self._ensure_period_document(filing)

        existing = [
            fact
            for fact in await self._facts_for_label(filing.company_id, metric.strip())
            if fact.period_id == period.id
        ]
        latest = max(existing, key=lambda fact: fact.created_at) if existing else None
        latest_value = reported_amount(latest) if latest is not None else None
        decision = restatement_decision(
            new_value=amount,
            latest_value=latest_value,
            latest_id=latest.id if latest is not None else None,
        )
        if decision.action == "duplicate" and latest is not None:
            await self.session.commit()
            return latest, False, None

        locator: dict[str, Any] = {"statement_name": statement_name}
        if page is not None:
            locator["page"] = page
        if table_id is not None:
            locator["table_id"] = table_id
        if row is not None:
            locator["row"] = row
        if col is not None:
            locator["col"] = col
        status = FactStatus.REPORTED if amount is not None else FactStatus.INSUFFICIENT_DATA
        fact = FinancialFact(
            id=uuid.uuid4(),
            period_id=period.id,
            document_id=document.id,
            company_id=filing.company_id,
            fact_type=fact_type_enum,
            reported_label=metric.strip(),
            normalized_label=metric.strip(),
            reported_value=amount,
            normalized_value=None,
            currency=currency,
            status=status,
            filing_id=filing.id,
            accounting_basis=basis,
            eas_tags=tags,
            locator=locator,
            extraction=dict(extraction or {}),
            audit_state=audit_state,
            methodology_version=DISCLOSURE_METHODOLOGY_VERSION,
            supersedes_id=decision.supersedes_id,
            is_restated=decision.action == "restate",
            unknown_reason=(
                f"missing numeral for {metric.strip()}" if amount is None else None
            ),
            reported_at=datetime(
                filing.report_date.year,
                filing.report_date.month,
                filing.report_date.day,
                tzinfo=UTC,
            ),
        )
        if created_at is not None:
            fact.created_at = created_at
        self.session.add(fact)
        await self.session.flush()

        period_label = self._period_label(period)
        diff: DisclosureFactDiff | None = None
        if decision.action == "restate" and latest is not None:
            diff = await self._write_diff(
                company_id=filing.company_id,
                metric=metric.strip(),
                prior_value=latest_value,
                current_value=amount,
                prior_period=period_label,
                current_period=period_label,
                kind="restatement",
                prior_fact_id=latest.id,
                current_fact_id=fact.id,
                estimate=estimate_amount,
            )
        else:
            prior = await self._prior_period_fact(filing.company_id, metric.strip(), period)
            if prior is not None:
                prior_fact, prior_label = prior
                diff = await self._write_diff(
                    company_id=filing.company_id,
                    metric=metric.strip(),
                    prior_value=reported_amount(prior_fact),
                    current_value=amount,
                    prior_period=prior_label,
                    current_period=period_label,
                    kind="period_diff",
                    prior_fact_id=prior_fact.id,
                    current_fact_id=fact.id,
                    estimate=estimate_amount,
                )
        await self.session.commit()
        return fact, True, diff

    async def _write_diff(
        self,
        *,
        company_id: uuid.UUID,
        metric: str,
        prior_value: Decimal | None,
        current_value: Decimal | None,
        prior_period: str,
        current_period: str,
        kind: str,
        prior_fact_id: uuid.UUID | None,
        current_fact_id: uuid.UUID | None,
        estimate: Decimal | None,
    ) -> DisclosureFactDiff:
        if kind not in DIFF_KINDS:
            raise ValueError(f"Unknown diff kind {kind!r}; expected {DIFF_KINDS}")
        row = build_diff_row(
            metric=metric,
            prior_value=prior_value,
            current_value=current_value,
            prior_period=prior_period,
            current_period=current_period,
            kind=kind,
            estimate=estimate,
        )
        diff = DisclosureFactDiff(
            id=uuid.uuid4(),
            company_id=company_id,
            methodology_version=DISCLOSURE_METHODOLOGY_VERSION,
            kind=kind,
            metric=metric,
            prior_fact_id=prior_fact_id,
            current_fact_id=current_fact_id,
            prior_value=prior_value,
            current_value=current_value,
            delta=Decimal(str(row["delta"])) if row["delta"] is not None else None,
            delta_pct=(
                Decimal(str(row["delta_pct"])) if row["delta_pct"] is not None else None
            ),
            prior_period=prior_period,
            current_period=current_period,
            estimate_value=estimate,
            beat_miss=row["beat_miss"],
        )
        return await self.diffs.create(diff)

    @staticmethod
    def _period_label(period: FinancialPeriod) -> str:
        if period.period_type.value in ("Q1", "Q2", "Q3", "Q4"):
            return f"{period.period_type.value}-{period.fiscal_year}"
        short = _PERIOD_LABELS.get(period.period_type.value, period.period_type.value)
        return f"{short}-{period.fiscal_year}"

    async def _prior_period_fact(
        self, company_id: uuid.UUID, metric: str, period: FinancialPeriod
    ) -> tuple[FinancialFact, str] | None:
        """Latest visible fact for the metric in an earlier period, if any."""
        result = await self.session.execute(
            select(FinancialFact, FinancialPeriod)
            .join(FinancialPeriod, FinancialPeriod.id == FinancialFact.period_id)
            .where(FinancialFact.company_id == company_id)
            .where(
                (FinancialFact.normalized_label == metric)
                | (FinancialFact.reported_label == metric)
            )
            .where(FinancialPeriod.end_date < period.end_date)
            .order_by(FinancialPeriod.end_date.desc())
        )
        rows = result.all()
        if not rows:
            return None
        fact, prior_period = rows[0]
        return fact, self._period_label(prior_period)

    async def parse_filing(
        self,
        filing_id: uuid.UUID,
        *,
        engine: str = "pdfplumber",
        method: str = "lattice",
        statement_pages: Mapping[str, Sequence[int]] | None = None,
        metrics: Sequence[str] | None = None,
        fact_type: str = "INCOME_STATEMENT",
        currency: str = "EGP",
        audit_state: str = "unaudited",
        eas_tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run the rule-based parse over stored upload bytes and persist cells."""
        if engine not in PARSE_ENGINES:
            raise ValueError(f"Unknown parse engine {engine!r}; expected {PARSE_ENGINES}")
        if method not in PARSE_METHODS:
            raise ValueError(f"Unknown parse method {method!r}; expected {PARSE_METHODS}")
        filing = await self.filings.get_by_id(filing_id)
        if filing is None:
            raise LookupError(f"Disclosure filing {filing_id} not found")
        if filing.pdf_bytes is None:
            raise ValueError(
                "URL-only registration has no stored bytes to parse; upload the PDF first"
            )
        outcome = parse_mod.parse_filing_bytes(
            bytes(filing.pdf_bytes),
            engine=engine,
            method=method,
            statement_pages=statement_pages,
            metrics=metrics,
        )
        if outcome.status != "OK":
            return {
                "status": outcome.status,
                "reason": outcome.reason,
                "engine": outcome.engine,
                "engine_version": outcome.engine_version,
                "method": outcome.method,
                "confidence": outcome.confidence,
                "facts": [],
            }
        stored: list[dict[str, Any]] = []
        for cell in outcome.cells:
            extraction: dict[str, Any] = {
                "engine": outcome.engine,
                "engine_version": outcome.engine_version,
                "method": outcome.method,
                "confidence": outcome.confidence,
            }
            fact, created, _ = await self.record_fact(
                filing_id=filing.id,
                metric=cell.metric,
                value=cell.value,
                statement_name=cell.statement_name,
                page=cell.page,
                table_id=cell.table_id,
                row=cell.row,
                col=cell.col,
                fact_type=fact_type,
                currency=currency,
                audit_state=audit_state,
                eas_tags=eas_tags,
                extraction=extraction,
            )
            stored.append({"fact_id": str(fact.id), "created": created})
        # record_fact commits per cell; refresh the filing handle for the payload.
        await self.session.refresh(filing)
        return {
            "status": "OK",
            "reason": None,
            "engine": outcome.engine,
            "engine_version": outcome.engine_version,
            "method": outcome.method,
            "confidence": outcome.confidence,
            "facts": stored,
        }

    async def list_fact_payloads(
        self,
        company_id: uuid.UUID,
        *,
        metric: str | None = None,
        as_of: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Provenance payloads for the visible facts (as_of → pre-restatement)."""
        company = await self._require_company(company_id)
        query = (
            select(FinancialFact, FinancialPeriod, DisclosureFiling)
            .join(FinancialPeriod, FinancialPeriod.id == FinancialFact.period_id)
            .outerjoin(DisclosureFiling, DisclosureFiling.id == FinancialFact.filing_id)
            .where(FinancialFact.company_id == company_id)
            .where(FinancialFact.filing_id.is_not(None))
        )
        if metric is not None:
            query = query.where(
                (FinancialFact.normalized_label == metric)
                | (FinancialFact.reported_label == metric)
            )
        query = query.order_by(FinancialFact.created_at.asc())
        rows = (await self.session.execute(query)).all()

        groups: _VersionGroup = {}
        period_of: dict[tuple[str, uuid.UUID], FinancialPeriod] = {}
        for fact, period, filing in rows:
            key = (fact.normalized_label or fact.reported_label, fact.period_id)
            groups.setdefault(key, []).append((fact, filing))
            period_of[key] = period

        payloads: list[dict[str, Any]] = []
        for key, versions in groups.items():
            if as_of is not None:
                candidate = select_as_of(
                    [
                        FactVersion(
                            id=fact.id,
                            value=reported_amount(fact),
                            created_at=fact.created_at,
                            supersedes_id=fact.supersedes_id,
                        )
                        for fact, _ in versions
                    ],
                    as_of=as_of,
                )
                if candidate is None:
                    continue
                chosen = next(fact for fact, _ in versions if fact.id == candidate.id)
                chosen_filing = next(
                    filing for fact, filing in versions if fact.id == candidate.id
                )
            else:
                superseded = {
                    fact.supersedes_id for fact, _ in versions
                    if fact.supersedes_id is not None
                }
                visible = [(f, fl) for f, fl in versions if f.id not in superseded]
                if not visible:
                    continue
                chosen, chosen_filing = visible[-1]
            period = period_of[key]
            payloads.append(
                fact_payload(
                    chosen,
                    company_ticker=company.ticker,
                    filing=chosen_filing,
                    period_end=period.end_date,
                    period_label=self._period_label(period),
                )
            )
        return payloads

    async def _quarterly_series(
        self, company_id: uuid.UUID, metric: str
    ) -> list[tuple[FinancialPeriod, FinancialFact]]:
        """Oldest-first visible quarterly facts for one metric (superseded dropped)."""
        result = await self.session.execute(
            select(FinancialFact, FinancialPeriod)
            .join(FinancialPeriod, FinancialPeriod.id == FinancialFact.period_id)
            .where(FinancialFact.company_id == company_id)
            .where(
                (FinancialFact.normalized_label == metric)
                | (FinancialFact.reported_label == metric)
            )
            .order_by(FinancialPeriod.fiscal_year.asc(), FinancialPeriod.fiscal_quarter.asc())
        )
        superseded: set[uuid.UUID] = set()
        pairs = [(fact, period) for fact, period in result.all()]
        for fact, _ in pairs:
            if fact.supersedes_id is not None:
                superseded.add(fact.supersedes_id)
        return [
            (period, fact)
            for fact, period in pairs
            if period.period_type.value in QUARTER_PERIOD_TYPES
            and fact.id not in superseded
        ]

    async def compare(
        self, company_id: uuid.UUID, metric: str
    ) -> dict[str, Any]:
        """TTM + YoY payloads for one metric; mixed EAS/IFRS series raise."""
        await self._require_company(company_id)
        series = await self._quarterly_series(company_id, metric)
        ensure_comparable_basis({fact.accounting_basis for _, fact in series})
        values = [reported_amount(fact) for _, fact in series]
        ttm = compute_ttm(values[-4:] if len(values) >= 4 else values, metric=metric)
        if series:
            latest_period, latest_fact = series[-1]
            current = reported_amount(latest_fact)
            current_label = self._period_label(latest_period)
            prior_value: Decimal | None = None
            for period, fact in series[:-1]:
                if (
                    period.fiscal_year == latest_period.fiscal_year - 1
                    and period.fiscal_quarter == latest_period.fiscal_quarter
                ):
                    prior_value = reported_amount(fact)
            yoy = yoy_delta(
                current=current,
                prior=prior_value,
                metric=metric,
                current_label=current_label,
                prior_label=(
                    f"Q{latest_period.fiscal_quarter}-{latest_period.fiscal_year - 1}"
                    if latest_period.fiscal_quarter
                    else f"FY-{latest_period.fiscal_year - 1}"
                ),
            )
        else:
            yoy = yoy_delta(
                current=None, prior=None, metric=metric,
                current_label="none", prior_label="none",
            )
        return {
            "metric": metric,
            "ttm": ttm,
            "yoy": yoy,
            "quarters_used": [self._period_label(period) for period, _ in series[-4:]],
            "accounting_bases": sorted(
                {fact.accounting_basis for _, fact in series if fact.accounting_basis}
            ),
            "methodology_version": DISCLOSURE_METHODOLOGY_VERSION,
        }

    async def margin_block(self, company_id: uuid.UUID) -> dict[str, Any]:
        """TTM-margin-vs-prior-year from revenue + net_income quarterly series."""
        await self._require_company(company_id)
        revenue = await self._quarterly_series(company_id, MARGIN_REVENUE_METRIC)
        income = await self._quarterly_series(company_id, MARGIN_INCOME_METRIC)
        ensure_comparable_basis(
            {fact.accounting_basis for _, fact in [*revenue, *income]}
        )

        def _window_total(
            pairs: list[tuple[FinancialPeriod, FinancialFact]], window: slice
        ) -> Decimal | None:
            """Sum one 4-quarter window; short or gappy windows stay None."""
            amounts = [reported_amount(fact) for _, fact in pairs[window]]
            clean: list[Decimal] = []
            for amount in amounts:
                if amount is None:
                    return None
                clean.append(amount)
            if len(clean) != 4:
                return None
            total = Decimal("0")
            for amount in clean:
                total += amount
            return total

        current = ttm_margin(
            ttm_net_income=_window_total(income, slice(-4, None)),
            ttm_revenue=_window_total(revenue, slice(-4, None)),
        )
        prior = ttm_margin(
            ttm_net_income=_window_total(income, slice(-8, -4)),
            ttm_revenue=_window_total(revenue, slice(-8, -4)),
        )
        return margin_vs_prior_year(current_margin=current, prior_margin=prior)

    async def list_diffs(self, company_id: uuid.UUID) -> list[dict[str, Any]]:
        """Serialized diff-ledger rows, newest first (str/isoformat)."""
        await self._require_company(company_id)
        diffs = await self.diffs.list_by_company(company_id)
        return [
            {
                "id": str(diff.id),
                "metric": diff.metric,
                "kind": diff.kind,
                "prior_value": str(diff.prior_value)
                if diff.prior_value is not None
                else None,
                "current_value": str(diff.current_value)
                if diff.current_value is not None
                else None,
                "delta": str(diff.delta) if diff.delta is not None else None,
                "delta_pct": str(diff.delta_pct) if diff.delta_pct is not None else None,
                "prior_period": diff.prior_period,
                "current_period": diff.current_period,
                "estimate": str(diff.estimate_value)
                if diff.estimate_value is not None
                else None,
                "beat_miss": diff.beat_miss,
                "methodology_version": diff.methodology_version,
                "created_at": diff.created_at.isoformat(),
            }
            for diff in diffs
        ]

    async def list_filings(self, company_id: uuid.UUID) -> list[dict[str, Any]]:
        """Serialized intake registry rows for one company (str/isoformat)."""
        await self._require_company(company_id)
        return [
            self.filing_payload(filing)
            for filing in await self.filings.list_by_company(company_id)
        ]

    @staticmethod
    def filing_payload(filing: DisclosureFiling) -> dict[str, Any]:
        """One registry row serialized with str/isoformat (no bytes on the wire)."""
        return {
            "id": str(filing.id),
            "company_id": str(filing.company_id),
            "filing_url": filing.filing_url,
            "bulletin_id": filing.bulletin_id,
            "report_date": filing.report_date.isoformat(),
            "filing_type": filing.filing_type,
            "accounting_basis": filing.accounting_basis,
            "content_hash": filing.content_hash,
            "byte_size": filing.byte_size,
            "storage_path": filing.storage_path,
            "has_bytes": filing.pdf_bytes is not None,
            "downloaded_at": filing.downloaded_at.isoformat(),
            "created_at": filing.created_at.isoformat(),
        }


__all__ = ["BasisMixError", "DisclosureService"]
