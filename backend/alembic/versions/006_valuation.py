"""Add valuation tables.

Revision ID: 006
Revises: 005
Create Date: 2026-09-26
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create valuation_model enum
    valuation_model = sa.Enum(
        "PE", "PB", "EV_EBITDA", "DCF",
        name="valuation_model",
    )
    # Enums are created as a side effect of the first create_table (see the
    # 004→005 enum fix): pre-creating them before create_table made asyncpg
    # emit CREATE TYPE a second time and fails on any fresh database.

    # Create valuation_status enum
    valuation_status = sa.Enum(
        "AVAILABLE", "INSUFFICIENT_DATA", "INVALID",
        name="valuation_status",
    )
    # Create valuation_results table
    op.create_table(
        "valuation_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model", valuation_model, nullable=False),
        sa.Column("value", sa.Numeric(20, 4), nullable=True),
        sa.Column("status", valuation_status, nullable=False),
        sa.Column("assumptions", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "model", "calculated_at", name="uq_valuation_result"),
    )
    op.create_index("ix_valuation_results_company_id", "valuation_results", ["company_id"])
    op.create_index("ix_valuation_results_model", "valuation_results", ["model"])


def downgrade() -> None:
    op.drop_table("valuation_results")
    sa.Enum(name="valuation_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="valuation_model").drop(op.get_bind(), checkfirst=True)
