import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.financial_provider import FinancialDataProvider
from app.models.financial import DocumentStatus, FactStatus, FactType, ReportingPeriodType
from app.models.market import DataSourceType
from app.repositories.company import CompanyRepository
from app.repositories.data_source import DataSourceRepository
from app.repositories.financial import (
    FinancialDocumentRepository,
    FinancialFactRepository,
    FinancialPeriodRepository,
)
from app.schemas.financial import (
    FinancialDocumentCreate,
    FinancialFactCreate,
    FinancialPeriodCreate,
)

logger = logging.getLogger(__name__)


class FinancialDataIngestionService:
    """Orchestrates financial data ingestion from a provider into the database.

    Responsibilities:
    1. Receive provider data.
    2. Validate it.
    3. Resolve companies (must exist).
    4. Normalize fields.
    5. Persist data.
    6. Record source/provenance.
    7. Report failures.
    """

    def __init__(
        self,
        session: AsyncSession,
        provider: FinancialDataProvider,
        source_name: str,
        source_type: DataSourceType,
    ) -> None:
        self.session = session
        self.provider = provider
        self.company_repo = CompanyRepository(session)
        self.period_repo = FinancialPeriodRepository(session)
        self.document_repo = FinancialDocumentRepository(session)
        self.fact_repo = FinancialFactRepository(session)
        self.source_repo = DataSourceRepository(session)
        self.source_name = source_name
        self.source_type = source_type

    async def ingest_financial_data(
        self,
        ticker: str,
        fiscal_year: int | None = None,
    ) -> dict[str, int]:
        """Ingest all financial data (periods, documents, facts) for a company.

        Returns counts of ingested records.
        """
        company = await self.company_repo.get_by_ticker(ticker)
        if not company:
            raise ValueError(f"Company with ticker '{ticker}' not found")

        data_source = await self.source_repo.get_or_create(
            name=self.source_name,
            source_type=self.source_type,
        )

        counts = {"periods": 0, "documents": 0, "facts": 0}

        # Ingest periods
        periods = await self.provider.get_financial_periods(ticker)
        for p in periods:
            await self.period_repo.upsert(
                FinancialPeriodCreate(
                    company_id=company.id,
                    period_type=ReportingPeriodType(p.period_type),
                    fiscal_year=p.fiscal_year,
                    fiscal_quarter=p.fiscal_quarter,
                    start_date=p.start_date,
                    end_date=p.end_date,
                )
            )
            counts["periods"] += 1

        await self.session.flush()
        logger.info("Ingested %d periods for %s", counts["periods"], ticker)

        # Ingest documents
        documents = await self.provider.get_financial_documents(ticker, fiscal_year)
        for d in documents:
            # Find the matching period
            period = await self._find_period(
                company.id, d.period_type, d.fiscal_year
            )
            if not period:
                logger.warning(
                    "Period not found for %s %s %d, skipping document",
                    ticker, d.period_type, d.fiscal_year
                )
                continue

            await self.document_repo.upsert(
                FinancialDocumentCreate(
                    period_id=period.id,
                    source_id=data_source.id,
                    document_status=DocumentStatus(d.document_status),
                    document_type=d.document_type,
                    document_url=None,
                    filing_date=d.filing_date,
                    publication_date=d.publication_date,
                    fiscal_year_end=d.fiscal_year_end,
                    notes=d.notes,
                )
            )
            counts["documents"] += 1

        await self.session.flush()
        logger.info("Ingested %d documents for %s", counts["documents"], ticker)

        # Ingest facts
        facts = await self.provider.get_financial_facts(ticker, fiscal_year)
        fact_records = []
        for f in facts:
            # Find the matching period and document
            period = await self._find_period(
                company.id, f.period_type, f.fiscal_year
            )
            if not period:
                logger.warning(
                    "Period not found for %s %s %d, skipping fact",
                    ticker, f.period_type, f.fiscal_year
                )
                continue

            document = await self._find_document(
                period.id, data_source.id, f.reported_label
            )
            if not document:
                logger.warning(
                    "Document not found for %s period %s, skipping fact",
                    ticker, period.id
                )
                continue

            fact_records.append(
                FinancialFactCreate(
                    period_id=period.id,
                    document_id=document.id,
                    company_id=company.id,
                    fact_type=FactType(f.fact_type),
                    reported_label=f.reported_label,
                    normalized_label=None,
                    reported_value=f.reported_value,
                    normalized_value=None,
                    currency=f.currency,
                    unit=f.unit,
                    scale=f.scale,
                    status=FactStatus.REPORTED,
                    source_page=f.source_page,
                    source_line=f.source_line,
                    reported_at=(
                        datetime.combine(f.reported_at, datetime.min.time())
                        if f.reported_at else None
                    ),
                    normalized_at=None,
                )
            )

        if fact_records:
            counts["facts"] = await self.fact_repo.bulk_create(fact_records)

        await self.session.commit()
        logger.info("Ingested %d facts for %s", counts["facts"], ticker)

        return counts

    async def _find_period(
        self,
        company_id,
        period_type: str,
        fiscal_year: int,
    ):
        """Find an existing period for the company."""
        from sqlalchemy import select

        from app.models.financial import FinancialPeriod, ReportingPeriodType

        query = select(FinancialPeriod).where(
            FinancialPeriod.company_id == company_id,
            FinancialPeriod.period_type == ReportingPeriodType(period_type),
            FinancialPeriod.fiscal_year == fiscal_year,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _find_document(
        self,
        period_id,
        source_id,
        reported_label: str,
    ):
        """Find an existing document for the period."""
        from sqlalchemy import select

        from app.models.financial import FinancialDocument

        query = select(FinancialDocument).where(
            FinancialDocument.period_id == period_id,
            FinancialDocument.source_id == source_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
