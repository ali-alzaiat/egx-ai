"""LiteLLM adapter: the only module in the app that imports ``litellm``.

Rules (R49 A6/A7): the provider endpoint is whatever LiteLLM uses for the vendor, never a
custom ``api_base``; telemetry, callbacks and debug logging are off; the cost is read from
LiteLLM's local cost map (never fetched at import); an exception's text is scrubbed of the
API key before it is logged or re-raised, and the original exception is not chained.
"""

import json
import logging
import os
from collections.abc import AsyncIterator, Sequence
from decimal import ROUND_UP, Decimal
from functools import cache
from typing import Any

from app.ai.catalog import get_model
from app.ai.gateway.base import (
    ChatEvent,
    ChatMessage,
    Done,
    ProviderError,
    TextDelta,
    ToolCall,
    ToolSpec,
)
from app.ai.redact import scrub

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 90
_LITELLM_LOGGERS = ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy")
_MAX_ERROR_CHARS = 300


class _ScrubFilter(logging.Filter):
    """Defence in depth: whatever LiteLLM does log is scrubbed of key shapes."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = scrub(record.getMessage())
        record.args = ()
        return True


@cache
def load_litellm() -> Any:
    """Import LiteLLM once with its network and logging side effects switched off."""
    # Read at import time: keep the cost map and static tables local instead of fetching them.
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    os.environ["LITELLM_LOCAL_BLOG_POSTS"] = "True"
    os.environ["LITELLM_LOCAL_ANTHROPIC_BETA_HEADERS"] = "True"
    os.environ["LITELLM_LOCAL_POLICY_TEMPLATES"] = "True"
    os.environ["LITELLM_LOG"] = "CRITICAL"

    import litellm

    litellm.suppress_debug_info = True
    litellm.set_verbose = False  # type: ignore[attr-defined]
    litellm.callbacks = []
    litellm.success_callback = []
    litellm.failure_callback = []
    litellm.turn_off_message_logging = True
    litellm.redact_messages_in_exceptions = True
    if hasattr(litellm, "telemetry"):
        litellm.telemetry = False
    for name in _LITELLM_LOGGERS:
        lg = logging.getLogger(name)
        lg.setLevel(logging.CRITICAL)
        lg.addFilter(_ScrubFilter())
    return litellm


def _tool_call_json(call: ToolCall) -> dict[str, Any]:
    return {
        "id": call.id,
        "type": "function",
        "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
    }


def to_wire_messages(messages: Sequence[ChatMessage]) -> list[dict[str, Any]]:
    """Our messages as OpenAI-style dicts (what LiteLLM accepts for every vendor)."""
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "tool":
            out.append({"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content or ""})
        elif m.role == "assistant" and m.tool_calls:
            out.append(
                {
                    "role": "assistant",
                    "content": m.content,
                    "tool_calls": [_tool_call_json(c) for c in m.tool_calls],
                }
            )
        else:
            out.append({"role": m.role, "content": m.content or ""})
    return out


def to_wire_tools(tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
        }
        for t in tools
    ]


def translate_error(exc: BaseException, api_key: str) -> ProviderError:
    """Map any exception to a ProviderError whose text has the key scrubbed out."""
    name = type(exc).__name__
    if name in ("AuthenticationError", "PermissionDeniedError"):
        code = "auth"
    elif name == "RateLimitError":
        code = "rate_limit"
    elif name in (
        "ServiceUnavailableError",
        "InternalServerError",
        "APIConnectionError",
        "Timeout",
        "APITimeoutError",
        "BadGatewayError",
    ):
        code = "unavailable"
    elif name in ("BadRequestError", "NotFoundError", "ContextWindowExceededError"):
        code = "bad_request"
    else:
        code = "unknown"
    message = scrub(f"{name}: {exc}", api_key)[:_MAX_ERROR_CHARS]
    return ProviderError(code, message)


class _PartialCall:
    def __init__(self, call_id: str, name: str) -> None:
        self.call_id = call_id
        self.name = name
        self.arguments = ""


def _parse_arguments(raw: str) -> dict[str, Any]:
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {"__invalid_arguments__": raw[:200]}
    return parsed if isinstance(parsed, dict) else {"__invalid_arguments__": raw[:200]}


def _collect_tool_delta(partial: dict[int, _PartialCall], tc: Any) -> None:
    """Fold one streamed tool-call fragment into ``partial`` (id/name arrive once, args split)."""
    index = tc.index if tc.index is not None else 0
    fn = tc.function
    current = partial.get(index)
    # A new id at a used index starts a new call (some vendors send every call at index 0).
    if current is None or (tc.id and current.call_id and tc.id != current.call_id):
        index = index if current is None else max(partial) + 1
        name = (fn.name or "") if fn else ""
        current = partial[index] = _PartialCall(tc.id or f"call_{index}", name)
    elif fn is not None and fn.name and not current.name:
        current.name = fn.name
    if fn is not None and fn.arguments:
        current.arguments += fn.arguments


def _cost(
    litellm: Any, entry_key: str, provider: str, tokens_in: int, tokens_out: int
) -> Decimal | None:
    try:
        prompt_cost, completion_cost = litellm.cost_per_token(
            model=entry_key,
            prompt_tokens=tokens_in,
            completion_tokens=tokens_out,
            custom_llm_provider=provider,
        )
        # Float noise (0.0032000000000000001) is rounded away before the final rounding.
        total = Decimal(str(round(float(prompt_cost) + float(completion_cost), 10)))
        # Stored with 6 decimals; round up so the monthly cap is never under-counted.
        return total.quantize(Decimal("0.000001"), rounding=ROUND_UP)
    except Exception:
        return None  # unpriced: reported as unknown, never as zero


class LiteLLMProvider:
    """Streams a chat completion through LiteLLM with the caller's API key."""

    async def stream(
        self,
        model: str,
        api_key: str,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        max_tokens: int,
    ) -> AsyncIterator[ChatEvent]:
        entry = get_model(model)
        if entry is None:
            raise ProviderError("bad_request", "Unknown model")
        litellm = load_litellm()
        kwargs: dict[str, Any] = {
            "model": entry.litellm_model,
            "messages": to_wire_messages(messages),
            "api_key": api_key,
            "stream": True,
            "max_tokens": max_tokens,
            "timeout": REQUEST_TIMEOUT_SECONDS,
            "num_retries": 0,
        }
        if entry.provider == "openai":
            # Anthropic and Gemini report usage in the final chunk without being asked.
            kwargs["stream_options"] = {"include_usage": True}
        if tools:
            kwargs["tools"] = to_wire_tools(tools)
        partial: dict[int, _PartialCall] = {}
        input_tokens: int | None = None
        output_tokens: int | None = None
        try:
            response = await litellm.acompletion(**kwargs)
            async for chunk in response:
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    input_tokens = getattr(usage, "prompt_tokens", None)
                    output_tokens = getattr(usage, "completion_tokens", None)
                for choice in getattr(chunk, "choices", None) or []:
                    delta = choice.delta
                    if delta is None:
                        continue
                    if delta.content:
                        yield TextDelta(delta.content)
                    for tc in getattr(delta, "tool_calls", None) or []:
                        _collect_tool_delta(partial, tc)
            for index in sorted(partial):
                call = partial[index]
                if call.name:
                    yield ToolCall(call.call_id, call.name, _parse_arguments(call.arguments))
            cost = None
            if input_tokens is not None and output_tokens is not None:
                cost = _cost(litellm, entry.cost_key, entry.provider, input_tokens, output_tokens)
            yield Done(input_tokens, output_tokens, cost)
        except ProviderError:
            raise
        except Exception as exc:
            error = translate_error(exc, api_key)
            logger.warning(
                "provider call failed model=%s code=%s: %s", model, error.code, error.message
            )
            raise error from None
