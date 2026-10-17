"""DEV/TEST ONLY payment provider. Collects no real funds."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from typing import Any

from app.billing.provider import (
    Checkout,
    PaymentProviderSignatureError,
    WebhookEvent,
)
from app.core.config import settings


class ManualPaymentProvider:
    """HMAC-SHA256 based manual/test provider. NOT production."""

    def __init__(self, secret: str | None = None) -> None:
        self.secret = (secret or settings.BILLING_WEBHOOK_SECRET).encode()

    def create_checkout(self, subscription: Any, plan: Any) -> Checkout:
        return Checkout(url=None, provider="manual", external_id=str(uuid.uuid4()))

    def verify_webhook(self, body: bytes, signature: str | None) -> WebhookEvent:
        if not signature:
            raise PaymentProviderSignatureError("missing signature")
        expected = hmac.new(self.secret, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise PaymentProviderSignatureError("bad signature")
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as exc:  # pragma: no cover
            raise PaymentProviderSignatureError("bad body") from exc
        event_id = str(payload.get("event_id") or "")
        subscription_id = str(payload.get("subscription_id") or "")
        event_type = str(payload.get("type") or "")
        if event_type not in ("paid", "canceled"):
            raise PaymentProviderSignatureError("bad type")
        if not event_id or not subscription_id:
            raise PaymentProviderSignatureError("missing fields")
        return WebhookEvent(event_id=event_id, subscription_id=subscription_id, type=event_type)  # type: ignore[arg-type]

    def cancel(self, subscription: Any) -> None:
        return None