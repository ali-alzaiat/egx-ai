"""The tool loop: model -> tool calls -> tools -> model, then verify, retry once, else withhold.

No database or HTTP here: the provider, the tool runner and the cap check are injected, so the
whole loop runs against the fake provider in tests. The answer is never streamed before it is
verified (R49 A3); callers get progress events and then one final ``TurnResult``.
"""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.ai.constants import (
    MAX_OUTPUT_TOKENS,
    MAX_TOOL_ROUNDS,
    STATUS_ANSWERED,
    STATUS_CAP_REACHED,
    STATUS_ERROR,
    STATUS_UNVERIFIED,
)
from app.ai.gateway.base import (
    ChatMessage,
    ChatProvider,
    Done,
    ProviderError,
    TextDelta,
    ToolCall,
    ToolSpec,
)
from app.ai.prompts import RETRY_PROMPT
from app.ai.tools import ToolOutcome, to_json
from app.ai.verify import VerifyResult, verify

logger = logging.getLogger(__name__)

ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[ToolOutcome]]
#: Called before every model call with the cost of this turn so far; False = cap reached.
CapCheck = Callable[[Decimal], Awaitable[bool]]

PROVIDER_ERROR_DETAILS = {
    "auth": "The provider rejected the API key. Check it in Admin > AI settings.",
    "rate_limit": "The provider is rate limiting requests. Try again shortly.",
    "unavailable": "The provider is unavailable right now. Try again shortly.",
    "bad_request": "The provider refused the request for this model.",
    "unknown": "The provider call failed.",
}


@dataclass(frozen=True)
class Progress:
    """A stage the UI can show: thinking, tool (with the tool name), verifying, retrying."""

    stage: str
    tool: str | None = None


@dataclass
class ToolRecord:
    call_id: str
    name: str
    arguments: dict[str, Any]
    output: dict[str, Any]
    ok: bool
    ticker: str | None


@dataclass
class Usage:
    """Tokens and cost of a turn. Unreported values stay unknown, never zero."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: Decimal | None = None
    calls: int = 0

    def add(self, done: Done) -> None:
        self.calls += 1
        if done.input_tokens is not None:
            self.input_tokens = (self.input_tokens or 0) + done.input_tokens
        if done.output_tokens is not None:
            self.output_tokens = (self.output_tokens or 0) + done.output_tokens
        if done.cost_usd is not None:
            self.cost_usd = (self.cost_usd or Decimal(0)) + done.cost_usd


@dataclass
class TurnResult:
    status: str
    text: str = ""
    verification: VerifyResult | None = None
    tool_records: list[ToolRecord] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    error_code: str | None = None
    error_detail: str | None = None
    retried: bool = False

    @property
    def sources(self) -> list[dict[str, Any]]:
        """Distinct (tool, ticker) pairs whose results the turn used."""
        seen: list[dict[str, Any]] = []
        for r in self.tool_records:
            if not r.ok:
                continue
            item: dict[str, Any] = {"tool": r.name}
            if r.ticker:
                item["ticker"] = r.ticker
            if item not in seen:
                seen.append(item)
        return seen


def _failure(
    status: str, code: str, detail: str, records: list[ToolRecord], usage: Usage, retried: bool
) -> TurnResult:
    return TurnResult(
        status=status,
        tool_records=records,
        usage=usage,
        error_code=code,
        error_detail=detail,
        retried=retried,
    )


async def run_turn(
    *,
    provider: ChatProvider,
    model: str,
    api_key: str,
    messages: Sequence[ChatMessage],
    tools: Sequence[ToolSpec],
    execute: ToolExecutor,
    allow_call: CapCheck,
    user_text: str,
    seed_records: Sequence[ToolRecord] = (),
) -> AsyncIterator[Progress | TurnResult]:
    """Run one assistant turn. Yields ``Progress`` events, then exactly one ``TurnResult``."""
    convo = list(messages)
    records = list(seed_records)
    usage = Usage()
    rounds = 0
    retried = False

    while True:
        if not await allow_call(usage.cost_usd or Decimal(0)):
            yield _failure(
                STATUS_CAP_REACHED,
                "CAP_REACHED",
                "The monthly AI cost cap is reached. Raise it in Admin > AI settings.",
                records,
                usage,
                retried,
            )
            return
        yield Progress("thinking")
        offered = list(tools) if rounds < MAX_TOOL_ROUNDS else []
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        try:
            async for event in provider.stream(model, api_key, convo, offered, MAX_OUTPUT_TOKENS):
                if isinstance(event, TextDelta):
                    text_parts.append(event.text)
                elif isinstance(event, ToolCall):
                    calls.append(event)
                elif isinstance(event, Done):
                    usage.add(event)
                    logger.info(
                        "assistant call model=%s input_tokens=%s output_tokens=%s cost_usd=%s",
                        model,
                        event.input_tokens,
                        event.output_tokens,
                        event.cost_usd,
                    )
        except ProviderError as exc:
            logger.warning("assistant provider error code=%s model=%s", exc.code, model)
            yield _failure(
                STATUS_ERROR,
                "PROVIDER_ERROR",
                PROVIDER_ERROR_DETAILS.get(exc.code, PROVIDER_ERROR_DETAILS["unknown"]),
                records,
                usage,
                retried,
            )
            return
        text = "".join(text_parts)

        if calls and offered:
            rounds += 1
            convo.append(ChatMessage("assistant", text or None, tool_calls=list(calls)))
            for call in calls:
                yield Progress("tool", call.name)
                outcome = await execute(call.name, call.arguments)
                records.append(
                    ToolRecord(
                        call.id,
                        call.name,
                        call.arguments,
                        outcome.output,
                        outcome.ok,
                        outcome.ticker,
                    )
                )
                convo.append(ChatMessage("tool", to_json(outcome.output), tool_call_id=call.id))
            continue

        if not text.strip():
            yield _failure(
                STATUS_ERROR,
                "PROVIDER_ERROR",
                "The model returned no answer.",
                records,
                usage,
                retried,
            )
            return

        yield Progress("verifying")
        result = verify(text, [r.output for r in records if r.ok], user_text)
        if result.verified:
            yield TurnResult(
                STATUS_ANSWERED,
                text=text,
                verification=result,
                tool_records=records,
                usage=usage,
                retried=retried,
            )
            return
        if retried:
            yield TurnResult(
                STATUS_UNVERIFIED,
                verification=result,
                tool_records=records,
                usage=usage,
                retried=True,
            )
            return
        retried = True
        yield Progress("retrying")
        convo.append(ChatMessage("assistant", text))
        convo.append(ChatMessage("user", RETRY_PROMPT.format(figures=", ".join(result.unverified))))
