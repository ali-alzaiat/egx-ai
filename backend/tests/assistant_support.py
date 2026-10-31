"""Shared helpers for the R49 assistant API tests (every test uses the fake provider)."""

from collections.abc import Sequence
from typing import Any

from httpx import AsyncClient

from app.ai.gateway.fake import FakeChatProvider, Turn
from app.ai.sse import parse_events
from app.api.assistant import get_chat_provider
from app.main import app

SECRET_KEY = "sk-proj-TOPSECRETKEYVALUE9876"


def install_provider(turns: Sequence[Turn]) -> FakeChatProvider:
    """Make every assistant request use a scripted fake provider (no network, ever)."""
    fake = FakeChatProvider(turns)
    app.dependency_overrides[get_chat_provider] = lambda: fake
    return fake


async def post_stream(
    client: AsyncClient, path: str, body: dict[str, Any]
) -> list[tuple[str, dict[str, Any]]]:
    response = await client.post(f"/api/assistant{path}", json=body)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return parse_events(response.text)


def names(events: list[tuple[str, dict[str, Any]]]) -> list[str]:
    return [name for name, _ in events]


def first(events: list[tuple[str, dict[str, Any]]], name: str) -> dict[str, Any]:
    for n, data in events:
        if n == name:
            return data
    raise AssertionError(f"no {name!r} event in {names(events)}")
