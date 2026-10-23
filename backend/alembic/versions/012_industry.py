"""Add GICS taxonomy, EGX sector mapping, peer overrides, metric profiles.

Revision ID: 012
Revises: 011
Create Date: 2026-10-10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gics_sectors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(2), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.UniqueConstraint("code", name="uq_gics_sector_code"),
    )
    op.create_index("ix_gics_sectors_code", "gics_sectors", ["code"])

    op.create_table(
        "gics_industry_groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("sector_id", UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(4), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.ForeignKeyConstraint(["sector_id"], ["gics_sectors.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("code", name="uq_gics_industry_group_code"),
    )
    op.create_index(
        "ix_gics_industry_groups_code", "gics_industry_groups", ["code"]
    )
    op.create_index(
        "ix_gics_industry_groups_sector_id", "gics_industry_groups", ["sector_id"]
    )

    op.create_table(
        "gics_industries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("group_id", UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(6), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.ForeignKeyConstraint(
            ["group_id"], ["gics_industry_groups.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("code", name="uq_gics_industry_code"),
    )
    op.create_index("ix_gics_industries_code", "gics_industries", ["code"])
    op.create_index("ix_gics_industries_group_id", "gics_industries", ["group_id"])

    op.create_table(
        "gics_sub_industries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("industry_id", UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(8), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.ForeignKeyConstraint(
            ["industry_id"], ["gics_industries.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("code", name="uq_gics_sub_industry_code"),
    )
    op.create_index("ix_gics_sub_industries_code", "gics_sub_industries", ["code"])
    op.create_index(
        "ix_gics_sub_industries_industry_id", "gics_sub_industries", ["industry_id"]
    )

    op.create_table(
        "egx_sectors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.UniqueConstraint("name", name="uq_egx_sector_name"),
    )
    op.create_index("ix_egx_sectors_name", "egx_sectors", ["name"])

    op.create_table(
        "egx_sector_gics_map",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("egx_sector_id", UUID(as_uuid=True), nullable=False),
        sa.Column("sub_industry_id", UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["egx_sector_id"], ["egx_sectors.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["sub_industry_id"], ["gics_sub_industries.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["data_sources.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "egx_sector_id", "sub_industry_id", name="uq_egx_sector_gics_map"
        ),
    )
    op.create_index(
        "ix_egx_sector_gics_map_egx_sector_id", "egx_sector_gics_map", ["egx_sector_id"]
    )
    op.create_index(
        "ix_egx_sector_gics_map_sub_industry_id",
        "egx_sector_gics_map",
        ["sub_industry_id"],
    )

    op.create_table(
        "company_peer_overrides",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", UUID(as_uuid=True), nullable=False),
        sa.Column("peer_company_ids", JSONB(), nullable=False, server_default="[]"),
        sa.Column("methodology_version", sa.String(20), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("company_id", name="uq_company_peer_override"),
    )
    op.create_index(
        "ix_company_peer_overrides_company_id", "company_peer_overrides", ["company_id"]
    )

    op.create_table(
        "industry_metric_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_key", sa.String(50), nullable=False),
        sa.Column("sub_industry_id", UUID(as_uuid=True), nullable=True),
        sa.Column("egx_sector_id", UUID(as_uuid=True), nullable=True),
        sa.Column("metric_key", sa.String(100), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("methodology_version", sa.String(20), nullable=False),
        sa.ForeignKeyConstraint(
            ["sub_industry_id"], ["gics_sub_industries.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["egx_sector_id"], ["egx_sectors.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "profile_key",
            "metric_key",
            "methodology_version",
            name="uq_industry_metric_profile",
        ),
    )
    op.create_index(
        "ix_industry_metric_profiles_profile_key",
        "industry_metric_profiles",
        ["profile_key"],
    )
    op.create_index(
        "ix_industry_metric_profiles_egx_sector_id",
        "industry_metric_profiles",
        ["egx_sector_id"],
    )
    op.create_index(
        "ix_industry_metric_profiles_sub_industry_id",
        "industry_metric_profiles",
        ["sub_industry_id"],
    )

    op.add_column(
        "companies",
        sa.Column("egx_sector_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("gics_sub_industry_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_companies_egx_sector_id",
        "companies",
        "egx_sectors",
        ["egx_sector_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_companies_gics_sub_industry_id",
        "companies",
        "gics_sub_industries",
        ["gics_sub_industry_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_companies_egx_sector_id", "companies", ["egx_sector_id"]
    )
    op.create_index(
        "ix_companies_gics_sub_industry_id", "companies", ["gics_sub_industry_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_companies_gics_sub_industry_id", table_name="companies")
    op.drop_index("ix_companies_egx_sector_id", table_name="companies")
    op.drop_constraint("fk_companies_gics_sub_industry_id", "companies", type_="foreignkey")
    op.drop_constraint("fk_companies_egx_sector_id", "companies", type_="foreignkey")
    op.drop_column("companies", "gics_sub_industry_id")
    op.drop_column("companies", "egx_sector_id")

    op.drop_index(
        "ix_industry_metric_profiles_sub_industry_id",
        table_name="industry_metric_profiles",
    )
    op.drop_index(
        "ix_industry_metric_profiles_egx_sector_id",
        table_name="industry_metric_profiles",
    )
    op.drop_index(
        "ix_industry_metric_profiles_profile_key",
        table_name="industry_metric_profiles",
    )
    op.drop_table("industry_metric_profiles")

    op.drop_index(
        "ix_company_peer_overrides_company_id", table_name="company_peer_overrides"
    )
    op.drop_table("company_peer_overrides")

    op.drop_index(
        "ix_egx_sector_gics_map_sub_industry_id", table_name="egx_sector_gics_map"
    )
    op.drop_index(
        "ix_egx_sector_gics_map_egx_sector_id", table_name="egx_sector_gics_map"
    )
    op.drop_table("egx_sector_gics_map")

    op.drop_index("ix_egx_sectors_name", table_name="egx_sectors")
    op.drop_table("egx_sectors")

    op.drop_index(
        "ix_gics_sub_industries_industry_id", table_name="gics_sub_industries"
    )
    op.drop_index("ix_gics_sub_industries_code", table_name="gics_sub_industries")
    op.drop_table("gics_sub_industries")

    op.drop_index("ix_gics_industries_group_id", table_name="gics_industries")
    op.drop_index("ix_gics_industries_code", table_name="gics_industries")
    op.drop_table("gics_industries")

    op.drop_index(
        "ix_gics_industry_groups_sector_id", table_name="gics_industry_groups"
    )
    op.drop_index("ix_gics_industry_groups_code", table_name="gics_industry_groups")
    op.drop_table("gics_industry_groups")

    op.drop_index("ix_gics_sectors_code", table_name="gics_sectors")
    op.drop_table("gics_sectors")
