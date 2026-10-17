"""Billing, plans, subscriptions and usage counters (migration 020).

Revision ID: 020
Revises: 019
Create Date: 2026-10-17
"""

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None

_PLANS = [
    ("free", 0, {"daily_stance_quota": 3, "daily_radar": 1, "company_hub_full": False}),
    ("pro", 199, {"daily_stance_quota": 10000, "daily_radar": 100000, "company_hub_full": True}),
    ("max", 399, {"daily_stance_quota": 10000, "daily_radar": 100000, "company_hub_full": True}),
]


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tier",
            sa.Enum("free", "pro", "max", name="plan_tier", create_constraint=True),
            nullable=False,
            unique=True,
        ),
        sa.Column("price_egp", sa.Numeric(10, 2), nullable=False),
        sa.Column("entitlements", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_key", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "tier",
            sa.Enum("free", "pro", "max", name="plan_tier", create_constraint=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("active", "canceled", name="subscription_status", create_constraint=True),
            nullable=False,
            server_default="active",
        ),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "usage_counters",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_key", sa.String(64), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("view_counter", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("user_key", "day", name="uq_billing_user_key_day"),
    )
    op.create_table(
        "billing_webhook_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", sa.String(128), nullable=False, unique=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    bind = op.get_bind()
    for tier, price, entitlements in _PLANS:
        bind.execute(
            sa.text(
                "INSERT INTO plans (id, tier, price_egp, entitlements, active) "
                "VALUES (:id, :tier, :price, CAST(:entitlements AS jsonb), true) "
                "ON CONFLICT (tier) DO NOTHING"
            ),
            {"id": uuid.uuid4(), "tier": tier, "price": price, "entitlements": __import__("json").dumps(entitlements)},
        )


def downgrade() -> None:
    op.drop_table("billing_webhook_events")
    op.drop_table("usage_counters")
    op.drop_table("subscriptions")
    op.drop_table("plans")
    sa.Enum(name="subscription_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="plan_tier").drop(op.get_bind(), checkfirst=True)