"""Validate a provider key with one minimal model call before it is saved ("Test & save")."""

import logging
from dataclasses import dataclass

from app.ai.catalog import KEY_TEST_MODEL
from app.ai.constants import KEY_TEST_MAX_TOKENS
from app.ai.gateway.base import ChatMessage, ChatProvider, Done, ProviderError
from app.ai.prompts import KEY_TEST_PROMPT

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KeyCheck:
    """``rejected`` = the provider refused the key; ``error`` = we could not tell (try again)."""

    outcome: str  # "ok" | "rejected" | "error"
    detail: str


async def check_key(provider_impl: ChatProvider, provider: str, api_key: str) -> KeyCheck:
    model = KEY_TEST_MODEL[provider]
    try:
        async for event in provider_impl.stream(
            model,
            api_key,
            [ChatMessage("user", KEY_TEST_PROMPT)],
            [],
            KEY_TEST_MAX_TOKENS,
        ):
            if isinstance(event, Done):
                break
    except ProviderError as exc:
        logger.info("key check for %s failed: code=%s", provider, exc.code)
        if exc.code in ("auth", "bad_request"):
            return KeyCheck("rejected", "The provider refused this key.")
        return KeyCheck("error", "Could not reach the provider to check the key. Try again.")
    return KeyCheck("ok", "The key works.")
