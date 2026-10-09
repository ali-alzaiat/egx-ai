"""Wiring tests: normalization + validation inside financial ingestion.

Driven through FinancialDataIngestionService with the SYNTHETIC fake provider
(tests/dev only — the module stays unwired from production routes).
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.fake_financial_provider import FakeFinancialDataProvider
from app.ingestion.financial_provider import (
    FinancialDocumentData,
    FinancialFactData,
)
from app.ingestion.financial_service import FinancialDataIngestionService
from app.models.financial import (
    FactStatus,
    FactType,
    FinancialDocument,
    FinancialFact,
    FinancialPeriod,
)
from app.models.market import Company, DataSourceType

SOURCE_NAME = "Test Financial Ingestion"


async def _ingest(
    db_session: AsyncSession,
    ticker: str,
    provider: FakeFinancialDataProvider,
) -> dict[str, int]:
    """Run one ingestion through the service under test."""
    service = FinancialDataIngestionService(
        db_session, provider, SOURCE_NAME, DataSourceType.SYNTHETIC
    )
    return await service.ingest_financial_data(ticker)


class _UrlProvider(FakeFinancialDataProvider):
    """Synthetic documents that carry a filing URL."""

    async def get_financial_documents(
        self, ticker: str, fiscal_year: int | None = None
    ) -> list[FinancialDocumentData]:
        documents = await super().get_financial_documents(ticker, fiscal_year)
        return [
            d._replace(document_url="https://example.com/annual.pdf") for d in documents
        ]


class _TwoDocTypeProvider(FakeFinancialDataProvider):
    """One period carries an annual and a quarterly document."""

    async def get_financial_documents(
        self, ticker: str, fiscal_year: int | None = None
    ) -> list[FinancialDocumentData]:
        documents = await super().get_financial_documents(ticker, fiscal_year)
        return documents + [
            d._replace(document_type="QUARTERLY_REPORT") for d in documents
        ]

    async def get_financial_facts(
        self, ticker: str, fiscal_year: int | None = None
    ) -> list[FinancialFactData]:
        facts = await super().get_financial_facts(ticker, fiscal_year)
        return [
            f._replace(
                document_type=(
                    "ANNUAL_REPORT"
                    if f.fact_type == "INCOME_STATEMENT"
                    else "QUARTERLY_REPORT"
                )
            )
            for f in facts
        ]


class _InvalidCurrencyProvider(FakeFinancialDataProvider):
    """Exactly one fact carries a currency code that fails validation."""

    async def get_financial_facts(
        self, ticker: str, fiscal_year: int | None = None
    ) -> list[FinancialFactData]:
        facts = await super().get_financial_facts(ticker, fiscal_year)
        return [facts[0]._replace(currency="EG"), *facts[1:]]


class _EdgeCaseProvider(FakeFinancialDataProvider):
    """Zero, negative, missing and unmatched-label facts in one period."""

    async def get_financial_facts(
        self, ticker: str, fiscal_year: int | None = None
    ) -> list[FinancialFactData]:
        facts = await super().get_financial_facts(ticker, fiscal_year)
        return [
            facts[0]._replace(reported_value=Decimal("0")),
            facts[5]._replace(reported_value=Decimal("-100")),
            facts[6]._replace(reported_value=None),
            facts[1]._replace(reported_label="Mystery Metric"),
        ]


async def test_ingest_normalizes_known_labels(
    db_session: AsyncSession, test_company: Company
) -> None:
    counts = await _ingest(db_session, test_company.ticker, FakeFinancialDataProvider())
    assert counts["facts"] > 0

    result = await db_session.execute(
        select(FinancialFact).where(
            FinancialFact.company_id == test_company.id,
            FinancialFact.reported_label == "Total Revenue",
        )
    )
    revenue_facts = result.scalars().all()
    assert revenue_facts
    for fact in revenue_facts:
        assert fact.normalized_label == "revenue"
        assert fact.status == FactStatus.NORMALIZED

    result = await db_session.execute(
        select(FinancialFact).where(
            FinancialFact.company_id == test_company.id,
            FinancialFact.status == FactStatus.NORMALIZED,
        )
    )
    assert len(result.scalars().all()) == counts["normalized"]


async def test_ingest_preserves_document_url(
    db_session: AsyncSession, test_company: Company
) -> None:
    counts = await _ingest(db_session, test_company.ticker, _UrlProvider())
    assert counts["documents"] > 0

    result = await db_session.execute(
        select(FinancialDocument)
        .join(FinancialPeriod, FinancialDocument.period_id == FinancialPeriod.id)
        .where(FinancialPeriod.company_id == test_company.id)
    )
    documents = result.scalars().all()
    assert documents
    for document in documents:
        assert document.document_url == "https://example.com/annual.pdf"


async def test_ingest_attaches_facts_to_matching_document_type(
    db_session: AsyncSession, test_company: Company
) -> None:
    # Two documents share the period: must not raise MultipleResultsFound.
    await _ingest(db_session, test_company.ticker, _TwoDocTypeProvider())

    result = await db_session.execute(
        select(FinancialDocument)
        .join(FinancialPeriod, FinancialDocument.period_id == FinancialPeriod.id)
        .where(FinancialPeriod.company_id == test_company.id)
    )
    document_types = {d.document_type for d in result.scalars().all()}
    assert document_types == {"ANNUAL_REPORT", "QUARTERLY_REPORT"}

    result = await db_session.execute(
        select(FinancialFact, FinancialDocument)
        .join(FinancialDocument, FinancialFact.document_id == FinancialDocument.id)
        .join(FinancialPeriod, FinancialFact.period_id == FinancialPeriod.id)
        .where(FinancialPeriod.company_id == test_company.id)
    )
    rows = result.all()
    assert rows
    for fact, document in rows:
        expected = (
            "ANNUAL_REPORT"
            if fact.fact_type == FactType.INCOME_STATEMENT
            else "QUARTERLY_REPORT"
        )
        assert document.document_type == expected


async def test_ingest_invalid_fact_keeps_reported_value(
    db_session: AsyncSession, test_company: Company
) -> None:
    provider = _InvalidCurrencyProvider()
    expected_facts = await provider.get_financial_facts(test_company.ticker)

    counts = await _ingest(db_session, test_company.ticker, provider)
    assert counts["invalid"] == 1

    result = await db_session.execute(
        select(FinancialFact).where(
            FinancialFact.company_id == test_company.id,
            FinancialFact.currency == "EG",
        )
    )
    fact = result.scalar_one()
    assert fact.status == FactStatus.INSUFFICIENT_DATA
    assert fact.normalized_value is None
    assert fact.reported_value == expected_facts[0].reported_value
    assert fact.normalized_label == "revenue"


async def test_ingest_counts_match_persisted_rows(
    db_session: AsyncSession, test_company: Company
) -> None:
    counts = await _ingest(db_session, test_company.ticker, _InvalidCurrencyProvider())

    result = await db_session.execute(
        select(FinancialFact).where(FinancialFact.company_id == test_company.id)
    )
    facts = result.scalars().all()
    assert counts["facts"] == len(facts) > 0
    assert counts["normalized"] == sum(
        1 for f in facts if f.status == FactStatus.NORMALIZED
    )
    assert counts["invalid"] == sum(
        1 for f in facts if f.status == FactStatus.INSUFFICIENT_DATA
    )


async def test_ingest_edge_case_values(
    db_session: AsyncSession, test_company: Company
) -> None:
    counts = await _ingest(db_session, test_company.ticker, _EdgeCaseProvider())
    assert counts["facts"] == 4

    result = await db_session.execute(
        select(FinancialFact).where(FinancialFact.company_id == test_company.id)
    )
    facts = {f.reported_label: f for f in result.scalars().all()}
    assert len(facts) == 4

    zero = facts["Total Revenue"]
    assert zero.reported_value == Decimal("0")
    assert zero.normalized_value == Decimal("0")
    assert zero.status == FactStatus.NORMALIZED

    negative = facts["Net Income"]
    assert negative.reported_value == Decimal("-100")
    assert negative.normalized_value == Decimal("-100")
    assert negative.status == FactStatus.NORMALIZED

    missing = facts["Basic EPS"]
    assert missing.reported_value is None
    assert missing.normalized_value is None
    assert missing.status == FactStatus.NORMALIZED

    unmatched = facts["Mystery Metric"]
    assert unmatched.status == FactStatus.REPORTED
    assert unmatched.normalized_label == "Mystery Metric"
    assert unmatched.normalized_at is None
