"""LiteLLM adapter, catalog and key store tests. No network: LiteLLM's call is replaced."""

import logging
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.catalog import CATALOG, ENV_KEY_SETTING, KEY_TEST_MODEL, PROVIDERS, get_model
from app.ai.gateway.base import ChatMessage, Done, ProviderError, TextDelta, ToolCall, ToolSpec
from app.ai.gateway.litellm_provider import (
    LiteLLMProvider,
    load_litellm,
    to_wire_messages,
    to_wire_tools,
    translate_error,
)
from app.ai.keys import (
    KeyStore,
    SecretsKeyMissing,
    decrypt_secret,
    encrypt_secret,
    secrets_key_set,
)
from app.core.config import settings

SECRET = "sk-proj-SECRETVALUE1234567890"


@pytest.fixture
def secrets_key(monkeypatch: pytest.MonkeyPatch) -> str:
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "AI_SECRETS_KEY", key)
    for name in ENV_KEY_SETTING.values():
        monkeypatch.setattr(settings, name, "")
    return key


# -- catalog ------------------------------------------------------------------------------


@pytest.mark.parametrize("entry", CATALOG, ids=lambda m: m.id)
def test_catalog_entry_is_valid_in_litellm_cost_map(entry: Any) -> None:
    litellm = load_litellm()
    info = litellm.model_cost.get(entry.cost_key)
    assert info is not None, f"{entry.cost_key} missing from LiteLLM model_cost"
    assert info["mode"] == "chat"
    assert info.get("supports_function_calling") is True
    assert info["litellm_provider"] == entry.provider
    assert info["input_cost_per_token"] > 0 and info["output_cost_per_token"] > 0
    _, resolved_provider, _, _ = litellm.get_llm_provider(entry.litellm_model)
    assert resolved_provider == entry.provider


def test_catalog_covers_each_provider_and_key_test_models_exist() -> None:
    assert {m.provider for m in CATALOG} == set(PROVIDERS)
    ids = [m.id for m in CATALOG]
    assert len(ids) == len(set(ids))
    for provider, model_id in KEY_TEST_MODEL.items():
        entry = get_model(model_id)
        assert entry is not None and entry.provider == provider
    assert {m.id for m in CATALOG if m.provider == "anthropic"} >= {
        "claude-opus-5-5",
        "claude-sonnet-5-5",
    }


def test_litellm_is_configured_quiet() -> None:
    litellm = load_litellm()
    assert litellm.callbacks == [] and litellm.success_callback == []
    assert litellm.set_verbose is False
    assert litellm.turn_off_message_logging is True
    import os

    assert os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] == "True"


# -- key encryption -------------------------------------------------------------------------


def test_key_round_trip_and_ciphertext_hides_the_key(secrets_key: str) -> None:
    token = encrypt_secret(SECRET)
    assert SECRET not in token
    assert decrypt_secret(token) == SECRET


def test_encrypt_fails_closed_without_secrets_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AI_SECRETS_KEY", "")
    assert not secrets_key_set()
    with pytest.raises(SecretsKeyMissing):
        encrypt_secret(SECRET)
    monkeypatch.setattr(settings, "AI_SECRETS_KEY", "not-a-fernet-key")
    assert not secrets_key_set()
    with pytest.raises(SecretsKeyMissing):
        encrypt_secret(SECRET)


