"""The tool loop: model -> tool calls -> tools -> model, then verify, retry once, else withhold.

No database or HTTP here: the provider, the tool runner and the cap check are injected, so the
whole loop runs against the fake provider in tests. The answer is never streamed before it is
verified (R49 A3); callers get progress events and then one final ``TurnResult``.
"""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Collection, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.ai.constants import (
    MAX_OUTPUT_TOKENS,
    MAX_TOOL_ROUNDS,
    MAX_WEB_SEARCHES,
    STATUS_ANSWERED,
    STATUS_CAP_REACHED,
    STATUS_ERROR,
    STATUS_UNVERIFIED,
)
from app.ai.gateway.base import (
    ChatMessage,
    ChatProvider,
    Citation,
    Done,
    ProviderError,
    TextDelta,
    ToolCall,
    ToolSpec,
)
from app.ai.prompts import RETRY_PROMPT, SEARCH_REFUSED
from app.ai.scope import names_company
from app.ai.search_refusal import is_refused, mark_refused
from app.ai.tools import ToolOutcome, to_json
from app.ai.verify import VerifyResult, verify

logger = logging.getLogger(__name__)

ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[ToolOutcome]]
#: Called before every model call with the cost of this turn so far; False = cap reached.
CapCheck = Callable[[Decimal], Awaitable[bool]]

#: ``{model}`` is the catalog id of the model that failed.
PROVIDER_ERROR_DETAILS = {
    "auth": "The provider rejected the API key. Check it in Admin > AI settings.",
    "rate_limit": "The provider is rate limiting requests. Try again shortly.",
    "quota": (
        "This API key has no quota for {model}. Choose another model, or enable billing "
        "for the key with the provider."
    ),
    "unavailable": "The provider is unavailable right now. Try again shortly.",
    "bad_request": "The provider refused the request for {model}.",
    "unknown": "The provider call failed.",
}

#: Errors of a call with web search that mean "the provider will not search for this key".
_SEARCH_REFUSAL_CODES = ("quota", "rate_limit")
_SEARCH_WORDS = ("web_search", "web search", "google_search", "googlesearch", "grounding")


def _search_refusal(exc: ProviderError) -> bool:
    """Did a call WITH web search fail because the provider refuses to search?"""
    if exc.code in _SEARCH_REFUSAL_CODES:
        return True
    return exc.code == "bad_request" and any(w in exc.message.lower() for w in _SEARCH_WORDS)


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
    #: Web searches the vendor reported over the turn (unreported counts as none).
    web_searches: int = 0

    def add(self, done: Done) -> None:
        self.calls += 1
        self.web_searches += done.web_searches or 0
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
    #: Why a PROVIDER_ERROR happened (auth, rate_limit, quota, unavailable, bad_request, unknown).
    error_reason: str | None = None
    retried: bool = False
    #: Whether news was checked: searched | not_offered | unsupported | refused (R50 B17).
    news: str = "not_offered"
    #: Web sources the vendor cited. Never part of the verify pool (R50 B4).
    citations: list[Citation] = field(default_factory=list)
    #: General education (R50 B8): names no company of ours, used no tool, figures unchecked.
    general: bool = False

    @property
    def sources(self) -> list[dict[str, Any]]:
        """Distinct (tool, ticker) pairs whose results the turn used, then the web sources."""
        seen: list[dict[str, Any]] = []
        for r in self.tool_records:
            if not r.ok:
                continue
            item: dict[str, Any] = {"tool": r.name}
            if r.ticker:
                item["ticker"] = r.ticker
            if item not in seen:
                seen.append(item)
        for citation in self.citations:
            seen.append({"tool": "web", "url": citation.url, "title": citation.title})
        return seen


def _with_refusal_notice(convo: list[ChatMessage]) -> list[ChatMessage]:
    """The conversation with the system prompt told that web search was refused (a copy)."""
    out = list(convo)
    for i, message in enumerate(out):
        if message.role == "system":
            out[i] = ChatMessage("system", f"{message.content or ''}\n{SEARCH_REFUSED}")
            break
    return out


