"""Billing and entitlement models (migration 020)."""

import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Enum, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlanTier(enum.StrEnum):
    FREE = "free"
    PRO = "pro"
    MAX = "max"


class SubscriptionStatus(enum.StrEnum):
    ACTIVE = "active"
    CANCELED = "canceled"


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tier: Mapped[PlanTier] = mapped_column(
        Enum(
            PlanTier,
            name="plan_tier",
            create_constraint=True,
            # DB enum stores the lowercase VALUES; SQLAlchemy defaults to
            # member NAMES — bridge it (same pattern as Event.type).
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        unique=True,
    )
    price_egp: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    entitlements: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    tier: Mapped[PlanTier] = mapped_column(
        Enum(
            PlanTier,
            name="plan_tier",
            create_constraint=True,
            # DB enum stores the lowercase VALUES; SQLAlchemy defaults to
            # member NAMES — bridge it (same pattern as Plan.tier above).
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(
            SubscriptionStatus,
            name="subscription_status",
            create_constraint=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UsageCounter(Base):
    __tablename__ = "usage_counters"
    __table_args__ = (UniqueConstraint("user_key", "day", name="uq_billing_user_key_day"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_key: Mapped[str] = mapped_column(String(64), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    view_counter: Mapped[int] = mapped_column(nullable=False, default=0)


class WebhookEventLog(Base):
    __tablename__ = "billing_webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
