"""Add data-quality assessments table and ingestion provenance columns.

Revision ID: 011
Revises: 010
Create Date: 2026-10-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_quality_assessments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(50), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column(
            "status",
            sa.Enum("OK", "DEGRADED", "POOR", "MISSING", name="data_quality_status"),
            nullable=False,
        ),
        sa.Column("components", JSONB(), nullable=False, server_default="[]"),
        sa.Column("issues", JSONB(), nullable=False, server_default="[]"),
        sa.Column("methodology_version", sa.String(20), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["data_sources.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "company_id", "scope", "as_of", "methodology_version",
            name="uq_data_quality_assessment",
        ),
    )
    op.create_index(
        "ix_data_quality_assessment_company_scope",
        "data_quality_assessments",
        ["company_id", "scope", sa.text("as_of DESC")],
    )

    op.add_column(
        "data_sources",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "daily_prices",
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Declared in models/screening.py but never created by 005; backfill idempotently.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_shariah_screening_results_methodology_version "
        "ON shariah_screening_results (methodology_version)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_screening_rule_results_rule_name "
        "ON screening_rule_results (rule_name)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_screening_rule_results_rule_name")
    op.execute("DROP INDEX IF EXISTS ix_shariah_screening_results_methodology_version")
    op.drop_column("daily_prices", "ingested_at")
    op.drop_column("data_sources", "last_synced_at")
    op.drop_table("data_quality_assessments")
    sa.Enum(name="data_quality_status").drop(op.get_bind(), checkfirst=True)
