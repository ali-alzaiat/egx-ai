"""Add industry score profiles + investment-score snapshots.

Revision ID: 014
Revises: 013
Create Date: 2026-10-10
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "industry_score_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_key", sa.String(50), nullable=False),
        sa.Column("sub_industry_id", UUID(as_uuid=True), nullable=True),
        sa.Column("egx_sector_id", UUID(as_uuid=True), nullable=True),
        sa.Column("health_track", sa.String(20), nullable=False),
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
            name="uq_industry_score_profile",
        ),
    )
    op.create_index(
        "ix_industry_score_profiles_profile_key",
        "industry_score_profiles",
        ["profile_key"],
    )
    op.create_index(
        "ix_industry_score_profiles_egx_sector_id",
        "industry_score_profiles",
        ["egx_sector_id"],
    )
    op.create_index(
        "ix_industry_score_profiles_sub_industry_id",
        "industry_score_profiles",
        ["sub_industry_id"],
    )

    op.create_table(
        "investment_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("profile_key", sa.String(50), nullable=False),
        sa.Column("methodology_version", sa.String(20), nullable=False),
        sa.Column("headline", sa.Numeric(20, 4), nullable=True),
        sa.Column("headline_status", sa.String(20), nullable=False),
        sa.Column("components", JSONB(), nullable=False, server_default="{}"),
        sa.Column("checks", JSONB(), nullable=False, server_default="[]"),
        sa.Column("confidence", JSONB(), nullable=False, server_default="{}"),
        sa.Column("buy_zone", JSONB(), nullable=False, server_default="{}"),
        sa.Column("n_with_data", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("margin_of_safety", sa.Numeric(10, 4), nullable=True),
        sa.Column("inputs_echo", JSONB(), nullable=False, server_default="{}"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "company_id", "methodology_version", name="uq_investment_score"
        ),
    )
    op.create_index(
        "ix_investment_scores_company_id", "investment_scores", ["company_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_investment_scores_company_id", table_name="investment_scores")
    op.drop_table("investment_scores")

    op.drop_index(
        "ix_industry_score_profiles_sub_industry_id",
        table_name="industry_score_profiles",
    )
    op.drop_index(
        "ix_industry_score_profiles_egx_sector_id",
        table_name="industry_score_profiles",
    )
    op.drop_index(
        "ix_industry_score_profiles_profile_key",
        table_name="industry_score_profiles",
    )
    op.drop_table("industry_score_profiles")
