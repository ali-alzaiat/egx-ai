"""Allow Shariah screening results that lack sufficient data.

Revision ID: 010
Revises: 009
Create Date: 2026-10-08
"""

import sqlalchemy as sa
from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # is_compliant may be NULL when status is INSUFFICIENT_DATA (tri-state).
    op.alter_column(
        "shariah_screening_results",
        "is_compliant",
        existing_type=sa.Boolean(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "shariah_screening_results",
        "is_compliant",
        existing_type=sa.Boolean(),
        nullable=False,
    )
