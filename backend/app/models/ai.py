"""Database models for AI analysis and RAG."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None  # type: ignore[misc,assignment]

if TYPE_CHECKING:
    from app.models.financial import FinancialDocument
    from app.models.market import Company


class AnalysisTypeDB(enum.Enum):
    """AI analysis types."""
    COMPANY_SYNTHESIS = "company_synthesis"
    DOCUMENT_SUMMARY = "document_summary"
    METRIC_EXPLANATION = "metric_explanation"
    SCREENING_EXPLANATION = "screening_explanation"
    VALUATION_EXPLANATION = "valuation_explanation"


class AnalysisStatusDB(enum.Enum):
    """AI analysis status."""
    COMPLETED = "completed"
    FAILED = "failed"
    INSUFFICIENT_DATA = "insufficient_data"


class ChunkTypeDB(enum.Enum):
    """Document chunk types for RAG."""
    FINANCIAL_FACT = "financial_fact"
    METRIC = "metric"
    VALUATION = "valuation"
    SCREENING = "screening"
    DOCUMENT_TEXT = "document_text"


class DocumentChunk(Base):
    """A chunk of text from a financial document, embedded for RAG retrieval."""

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_documents.id", ondelete="SET NULL"), nullable=True
    )
    chunk_type: Mapped[ChunkTypeDB] = mapped_column(
        Enum(ChunkTypeDB, name="chunk_type", create_constraint=True),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding = (
        mapped_column(Vector(384), nullable=True)
        if Vector is not None
        else mapped_column(Text, nullable=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship("Company")
    document: Mapped["FinancialDocument | None"] = relationship("FinancialDocument")

    __table_args__ = (
        Index("ix_document_chunks_company_id", "company_id"),
        Index("ix_document_chunks_chunk_type", "chunk_type"),
    )


class AIAnalysis(Base):
    """AI-generated analysis with source attribution."""

    __tablename__ = "ai_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    analysis_type: Mapped[AnalysisTypeDB] = mapped_column(
        Enum(AnalysisTypeDB, name="analysis_type", create_constraint=True),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detailed_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_chunk_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    disclaimer: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AnalysisStatusDB] = mapped_column(
        Enum(AnalysisStatusDB, name="analysis_status", create_constraint=True),
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company: Mapped["Company"] = relationship("Company")

    __table_args__ = (
        Index("ix_ai_analyses_company_id", "company_id"),
        Index("ix_ai_analyses_analysis_type", "analysis_type"),
    )