def _failure(
    status: str,
    code: str,
    detail: str,
    records: list[ToolRecord],
    usage: Usage,
    retried: bool,
    reason: str | None = None,
) -> TurnResult:
    return TurnResult(
        status=status,
        tool_records=records,
        usage=usage,
        error_code=code,
        error_detail=detail,
        error_reason=reason,
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
    web_search: bool = False,
    known_tickers: Collection[str] | None = None,
    known_names: Collection[str] = (),
    provider_name: str = "",
    news: str = "not_offered",
) -> AsyncIterator[Progress | TurnResult]:
    """Run one assistant turn. Yields ``Progress`` events, then exactly one ``TurnResult``.

    ``web_search`` lets the model search the web, at most ``MAX_WEB_SEARCHES`` times over the
    whole turn. ``known_tickers`` (None = off) enables the general-education path (R50 B8):
    an answer that names none of ``known_tickers`` / ``known_names``, from a turn in which no
    tool succeeded, is returned labelled ``general`` with its figures unchecked.

    A call with web search that the provider refuses (quota, rate limit, or a bad request about
    the search tool) is retried once without search at no cost, and ``provider_name`` is
    remembered as refusing search until the next UTC midnight (R50 B15). ``news`` is the
    result's default news state: ``searched`` / ``unsupported`` / ``not_offered`` (see
    ``TurnResult.news``); a refusal turns it into ``refused``.
    """
    convo = list(messages)
    records = list(seed_records)
    usage = Usage()
    rounds = 0
    retried = False
    citations: dict[str, Citation] = {}
    refused = web_search and is_refused(provider_name)
    searching = web_search and not refused

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
        searches_left = MAX_WEB_SEARCHES - usage.web_searches
        call_search = searching and searches_left > 0
        failure: ProviderError | None = None
        while True:  # at most two attempts: with search, then (after a refusal) without
            text_parts: list[str] = []
            calls: list[ToolCall] = []
            call_citations: dict[str, Citation] = {}
            dones: list[Done] = []
            try:
                async for event in provider.stream(
                    model,
                    api_key,
                    convo,
                    offered,
                    MAX_OUTPUT_TOKENS,
                    web_search=call_search,
                    max_web_searches=max(searches_left, 0),
                ):
                    if isinstance(event, TextDelta):
                        text_parts.append(event.text)
                    elif isinstance(event, ToolCall):
                        calls.append(event)
                    elif isinstance(event, Citation):
                        call_citations.setdefault(event.url, event)
                    elif isinstance(event, Done):
                        dones.append(event)
                failure = None
                break
            except ProviderError as exc:
                logger.warning(
                    "assistant provider error code=%s model=%s search=%s",
                    exc.code,
                    model,
                    call_search,
                )
                if call_search and _search_refusal(exc):
                    # Nothing from the refused call is kept and it adds no cost.
                    mark_refused(provider_name)
                    refused, searching, call_search = True, False, False
                    convo = _with_refusal_notice(convo)
                    continue
                failure = exc
                break
        if failure is not None:
            yield _failure(
                STATUS_ERROR,
                "PROVIDER_ERROR",
                PROVIDER_ERROR_DETAILS.get(
                    failure.code, PROVIDER_ERROR_DETAILS["unknown"]
                ).format(model=model),
                records,
                usage,
                retried,
                reason=failure.code,
            )
            return
        for citation in call_citations.values():
            citations.setdefault(citation.url, citation)
        for done in dones:
            usage.add(done)
            logger.info(
                "assistant call model=%s input_tokens=%s output_tokens=%s cost_usd=%s",
                model,
                done.input_tokens,
                done.output_tokens,
                done.cost_usd,
            )
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

        if (
            known_tickers is not None
            and not any(r.ok for r in records)
            and not names_company(user_text, known_tickers, known_names)
            and not names_company(text, known_tickers, known_names)
        ):
            yield TurnResult(
                STATUS_ANSWERED,
                text=text,
                verification=VerifyResult(verified=True, checked=0, unverified=[]),
                tool_records=records,
                usage=usage,
                retried=retried,
                citations=list(citations.values()),
                general=True,
                news="refused" if refused else "not_offered",
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
                citations=list(citations.values()),
                news="refused" if refused else news,
            )
            return
        if retried:
            yield TurnResult(
                STATUS_UNVERIFIED,
                verification=result,
                tool_records=records,
                usage=usage,
                retried=True,
                citations=list(citations.values()),
                news="refused" if refused else news,
            )
            return
        retried = True
        yield Progress("retrying")
        convo.append(ChatMessage("assistant", text))
        convo.append(ChatMessage("user", RETRY_PROMPT.format(figures=", ".join(result.unverified))))
