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
from urllib.parse import urlparse

from app.ai.catalog import CatalogModel, get_model
from app.ai.gateway.base import (
    ChatEvent,
    ChatMessage,
    Citation,
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
_MAX_URL_CHARS = 2000
_MAX_TITLE_CHARS = 300

# The hosted web-search tool of Anthropic. LiteLLM 1.105.1 only builds it from
# `web_search_options` with `max_uses` of 1, 5 or 10 (`search_context_size`), so the tool is passed
# directly in `tools`: LiteLLM forwards its `max_uses` untouched, which gives the exact cap of 3.
ANTHROPIC_WEB_SEARCH_TOOL = "web_search_20250305"


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


_AUTH_ERRORS = ("AuthenticationError", "PermissionDeniedError")
_UNAVAILABLE_ERRORS = (
    "ServiceUnavailableError",
    "InternalServerError",
    "APIConnectionError",
    "Timeout",
    "APITimeoutError",
    "BadGatewayError",
)
_BAD_REQUEST_ERRORS = ("BadRequestError", "NotFoundError", "ContextWindowExceededError")
_QUOTA_MARKERS = ("exceeded your current quota", "quota exceeded", "resource_exhausted")
#: How many wrapper layers (`original_exception`, `__cause__`, `__context__`) are followed.
_MAX_UNWRAP_DEPTH = 4


def _error_chain(exc: BaseException) -> list[BaseException]:
    """`exc` and the exceptions it wraps, outermost first (LiteLLM wraps stream errors)."""
    chain: list[BaseException] = [exc]
    current: BaseException = exc
    for _ in range(_MAX_UNWRAP_DEPTH):
        inner = getattr(current, "original_exception", None)
        if not isinstance(inner, BaseException):
            inner = current.__cause__ or current.__context__
        if inner is None or any(inner is seen for seen in chain):
            break
        chain.append(inner)
        current = inner
    return chain


def _classify(name: str) -> str | None:
    if name in _AUTH_ERRORS:
        return "auth"
    if name == "RateLimitError":
        return "rate_limit"
    if name in _UNAVAILABLE_ERRORS:
        return "unavailable"
    if name in _BAD_REQUEST_ERRORS:
        return "bad_request"
    return None


def translate_error(exc: BaseException, api_key: str) -> ProviderError:
    """Map any exception to a ProviderError whose text has the key scrubbed out.

    Wrappers (such as LiteLLM's MidStreamFallbackError) are unwrapped and the innermost
    known class decides the code; a quota-exhausted text is `quota` (not `rate_limit`) whether
    or not the class is recognised.
    """
    chain = _error_chain(exc)
    code = next((c for c in map(_classify, (type(e).__name__ for e in reversed(chain))) if c), None)
    if code in (None, "rate_limit"):
        # A 429 that says the quota is used up will not clear by retrying: its own code.
        text = " ".join(str(e) for e in chain).lower()
        if any(marker in text for marker in _QUOTA_MARKERS):
            code = "quota"
    code = code or "unknown"
    message = scrub(f"{type(exc).__name__}: {exc}", api_key)[:_MAX_ERROR_CHARS]
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


def _field(obj: Any, name: str) -> Any:
    """`obj[name]` for a dict, `obj.name` for an object, else None."""
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def safe_citation(url: Any, title: Any) -> Citation | None:
    """A citation with an http(s) URL only; anything else (javascript:, data:, ...) is dropped."""
    if not isinstance(url, str):
        return None
    url = url.strip()
    if not url or len(url) > _MAX_URL_CHARS:
        return None
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    text = title.strip() if isinstance(title, str) else ""
    return Citation(url, (text or parsed.netloc)[:_MAX_TITLE_CHARS])


def citations_from_delta(delta: Any) -> list[Citation]:
    """Citations the vendor attached to one streamed delta.

    Anthropic: `provider_specific_fields["citation"]` (a web_search_result_location).
    Gemini: `annotations` of type `url_citation`. Model text is never read.
    """
    found: list[Citation] = []
    fields = _field(delta, "provider_specific_fields")
    if isinstance(fields, dict):
        raw = fields.get("citation")
        if raw is not None:
            citation = safe_citation(_field(raw, "url"), _field(raw, "title"))
            if citation is not None:
                found.append(citation)
    for annotation in _field(delta, "annotations") or []:
        if _field(annotation, "type") != "url_citation":
            continue
        inner = _field(annotation, "url_citation")
        citation = safe_citation(_field(inner, "url"), _field(inner, "title"))
        if citation is not None:
            found.append(citation)
    return found


def _reported_searches(usage: Any) -> int | None:
    """Web searches the vendor reports in a usage object (Anthropic or Gemini), else None."""
    for source in (_field(usage, "server_tool_use"), _field(usage, "prompt_tokens_details")):
        count = _field(source, "web_search_requests")
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            return count
    return None


def _search_price(litellm: Any, entry_key: str) -> Decimal | None:
    """USD per web search from LiteLLM's cost map; None when the model has no listed price."""
    try:
        pricing = litellm.model_cost[entry_key]["search_context_cost_per_query"]
        return Decimal(str(pricing["search_context_size_medium"]))
    except (KeyError, TypeError, ArithmeticError):
        return None


def _quantize_cost(total: Decimal) -> Decimal:
    # Stored with 6 decimals; round up so the monthly cap is never under-counted.
    return total.quantize(Decimal("0.000001"), rounding=ROUND_UP)


def _cost(
    litellm: Any,
    entry: CatalogModel,
    tokens_in: int,
    tokens_out: int,
    *,
    searches: int | None = 0,
) -> Decimal | None:
    """Token cost plus `searches` x the model's search price (None searches = unknown)."""
    try:
        prompt_cost, completion_cost = litellm.cost_per_token(
            model=entry.cost_key,
            prompt_tokens=tokens_in,
            completion_tokens=tokens_out,
            custom_llm_provider=entry.provider,
        )
        # Float noise (0.0032000000000000001) is rounded away before the final rounding.
        total = Decimal(str(round(float(prompt_cost) + float(completion_cost), 10)))
    except Exception:
        return None  # unpriced: reported as unknown, never as zero
    if searches is None:
        return None  # searched, but the number of searches is unknown
    if searches > 0:
        price = _search_price(litellm, entry.cost_key)
        if price is None:
            return None  # the model has no listed search price: unknown, never zero
        total += price * searches
    return _quantize_cost(total)


class LiteLLMProvider:
    """Streams a chat completion through LiteLLM with the caller's API key."""

    async def stream(
        self,
        model: str,
        api_key: str,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        max_tokens: int,
        web_search: bool = False,
        max_web_searches: int = 3,
    ) -> AsyncIterator[ChatEvent]:
        entry = get_model(model)
        if entry is None:
            raise ProviderError("bad_request", "Unknown model")
        searching = web_search and entry.web_search
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
        wire_tools = to_wire_tools(tools)
        if searching and entry.provider == "anthropic":
            wire_tools.append(
                {
                    "type": ANTHROPIC_WEB_SEARCH_TOOL,
                    "name": "web_search",
                    "max_uses": max(1, max_web_searches),
                }
            )
        elif searching and entry.provider == "gemini":
            # Without the flag LiteLLM drops the search tool when function tools are present.
            kwargs["web_search_options"] = {"search_context_size": "medium"}
            kwargs["include_server_side_tool_invocations"] = True
        if wire_tools:
            kwargs["tools"] = wire_tools
        partial: dict[int, _PartialCall] = {}
        input_tokens: int | None = None
        output_tokens: int | None = None
        reported_searches: int | None = None
        cited: dict[str, Citation] = {}
        try:
            response = await litellm.acompletion(**kwargs)
            async for chunk in response:
                usage = getattr(chunk, "usage", None)
                if usage is not None:
                    input_tokens = getattr(usage, "prompt_tokens", None)
                    output_tokens = getattr(usage, "completion_tokens", None)
                    found = _reported_searches(usage)
                    if found is not None:
                        reported_searches = found
                for choice in getattr(chunk, "choices", None) or []:
                    delta = choice.delta
                    if delta is None:
                        continue
                    if searching:
                        for citation in citations_from_delta(delta):
                            if citation.url not in cited:
                                cited[citation.url] = citation
                                yield citation
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
                searches: int | None = 0  # a call without search tools cannot have searched
                if searching:
                    searches = reported_searches
                    if searches is None and not cited:
                        searches = 0  # no search usage and no citation: it did not search
                cost = _cost(litellm, entry, input_tokens, output_tokens, searches=searches)
            yield Done(input_tokens, output_tokens, cost, reported_searches)
        except ProviderError:
            raise
        except Exception as exc:
            error = translate_error(exc, api_key)
            logger.warning(
                "provider call failed model=%s code=%s: %s", model, error.code, error.message
            )
            raise error from None
