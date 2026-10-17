from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


class PaymentProviderSignatureError(Exception):
    """Raised when a webhook signature cannot be verified."""


@dataclass
class Checkout:
    url: str | None
    provider: str
    external_id: str | None


@dataclass
class WebhookEvent:
    event_id: str
    subscription_id: str
    type: Literal["paid", "canceled"]


class PaymentProviderAdapter(Protocol):
    def create_checkout(self, subscription: object, plan: object) -> Checkout: ...

    def verify_webhook(self, body: bytes, signature: str | None) -> WebhookEvent: ...

    def cancel(self, subscription: object) -> None: ...