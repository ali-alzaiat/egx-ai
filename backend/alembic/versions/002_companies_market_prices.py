"""companies and market prices

Revision ID: 002
Revises: 001
Create Date: 2026-09-26 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    company_status = postgresql.ENUM(
        "ACTIVE",
        "SUSPENDED",
        "DELISTED",
        "UNKNOWN",
        name="company_status",
        create_type=False,
    )
    data_source_type = postgresql.ENUM(
        "EGX",
        "FRA",
        "COMPANY",
        "DATA_PROVIDER",
        "MANUAL",
        "SYNTHETIC",
        name="data_source_type",
        create_type=False,
    )

    company_status.create(op.get_bind(), checkfirst=True)
    data_source_type.create(op.get_bind(), checkfirst=True)

    now = sa.func.now()

    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False),
        sa.Column("isin", sa.String(12), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("name_ar", sa.String(255), nullable=True),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EGP"),
        sa.Column("shares_outstanding", sa.Numeric(20, 2), nullable=True),
        sa.Column("free_float", sa.Numeric(10, 4), nullable=True),
        sa.Column("listing_date", sa.Date(), nullable=True),
        sa.Column("status", company_status, nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=now,
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=now,
            nullable=False,
        ),
        sa.UniqueConstraint("ticker", name="uq_company_ticker"),
    )
    op.create_index("ix_companies_ticker", "companies", ["ticker"])
    op.create_index("ix_companies_isin", "companies", ["isin"])
    op.create_index("ix_companies_sector", "companies", ["sector"])
    op.create_index("ix_companies_status", "companies", ["status"])

    op.create_table(
        "data_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("source_type", data_source_type, nullable=False),
        sa.Column("base_url", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=now,
            nullable=False,
        ),
        sa.UniqueConstraint("name", name="uq_data_source_name"),
    )

    op.create_table(
        "daily_prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(12, 4), nullable=False),
        sa.Column("high", sa.Numeric(12, 4), nullable=False),
        sa.Column("low", sa.Numeric(12, 4), nullable=False),
        sa.Column("close", sa.Numeric(12, 4), nullable=False),
        sa.Column("adjusted_close", sa.Numeric(12, 4), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=False),
        sa.Column("value_traded", sa.Numeric(16, 2), nullable=True),
        sa.Column("trades", sa.BigInteger(), nullable=True),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=now,
            nullable=False,
        ),
        sa.UniqueConstraint("company_id", "date", name="uq_daily_price_company_date"),
    )
    op.create_index("ix_daily_prices_company_id", "daily_prices", ["company_id"])
    op.create_index("ix_daily_prices_date", "daily_prices", ["date"])
    op.create_index(
        "ix_daily_prices_company_date",
        "daily_prices",
        ["company_id", "date"],
    )


def downgrade() -> None:
    op.drop_table("daily_prices")
    op.drop_table("data_sources")
    op.drop_table("companies")

    postgresql.ENUM(name="data_source_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="company_status").drop(op.get_bind(), checkfirst=True)
