"""Database models for Phase-5 investment theses (R30 P7).

Four tables in migration 015: ``investment_theses`` (one row per company +
methodology version, last-writer-wins like Phase-3/Phase-4 snapshots),
``thesis_invalidations`` (2-4 stored conditions per thesis, upserted by
metric), ``thesis_ledger`` (append-only evidence timeline — rows are only
ever inserted), and ``thesis_catalysts`` (dated catalyst records).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InvestmentThesis(Base):
    """Persisted structured-thesis snapshot for one company."""

    __tablename__ = "investment_theses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    methodology_version: Mapped[str] = mapped_column(String(20), nullable=False)
    horizon_years: Mapped[int] = mapped_column(Integer, nullable=False)
    is_shareholder: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    fair_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4), nullable=True)
    fair_value_status: Mapped[str] = mapped_column(String(20), nullable=False)
    assumptions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    bulls: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    bears: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    scenarios: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    sensitivity: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    narrative: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    confidence: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    dq: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    score: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    needs_reassessment: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "company_id", "methodology_version",
            name="uq_investment_thesis",
        ),
        Index("ix_investment_theses_company_id", "company_id"),
    )


class ThesisInvalidation(Base):
    """One stored invalidation condition: metric + threshold + period + source."""

    __tablename__ = "thesis_invalidations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investment_theses.id", ondelete="CASCADE"), nullable=False
    )
    methodology_version: Mapped[str] = mapped_column(String(20), nullable=False)
    metric: Mapped[str] = mapped_column(String(100), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(20, 4), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    period: Mapped[str] = mapped_column(String(200), nullable=False)
    evidence_source: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    extraction_confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("thesis_id", "metric", name="uq_thesis_invalidation"),
        Index("ix_thesis_invalidations_thesis_id", "thesis_id"),
    )


class ThesisLedger(Base):
    """Append-only evidence timeline: rows are inserted, never updated."""

    __tablename__ = "thesis_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investment_theses.id", ondelete="CASCADE"), nullable=False
    )
    methodology_version: Mapped[str] = mapped_column(String(20), nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    variable: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    reviewer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_thesis_ledger_thesis_id", "thesis_id"),
    )


class ThesisCatalyst(Base):
    """One dated catalyst record with provenance + Confirmed-vs-Tentative label."""

    __tablename__ = "thesis_catalysts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investment_theses.id", ondelete="CASCADE"), nullable=False
    )
    methodology_version: Mapped[str] = mapped_column(String(20), nullable=False)
    event: Mapped[str] = mapped_column(String(300), nullable=False)
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    window: Mapped[str | None] = mapped_column(String(100), nullable=True)
    variable: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expectation: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    provenance: Mapped[str] = mapped_column(String(1000), nullable=False)
    label: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_thesis_catalysts_thesis_id", "thesis_id"),
    )
