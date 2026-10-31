"""R49 assistant API: settings, keys, safeguards, chat/explain streams, conversations."""

import logging
import uuid
from collections.abc import Iterator
from decimal import Decimal

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.gateway.base import ProviderError, ToolCall
from app.ai.gateway.fake import text_turn, tool_turn
from app.ai.sse import parse_events
from app.core.config import settings
from app.main import app
from app.models.assistant import AiMessage, AiProviderKey
from app.models.market import Company
from assistant_support import SECRET_KEY, first, install_provider, names, post_stream
from statement_seed import make_company, seed_prices


@pytest.fixture(autouse=True)
def assistant_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A clean slate: a fresh secrets key and no provider keys from the developer's .env."""
    monkeypatch.setattr(settings, "AI_SECRETS_KEY", Fernet.generate_key().decode())
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setattr(settings, name, "")
    yield


@pytest.fixture(autouse=True)
def no_network(assistant_env: None) -> None:
    """Default provider: a fake with an empty script, so a test that forgets to install its own
    fails loudly instead of ever reaching a real model."""
    install_provider([])


@pytest.fixture
def env_key(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", SECRET_KEY)
    return SECRET_KEY


@pytest.fixture
async def company(db_session: AsyncSession) -> Company:
    co = await make_company(db_session, sector="Banks")
    await seed_prices(db_session, co)  # last close 31.9
    return co


def _all_text(*responses: object) -> str:
    return " ".join(getattr(r, "text", str(r)) for r in responses)


# -- models, settings -----------------------------------------------------------------------


async def test_endpoints_require_the_api_token(anon_client: AsyncClient) -> None:
    assert (await anon_client.get("/api/assistant/models")).status_code == 401
    assert (await anon_client.post("/api/assistant/chat", json={"message": "x"})).status_code == 401


async def test_models_and_settings_with_no_key(client: AsyncClient) -> None:
    models = await client.get("/api/assistant/models")
    assert models.status_code == 200
    body = models.json()
    assert body["default_model"] is None
    assert {m["provider"] for m in body["models"]} == {"anthropic", "openai", "gemini"}
    assert not any(m["available"] for m in body["models"])
    assert models.headers["cache-control"] == "no-store"

    cfg = (await client.get("/api/assistant/settings")).json()
    assert cfg["secrets_key_set"] is True
    assert cfg["monthly_cap_usd"] is None and Decimal(cfg["month_spend_usd"]) == 0
    assert [p["provider"] for p in cfg["providers"]] == ["anthropic", "openai", "gemini"]
    assert all(not p["configured"] and p["source"] is None for p in cfg["providers"])


async def test_env_key_makes_provider_models_available(client: AsyncClient, env_key: str) -> None:
    body = (await client.get("/api/assistant/models")).json()
    available = {m["id"] for m in body["models"] if m["available"]}
    assert available == {"claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-4-5"}
    assert body["default_model"] == "claude-sonnet-5-5"
    cfg = await client.get("/api/assistant/settings")
    anthropic = cfg.json()["providers"][0]
    assert anthropic["source"] == "env" and anthropic["last4"] == SECRET_KEY[-4:]
    assert SECRET_KEY not in cfg.text


async def test_put_settings_validates_and_persists(client: AsyncClient, env_key: str) -> None:
    bad_model = await client.put("/api/assistant/settings", json={"default_model": "gpt-9"})
    assert bad_model.status_code == 422
    negative = await client.put("/api/assistant/settings", json={"monthly_cap_usd": "-1"})
    assert negative.status_code == 422

    ok = await client.put(
        "/api/assistant/settings",
        json={"default_model": "claude-opus-5-5", "monthly_cap_usd": "12.50"},
    )
    assert ok.status_code == 200 and ok.headers["cache-control"] == "no-store"
    assert ok.json()["default_model"] == "claude-opus-5-5"
    assert ok.json()["monthly_cap_usd"] == "12.5"  # no column padding ("12.5000")
    zero = await client.put("/api/assistant/settings", json={"monthly_cap_usd": "0"})
    assert zero.json()["monthly_cap_usd"] == "0"
    ok = await client.put("/api/assistant/settings", json={"monthly_cap_usd": "12.50"})
    assert (await client.get("/api/assistant/models")).json()["default_model"] == "claude-opus-5-5"

    # Leaving a field out keeps it; null clears the cap.
    kept = await client.put("/api/assistant/settings", json={"default_model": "claude-haiku-4-5"})
    assert Decimal(kept.json()["monthly_cap_usd"]) == Decimal("12.5")
    cleared = await client.put("/api/assistant/settings", json={"monthly_cap_usd": None})
    assert cleared.json()["monthly_cap_usd"] is None
    assert cleared.json()["default_model"] == "claude-haiku-4-5"


# -- keys ------------------------------------------------------------------------------------


async def test_save_key_encrypts_it_and_never_returns_it(
    client: AsyncClient, db_session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    fake = install_provider([text_turn("ok")])
    caplog.set_level(logging.DEBUG)
    saved = await client.put("/api/assistant/keys/openai", json={"api_key": f"  {SECRET_KEY} "})
    assert saved.status_code == 200
    row = saved.json()
    assert row["provider"] == "openai" and row["source"] == "ui" and row["configured"] is True
    assert row["last4"] == SECRET_KEY[-4:] and row["set_at"]
    assert saved.headers["cache-control"] == "no-store"
    # One minimal call tested the key before it was saved.
    assert len(fake.calls) == 1 and fake.calls[0].api_key == SECRET_KEY
    assert fake.calls[0].max_tokens <= 16 and fake.calls[0].tools == []

    stored = (await db_session.execute(select(AiProviderKey))).scalar_one()
    assert SECRET_KEY not in stored.ciphertext and stored.last4 == SECRET_KEY[-4:]

    everything = [
        saved,
        await client.get("/api/assistant/settings"),
        await client.get("/api/assistant/models"),
    ]
    assert SECRET_KEY not in _all_text(*everything)
    assert SECRET_KEY not in caplog.text
    models = everything[2].json()
    assert {m["id"] for m in models["models"] if m["available"]} == {"gpt-5.5", "gpt-5.4-mini"}

    removed = await client.delete("/api/assistant/keys/openai")
    assert removed.status_code == 200 and removed.json()["configured"] is False
    assert SECRET_KEY not in removed.text


async def test_save_key_fails_closed_without_secrets_key(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession
) -> None:
    monkeypatch.setattr(settings, "AI_SECRETS_KEY", "")
    fake = install_provider([text_turn("ok")])
    resp = await client.put("/api/assistant/keys/anthropic", json={"api_key": SECRET_KEY})
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "AI_SECRETS_KEY_MISSING"
    assert SECRET_KEY not in resp.text
    assert fake.calls == []  # not even tested
    assert (await db_session.execute(select(func.count()).select_from(AiProviderKey))).scalar() == 0
    cfg = (await client.get("/api/assistant/settings")).json()
    assert cfg["secrets_key_set"] is False

    # .env keys keep working without the secrets key.
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "AIzaEnvKeyValue0001")
    models = (await client.get("/api/assistant/models")).json()["models"]
    assert any(m["available"] and m["provider"] == "gemini" for m in models)


async def test_rejected_key_is_not_saved_and_not_leaked(
    client: AsyncClient, db_session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    install_provider([ProviderError("auth", f"Incorrect API key provided: {SECRET_KEY}")])
    caplog.set_level(logging.DEBUG)
    resp = await client.put("/api/assistant/keys/openai", json={"api_key": SECRET_KEY})
    assert resp.status_code == 422 and resp.json()["detail"]["code"] == "KEY_REJECTED"
    assert SECRET_KEY not in resp.text
    assert SECRET_KEY not in caplog.text
    assert (await db_session.execute(select(func.count()).select_from(AiProviderKey))).scalar() == 0


async def test_provider_outage_during_key_check_is_not_a_rejection(client: AsyncClient) -> None:
    install_provider([ProviderError("unavailable", "down")])
    resp = await client.put("/api/assistant/keys/openai", json={"api_key": SECRET_KEY})
    assert resp.status_code == 502 and resp.json()["detail"]["code"] == "PROVIDER_ERROR"


async def test_invalid_key_body_does_not_echo_the_submitted_value(client: AsyncClient) -> None:
    install_provider([])
    resp = await client.put("/api/assistant/keys/openai", json={"api_key": "short-k"})
    assert resp.status_code == 422 and "short-k" not in resp.text
    missing = await client.put("/api/assistant/keys/openai", json={"wrong": SECRET_KEY})
    assert missing.status_code == 422 and SECRET_KEY not in missing.text
    unknown = await client.put("/api/assistant/keys/mistral", json={"api_key": SECRET_KEY})
    assert unknown.status_code == 404 and SECRET_KEY not in unknown.text


async def test_key_test_endpoint_uses_the_active_key(client: AsyncClient, env_key: str) -> None:
    fake = install_provider([text_turn("ok")])
    resp = await client.post("/api/assistant/keys/anthropic/test")
    assert resp.json()["ok"] is True and fake.calls[0].api_key == env_key
    assert env_key not in resp.text
    none = await client.post("/api/assistant/keys/openai/test")
    assert none.json()["ok"] is False and len(fake.calls) == 1


async def test_ui_key_wins_over_env_key_in_calls(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-ant-ENVENVENV0000")
    fake = install_provider([text_turn("ok"), text_turn("ok")])
    await client.put("/api/assistant/keys/anthropic", json={"api_key": SECRET_KEY})
    await client.post("/api/assistant/keys/anthropic/test")
    assert [c.api_key for c in fake.calls] == [SECRET_KEY, SECRET_KEY]
    cfg = (await client.get("/api/assistant/settings")).json()
    assert cfg["providers"][0]["source"] == "ui"
    await client.delete("/api/assistant/keys/anthropic")
    cfg = (await client.get("/api/assistant/settings")).json()
    assert cfg["providers"][0]["source"] == "env"


# -- origin and transport ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("PUT", "/api/assistant/keys/openai", {"api_key": SECRET_KEY}),
        ("DELETE", "/api/assistant/keys/openai", None),
        ("PUT", "/api/assistant/settings", {"monthly_cap_usd": "5"}),
    ],
)
async def test_foreign_origin_is_rejected_for_key_changes(
    client: AsyncClient, method: str, path: str, body: dict[str, str] | None
) -> None:
    fake = install_provider([text_turn("ok")])
    resp = await client.request(method, path, json=body, headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "ORIGIN_NOT_ALLOWED"
    assert fake.calls == []
    assert SECRET_KEY not in resp.text
    null_origin = await client.request(method, path, json=body, headers={"Origin": "null"})
    assert null_origin.status_code == 403


async def test_configured_origin_and_no_origin_are_accepted(client: AsyncClient) -> None:
    install_provider([text_turn("ok")])
    ok = await client.put(
        "/api/assistant/settings",
        json={"monthly_cap_usd": "5"},
        headers={"Origin": settings.CORS_ORIGINS[0]},
    )
    assert ok.status_code == 200
    # Reading settings is not a key change: no origin check.
    read = await client.get("/api/assistant/settings", headers={"Origin": "https://evil.example"})
    assert read.status_code == 200


async def _remote_client(base_url: str, host: str, token: str) -> AsyncClient:
    transport = ASGITransport(app=app, client=(host, 40000))
    return AsyncClient(
        transport=transport, base_url=base_url, headers={"Authorization": f"Bearer {token}"}
    )


async def test_plain_http_from_a_public_address_is_refused(
    client: AsyncClient, api_token: str, db_session: AsyncSession
) -> None:
    fake = install_provider([text_turn("ok")])
    async with await _remote_client("http://test", "8.8.8.8", api_token) as remote:
        resp = await remote.put("/api/assistant/keys/openai", json={"api_key": SECRET_KEY})
        assert resp.status_code == 403 and resp.json()["detail"]["code"] == "INSECURE_TRANSPORT"
        assert SECRET_KEY not in resp.text
        settings_resp = await remote.put("/api/assistant/settings", json={"monthly_cap_usd": "1"})
        assert settings_resp.status_code == 403
    assert fake.calls == []


@pytest.mark.parametrize(
    ("base_url", "host"),
    [
        ("https://test", "8.8.8.8"),  # HTTPS from anywhere
        ("http://test", "127.0.0.1"),  # loopback
        ("http://test", "172.18.0.5"),  # docker network
        ("http://test", "192.168.1.20"),  # private LAN
        ("http://test", "::1"),
    ],
)
async def test_https_loopback_and_private_networks_may_set_keys(
    client: AsyncClient, api_token: str, base_url: str, host: str
) -> None:
    install_provider([text_turn("ok")])
    async with await _remote_client(base_url, host, api_token) as remote:
        resp = await remote.put("/api/assistant/keys/openai", json={"api_key": SECRET_KEY})
        assert resp.status_code == 200, resp.text


# -- chat -------------------------------------------------------------------------------------


async def test_chat_streams_progress_then_a_verified_answer_and_persists(
    client: AsyncClient, env_key: str, company: Company, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    ticker = company.ticker
    fake = install_provider(
        [
            tool_turn(ToolCall("c1", "price_summary", {"ticker": ticker})),
            text_turn(f"{ticker} last closed at 31.9 (source: price_summary)."),
        ]
    )
    events = await post_stream(
        client, "/chat", {"message": "What is the latest close?", "ticker": ticker, "lang": "en"}
    )
    assert names(events) == [
        "meta",
        "status",
        "status",
        "status",
        "status",
        "answer",
        "done",
    ]
    stages = [(d["stage"], d.get("tool")) for n, d in events if n == "status"]
    assert stages == [
        ("thinking", None),
        ("tool", "price_summary"),
        ("thinking", None),
        ("verifying", None),
    ]
    meta = first(events, "meta")
    assert meta["model"] == "claude-sonnet-5-5" and meta["conversation_id"]
    assert meta["web_search"] is True  # R50: Sonnet 5.5 can search the web
    answer = first(events, "answer")
    assert answer["verified"] is True and answer["checked"] >= 1
    assert answer["general"] is False  # R50: a company-scoped answer is checked, not "general"
    assert {"tool": "price_summary", "ticker": ticker} in answer["sources"]
    assert {"tool": "company_overview", "ticker": ticker} in answer["sources"]
    done = first(events, "done")
    assert done["input_tokens"] == 200 and done["output_tokens"] == 30
    assert Decimal(done["cost_usd"]) == Decimal("0.002")
    assert Decimal(done["month_spend_usd"]) == Decimal("0.002")

    # The scoped chat put the company overview in the model's context; no key ever did.
    system_text = " ".join(m.content or "" for m in fake.calls[0].messages if m.role == "system")
    assert ticker in system_text and "company_overview" in system_text
    assert env_key not in system_text and env_key not in caplog.text
    assert {t.name for t in fake.calls[0].tools} >= {"valuation", "screen_companies"}

    # Stored conversation.
    conv_id = meta["conversation_id"]
    conv = (await client.get(f"/api/assistant/conversations/{conv_id}")).json()
    assert conv["ticker"] == ticker and conv["title"] == "What is the latest close?"
    assert [(m["role"], m["status"]) for m in conv["messages"]] == [
        ("user", "answered"),
        ("assistant", "answered"),
    ]
    assert conv["messages"][1]["content"] == answer["text"]
    assert conv["messages"][1]["verification"]["verified"] is True
    assert conv["messages"][1]["model"] == "claude-sonnet-5-5"
    listing = (await client.get("/api/assistant/conversations?limit=5")).json()
    assert listing[0]["id"] == conv_id and listing[0]["ticker"] == ticker


async def test_follow_up_message_carries_history(
    client: AsyncClient, env_key: str, company: Company
) -> None:
    fake = install_provider([text_turn("Hello, how can I help?"), text_turn("Glad to help.")])
    first_events = await post_stream(client, "/chat", {"message": "Hi there"})
    conv_id = first(first_events, "meta")["conversation_id"]
    await post_stream(client, "/chat", {"message": "Thanks", "conversation_id": conv_id})
    roles = [(m.role, m.content) for m in fake.calls[1].messages if m.role != "system"]
    assert roles == [
        ("user", "Hi there"),
        ("assistant", "Hello, how can I help?"),
        ("user", "Thanks"),
    ]
    assert len((await client.get("/api/assistant/conversations")).json()) == 1


async def test_planted_number_is_retried_and_a_clean_retry_is_shown(
    client: AsyncClient, env_key: str, company: Company
) -> None:
    ticker = company.ticker
    fake = install_provider(
        [
            tool_turn(ToolCall("c1", "price_summary", {"ticker": ticker})),
            text_turn("The close is 77.77."),
            text_turn("The close is 31.9."),
        ]
    )
    events = await post_stream(client, "/chat", {"message": "close?", "ticker": ticker})
    assert "retrying" in [d["stage"] for n, d in events if n == "status"]
    assert first(events, "answer")["text"] == "The close is 31.9."
    assert "77.77" in (fake.calls[2].messages[-1].content or "")
    assert "unverified" not in names(events)


async def test_second_failure_is_withheld_never_shown(
    client: AsyncClient, env_key: str, company: Company, db_session: AsyncSession
) -> None:
    ticker = company.ticker
    install_provider(
        [
            tool_turn(ToolCall("c1", "price_summary", {"ticker": ticker})),
            text_turn("The close is 77.77."),
            text_turn("The close is 88.88."),
        ]
    )
    response = await client.post(
        "/api/assistant/chat", json={"message": "close?", "ticker": ticker}
    )
    assert "77.77" not in response.text and "88.88" in response.text  # only listed as unverified
    events = parse_events(response.text)
    assert "answer" not in names(events)
    unverified = first(events, "unverified")
    assert unverified["unverified"] == ["88.88"]
    assert "The close is" not in response.text
    stored = (
        await db_session.execute(select(AiMessage).where(AiMessage.status == "unverified"))
    ).scalar_one()
    assert stored.content == "" and stored.verification["unverified"] == ["88.88"]


async def test_no_key_and_unknown_model_are_error_events_without_provider_calls(
    client: AsyncClient,
) -> None:
    fake = install_provider([text_turn("never")])
    events = await post_stream(client, "/chat", {"message": "hi"})
    assert names(events) == ["error", "done"]
    assert first(events, "error")["code"] == "NO_KEY"
    unknown = await post_stream(client, "/chat", {"message": "hi", "model": "gpt-9"})
    assert first(unknown, "error")["code"] == "UNKNOWN_MODEL"
    no_key_for_model = await post_stream(client, "/chat", {"message": "hi", "model": "gpt-5.5"})
    assert first(no_key_for_model, "error")["code"] == "NO_KEY"
    assert fake.calls == []
    assert (await client.get("/api/assistant/conversations")).json() == []


async def test_free_tier_provider_skips_the_cap_and_costs_nothing(
    client: AsyncClient, env_key: str, db_session: AsyncSession
) -> None:
    # A cap of 0 blocks every priced call ...
    await client.put("/api/assistant/settings", json={"monthly_cap_usd": "0"})
    blocked = install_provider([text_turn("never")])
    events = await post_stream(client, "/chat", {"message": "hello"})
    assert first(events, "error")["code"] == "CAP_REACHED"
    assert blocked.calls == []
    # ... but a free-tier provider is not charged, so its calls go through at cost 0.
    resp = await client.put(
        "/api/assistant/settings", json={"free_tier_providers": ["anthropic"]}
    )
    assert resp.status_code == 200
    rows = {p["provider"]: p["free_tier"] for p in resp.json()["providers"]}
    assert rows == {"anthropic": True, "openai": False, "gemini": False}
    assert resp.json()["monthly_cap_usd"] == "0"  # leaving the cap out keeps it
    fake = install_provider([text_turn("Hello!", cost="0.002")])
    events = await post_stream(client, "/chat", {"message": "hello"})
    assert first(events, "answer")["text"] == "Hello!"
    assert first(events, "done")["cost_usd"] == "0"
    assert len(fake.calls) == 1
    stored = (
        await db_session.execute(
            select(AiMessage).where(AiMessage.role == "assistant", AiMessage.status == "answered")
        )
    ).scalar_one()
    assert stored.cost_usd == Decimal(0)
    settings_now = (await client.get("/api/assistant/settings")).json()
    assert Decimal(settings_now["month_spend_usd"]) == 0
    bad = await client.put("/api/assistant/settings", json={"free_tier_providers": ["acme"]})
    assert bad.status_code == 422


async def test_cap_reached_stops_before_calling_the_model(
    client: AsyncClient, env_key: str, db_session: AsyncSession
) -> None:
    fake = install_provider([text_turn("never")])
    await client.put("/api/assistant/settings", json={"monthly_cap_usd": "0.01"})
    db_session.add(
        AiMessage(
            id=uuid.uuid4(),
            conversation_id=None,
            role="assistant",
            content="",
            status="answered",
            cost_usd=Decimal("0.01"),
        )
    )
    await db_session.flush()
    events = await post_stream(client, "/chat", {"message": "hello"})
    assert first(events, "error")["code"] == "CAP_REACHED"
    assert names(events)[-1] == "done"
    assert fake.calls == []
    cap_row = (
        await db_session.execute(select(AiMessage).where(AiMessage.status == "cap_reached"))
    ).scalar_one()
    assert cap_row.conversation_id is not None and cap_row.cost_usd is None
    # Raising the cap lets the next message through.
    await client.put("/api/assistant/settings", json={"monthly_cap_usd": "5"})
    fake2 = install_provider([text_turn("Hello!")])
    again = await post_stream(client, "/chat", {"message": "hello"})
    assert "answer" in names(again) and len(fake2.calls) == 1


async def test_cap_counts_cost_within_the_turn(
    client: AsyncClient, env_key: str, company: Company
) -> None:
    ticker = company.ticker
    await client.put("/api/assistant/settings", json={"monthly_cap_usd": "0.001"})
    fake = install_provider(
        [
            tool_turn(ToolCall("c1", "price_summary", {"ticker": ticker})),
            text_turn("never reached"),
        ]
    )
    events = await post_stream(client, "/chat", {"message": "close?"})
    assert first(events, "error")["code"] == "CAP_REACHED"
    assert len(fake.calls) == 1  # the second call was blocked by this turn's own spend


async def test_deleting_a_conversation_keeps_the_spend(
    client: AsyncClient, env_key: str, db_session: AsyncSession
) -> None:
    install_provider([text_turn("Hello!")])
    events = await post_stream(client, "/chat", {"message": "private question"})
    conv_id = first(events, "meta")["conversation_id"]
    before = (await client.get("/api/assistant/settings")).json()["month_spend_usd"]
    assert (await client.delete(f"/api/assistant/conversations/{conv_id}")).status_code == 204
    assert (await client.get(f"/api/assistant/conversations/{conv_id}")).status_code == 404
    assert (await client.delete(f"/api/assistant/conversations/{conv_id}")).status_code == 404
    assert (await client.get("/api/assistant/conversations")).json() == []
    assert (await client.get("/api/assistant/settings")).json()["month_spend_usd"] == before
    texts = (await db_session.execute(select(AiMessage.content))).scalars().all()
    assert "private question" not in texts and "Hello!" not in texts


async def test_provider_failures_never_leak_the_key_into_the_stream_or_logs(
    client: AsyncClient, env_key: str, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    install_provider([ProviderError("auth", f"Incorrect API key provided: {env_key}")])
    response = await client.post("/api/assistant/chat", json={"message": "hello"})
    assert env_key not in response.text and env_key not in caplog.text
    err = first(parse_events(response.text), "error")
    assert err["code"] == "PROVIDER_ERROR"

    # An unexpected exception that happens to contain the key is scrubbed before logging.
    install_provider([RuntimeError(f"boom with {env_key} inside")])
    crashed = await client.post("/api/assistant/chat", json={"message": "hello again"})
    assert env_key not in crashed.text and env_key not in caplog.text
    assert "PROVIDER_ERROR" in crashed.text


async def test_chat_request_errors_use_http_codes(client: AsyncClient, env_key: str) -> None:
    install_provider([])
    assert (await client.post("/api/assistant/chat", json={"message": ""})).status_code == 422
    too_long = await client.post("/api/assistant/chat", json={"message": "x" * 4001})
    assert too_long.status_code == 422
    bad_lang = await client.post("/api/assistant/chat", json={"message": "x", "lang": "fr"})
    assert bad_lang.status_code == 422
    no_ticker = await client.post("/api/assistant/chat", json={"message": "x", "ticker": "NOPE"})
    assert no_ticker.status_code == 404
    no_conv = await client.post(
        "/api/assistant/chat", json={"message": "x", "conversation_id": str(uuid.uuid4())}
    )
    assert no_conv.status_code == 404
    assert (await client.get(f"/api/assistant/conversations/{uuid.uuid4()}")).status_code == 404
    assert (await client.get("/api/assistant/conversations?limit=51")).status_code == 422


# -- explain ----------------------------------------------------------------------------------


async def test_explain_runs_the_card_tool_and_stores_without_a_conversation(
    client: AsyncClient, env_key: str, company: Company, db_session: AsyncSession
) -> None:
    ticker = company.ticker
    fake = install_provider([text_turn("The stance combines the engines that had data.")])
    events = await post_stream(
        client, "/explain", {"ticker": ticker, "card": "stance", "lang": "en"}
    )
    assert names(events)[0] == "meta" and first(events, "meta")["conversation_id"] is None
    assert first(events, "meta")["web_search"] is False  # explain never searches
    assert first(events, "answer")["general"] is False
    assert ("tool", "stance") in [(d["stage"], d.get("tool")) for n, d in events if n == "status"]
    answer = first(events, "answer")
    assert {"tool": "stance", "ticker": ticker} in answer["sources"]
    # The model got the card's tool result as a completed tool exchange, then the fixed prompt.
    sent = fake.calls[0].messages
    assert sent[1].role == "user" and ticker in (sent[1].content or "")
    assert sent[2].tool_calls[0].name == "stance" and sent[3].role == "tool"
    assert "leans" in (sent[3].content or "") or "neutral" in (sent[3].content or "")
    assert '"stance": "buy"' not in (sent[3].content or "")
    stored = (await db_session.execute(select(AiMessage))).scalars().all()
    assert len(stored) == 1 and stored[0].conversation_id is None
    assert (await client.get("/api/assistant/conversations")).json() == []


async def test_explain_with_nothing_to_explain_is_insufficient_data_without_a_call(
    client: AsyncClient, env_key: str, db_session: AsyncSession
) -> None:
    bare = await make_company(db_session)
    fake = install_provider([text_turn("never")])
    events = await post_stream(client, "/explain", {"ticker": bare.ticker, "card": "score"})
    err = first(events, "error")
    assert err["code"] == "INSUFFICIENT_DATA" and err["detail"]
    assert names(events)[-1] == "done"
    assert fake.calls == []


async def test_explain_errors(client: AsyncClient, env_key: str) -> None:
    install_provider([])
    unknown = await client.post("/api/assistant/explain", json={"ticker": "NOPE", "card": "score"})
    assert unknown.status_code == 404
    bad_card = await client.post("/api/assistant/explain", json={"ticker": "X", "card": "news"})
    assert bad_card.status_code == 422


async def test_saved_default_without_a_key_is_shown_but_not_used(
    client: AsyncClient, env_key: str
) -> None:
    saved = await client.put("/api/assistant/settings", json={"default_model": "gpt-5.5"})
    assert saved.json()["default_model"] == "gpt-5.5"  # what the owner chose
    models = (await client.get("/api/assistant/models")).json()
    assert models["default_model"] == "claude-sonnet-5-5"  # what a chat can actually use
    fake = install_provider([text_turn("Hello!")])
    await post_stream(client, "/chat", {"message": "hi"})
    assert len(fake.calls) == 1
