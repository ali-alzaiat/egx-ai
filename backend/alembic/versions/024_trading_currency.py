"""Record each listing's trading currency (024, R46 C1).

``companies.currency`` is defaulted to EGP when Yahoo has no profile, so it is not a source of
truth. ``trading_currency`` is the currency Yahoo reports the price series in (NULL = not yet
checked or not reported); ``trading_currency_checked_at`` says when it was read.

Revision ID: 024
Revises: 023
Create Date: 2026-10-30
"""

import sqlalchemy as sa
from alembic import op

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("trading_currency", sa.String(3), nullable=True))
    op.add_column(
        "companies",
        sa.Column("trading_currency_checked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("companies", "trading_currency_checked_at")
    op.drop_column("companies", "trading_currency")
