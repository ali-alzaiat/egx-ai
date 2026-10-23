"""Drop billing tables; billing is removed from the product for now (migration 021).

Revision ID: 021
Revises: 020
Create Date: 2026-10-23
"""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("billing_webhook_events")
    op.drop_table("usage_counters")
    op.drop_table("subscriptions")
    op.drop_table("plans")
    sa.Enum(name="subscription_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="plan_tier").drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    # Recreate exactly what 020 built (tables + seeded plans) from its own source.
    spec = importlib.util.spec_from_file_location(
        "migration_020", Path(__file__).with_name("020_billing.py")
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.upgrade()
