"""financial metrics

Revision ID: 004
Revises: 003
Create Date: 2026-09-26 00:02:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    metric_status = postgresql.ENUM(
        "AVAILABLE", "INSUFFICIENT_DATA", "NOT_APPLICABLE", "INVALID",
        name="metric_status",
        create_type=False,
    )

    metric_status.create(op.get_bind(), checkfirst=True)

    now = sa.func.now()

    op.create_table(
        "financial_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "period_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_periods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric_code", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("value", sa.Numeric(20, 4), nullable=True),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("status", metric_status, nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("warnings", sa.Text(), nullable=True),
        sa.Column("formula_version", sa.BigInteger(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.UniqueConstraint(
            "company_id", "period_id", "metric_code", "formula_version",
            name="uq_financial_metric",
        ),
    )
    op.create_index("ix_financial_metrics_company_id", "financial_metrics", ["company_id"])
    op.create_index("ix_financial_metrics_period_id", "financial_metrics", ["period_id"])
    op.create_index("ix_financial_metrics_metric_code", "financial_metrics", ["metric_code"])
    op.create_index("ix_financial_metrics_status", "financial_metrics", ["status"])

    op.create_table(
        "financial_metric_inputs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "metric_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_metrics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "fact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_facts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("input_role", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=now, nullable=False),
        sa.UniqueConstraint(
            "metric_id", "fact_id", "input_role",
            name="uq_financial_metric_input",
        ),
    )
    op.create_index("ix_financial_metric_inputs_metric_id", "financial_metric_inputs", ["metric_id"])
    op.create_index("ix_financial_metric_inputs_fact_id", "financial_metric_inputs", ["fact_id"])


def downgrade() -> None:
    op.drop_table("financial_metric_inputs")
    op.drop_table("financial_metrics")

    postgresql.ENUM(name="metric_status").drop(op.get_bind(), checkfirst=True)
