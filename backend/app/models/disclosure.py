"""Database models for Phase-7 disclosure intake + diff ledger (R34 P0-1/P0-6).

Two tables in migration 017: ``disclosure_filings`` (the intake registry —
explicit URL registration + file upload, sha256 dedupe, own mirror bytes;
no crawler, no scheduler) and ``disclosure_fact_diffs`` (the append-only
"what changed?" ledger — period-over-period deltas plus restatement links).
Parsed facts live on the Phase-1 ``financial_facts`` surface, extended with
provenance columns (locator, extraction, accounting_basis, eas_tags,
methodology_version, supersedes, audit_state) — no parallel fact table.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DisclosureFiling(Base):
    """One registered disclosure PDF: bulletin/IR/CBE-bank pack, mirrored."""

    __tablename__ = "disclosure_filings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    filing_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    bulletin_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    filing_type: Mapped[str] = mapped_column(String(20), nullable=False)
    accounting_basis: Mapped[str] = mapped_column(String(20), nullable=False, default="EAS")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    pdf_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_disclosure_filing_hash"),
        Index("ix_disclosure_filings_company_id", "company_id"),
        Index("ix_disclosure_filings_bulletin_id", "bulletin_id"),
    )


class DisclosureFactDiff(Base):
    """One append-only "what changed?" row: period diff or restatement link."""

    __tablename__ = "disclosure_fact_diffs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    methodology_version: Mapped[str] = mapped_column(String(20), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    metric: Mapped[str] = mapped_column(String(255), nullable=False)
    prior_fact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_facts.id", ondelete="SET NULL"),
        nullable=True,
    )
    current_fact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("financial_facts.id", ondelete="SET NULL"),
        nullable=True,
    )
    prior_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    delta: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    delta_pct: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    prior_period: Mapped[str] = mapped_column(String(100), nullable=False)
    current_period: Mapped[str] = mapped_column(String(100), nullable=False)
    estimate_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    beat_miss: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_disclosure_fact_diffs_company_id", "company_id"),
        Index("ix_disclosure_fact_diffs_metric", "metric"),
    )
