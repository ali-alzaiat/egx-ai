"""R43 computed company data: compute state, valuation assumptions, metric line inputs (023).

Revision ID: 023
Revises: 022
Create Date: 2026-10-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_compute_state",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("engine", sa.String(32), nullable=False),
        sa.Column("methodology_version", sa.String(64), nullable=False),
        sa.Column("inputs_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("trigger", sa.String(32), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_as_of", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("source_tier", sa.String(10), nullable=True),
        sa.Column("provisional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "company_id", "engine", "methodology_version", name="uq_company_compute_state"
        ),
    )
    op.create_index(
        "ix_company_compute_state_company_id", "company_compute_state", ["company_id"]
    )

    op.create_table(
        "valuation_assumptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("methodology_version", sa.String(20), nullable=False),
        sa.Column("key", sa.String(40), nullable=False),
        sa.Column("scope", sa.String(50), nullable=False),
        sa.Column("value", sa.Numeric(12, 6), nullable=False),
        sa.Column("source_url", sa.String(500), nullable=False),
        sa.Column("source_title", sa.String(255), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "methodology_version", "key", "scope", "as_of", name="uq_valuation_assumption"
        ),
    )
    op.create_index("ix_valuation_assumptions_key", "valuation_assumptions", ["key"])

    op.alter_column("financial_metric_inputs", "fact_id", nullable=True)
    op.add_column(
        "financial_metric_inputs",
        sa.Column(
            "statement_line_id",
            UUID(as_uuid=True),
            sa.ForeignKey("financial_statement_lines.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_financial_metric_inputs_one_source",
        "financial_metric_inputs",
        "(fact_id IS NULL) <> (statement_line_id IS NULL)",
    )
    op.create_index(
        "ix_financial_metric_inputs_statement_line_id",
        "financial_metric_inputs",
        ["statement_line_id"],
    )
    op.create_unique_constraint(
        "uq_financial_metric_input_line",
        "financial_metric_inputs",
        ["metric_id", "statement_line_id", "input_role"],
    )

    op.add_column("financial_metrics", sa.Column("source_tier", sa.String(10), nullable=True))
    op.add_column(
        "financial_metrics",
        sa.Column("provisional", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("financial_metrics", "provisional")
    op.drop_column("financial_metrics", "source_tier")

    op.drop_constraint(
        "uq_financial_metric_input_line", "financial_metric_inputs", type_="unique"
    )
    op.drop_index(
        "ix_financial_metric_inputs_statement_line_id", table_name="financial_metric_inputs"
    )
    op.drop_constraint(
        "ck_financial_metric_inputs_one_source", "financial_metric_inputs", type_="check"
    )
    # Statement-line-only inputs cannot survive fact_id NOT NULL.
    op.execute("DELETE FROM financial_metric_inputs WHERE fact_id IS NULL")
    op.drop_column("financial_metric_inputs", "statement_line_id")
    op.alter_column("financial_metric_inputs", "fact_id", nullable=False)

    op.drop_index("ix_valuation_assumptions_key", table_name="valuation_assumptions")
    op.drop_table("valuation_assumptions")
    op.drop_index("ix_company_compute_state_company_id", table_name="company_compute_state")
    op.drop_table("company_compute_state")
