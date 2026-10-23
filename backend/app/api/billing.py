"""Billing API (manual/test provider only)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.manual_provider import ManualPaymentProvider
from app.billing.provider import PaymentProviderSignatureError
from app.billing.service import BillingService
from app.db.session import get_session
from app.models.billing import Plan, PlanTier

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/plans")
async def list_plans(session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    service = BillingService(session)
    plans = await service.plans()
    return [
        {
            "id": str(p.id),
            "tier": p.tier.value,
            "price_egp": str(p.price_egp),
            "entitlements": p.entitlements,
            "active": p.active,
        }
        for p in plans
    ]


@router.post("/checkout")
async def checkout(
    user_key: str = Query(...),
    tier: str = Query("pro"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = BillingService(session)
    sub = await service.subscription_for(user_key)
    # manual provider: no real checkout URL
    provider = ManualPaymentProvider()
    try:
        tier_enum = PlanTier(tier)
    except ValueError as exc:
        # unknown tier is a client error, not a server error (pricing page
        # sends user-selected tiers; a 404 keeps the honest no-provider path)
        raise HTTPException(status_code=404, detail="plan not found") from exc
    plan = await session.execute(select(Plan).where(Plan.tier == tier_enum))
    plan_row = plan.scalar_one_or_none()
    if plan_row is None:
        raise HTTPException(status_code=404, detail="plan not found")
    checkout = provider.create_checkout(sub, plan_row)
    return {
        "provider": checkout.provider,
        "url": checkout.url,
        "external_id": checkout.external_id,
    }


@router.post("/webhooks/manual")
async def webhook_manual(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    body = await request.body()
    signature = request.headers.get("X-Signature")
    service = BillingService(session)
    try:
        await service.handle_webhook(body, signature)
    except PaymentProviderSignatureError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
        raise
    await session.commit()
    return {"status": "ok"}


@router.get("/me")
async def me(
    user_key: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    service = BillingService(session)
    sub = await service.subscription_for(user_key)
    return {
        "user_key": sub.user_key,
        "tier": sub.tier.value,
        "status": sub.status.value,
        "period_start": sub.period_start.isoformat(),
        "period_end": sub.period_end.isoformat(),
    }
