"""Add investment-thesis tables (Phase 5, R30 P7).

Revision ID: 015
Revises: 014
Create Date: 2026-10-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investment_theses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("methodology_version", sa.String(20), nullable=False),
        sa.Column("horizon_years", sa.Integer(), nullable=False),
        sa.Column("is_shareholder", sa.Boolean(), nullable=True),
        sa.Column("fair_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("fair_value_status", sa.String(20), nullable=False),
        sa.Column("assumptions", JSONB(), nullable=False, server_default="[]"),
        sa.Column("bulls", JSONB(), nullable=False, server_default="[]"),
        sa.Column("bears", JSONB(), nullable=False, server_default="[]"),
        sa.Column("scenarios", JSONB(), nullable=False, server_default="{}"),
        sa.Column("sensitivity", JSONB(), nullable=False, server_default="{}"),
        sa.Column("narrative", sa.Text(), nullable=False, server_default=""),
        sa.Column("confidence", JSONB(), nullable=False, server_default="{}"),
        sa.Column("dq", JSONB(), nullable=False, server_default="{}"),
        sa.Column("score", JSONB(), nullable=True),
        sa.Column("needs_reassessment", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "company_id", "methodology_version", name="uq_investment_thesis"
        ),
    )
    op.create_index(
        "ix_investment_theses_company_id", "investment_theses", ["company_id"]
    )

    op.create_table(
        "thesis_invalidations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("thesis_id", UUID(as_uuid=True), nullable=False),
        sa.Column("methodology_version", sa.String(20), nullable=False),
        sa.Column("metric", sa.String(100), nullable=False),
        sa.Column("threshold", sa.Numeric(20, 4), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("period", sa.String(200), nullable=False),
        sa.Column("evidence_source", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("extraction_confidence", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["thesis_id"], ["investment_theses.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("thesis_id", "metric", name="uq_thesis_invalidation"),
    )
    op.create_index(
        "ix_thesis_invalidations_thesis_id", "thesis_invalidations", ["thesis_id"]
    )

    op.create_table(
        "thesis_ledger",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("thesis_id", UUID(as_uuid=True), nullable=False),
        sa.Column("methodology_version", sa.String(20), nullable=False),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("variable", sa.String(100), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence", JSONB(), nullable=False, server_default="{}"),
        sa.Column("reviewer", sa.String(200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["thesis_id"], ["investment_theses.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_thesis_ledger_thesis_id", "thesis_ledger", ["thesis_id"])

    op.create_table(
        "thesis_catalysts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("thesis_id", UUID(as_uuid=True), nullable=False),
        sa.Column("methodology_version", sa.String(20), nullable=False),
        sa.Column("event", sa.String(300), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("window", sa.String(100), nullable=True),
        sa.Column("variable", sa.String(100), nullable=True),
        sa.Column("expectation", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("provenance", sa.String(1000), nullable=False),
        sa.Column("label", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["thesis_id"], ["investment_theses.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_thesis_catalysts_thesis_id", "thesis_catalysts", ["thesis_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_thesis_catalysts_thesis_id", table_name="thesis_catalysts")
    op.drop_table("thesis_catalysts")

    op.drop_index("ix_thesis_ledger_thesis_id", table_name="thesis_ledger")
    op.drop_table("thesis_ledger")

    op.drop_index(
        "ix_thesis_invalidations_thesis_id", table_name="thesis_invalidations"
    )
    op.drop_table("thesis_invalidations")

    op.drop_index("ix_investment_theses_company_id", table_name="investment_theses")
    op.drop_table("investment_theses")
