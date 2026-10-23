from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.entitlements import PLAN_ENTITLEMENTS
from app.billing.entitlements import PlanTier as BillingPlanTier
from app.billing.manual_provider import ManualPaymentProvider
from app.billing.provider import PaymentProviderSignatureError, WebhookEvent
from app.models.billing import (
    Plan,
    PlanTier,
    Subscription,
    SubscriptionStatus,
    UsageCounter,
    WebhookEventLog,
)


class QuotaExceeded(Exception):
    def __init__(self, quota: int, tier: str) -> None:
        self.quota = quota
        self.tier = tier
        super().__init__(f"quota exceeded: {quota}")


class BillingService:
    def __init__(self, session: AsyncSession, provider: Any | None = None) -> None:
        self.session = session
        self.provider = provider or ManualPaymentProvider()

    async def _plan(self, tier: PlanTier) -> Plan | None:
        result = await self.session.execute(select(Plan).where(Plan.tier == tier))
        return result.scalar_one_or_none()

    async def subscription_for(self, user_key: str) -> Subscription:
        result = await self.session.execute(
            select(Subscription).where(Subscription.user_key == user_key)
        )
        sub = result.scalar_one_or_none()
        if sub is not None:
            return sub
        today = date.today()
        sub = Subscription(
            user_key=user_key,
            tier=PlanTier.FREE,
            status=SubscriptionStatus.ACTIVE,
            period_start=today,
            period_end=today + timedelta(days=30),
            created_at=datetime.now(UTC),
        )
        self.session.add(sub)
        await self.session.flush()
        return sub

    def _entitlements(self, tier: PlanTier) -> Any:
        try:
            bp = BillingPlanTier(tier.value)
        except ValueError:
            bp = BillingPlanTier.FREE
        return PLAN_ENTITLEMENTS.get(bp, PLAN_ENTITLEMENTS[BillingPlanTier.FREE])

    async def assert_quota(self, user_key: str, kind: str) -> None:
        sub = await self.subscription_for(user_key)
        # canceled subscriptions drop to the FREE tier immediately — the
        # status, not the stored tier, decides the quota (plan Task 10)
        effective_tier = (
            PlanTier.FREE
            if sub.status == SubscriptionStatus.CANCELED
            else sub.tier
        )
        ent = self._entitlements(effective_tier)
        if kind == "stance":
            quota = ent.daily_stance_quota
        elif kind == "radar":
            quota = ent.daily_radar
        else:
            quota = 10_000

        today = date.today()
        result = await self.session.execute(
            select(UsageCounter).where(
                UsageCounter.user_key == user_key, UsageCounter.day == today
            )
        )
        counter = result.scalar_one_or_none()
        if counter is None:
            counter = UsageCounter(user_key=user_key, day=today, view_counter=0)
            self.session.add(counter)
            await self.session.flush()

        if counter.view_counter >= quota:
            raise QuotaExceeded(quota=quota, tier=sub.tier.value)
        counter.view_counter += 1
        await self.session.flush()

    async def handle_webhook(self, body: bytes, signature: str | None) -> None:
        event: WebhookEvent = self.provider.verify_webhook(body, signature)
        # replay protection
        existing = await self.session.execute(
            select(WebhookEventLog).where(WebhookEventLog.event_id == event.event_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise PaymentProviderSignatureError("replayed event")
        self.session.add(
            WebhookEventLog(event_id=event.event_id, received_at=datetime.now(UTC))
        )

        result = await self.session.execute(
            select(Subscription).where(Subscription.id == uuid.UUID(event.subscription_id))
        )
        sub = result.scalar_one_or_none()
        if sub is None:
            # maybe user_key? try user_key
            result = await self.session.execute(
                select(Subscription).where(Subscription.user_key == event.subscription_id)
            )
            sub = result.scalar_one_or_none()
        if sub is None:
            return
        if event.type == "paid":
            # upgrade to pro by default (manual provider does not specify plan)
            sub.status = SubscriptionStatus.ACTIVE
            sub.tier = PlanTier.PRO
        elif event.type == "canceled":
            sub.status = SubscriptionStatus.CANCELED
            sub.tier = PlanTier.FREE
        await self.session.flush()

    async def plans(self) -> list[Plan]:
        result = await self.session.execute(select(Plan).where(Plan.active.is_(True)))
        return list(result.scalars().all())
