import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.market import Company, DataSource


class ReportingPeriodType(enum.StrEnum):
    ANNUAL = "ANNUAL"
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"
    SEMI_ANNUAL = "SEMI_ANNUAL"
    INTERIM = "INTERIM"


class FactType(enum.StrEnum):
    INCOME_STATEMENT = "INCOME_STATEMENT"
    BALANCE_SHEET = "BALANCE_SHEET"
    CASH_FLOW = "CASH_FLOW"
    SHAREHOLDERS_EQUITY = "SHAREHOLDERS_EQUITY"
    NOTES = "NOTES"


class DocumentStatus(enum.StrEnum):
    ORIGINAL = "ORIGINAL"
    RESTATED = "RESTATED"
    AMENDED = "AMENDED"
    ADJUSTED = "ADJUSTED"


class FactStatus(enum.StrEnum):
    REPORTED = "REPORTED"
    NORMALIZED = "NORMALIZED"
    CALCULATED = "CALCULATED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class FinancialPeriod(Base):
    """Represents a reporting period for a company."""

    __tablename__ = "financial_periods"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    period_type: Mapped[ReportingPeriodType] = mapped_column(
        Enum(ReportingPeriodType, name="reporting_period_type", create_constraint=True),
        nullable=False,
    )
    fiscal_year: Mapped[int] = mapped_column(BigInteger, nullable=False)
    fiscal_quarter: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    documents: Mapped[list["FinancialDocument"]] = relationship(
        "FinancialDocument", back_populates="period", lazy="selectin"
    )
    facts: Mapped[list["FinancialFact"]] = relationship(
        "FinancialFact", back_populates="period", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("company_id", "fiscal_year", "period_type", name="uq_financial_period"),
        Index("ix_financial_periods_company_id", "company_id"),
        Index("ix_financial_periods_fiscal_year", "fiscal_year"),
        Index("ix_financial_periods_period_type", "period_type"),
    )


class FinancialDocument(Base):
    """Source document containing financial data (annual report, quarterly report, etc.)."""

    __tablename__ = "financial_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_periods.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="RESTRICT"), nullable=False
    )
    document_status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", create_constraint=True),
        nullable=False,
        default=DocumentStatus.ORIGINAL,
    )
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    document_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    filing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    fiscal_year_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    # zborsa-upgrade fetch metadata (migration 019): where the bytes came from,
    # when they were fetched, and the content hash that de-duplicates them.
    source_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    period: Mapped["FinancialPeriod"] = relationship("FinancialPeriod", back_populates="documents")
    source: Mapped["DataSource"] = relationship("DataSource")

    __table_args__ = (
        UniqueConstraint(
            "period_id", "source_id", "document_type",
            name="uq_financial_document",
        ),
        Index("ix_financial_documents_period_id", "period_id"),
        Index("ix_financial_documents_source_id", "source_id"),
        Index("ix_financial_documents_document_status", "document_status"),
        Index("ix_financial_documents_content_hash", "content_hash"),
        Index("ix_financial_documents_publication_date", "publication_date"),
    )


class FinancialFact(Base):
    """Individual financial data point from a source document.

    Each fact has full provenance: company, period, document, source,
    reported label/value, and dates.
    Supports restatements by allowing multiple facts per label
    with different document statuses.
    """

    __tablename__ = "financial_facts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_periods.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_documents.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    fact_type: Mapped[FactType] = mapped_column(
        Enum(FactType, name="fact_type", create_constraint=True),
        nullable=False,
    )
    reported_label: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reported_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    normalized_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EGP")
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    scale: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[FactStatus] = mapped_column(
        Enum(FactStatus, name="fact_status", create_constraint=True),
        nullable=False,
        default=FactStatus.REPORTED,
    )
    source_page: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_line: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    normalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Phase-7 document-intelligence provenance (R34 P0-3/P0-4, migration 017).
    # Facts parsed from disclosure PDFs carry their filing link, cell locator,
    # extraction report, accounting basis + EAS gotcha tags, audit state, and
    # restatement chain here; Phase-1 writers leave every column null.
    filing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("disclosure_filings.id", ondelete="SET NULL"),
        nullable=True,
    )
    accounting_basis: Mapped[str | None] = mapped_column(String(20), nullable=True)
    eas_tags: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    locator: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    extraction: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    audit_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    methodology_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_facts.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_restated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    unknown_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    period: Mapped["FinancialPeriod"] = relationship("FinancialPeriod", back_populates="facts")
    document: Mapped["FinancialDocument"] = relationship("FinancialDocument")
    company: Mapped["Company"] = relationship("Company")

    __table_args__ = (
        Index("ix_financial_facts_period_id", "period_id"),
        Index("ix_financial_facts_document_id", "document_id"),
        Index("ix_financial_facts_company_id", "company_id"),
        Index("ix_financial_facts_fact_type", "fact_type"),
        Index("ix_financial_facts_reported_label", "reported_label"),
        Index("ix_financial_facts_normalized_label", "normalized_label"),
        Index("ix_financial_facts_status", "status"),
        Index("ix_financial_facts_filing_id", "filing_id"),
    )
