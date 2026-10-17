"""Sourced financial statements: line values, raw document blobs, fetch metadata.

Revision ID: 019
Revises: 018
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # financial_documents: fetch provenance (adds columns only).
    op.add_column(
        "financial_documents",
        sa.Column("source_kind", sa.String(20), nullable=True),
    )
    op.add_column(
        "financial_documents",
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "financial_documents",
        sa.Column("content_hash", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_financial_documents_content_hash",
        "financial_documents",
        ["content_hash"],
    )

    # financial_statement_lines (enums emitted with the table - see 005/006).
    op.create_table(
        "financial_statement_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("period_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("ontology_code", sa.String(64), nullable=False),
        sa.Column("ontology_version", sa.String(32), nullable=False),
        sa.Column("value", sa.Numeric(20, 4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EGP"),
        sa.Column("source_document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_label_reported", sa.String(255), nullable=True),
        sa.Column("source_label_en", sa.String(255), nullable=True),
        sa.Column("source_label_ar", sa.String(255), nullable=True),
        sa.Column("source_page", sa.String(32), nullable=True),
        sa.Column(
            "extraction_method",
            sa.Enum(
                "downloaded_document_table",
                "downloaded_document_text",
                "xbrl",
                "manual_seed",
                name="extraction_method",
            ),
            nullable=False,
        ),
        sa.Column(
            "ext_status",
            sa.Enum(
                "extraction_candidate",
                "auto_validated",
                "approved",
                "rejected",
                name="ext_status",
            ),
            nullable=False,
        ),
        sa.Column("ext_reason", sa.Text(), nullable=True),
        sa.Column("published_date", sa.Date(), nullable=True),
        sa.Column("supersedes_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["period_id"], ["financial_periods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_document_id"], ["financial_documents.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"], ["financial_statement_lines.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "period_id", "ontology_code", "source_document_id", name="uq_stmt_line"
        ),
    )
    op.create_index("ix_stmt_lines_company_id", "financial_statement_lines", ["company_id"])
    op.create_index("ix_stmt_lines_period_id", "financial_statement_lines", ["period_id"])
    op.create_index("ix_stmt_lines_ext_status", "financial_statement_lines", ["ext_status"])

    # financial_document_blobs (raw bytes, hash-deduped).
    op.create_table(
        "financial_document_blobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["financial_documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("content_hash", name="uq_statement_blob_hash"),
    )
    op.create_index("ix_statement_blobs_document_id", "financial_document_blobs", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_statement_blobs_document_id", table_name="financial_document_blobs")
    op.drop_table("financial_document_blobs")
    op.drop_index("ix_stmt_lines_ext_status", table_name="financial_statement_lines")
    op.drop_index("ix_stmt_lines_period_id", table_name="financial_statement_lines")
    op.drop_index("ix_stmt_lines_company_id", table_name="financial_statement_lines")
    op.drop_table("financial_statement_lines")
    op.drop_index("ix_financial_documents_content_hash", table_name="financial_documents")
    op.drop_column("financial_documents", "content_hash")
    op.drop_column("financial_documents", "fetched_at")
    op.drop_column("financial_documents", "source_kind")
    sa.Enum(name="ext_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="extraction_method").drop(op.get_bind(), checkfirst=True)
