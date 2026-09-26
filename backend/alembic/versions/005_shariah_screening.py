"""Add Shariah screening tables.

Revision ID: 005
Revises: 004
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create screening_status enum
    screening_status = sa.Enum(
        "COMPLIANT", "NON_COMPLIANT", "INSUFFICIENT_DATA",
        name="screening_status",
    )
    screening_status.create(op.get_bind(), checkfirst=True)

    # Create shariah_screening_results table
    op.create_table(
        "shariah_screening_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_compliant", sa.Boolean(), nullable=False),
        sa.Column("status", screening_status, nullable=False),
        sa.Column("methodology_version", sa.String(50), nullable=False),
        sa.Column("methodology_name", sa.String(255), nullable=False),
        sa.Column("overall_reason", sa.Text(), nullable=False),
        sa.Column("screened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "methodology_version", name="uq_shariah_screening_result"),
    )
    op.create_index("ix_shariah_screening_results_company_id", "shariah_screening_results", ["company_id"])
    op.create_index("ix_shariah_screening_results_is_compliant", "shariah_screening_results", ["is_compliant"])

    # Create screening_rule_results table
    op.create_table(
        "screening_rule_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("screening_result_id", UUID(as_uuid=True), sa.ForeignKey("shariah_screening_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("verdict", sa.String(50), nullable=False),
        sa.Column("value", sa.Numeric(20, 8), nullable=True),
        sa.Column("threshold", sa.Numeric(20, 8), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_screening_rule_results_screening_result_id", "screening_rule_results", ["screening_result_id"])


def downgrade() -> None:
    op.drop_table("screening_rule_results")
    op.drop_table("shariah_screening_results")
    sa.Enum(name="screening_status").drop(op.get_bind(), checkfirst=True)
