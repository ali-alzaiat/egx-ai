"""Add market-wide signal ranking and universe coverage tables.

Revision ID: 009
Revises: 008
Create Date: 2026-09-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("model_name", sa.String(50), nullable=False),
        sa.Column("model_version", sa.String(20), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "SCORED",
                "INSUFFICIENT_HISTORY",
                "NO_PRICE_DATA",
                "NOT_ACTIVE",
                name="signal_status",
            ),
            nullable=False,
            server_default="SCORED",
        ),
        sa.Column(
            "tier",
            sa.Enum(
                "STRONGEST", "STRONG", "NEUTRAL", "WEAK", "WEAKEST", name="signal_tier"
            ),
            nullable=True,
        ),
        sa.Column("score", sa.Numeric(6, 2), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("universe_size", sa.Integer(), nullable=True),
        sa.Column("data_coverage", sa.Numeric(5, 4), nullable=True),
        sa.Column("observations", sa.Integer(), nullable=True),
        sa.Column("factors", JSONB(), nullable=False, server_default="{}"),
        sa.Column("percentiles", JSONB(), nullable=False, server_default="{}"),
        sa.Column("excluded_factors", JSONB(), nullable=False, server_default="[]"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "company_id", "as_of", "model_version", name="uq_market_signal_company_date_model"
        ),
    )
    op.create_index(
        "ix_market_signals_as_of_model", "market_signals", ["as_of", "model_version"]
    )
    op.create_index("ix_market_signals_company_id", "market_signals", ["company_id"])
    op.create_index("ix_market_signals_rank", "market_signals", ["as_of", "rank"])

    op.create_table(
        "signal_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("model_name", sa.String(50), nullable=False),
        sa.Column("model_version", sa.String(20), nullable=False),
        sa.Column("universe_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scored_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unscorable_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coverage_ratio", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("config", JSONB(), nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("as_of", "model_version", name="uq_signal_run_date_model"),
    )
    op.create_index("ix_signal_runs_model", "signal_runs", ["model_name", "model_version"])

    op.create_table(
        "universe_coverage_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("universe_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("with_price_data", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("analyzable", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unscorable", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("coverage_ratio", sa.Numeric(5, 4), nullable=False, server_default="0"),
        sa.Column("universe_source", sa.String(80), nullable=True),
        sa.Column("universe_source_url", sa.String(500), nullable=True),
        sa.Column("unpriced_tickers", JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_fallback_source", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_universe_coverage_as_of", "universe_coverage_snapshots", ["as_of"]
    )


def downgrade() -> None:
    op.drop_index("ix_universe_coverage_as_of", table_name="universe_coverage_snapshots")
    op.drop_table("universe_coverage_snapshots")

    op.drop_index("ix_signal_runs_model", table_name="signal_runs")
    op.drop_table("signal_runs")

    op.drop_index("ix_market_signals_rank", table_name="market_signals")
    op.drop_index("ix_market_signals_company_id", table_name="market_signals")
    op.drop_index("ix_market_signals_as_of_model", table_name="market_signals")
    op.drop_table("market_signals")

    sa.Enum(name="signal_tier").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="signal_status").drop(op.get_bind(), checkfirst=True)
