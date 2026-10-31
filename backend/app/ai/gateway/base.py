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
class Done:
    """End of one model call. ``None`` = the provider did not report it (never guessed)."""

    input_tokens: int | None
    output_tokens: int | None
    cost_usd: Decimal | None


ChatEvent = TextDelta | ToolCall | Done


class ProviderError(Exception):
    """A provider failure with a stable code and a message already scrubbed of API keys.

    ``code`` is one of ``auth``, ``rate_limit``, ``unavailable``, ``bad_request``, ``unknown``.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ChatProvider(Protocol):
    """Streams one model call. ``model`` is a catalog id; the provider derives the vendor."""

    def stream(
        self,
        model: str,
        api_key: str,
        messages: Sequence[ChatMessage],
        tools: Sequence[ToolSpec],
        max_tokens: int,
    ) -> AsyncIterator[ChatEvent]: ...
