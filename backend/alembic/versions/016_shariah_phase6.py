"""Shariah Phase 6 (R32 B2/B3/B5): report dates, rule provenance, purification, EGX33.

Revision ID: 016
Revises: 015
Create Date: 2026-10-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shariah_screening_results",
        sa.Column("report_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "shariah_screening_results",
        sa.Column("report_date_reason", sa.Text(), nullable=True),
    )

    op.add_column(
        "screening_rule_results",
        sa.Column("missing_input", sa.String(255), nullable=True),
    )
    op.add_column(
        "screening_rule_results",
        sa.Column("source", sa.String(500), nullable=True),
    )
    op.add_column(
        "screening_rule_results",
        sa.Column("source_date", sa.Date(), nullable=True),
    )

    op.create_table(
        "screening_purification_estimates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("methodology_version", sa.String(50), nullable=False),
        sa.Column("doctrine", sa.String(50), nullable=False),
        sa.Column("branch", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("amount_egp", sa.Numeric(20, 4), nullable=True),
        sa.Column("dividend_egp", sa.Numeric(20, 4), nullable=True),
        sa.Column("ratio", sa.Numeric(20, 8), nullable=True),
        sa.Column("ratio_provenance", sa.String(500), nullable=True),
        sa.Column("dps", sa.Numeric(20, 4), nullable=True),
        sa.Column("dps_source", sa.String(500), nullable=True),
        sa.Column("dps_date", sa.Date(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("missing_input", sa.String(255), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "company_id", "methodology_version",
            name="uq_screening_purification_estimate",
        ),
    )
    op.create_index(
        "ix_screening_purification_estimates_company_id",
        "screening_purification_estimates",
        ["company_id"],
    )

    op.create_table(
        "screening_egx_memberships",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("methodology_version", sa.String(50), nullable=False),
        sa.Column("member", sa.Boolean(), nullable=False),
        sa.Column("review_cycle", sa.String(20), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("source", sa.String(500), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "company_id", "review_cycle",
            name="uq_screening_egx_membership",
        ),
    )
    op.create_index(
        "ix_screening_egx_memberships_company_id",
        "screening_egx_memberships",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_screening_egx_memberships_company_id",
        table_name="screening_egx_memberships",
    )
    op.drop_table("screening_egx_memberships")

    op.drop_index(
        "ix_screening_purification_estimates_company_id",
        table_name="screening_purification_estimates",
    )
    op.drop_table("screening_purification_estimates")

    op.drop_column("screening_rule_results", "source_date")
    op.drop_column("screening_rule_results", "source")
    op.drop_column("screening_rule_results", "missing_input")

    op.drop_column("shariah_screening_results", "report_date_reason")
    op.drop_column("shariah_screening_results", "report_date")
