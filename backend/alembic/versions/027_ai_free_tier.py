"""Free-tier providers in the AI settings (R49 A10).

A provider marked free tier has its calls stored at cost 0 and never blocked by the monthly cap,
because the provider does not charge that key (e.g. a Gemini key with billing off).

Revision ID: 027
Revises: 026
Create Date: 2026-10-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_settings",
        sa.Column(
            "free_tier_providers", ARRAY(sa.String(20)), nullable=False, server_default="{}"
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_settings", "free_tier_providers")