async def test_key_store_ui_key_wins_over_env_and_wrong_secrets_key_falls_back(
    db_session: AsyncSession, secrets_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = KeyStore(db_session)
    assert await store.resolve("openai") is None
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-env-ENVKEY0000")
    env = await store.resolve("openai")
    assert env is not None and env.source == "env"

    await store.save("openai", SECRET)
    ui = await store.resolve("openai")
    assert ui is not None and ui.source == "ui" and ui.api_key == SECRET
    status = await store.status("openai")
    assert status.source == "ui" and status.last4 == SECRET[-4:] and status.set_at is not None
    assert SECRET not in repr(ui)

    # Re-saving replaces the key and moves the date.
    await store.save("openai", "sk-proj-SECONDVALUE9999")
    assert (await store.status("openai")).last4 == "9999"

    # The secrets key changed: the saved key is unreadable, so the env key is used.
    monkeypatch.setattr(settings, "AI_SECRETS_KEY", Fernet.generate_key().decode())
    fallback = await store.resolve("openai")
    assert fallback is not None and fallback.source == "env"

    await store.delete("openai")
    monkeypatch.setattr(settings, "AI_SECRETS_KEY", secrets_key)
    still = await store.resolve("openai")
    assert still is not None and still.source == "env"


# -- adapter ----------------------------------------------------------------------------------


def test_wire_format_has_tool_calls_and_results() -> None:
    wire = to_wire_messages(
        [
            ChatMessage("system", "s"),
            ChatMessage(
                "assistant", None, tool_calls=[ToolCall("c1", "valuation", {"ticker": "A"})]
            ),
            ChatMessage("tool", "{}", tool_call_id="c1"),
        ]
    )
    assert wire[1]["tool_calls"][0]["function"] == {
        "name": "valuation",
        "arguments": '{"ticker": "A"}',
    }
    assert wire[2] == {"role": "tool", "tool_call_id": "c1", "content": "{}"}
    tools = to_wire_tools([ToolSpec("t", "d", {"type": "object"})])
    assert tools[0]["function"]["name"] == "t"


class _Capture:
    """Replaces litellm.acompletion: records kwargs, streams scripted chunks or raises."""

    def __init__(self, chunks: list[Any] | None = None, error: Exception | None = None) -> None:
        self.chunks = chunks or []
        self.error = error
        self.kwargs: dict[str, Any] = {}

    async def __call__(self, **kwargs: Any) -> AsyncIterator[Any]:
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error

        async def gen() -> AsyncIterator[Any]:
            for chunk in self.chunks:
                yield chunk

        return gen()


def _chunks() -> list[Any]:
    from litellm.types.utils import (
        ChatCompletionDeltaToolCall,
        Delta,
        Function,
        ModelResponseStream,
        StreamingChoices,
        Usage,
    )

    def delta(**kw: Any) -> Any:
        return ModelResponseStream(choices=[StreamingChoices(delta=Delta(**kw))])

    def call(index: int, call_id: str | None, name: str | None, args: str) -> Any:
        return ChatCompletionDeltaToolCall(
            id=call_id, function=Function(name=name, arguments=args), type="function", index=index
        )

    return [
        delta(content="Hel"),
        delta(content="lo"),
        delta(content=None, tool_calls=[call(0, "call_a", "valuation", '{"tick')]),
        delta(content=None, tool_calls=[call(0, None, None, 'er": "COMI"}')]),
        delta(content=None, tool_calls=[call(1, "call_b", "stance", '{"ticker": "SWDY"}')]),
        ModelResponseStream(
            choices=[], usage=Usage(prompt_tokens=1000, completion_tokens=100, total_tokens=1100)
        ),
    ]


# LiteLLM's own type module makes pydantic warn once when first imported.
@pytest.mark.filterwarnings("ignore:Item 'summary' on TypedDict:UserWarning")
async def test_stream_maps_text_tool_calls_usage_and_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    litellm = load_litellm()
    capture = _Capture(_chunks())
    monkeypatch.setattr(litellm, "acompletion", capture)
    events = [
        e
        async for e in LiteLLMProvider().stream(
            "gemini-3.1-pro-preview",
            SECRET,
            [ChatMessage("user", "hi")],
            [ToolSpec("valuation", "d", {"type": "object"})],
            1500,
        )
    ]
    assert events[:2] == [TextDelta("Hel"), TextDelta("lo")]
    assert events[2] == ToolCall("call_a", "valuation", {"ticker": "COMI"})
    assert events[3] == ToolCall("call_b", "stance", {"ticker": "SWDY"})
    done = events[-1]
    assert isinstance(done, Done)
    assert (done.input_tokens, done.output_tokens) == (1000, 100)
    # 1000 * 2e-6 + 100 * 1.2e-5 from LiteLLM's cost map.
    assert done.cost_usd == Decimal("0.0032")

    kwargs = capture.kwargs
    assert kwargs["model"] == "gemini/gemini-3.1-pro-preview"
    assert kwargs["api_key"] == SECRET and kwargs["stream"] is True
    assert kwargs["max_tokens"] == 1500
    # Endpoints are fixed in code: no custom URL is ever passed.
    assert not {"api_base", "base_url", "custom_llm_provider"} & set(kwargs)


async def test_unpriced_usage_stays_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    litellm = load_litellm()
    monkeypatch.setattr(litellm, "acompletion", _Capture(_chunks()[:2]))
    events = [
        e
        async for e in LiteLLMProvider().stream(
            "gpt-5.5", SECRET, [ChatMessage("user", "hi")], [], 100
        )
    ]
    done = events[-1]
    assert isinstance(done, Done)
    assert done.input_tokens is None and done.cost_usd is None


async def test_unknown_model_is_refused_before_any_call() -> None:
    with pytest.raises(ProviderError):
        async for _ in LiteLLMProvider().stream("gpt-nope", SECRET, [], [], 10):
            pass


async def test_provider_error_never_carries_or_logs_the_key(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    litellm = load_litellm()
    boom = litellm.AuthenticationError(
        f"Incorrect API key provided: {SECRET}", "openai", "gpt-5.5"
    )
    monkeypatch.setattr(litellm, "acompletion", _Capture(error=boom))
    caplog.set_level(logging.DEBUG)
    with pytest.raises(ProviderError) as info:
        async for _ in LiteLLMProvider().stream(
            "gpt-5.5", SECRET, [ChatMessage("user", "hi")], [], 100
        ):
            pass
    err = info.value
    assert err.code == "auth"
    assert SECRET not in err.message and SECRET not in str(err)
    assert err.__cause__ is None and err.__suppress_context__
    assert SECRET not in caplog.text


def test_translate_error_codes() -> None:
    litellm = load_litellm()
    assert translate_error(litellm.RateLimitError("x", "openai", "m"), "k").code == "rate_limit"
    assert (
        translate_error(litellm.ServiceUnavailableError("x", "openai", "m"), "k").code
        == "unavailable"
    )
    assert translate_error(litellm.BadRequestError("x", "openai", "m"), "k").code == "bad_request"
    assert translate_error(RuntimeError("x"), "k").code == "unknown"


def test_litellm_logger_filter_scrubs_key_shapes(caplog: pytest.LogCaptureFixture) -> None:
    load_litellm()
    record = logging.LogRecord(
        "LiteLLM", logging.ERROR, __file__, 1, "bad key %s", (SECRET,), None
    )
    for flt in logging.getLogger("LiteLLM").filters:
        flt.filter(record)
    assert SECRET not in record.getMessage()


def test_litellm_is_imported_only_by_the_adapter() -> None:
    from pathlib import Path

    app_dir = Path(__file__).parent.parent / "app"
    offenders = [
        str(path.relative_to(app_dir))
        for path in app_dir.rglob("*.py")
        if path.name != "litellm_provider.py"
        and any(
            line.strip().startswith(("import litellm", "from litellm"))
            for line in path.read_text(encoding="utf-8").splitlines()
        )
    ]
    assert offenders == []
