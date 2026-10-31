"""Provider-neutral chat types. Nothing here imports a vendor SDK."""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal, Protocol

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class ToolSpec:
    """A tool the model may call: JSON-schema parameters, read-only by construction."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """One tool call requested by the model (also a stream event)."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatMessage:
    """OpenAI-style message: system, user, assistant (+tool_calls) or tool (+tool_call_id)."""

    role: Role
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class Citation:
    """A web source the vendor cited (R50 B3/B4): built from vendor metadata, never model text."""

    url: str
    title: str


@dataclass(frozen=True)
class Done:
    """End of one model call. ``None`` = the provider did not report it (never guessed).

    ``cost_usd`` includes web-search fees when the call searched. ``web_searches`` is the
    number of searches the vendor reports (None = not reported).
    """

    input_tokens: int | None
    output_tokens: int | None
    cost_usd: Decimal | None
    web_searches: int | None = None


ChatEvent = TextDelta | ToolCall | Citation | Done


class ProviderError(Exception):
    """A provider failure with a stable code and a message already scrubbed of API keys.

    ``code`` is one of ``auth``, ``rate_limit``, ``quota``, ``unavailable``, ``bad_request``,
    ``unknown``.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ChatProvider(Protocol):
    """Streams one model call. ``model`` is a catalog id; the provider derives the vendor.

    ``web_search`` lets the model use its vendor's web search for this call;
    ``max_web_searches`` caps the searches where the vendor supports a cap.
    """

    def stream(
        self,
        model: str,
        api_key: str,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        max_tokens: int,
        web_search: bool = False,
        max_web_searches: int = 3,
    ) -> AsyncIterator[ChatEvent]: ...
