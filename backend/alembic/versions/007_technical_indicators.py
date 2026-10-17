"""Add technical indicators tables.

Revision ID: 007
Revises: 006
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create indicator_type enum
    indicator_type = sa.Enum(
        "SMA", "EMA", "RSI", "MACD", "BOLLINGER", "OBV", "VWAP",
        name="indicator_type",
    )

    # Create indicator_status enum
    indicator_status = sa.Enum(
        "AVAILABLE", "INSUFFICIENT_DATA", "INVALID",
        name="indicator_status",
    )

    # Create technical_indicators table
    op.create_table(
        "technical_indicators",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("indicator_type", indicator_type, nullable=False),
        sa.Column("value", sa.Numeric(20, 4), nullable=True),
        sa.Column("status", indicator_status, nullable=False),
        sa.Column("parameters", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "indicator_type", "calculated_at", name="uq_technical_indicator"),
    )
    op.create_index("ix_technical_indicators_company_id", "technical_indicators", ["company_id"])
    op.create_index("ix_technical_indicators_indicator_type", "technical_indicators", ["indicator_type"])


def downgrade() -> None:
    op.drop_table("technical_indicators")
    sa.Enum(name="indicator_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="indicator_type").drop(op.get_bind(), checkfirst=True)
