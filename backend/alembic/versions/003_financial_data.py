"""financial data

Revision ID: 003
Revises: 002
Create Date: 2026-09-26 00:01:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    reporting_period_type = postgresql.ENUM(
        "ANNUAL", "Q1", "Q2", "Q3", "Q4", "SEMI_ANNUAL", "INTERIM",
        name="reporting_period_type",
        create_type=False,
    )
    fact_type = postgresql.ENUM(
        "INCOME_STATEMENT", "BALANCE_SHEET", "CASH_FLOW", "SHAREHOLDERS_EQUITY", "NOTES",
        name="fact_type",
        create_type=False,
    )
    document_status = postgresql.ENUM(
        "ORIGINAL", "RESTATED", "AMENDED", "ADJUSTED",
        name="document_status",
        create_type=False,
    )
    fact_status = postgresql.ENUM(
        "REPORTED", "NORMALIZED", "CALCULATED", "INSUFFICIENT_DATA",
        name="fact_status",
        create_type=False,
    )

    reporting_period_type.create(op.get_bind(), checkfirst=True)
    fact_type.create(op.get_bind(), checkfirst=True)
    document_status.create(op.get_bind(), checkfirst=True)
    fact_status.create(op.get_bind(), checkfirst=True)

    now = sa.func.now()

    op.create_table(
        "financial_periods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_type", reporting_period_type, nullable=False),
        sa.Column("fiscal_year", sa.BigInteger(), nullable=False),
        sa.Column("fiscal_quarter", sa.BigInteger(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.UniqueConstraint(
            "company_id", "fiscal_year", "period_type",
            name="uq_financial_period",
        ),
    )
    op.create_index("ix_financial_periods_company_id", "financial_periods", ["company_id"])
    op.create_index("ix_financial_periods_fiscal_year", "financial_periods", ["fiscal_year"])
    op.create_index("ix_financial_periods_period_type", "financial_periods", ["period_type"])

    op.create_table(
        "financial_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "period_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_periods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("document_status", document_status, nullable=False, server_default="ORIGINAL"),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("document_url", sa.String(500), nullable=True),
        sa.Column("filing_date", sa.Date(), nullable=True),
        sa.Column("publication_date", sa.Date(), nullable=True),
        sa.Column("fiscal_year_end", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.UniqueConstraint(
            "period_id", "source_id", "document_type",
            name="uq_financial_document",
        ),
    )
    op.create_index("ix_financial_documents_period_id", "financial_documents", ["period_id"])
    op.create_index("ix_financial_documents_source_id", "financial_documents", ["source_id"])
    op.create_index(
        "ix_financial_documents_document_status",
        "financial_documents",
        ["document_status"],
    )
    op.create_index(
        "ix_financial_documents_publication_date",
        "financial_documents",
        ["publication_date"],
    )

    op.create_table(
        "financial_facts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "period_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_periods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fact_type", fact_type, nullable=False),
        sa.Column("reported_label", sa.String(255), nullable=False),
        sa.Column("normalized_label", sa.String(255), nullable=True),
        sa.Column("reported_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("normalized_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EGP"),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("scale", sa.BigInteger(), nullable=True),
        sa.Column("status", fact_status, nullable=False, server_default="REPORTED"),
        sa.Column("source_page", sa.String(100), nullable=True),
        sa.Column("source_line", sa.String(100), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("normalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
    )
    op.create_index("ix_financial_facts_period_id", "financial_facts", ["period_id"])
    op.create_index("ix_financial_facts_document_id", "financial_facts", ["document_id"])
    op.create_index("ix_financial_facts_company_id", "financial_facts", ["company_id"])
    op.create_index("ix_financial_facts_fact_type", "financial_facts", ["fact_type"])
    op.create_index("ix_financial_facts_reported_label", "financial_facts", ["reported_label"])
    op.create_index(
        "ix_financial_facts_normalized_label",
        "financial_facts",
        ["normalized_label"],
    )
    op.create_index("ix_financial_facts_status", "financial_facts", ["status"])


def downgrade() -> None:
    op.drop_table("financial_facts")
    op.drop_table("financial_documents")
    op.drop_table("financial_periods")

    postgresql.ENUM(name="fact_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="document_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="fact_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="reporting_period_type").drop(op.get_bind(), checkfirst=True)
