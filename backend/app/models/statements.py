"""Database models for sourced financial statements (zborsa upgrade, migration 019).

``FinancialStatementLine`` holds one canonical ontology value per period with full
provenance; ``FinancialDocumentBlob`` stores raw downloaded filing bytes so every
extraction is re-runnable against the same bytes (same hash -> same extraction).
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ExtractionMethod(enum.StrEnum):
    """How the line value was obtained (members equal stored values)."""

    downloaded_document_table = "downloaded_document_table"
    downloaded_document_text = "downloaded_document_text"
    xbrl = "xbrl"
    manual_seed = "manual_seed"
    # Third-party aggregator data: provisional, always outranked by filing-backed rows.
    vendor_aggregator = "vendor_aggregator"


class ExtStatus(enum.StrEnum):
    """Review-queue lifecycle of a statement line.

    Only ``approved`` and ``auto_validated`` rows ever reach user-facing
    calculations; ``extraction_candidate`` is visible only in the Ops review
    queue and ``rejected`` carries the failing gate in its reason.
    """

    extraction_candidate = "extraction_candidate"
    auto_validated = "auto_validated"
    approved = "approved"
    rejected = "rejected"


class FinancialStatementLine(Base):
    """One canonical ontology value for one reporting period."""

    __tablename__ = "financial_statement_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_periods.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    ontology_code: Mapped[str] = mapped_column(String(64), nullable=False)
    ontology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EGP")
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_label_reported: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_label_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_label_ar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_page: Mapped[str | None] = mapped_column(String(32), nullable=True)
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        Enum(ExtractionMethod, name="extraction_method", create_constraint=True), nullable=False
    )
    ext_status: Mapped[ExtStatus] = mapped_column(
        Enum(ExtStatus, name="ext_status", create_constraint=True),
        nullable=False,
        default=ExtStatus.extraction_candidate,
    )
    ext_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_statement_lines.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    period: Mapped["FinancialPeriod"] = relationship("FinancialPeriod")  # type: ignore[name-defined]  # noqa: F821
    company: Mapped["Company"] = relationship("Company")  # type: ignore[name-defined]  # noqa: F821
    source_document: Mapped["FinancialDocument"] = relationship("FinancialDocument")  # type: ignore[name-defined]  # noqa: F821
    supersedes: Mapped["FinancialStatementLine | None"] = relationship(
        "FinancialStatementLine", remote_side="FinancialStatementLine.id"
    )

    __table_args__ = (
        UniqueConstraint("period_id", "ontology_code", "source_document_id", name="uq_stmt_line"),
        Index("ix_stmt_lines_company_id", "company_id"),
        Index("ix_stmt_lines_period_id", "period_id"),
        Index("ix_stmt_lines_ext_status", "ext_status"),
    )


class FinancialDocumentBlob(Base):
    """Raw bytes of a downloaded filing, hash-keyed for de-duplication."""

    __tablename__ = "financial_document_blobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_documents.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["FinancialDocument"] = relationship("FinancialDocument")  # type: ignore[name-defined]  # noqa: F821

    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_statement_blob_hash"),
        Index("ix_statement_blobs_document_id", "document_id"),
    )
