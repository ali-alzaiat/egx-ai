"""EGX30 index prices and stored data cross-checks (R50 B10, B11).

``index_prices`` holds daily index closes (EGX30 from Yahoo ``^CASE30``) for the benchmark
column of the performance tool. ``data_crosschecks`` is append-only: every run adds one row per
check and "latest" means the newest run of a company.

Revision ID: 028
Revises: 027
Create Date: 2026-10-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "index_prices",
        sa.Column("index_code", sa.String(20), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("close", sa.Numeric(20, 4), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column(
            "fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("index_code", "trade_date"),
    )

    op.create_table(
        "data_crosschecks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("check_code", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("evidence", JSONB(), server_default="{}", nullable=False),
        sa.Column("methodology_version", sa.String(20), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "status IN ('pass', 'warn', 'fail', 'insufficient_data')",
            name="ck_data_crosschecks_status",
        ),
    )
    op.create_index(
        "ix_data_crosschecks_company_computed",
        "data_crosschecks",
        ["company_id", sa.text("computed_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_data_crosschecks_company_computed", table_name="data_crosschecks")
    op.drop_table("data_crosschecks")
    op.drop_table("index_prices")
