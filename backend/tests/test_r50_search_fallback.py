# ruff: noqa: F811  (R49 fixtures are imported, then used as test arguments)
"""R50 B15-B17: a refused web search falls back to a plain call, is remembered until the next
UTC midnight, and every answer says whether news was checked. Provider errors carry a reason."""

from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import search_refusal
from app.ai.constants import MAX_OUTPUT_TOKENS
from app.ai.gateway.base import ChatEvent, ChatMessage, ProviderError, ToolCall, ToolSpec
from app.ai.gateway.fake import FakeChatProvider, Turn, text_turn, tool_turn
from app.ai.orchestrator import PROVIDER_ERROR_DETAILS, Progress, TurnResult, run_turn
from app.ai.sse import ERROR_REASONS, format_event
from app.ai.tools import ToolOutcome
from app.api.assistant import get_chat_provider
from app.main import app
from app.models.assistant import AiMessage
from app.models.market import Company
from assistant_support import first, install_provider, names, post_stream
from test_assistant_api import (  # noqa: F401 - the R49 fixtures, autouse ones included
    assistant_env,
    company,
    env_key,
    no_network,
)

PRICE = {"tool": "price_summary", "ticker": "COMI", "data": {"latest": {"close": "84.50"}}}


class SearchRefusingProvider:
    """Plays ``turns`` like the fake, but a call WITH web search raises ``error`` first."""

    def __init__(self, turns: Sequence[Turn], error: ProviderError | None = None) -> None:
        self.inner = FakeChatProvider(turns)
        self.error = error or ProviderError("quota", "429 You exceeded your current quota")
        self.attempts: list[bool] = []  # web_search flag of every call, refused or not

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
        self.attempts.append(web_search)
        if web_search:
            raise self.error
        async for event in self.inner.stream(
            model, api_key, messages, tools, max_tokens, web_search, max_web_searches
        ):
            yield event


async def _execute(name: str, arguments: dict[str, Any]) -> ToolOutcome:
    return ToolOutcome(PRICE, True, "COMI")


async def _allow(_cost: Decimal) -> bool:
    return True


async def _turn(
    provider: Any,
    *,
    web_search: bool = True,
    news: str = "searched",
    name: str = "anthropic",
) -> TurnResult:
    result: TurnResult | None = None
    async for item in run_turn(
        provider=provider,
        model="claude-sonnet-5-5",
        api_key="k-test-1234",
        messages=[ChatMessage("system", "s"), ChatMessage("user", "COMI news?")],
        tools=[ToolSpec("price_summary", "d", {"type": "object"})],
        execute=_execute,
        allow_call=_allow,
        user_text="COMI news?",
        web_search=web_search,
        provider_name=name,
        news=news,
    ):
        if not isinstance(item, Progress):
            result = item
    assert result is not None
    return result


ANSWER = "COMI had no notable news today."
PRICED = "COMI last closed at 84.50."


# -- fallback ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        ProviderError("quota", "429 You exceeded your current quota"),
        ProviderError("rate_limit", "429 slow down"),
        ProviderError("bad_request", "Unsupported tool: web_search is not available"),
        ProviderError("bad_request", "googleSearch grounding not enabled"),
    ],
    ids=["quota", "rate_limit", "bad_request_search", "bad_request_grounding"],
)
async def test_a_refused_search_is_retried_once_without_search_and_at_no_cost(
    error: ProviderError,
) -> None:
    provider = SearchRefusingProvider([text_turn(ANSWER, cost="0.004")], error)
    result = await _turn(provider)
    assert result.status == "answered" and result.text == ANSWER
    assert provider.attempts == [True, False]  # the same call, once more, without search
    assert result.usage.cost_usd == Decimal("0.004") and result.usage.calls == 1
    assert result.news == "refused"
    assert search_refusal.is_refused("anthropic")


async def test_search_is_not_offered_again_while_the_provider_is_marked() -> None:
    await _turn(SearchRefusingProvider([text_turn(ANSWER)]))
    second = SearchRefusingProvider([text_turn(ANSWER)])
    result = await _turn(second)
    assert second.attempts == [False]  # no refused attempt: search was not even offered
    assert result.news == "refused"
    # Another provider is unaffected.
    other = FakeChatProvider([text_turn(ANSWER)])
    done = await _turn(other, name="gemini")
    assert other.calls[0].web_search is True and done.news == "searched"


async def test_the_mark_lapses_at_the_next_utc_midnight() -> None:
    now = [datetime(2026, 10, 31, 23, 59, tzinfo=UTC)]
    search_refusal.set_clock(lambda: now[0])
    await _turn(SearchRefusingProvider([text_turn(ANSWER)]))
    assert search_refusal.is_refused("anthropic")
    now[0] = datetime(2026, 10, 31, 23, 59, 59, tzinfo=UTC)
    assert search_refusal.is_refused("anthropic")
    now[0] = datetime(2026, 11, 1, 0, 0, 0, tzinfo=UTC)
    assert not search_refusal.is_refused("anthropic")
    again = FakeChatProvider([text_turn(ANSWER)])
    result = await _turn(again)
    assert again.calls[0].web_search is True and result.news == "searched"


