"""Scripted provider for tests: no network, records every call it receives."""

from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal

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

#: One scripted model call: events to stream, an exception to raise, or a function of the messages.
Turn = Sequence[ChatEvent] | Exception | Callable[[Sequence[ChatMessage]], Sequence[ChatEvent]]


@dataclass
class RecordedCall:
    model: str
    api_key: str
    messages: list[ChatMessage]
    tools: list[ToolSpec]
    max_tokens: int
    web_search: bool = False
    max_web_searches: int = 3


def text_turn(
    text: str,
    *,
    input_tokens: int = 100,
    output_tokens: int = 20,
    cost: str | None = "0.001",
    citations: Sequence[Citation] = (),
    web_searches: int | None = None,
) -> list[ChatEvent]:
    """A call that answers with ``text`` (split in two chunks to exercise streaming).

    ``citations`` are emitted between the two chunks, ``web_searches`` goes on ``Done``.
    """
    half = len(text) // 2
    return [
        TextDelta(text[:half]),
        *citations,
        TextDelta(text[half:]),
        Done(
            input_tokens,
            output_tokens,
            Decimal(cost) if cost is not None else None,
            web_searches,
        ),
    ]


def tool_turn(
    *calls: ToolCall,
    input_tokens: int = 100,
    output_tokens: int = 10,
    cost: str | None = "0.001",
    citations: Sequence[Citation] = (),
    web_searches: int | None = None,
) -> list[ChatEvent]:
    """A call that asks for tools."""
    return [
        *citations,
        *calls,
        Done(
            input_tokens,
            output_tokens,
            Decimal(cost) if cost is not None else None,
            web_searches,
        ),
    ]


class FakeChatProvider:
    """Plays ``turns`` in order, one per ``stream`` call; running out is a test bug."""

    def __init__(self, turns: Sequence[Turn]) -> None:
        self._turns = list(turns)
        self.calls: list[RecordedCall] = []

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
        self.calls.append(
            RecordedCall(
                model,
                api_key,
                list(messages),
                list(tools),
                max_tokens,
                web_search,
                max_web_searches,
            )
        )
        if len(self.calls) > len(self._turns):
            raise ProviderError("unknown", "fake provider script exhausted")
        turn = self._turns[len(self.calls) - 1]
        if isinstance(turn, Exception):
            raise turn
        events = turn(messages) if callable(turn) else turn
        for event in events:
            yield event
