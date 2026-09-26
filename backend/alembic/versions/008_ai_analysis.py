"""Add AI analysis and document chunks tables.

Revision ID: 008
Revises: 007
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create chunk_type enum
    chunk_type = sa.Enum(
        "financial_fact", "metric", "valuation", "screening", "document_text",
        name="chunk_type",
    )
    chunk_type.create(op.get_bind(), checkfirst=True)

    # Create analysis_type enum
    analysis_type = sa.Enum(
        "company_synthesis", "document_summary", "metric_explanation",
        "screening_explanation", "valuation_explanation",
        name="analysis_type",
    )
    analysis_type.create(op.get_bind(), checkfirst=True)

    # Create analysis_status enum
    analysis_status = sa.Enum(
        "completed", "failed", "insufficient_data",
        name="analysis_status",
    )
    analysis_status.create(op.get_bind(), checkfirst=True)

    # Create document_chunks table
    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("financial_documents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("chunk_type", chunk_type, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(384) if Vector is not None else sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_document_chunks_company_id", "document_chunks", ["company_id"])
    op.create_index("ix_document_chunks_chunk_type", "document_chunks", ["chunk_type"])

    # Create ai_analyses table
    op.create_table(
        "ai_analyses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analysis_type", analysis_type, nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("detailed_analysis", sa.Text(), nullable=True),
        sa.Column("source_chunk_ids", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("disclaimer", sa.Text(), nullable=True),
        sa.Column("status", analysis_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_analyses_company_id", "ai_analyses", ["company_id"])
    op.create_index("ix_ai_analyses_analysis_type", "ai_analyses", ["analysis_type"])


def downgrade() -> None:
    op.drop_table("ai_analyses")
    op.drop_table("document_chunks")
    sa.Enum(name="analysis_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="analysis_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="chunk_type").drop(op.get_bind(), checkfirst=True)
    op.execute("DROP EXTENSION IF EXISTS vector")