def test_the_day_is_judged_in_utc_not_local_time() -> None:
    cairo = timezone(timedelta(hours=3))
    search_refusal.set_clock(lambda: datetime(2026, 11, 1, 1, 30, tzinfo=cairo))  # 22:30 UTC, 31st
    search_refusal.mark_refused("gemini")
    search_refusal.set_clock(lambda: datetime(2026, 11, 1, 2, 30, tzinfo=cairo))  # 23:30 UTC, 31st
    assert search_refusal.is_refused("gemini")
    search_refusal.set_clock(lambda: datetime(2026, 11, 1, 3, 0, tzinfo=cairo))  # 00:00 UTC, 1st
    assert not search_refusal.is_refused("gemini")


async def test_the_retry_tells_the_model_search_was_refused() -> None:
    provider = SearchRefusingProvider([text_turn(ANSWER)])
    await _turn(provider)
    system = provider.inner.calls[0].messages[0].content or ""
    assert system.startswith("s\n") and "refused web search" in system


async def test_other_errors_with_search_are_not_a_refusal() -> None:
    for error in (
        ProviderError("auth", "bad key"),
        ProviderError("unavailable", "down"),
        ProviderError("bad_request", "messages too long"),
    ):
        provider = SearchRefusingProvider([text_turn(ANSWER)], error)
        result = await _turn(provider)
        assert result.status == "error" and result.error_reason == error.code
        assert provider.attempts == [True]
        assert not search_refusal.is_refused("anthropic")


async def test_a_failing_retry_is_a_normal_error() -> None:
    provider = SearchRefusingProvider([ProviderError("unavailable", "down")])
    result = await _turn(provider)
    assert result.status == "error" and result.error_reason == "unavailable"
    assert provider.attempts == [True, False]
    assert search_refusal.is_refused("anthropic")  # the refusal itself still counts


async def test_refusal_inside_a_tool_loop_keeps_earlier_rounds_and_citations_out() -> None:
    call = ToolCall("c1", "price_summary", {"ticker": "COMI"})
    provider = SearchRefusingProvider([tool_turn(call), text_turn(PRICED)])
    result = await _turn(provider)
    # round 1: refused with search, retried plain (tool call); round 2: no search offered.
    assert provider.attempts == [True, False, False]
    assert result.status == "answered" and result.citations == []
    assert result.usage.calls == 2


# -- news state -------------------------------------------------------------------------------


async def test_news_states() -> None:
    searched = await _turn(FakeChatProvider([text_turn(ANSWER)]))
    assert searched.news == "searched"
    unsupported = await _turn(
        FakeChatProvider([text_turn(ANSWER)]), web_search=False, news="unsupported"
    )
    assert unsupported.news == "unsupported"
    explain_like = await _turn(
        FakeChatProvider([text_turn(ANSWER)]), web_search=False, news="not_offered"
    )
    assert explain_like.news == "not_offered"
    # A provider already marked does not turn an unsupported model into "refused".
    search_refusal.mark_refused("anthropic")
    still = await _turn(FakeChatProvider([text_turn(ANSWER)]), web_search=False, news="unsupported")
    assert still.news == "unsupported"


# -- errors: quota, reason ------------------------------------------------------------------


def test_quota_detail_names_the_model_and_never_says_try_again() -> None:
    detail = PROVIDER_ERROR_DETAILS["quota"].format(model="gemini-3.1-pro-preview")
    assert "gemini-3.1-pro-preview" in detail and "billing" in detail
    assert "try again" not in detail.lower()
    assert "try again" in PROVIDER_ERROR_DETAILS["rate_limit"].lower()


async def test_a_quota_failure_without_search_is_a_quota_error() -> None:
    provider = FakeChatProvider([ProviderError("quota", "exceeded your current quota")])
    result = await _turn(provider, web_search=False, news="unsupported")
    assert result.status == "error" and result.error_code == "PROVIDER_ERROR"
    assert result.error_reason == "quota"
    assert "claude-sonnet-5-5" in (result.error_detail or "")
    assert "try again" not in (result.error_detail or "").lower()
    assert not search_refusal.is_refused("anthropic")


