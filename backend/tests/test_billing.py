"""Billing service + API (zborsa plan Task 10).

Covers the plan's Review Focus #5: a forged webhook must be rejected
BEFORE any entitlement mutation, and replayed events must be rejected.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.billing.entitlements import PlanTier
from app.billing.manual_provider import ManualPaymentProvider
from app.billing.provider import PaymentProviderSignatureError
from app.billing.service import BillingService, QuotaExceeded
from app.core.config import settings
from app.models.billing import Subscription, SubscriptionStatus, UsageCounter

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.market import Company


def _sign(body: bytes, secret: str | None = None) -> str:
    return hmac.new(
        (secret or settings.BILLING_WEBHOOK_SECRET).encode(), body, hashlib.sha256
    ).hexdigest()


def _event_body(event_id: str, subscription_id: str, event_type: str) -> bytes:
    return json.dumps(
        {"event_id": event_id, "subscription_id": subscription_id, "type": event_type}
    ).encode("utf-8")


@pytest_asyncio.fixture
async def free_subscription(db_session: AsyncSession) -> Subscription:
    today = date.today()
    sub = Subscription(
        user_key="hook-user",
        tier=PlanTier.FREE,
        status=SubscriptionStatus.ACTIVE,
        period_start=today,
        period_end=today + timedelta(days=30),
        created_at=datetime.now(UTC),
    )
    db_session.add(sub)  # type: ignore[arg-type]
    await db_session.flush()
    return sub


# ---- model/service level -------------------------------------------------


class TestSubscriptionFor:
    async def test_creates_free_row_on_miss(self, db_session: AsyncSession) -> None:
        svc = BillingService(db_session)
        sub = await svc.subscription_for("fresh-user")
        assert sub.tier == PlanTier.FREE
        assert sub.status == SubscriptionStatus.ACTIVE

    async def test_same_user_key_is_idempotent(self, db_session: AsyncSession) -> None:
        svc = BillingService(db_session)
        first = await svc.subscription_for("same-user")
        second = await svc.subscription_for("same-user")
        assert first.id == second.id


class TestQuota:
    async def test_free_stance_quota_cut_on_fourth_of_day(
        self, db_session: AsyncSession
    ) -> None:
        svc = BillingService(db_session)
        for _ in range(3):
            await svc.assert_quota("quota-user", "stance")
        with pytest.raises(QuotaExceeded) as exc:
            await svc.assert_quota("quota-user", "stance")
        assert exc.value.quota == 3
        assert exc.value.tier == "free"
        # the rejected call must not have consumed a slot
        result = await db_session.execute(
            select(UsageCounter).where(UsageCounter.user_key == "quota-user")
        )
        counter = result.scalar_one()
        assert counter.view_counter == 3

    async def test_free_radar_quota_cut_on_second(self, db_session: AsyncSession) -> None:
        svc = BillingService(db_session)
        await svc.assert_quota("radar-user", "radar")
        with pytest.raises(QuotaExceeded) as exc:
            await svc.assert_quota("radar-user", "radar")
        assert exc.value.quota == 1

    async def test_unknown_kind_gets_default_quota(self, db_session: AsyncSession) -> None:
        svc = BillingService(db_session)
        # default quota 10_000 — must not raise on the first call
        await svc.assert_quota("other-user", "misc")
        result = await db_session.execute(
            select(UsageCounter).where(UsageCounter.user_key == "other-user")
        )
        counter = result.scalar_one()
        assert counter.view_counter == 1

    async def test_canceled_sub_drops_to_free_quota_immediately(
        self, db_session: AsyncSession
    ) -> None:
        today = date.today()
        sub = Subscription(
            user_key="canceled-user",
            tier=PlanTier.PRO,
            status=SubscriptionStatus.CANCELED,
            period_start=today,
            period_end=today + timedelta(days=30),
            created_at=datetime.now(UTC),
        )
        db_session.add(sub)  # type: ignore[arg-type]
        await db_session.flush()
        svc = BillingService(db_session)
        # PRO quotas would allow 10k/day — the canceled row drops to FREE (3)
        await svc.assert_quota("canceled-user", "stance")
        await svc.assert_quota("canceled-user", "stance")
        await svc.assert_quota("canceled-user", "stance")
        with pytest.raises(QuotaExceeded) as exc:
            await svc.assert_quota("canceled-user", "stance")
        assert exc.value.quota == 3


class TestWebhookForgery:
    async def test_missing_signature_rejected_and_row_unchanged(
        self, db_session: AsyncSession, free_subscription: Subscription
    ) -> None:
        svc = BillingService(db_session)
        body = _event_body("evt-missing", str(free_subscription.id), "paid")
        with pytest.raises(PaymentProviderSignatureError):
            await svc.handle_webhook(body, None)
        await db_session.refresh(free_subscription)
        assert free_subscription.tier == PlanTier.FREE  # unchanged

    async def test_bad_signature_rejected_and_row_unchanged(
        self, db_session: AsyncSession, free_subscription: Subscription
    ) -> None:
        svc = BillingService(db_session)
        body = _event_body("evt-bad", str(free_subscription.id), "paid")
        with pytest.raises(PaymentProviderSignatureError):
            await svc.handle_webhook(body, "0" * 64)
        await db_session.refresh(free_subscription)
        assert free_subscription.tier == PlanTier.FREE  # unchanged

    async def test_paid_event_upgrades_subscription(
        self, db_session: AsyncSession, free_subscription: Subscription
    ) -> None:
        svc = BillingService(db_session)
        body = _event_body("evt-paid-1", str(free_subscription.id), "paid")
        await svc.handle_webhook(body, _sign(body))
        await db_session.refresh(free_subscription)
        assert free_subscription.tier == PlanTier.PRO
        assert free_subscription.status == SubscriptionStatus.ACTIVE

    async def test_replayed_event_rejected(
        self, db_session: AsyncSession, free_subscription: Subscription
    ) -> None:
        svc = BillingService(db_session)
        body = _event_body("evt-replay", str(free_subscription.id), "paid")
        await svc.handle_webhook(body, _sign(body))
        with pytest.raises(PaymentProviderSignatureError, match="replayed"):
            await svc.handle_webhook(body, _sign(body))


class TestManualProvider:
    def test_checkout_has_no_url_collects_no_funds(self) -> None:
        provider = ManualPaymentProvider(secret="k")
        checkout = provider.create_checkout(object(), object())
        assert checkout.url is None
        assert checkout.provider == "manual"
        assert checkout.external_id is not None

    def test_verify_rejects_bad_type(self) -> None:
        provider = ManualPaymentProvider(secret="k")
        body = _event_body("evt-t", "sub-x", "unlocked")
        with pytest.raises(PaymentProviderSignatureError):
            provider.verify_webhook(body, _sign(body, "k"))


# ---- API level ------------------------------------------------------------


class TestBillingApi:
    async def test_plans_endpoint_exact_entitlements(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        # gate DB seeds exactly free/pro/max (migration 020 idempotent seeds)
        res = await client.get("/api/billing/plans")
        assert res.status_code == 200
        plans = res.json()
        tiers = {p["tier"] for p in plans}
        assert tiers == {"free", "pro", "max"}
        free = next(p for p in plans if p["tier"] == "free")
        assert free["entitlements"] == {
            "daily_stance_quota": 3,
            "daily_radar": 1,
            "company_hub_full": False,
        }
        assert free["active"] is True
        assert {p["tier"]: p["id"] is not None for p in plans} == {
            "free": True,
            "pro": True,
            "max": True,
        }

    async def test_checkout_free_no_url(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        res = await client.post("/api/billing/checkout?user_key=co-user&tier=free")
        assert res.status_code == 200
        body = res.json()
        assert body["provider"] == "manual"
        assert body["url"] is None
        assert body["external_id"] is not None

    async def test_checkout_unknown_tier_404(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        res = await client.post("/api/billing/checkout?user_key=co-user&tier=bogus")
        assert res.status_code == 404

    async def test_webhook_missing_signature_401_subscription_unchanged(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        free_subscription: Subscription,
    ) -> None:
        body = _event_body("evt-api-missing", str(free_subscription.id), "paid")
        res = await client.post("/api/billing/webhooks/manual", content=body)
        assert res.status_code == 401
        await db_session.refresh(free_subscription)
        assert free_subscription.tier == PlanTier.FREE

    async def test_webhook_bad_signature_401_subscription_unchanged(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        free_subscription: Subscription,
    ) -> None:
        body = _event_body("evt-api-bad", str(free_subscription.id), "paid")
        res = await client.post(
            "/api/billing/webhooks/manual", content=body, headers={"X-Signature": "0" * 64}
        )
        assert res.status_code == 401
        await db_session.refresh(free_subscription)
        assert free_subscription.tier == PlanTier.FREE

    async def test_webhook_paid_flow_end_to_end(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        free_subscription: Subscription,
    ) -> None:
        body = _event_body("evt-api-paid", str(free_subscription.id), "paid")
        res = await client.post(
            "/api/billing/webhooks/manual",
            content=body,
            headers={"X-Signature": _sign(body)},
        )
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}
        await db_session.refresh(free_subscription)
        assert free_subscription.tier == PlanTier.PRO

    async def test_webhook_replayed_event_401(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        free_subscription: Subscription,
    ) -> None:
        body = _event_body("evt-api-replay", str(free_subscription.id), "paid")
        first = await client.post(
            "/api/billing/webhooks/manual",
            content=body,
            headers={"X-Signature": _sign(body)},
        )
        assert first.status_code == 200
        replay = await client.post(
            "/api/billing/webhooks/manual",
            content=body,
            headers={"X-Signature": _sign(body)},
        )
        assert replay.status_code == 401

    async def test_me_endpoint_shape(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        res = await client.get("/api/billing/me?user_key=me-user")
        assert res.status_code == 200
        body = res.json()
        assert body["user_key"] == "me-user"
        assert body["tier"] == "free"
        assert body["status"] == "active"
        assert body["period_start"] and body["period_end"]


# ---- quota enforcement flows through the stance endpoints ------------------


class TestQuotaEnforcementViaStance:
    async def test_fourth_stance_request_is_429_exact_body(
        self, client: AsyncClient, test_company: Company, db_session: AsyncSession
    ) -> None:
        url = f"/api/stance/companies/{test_company.ticker}?user_key=st-user"
        for _ in range(3):
            (await client.get(url)).raise_for_status()
        fourth = await client.get(url)
        assert fourth.status_code == 429
        assert fourth.json()["detail"] == {
            "error": "QUOTA_EXCEEDED",
            "quota": 3,
            "tier": "free",
        }

    async def test_stance_without_user_key_is_not_quota_gated(
        self, client: AsyncClient, test_company: Company, db_session: AsyncSession
    ) -> None:
        # no user_key sent -> no billing call; server-side gate only pays off
        # when the client identifies itself (spec: entitlements are per user_key)
        res = await client.get(f"/api/stance/companies/{test_company.ticker}")
        assert res.status_code == 200

    async def test_radar_quota_cut_on_second(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        url = "/api/stance/radar?page_size=50&user_key=rd-user"
        first = await client.get(url)
        assert first.status_code == 200
        second = await client.get(url)
        assert second.status_code == 429
        assert second.json()["detail"] == {
            "error": "QUOTA_EXCEEDED",
            "quota": 1,
            "tier": "free",
        }


# ---- plan seeds table contract -------------------------------------------


class TestPlanSeeds:
    async def test_all_three_tiers_seeded(self, client: AsyncClient) -> None:
        res = await client.get("/api/billing/plans")
        tiers = sorted(p["tier"] for p in res.json())
        assert tiers == ["free", "max", "pro"]
        by_tier = {p["tier"]: p for p in res.json()}
        pro_price = float(by_tier["pro"]["price_egp"])
        max_price = float(by_tier["max"]["price_egp"])
        assert pro_price > 0 and max_price > pro_price
