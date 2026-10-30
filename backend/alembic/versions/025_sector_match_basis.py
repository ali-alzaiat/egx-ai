"""Record how each company's EGX sector was matched (025, R47 S1).

``companies.sector_match_basis`` is one of ``sector_index_reuters`` (EGX sector-index page joined
on the Reuters code), ``alias`` (a reviewed ticker alias) or ``name_review`` (a human name match
against the EGX listed-stocks page). NULL = no sector assigned.

Revision ID: 025
Revises: 024
Create Date: 2026-10-30
"""

import sqlalchemy as sa
from alembic import op

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("sector_match_basis", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "sector_match_basis")
