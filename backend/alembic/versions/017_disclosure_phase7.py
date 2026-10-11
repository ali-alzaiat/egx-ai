"""Add disclosure intake registry + Phase-7 fact provenance + diff ledger.

Revision ID: 017
Revises: 016
Create Date: 2026-10-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "disclosure_filings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("filing_url", sa.String(1000), nullable=True),
        sa.Column("bulletin_id", sa.String(100), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("filing_type", sa.String(20), nullable=False),
        sa.Column(
            "accounting_basis", sa.String(20), nullable=False, server_default="EAS"
        ),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("storage_path", sa.String(1000), nullable=True),
        sa.Column("pdf_bytes", sa.LargeBinary(), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("content_hash", name="uq_disclosure_filing_hash"),
    )
    op.create_index(
        "ix_disclosure_filings_company_id", "disclosure_filings", ["company_id"]
    )
    op.create_index(
        "ix_disclosure_filings_bulletin_id", "disclosure_filings", ["bulletin_id"]
    )

    op.add_column(
        "financial_facts", sa.Column("filing_id", UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_financial_facts_filing_id",
        "financial_facts",
        "disclosure_filings",
        ["filing_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "financial_facts", sa.Column("accounting_basis", sa.String(20), nullable=True)
    )
    op.add_column("financial_facts", sa.Column("eas_tags", JSONB(), nullable=True))
    op.add_column("financial_facts", sa.Column("locator", JSONB(), nullable=True))
    op.add_column("financial_facts", sa.Column("extraction", JSONB(), nullable=True))
    op.add_column(
        "financial_facts", sa.Column("audit_state", sa.String(20), nullable=True)
    )
    op.add_column(
        "financial_facts",
        sa.Column("methodology_version", sa.String(20), nullable=True),
    )
    op.add_column(
        "financial_facts", sa.Column("supersedes_id", UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_financial_facts_supersedes_id",
        "financial_facts",
        "financial_facts",
        ["supersedes_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "financial_facts",
        sa.Column(
            "is_restated", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.add_column(
        "financial_facts", sa.Column("unknown_reason", sa.Text(), nullable=True)
    )
    op.create_index(
        "ix_financial_facts_filing_id", "financial_facts", ["filing_id"]
    )

    op.create_table(
        "disclosure_fact_diffs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("methodology_version", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("metric", sa.String(255), nullable=False),
        sa.Column("prior_fact_id", UUID(as_uuid=True), nullable=True),
        sa.Column("current_fact_id", UUID(as_uuid=True), nullable=True),
        sa.Column("prior_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("current_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("delta", sa.Numeric(20, 4), nullable=True),
        sa.Column("delta_pct", sa.Numeric(20, 8), nullable=True),
        sa.Column("prior_period", sa.String(100), nullable=False),
        sa.Column("current_period", sa.String(100), nullable=False),
        sa.Column("estimate_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("beat_miss", sa.String(10), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["prior_fact_id"], ["financial_facts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["current_fact_id"], ["financial_facts.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_disclosure_fact_diffs_company_id", "disclosure_fact_diffs", ["company_id"]
    )
    op.create_index(
        "ix_disclosure_fact_diffs_metric", "disclosure_fact_diffs", ["metric"]
    )


def downgrade() -> None:
    op.drop_index("ix_disclosure_fact_diffs_metric", table_name="disclosure_fact_diffs")
    op.drop_index(
        "ix_disclosure_fact_diffs_company_id", table_name="disclosure_fact_diffs"
    )
    op.drop_table("disclosure_fact_diffs")

    op.drop_index("ix_financial_facts_filing_id", table_name="financial_facts")
    op.drop_column("financial_facts", "unknown_reason")
    op.drop_column("financial_facts", "is_restated")
    op.drop_constraint(
        "fk_financial_facts_supersedes_id", "financial_facts", type_="foreignkey"
    )
    op.drop_column("financial_facts", "supersedes_id")
    op.drop_column("financial_facts", "methodology_version")
    op.drop_column("financial_facts", "audit_state")
    op.drop_column("financial_facts", "extraction")
    op.drop_column("financial_facts", "locator")
    op.drop_column("financial_facts", "eas_tags")
    op.drop_column("financial_facts", "accounting_basis")
    op.drop_constraint(
        "fk_financial_facts_filing_id", "financial_facts", type_="foreignkey"
    )
    op.drop_column("financial_facts", "filing_id")

    op.drop_index("ix_disclosure_filings_bulletin_id", table_name="disclosure_filings")
    op.drop_index("ix_disclosure_filings_company_id", table_name="disclosure_filings")
    op.drop_table("disclosure_filings")