def test_every_provider_error_code_has_a_detail_and_a_known_reason() -> None:
    codes = {"auth", "rate_limit", "quota", "unavailable", "bad_request", "unknown"}
    assert set(PROVIDER_ERROR_DETAILS) == codes == ERROR_REASONS
    with pytest.raises(ValueError):
        format_event("error", {"code": "PROVIDER_ERROR", "detail": "x"})
    with pytest.raises(ValueError):
        format_event("error", {"code": "PROVIDER_ERROR", "detail": "x", "reason": "weird"})
    assert format_event("error", {"code": "NO_KEY", "detail": "x"}).startswith("event: error")


# -- frames -----------------------------------------------------------------------------------


def _use(provider: Any) -> None:
    app.dependency_overrides[get_chat_provider] = lambda: provider


async def test_chat_answer_frame_reports_a_refused_search_and_stores_it(
    client: AsyncClient, env_key: str, company: Company, db_session: AsyncSession
) -> None:
    provider = SearchRefusingProvider(
        [
            tool_turn(ToolCall("c1", "price_summary", {"ticker": company.ticker})),
            text_turn(f"{company.ticker} last closed at 31.9 (source: price_summary)."),
        ]
    )
    _use(provider)
    events = await post_stream(
        client, "/chat", {"message": "What is the latest close?", "ticker": company.ticker}
    )
    answer = first(events, "answer")
    assert answer["news"] == "refused" and answer["general"] is False
    assert first(events, "meta")["web_search"] is True  # the model is capable; the key refused
    assert provider.attempts == [True, False, False]
    stored = (
        await db_session.execute(select(AiMessage).where(AiMessage.role == "assistant"))
    ).scalar_one()
    assert stored.verification["news"] == "refused" and stored.verification["verified"] is True

    # The next question in the same day does not even try to search.
    provider2 = SearchRefusingProvider([text_turn("Nothing to add.")])
    _use(provider2)
    again = await post_stream(client, "/chat", {"message": "hello", "ticker": company.ticker})
    assert first(again, "answer")["news"] == "refused"
    assert provider2.attempts == [False]
    assert "refused web search" in (provider2.inner.calls[0].messages[0].content or "")


async def test_chat_news_state_for_each_kind_of_turn(
    client: AsyncClient, env_key: str, company: Company
) -> None:
    install_provider([text_turn("Hello there.")])
    scoped = await post_stream(client, "/chat", {"message": "hi", "ticker": company.ticker})
    assert first(scoped, "answer")["news"] == "searched"  # offered, whether or not it was used

    install_provider([text_turn("Hello there.")])
    haiku = await post_stream(
        client, "/chat", {"message": "hi", "ticker": company.ticker, "model": "claude-haiku-4-5"}
    )
    assert first(haiku, "answer")["news"] == "unsupported"

    install_provider([text_turn("A P/E ratio compares price with earnings, often near 15.")])
    general = await post_stream(client, "/chat", {"message": "What is a P/E ratio?"})
    assert first(general, "answer")["general"] is True
    assert first(general, "answer")["news"] == "not_offered"

    install_provider([text_turn("The stance combines the engines that had data.")])
    explain = await post_stream(
        client, "/explain", {"ticker": company.ticker, "card": "stance", "lang": "en"}
    )
    assert first(explain, "answer")["news"] == "not_offered"


async def test_unverified_frame_carries_news(
    client: AsyncClient, env_key: str, company: Company
) -> None:
    bad = text_turn(f"{company.ticker} trades at 99.9.")
    install_provider([bad, bad])
    events = await post_stream(client, "/chat", {"message": "price?", "ticker": company.ticker})
    assert first(events, "unverified")["news"] == "searched"


async def test_provider_error_frame_carries_the_reason(
    client: AsyncClient, env_key: str, company: Company
) -> None:
    install_provider([ProviderError("quota", "exceeded your current quota")])
    events = await post_stream(
        client, "/chat", {"message": "hi", "ticker": company.ticker, "model": "claude-haiku-4-5"}
    )
    error = first(events, "error")
    assert error["code"] == "PROVIDER_ERROR" and error["reason"] == "quota"
    assert "claude-haiku-4-5" in error["detail"] and "try again" not in error["detail"].lower()
    assert names(events)[-1] == "done"

    install_provider([ProviderError("auth", "bad")])
    auth = await post_stream(client, "/chat", {"message": "hi", "model": "claude-haiku-4-5"})
    assert first(auth, "error")["reason"] == "auth"
    # Errors that are not provider errors carry no reason.
    install_provider([])
    no_key = await post_stream(client, "/chat", {"message": "hi", "model": "gpt-5.5"})
    assert first(no_key, "error")["code"] == "NO_KEY" and "reason" not in first(no_key, "error")


async def test_max_tokens_and_search_flag_on_the_retry() -> None:
    provider = SearchRefusingProvider([text_turn(ANSWER)])
    await _turn(provider)
    assert provider.inner.calls[0].max_tokens == MAX_OUTPUT_TOKENS
    assert provider.inner.calls[0].web_search is False
