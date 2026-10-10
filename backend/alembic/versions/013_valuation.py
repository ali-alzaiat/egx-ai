"""Add industry valuation profiles + fair-value snapshots.

Revision ID: 013
Revises: 012
Create Date: 2026-10-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "industry_valuation_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_key", sa.String(50), nullable=False),
        sa.Column("sub_industry_id", UUID(as_uuid=True), nullable=True),
        sa.Column("egx_sector_id", UUID(as_uuid=True), nullable=True),
        sa.Column("primary_model", sa.String(50), nullable=False),
        sa.Column("fallback_model", sa.String(50), nullable=False),
        sa.Column("preferred_multiple", sa.String(10), nullable=False),
        sa.Column("methodology_version", sa.String(20), nullable=False),
        sa.ForeignKeyConstraint(
            ["sub_industry_id"], ["gics_sub_industries.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["egx_sector_id"], ["egx_sectors.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "profile_key",
            "methodology_version",
            name="uq_industry_valuation_profile",
        ),
    )
    op.create_index(
        "ix_industry_valuation_profiles_profile_key",
        "industry_valuation_profiles",
        ["profile_key"],
    )
    op.create_index(
        "ix_industry_valuation_profiles_egx_sector_id",
        "industry_valuation_profiles",
        ["egx_sector_id"],
    )
    op.create_index(
        "ix_industry_valuation_profiles_sub_industry_id",
        "industry_valuation_profiles",
        ["sub_industry_id"],
    )

    op.create_table(
        "valuation_fair_values",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("profile_key", sa.String(50), nullable=False),
        sa.Column("methodology_version", sa.String(20), nullable=False),
        sa.Column("fair_value", sa.Numeric(20, 4), nullable=True),
        sa.Column("fair_value_status", sa.String(20), nullable=False),
        sa.Column("legs", JSONB(), nullable=False, server_default="{}"),
        sa.Column("weights", JSONB(), nullable=False, server_default="{}"),
        sa.Column("scenarios", JSONB(), nullable=False, server_default="{}"),
        sa.Column("sensitivity", JSONB(), nullable=False, server_default="[]"),
        sa.Column("confidence", JSONB(), nullable=False, server_default="{}"),
        sa.Column("verdict", JSONB(), nullable=False, server_default="{}"),
        sa.Column("inputs_echo", JSONB(), nullable=False, server_default="{}"),
        sa.Column("current_price", sa.Numeric(20, 4), nullable=True),
        sa.Column("price_as_of", sa.Date(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "company_id", "methodology_version", name="uq_valuation_fair_value"
        ),
    )
    op.create_index(
        "ix_valuation_fair_values_company_id", "valuation_fair_values", ["company_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_valuation_fair_values_company_id", table_name="valuation_fair_values"
    )
    op.drop_table("valuation_fair_values")

    op.drop_index(
        "ix_industry_valuation_profiles_sub_industry_id",
        table_name="industry_valuation_profiles",
    )
    op.drop_index(
        "ix_industry_valuation_profiles_egx_sector_id",
        table_name="industry_valuation_profiles",
    )
    op.drop_index(
        "ix_industry_valuation_profiles_profile_key",
        table_name="industry_valuation_profiles",
    )
    op.drop_table("industry_valuation_profiles")
