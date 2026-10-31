# ruff: noqa: F811  (R49 fixtures are imported, then used as test arguments)
"""R50 assistant API: web search frames, general answers, data_check explain, prompt version."""

import json
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.constants import AI_PROMPT_VERSION
from app.ai.gateway.base import Citation, ToolCall
from app.ai.gateway.fake import text_turn, tool_turn
from app.models.assistant import AiMessage
from app.models.market import Company
from assistant_support import first, install_provider, names, post_stream
from statement_seed import FULL_YEAR, make_company, seed_prices, seed_year
from test_assistant_api import (  # noqa: F401 - the R49 fixtures, autouse ones included
    assistant_env,
    company,
    env_key,
    no_network,
)


def _statuses(events: list[tuple[str, dict]]) -> list[str]:  # type: ignore[type-arg]
    return [d["stage"] for n, d in events if n == "status"]


def test_prompt_version_is_bumped() -> None:
    assert AI_PROMPT_VERSION == "assistant-1.2"


async def test_models_list_marks_the_search_capable_models(client: AsyncClient) -> None:
    models = {m["id"]: m for m in (await client.get("/api/assistant/models")).json()["models"]}
    assert models["claude-sonnet-5-5"]["web_search"] is True
    assert models["claude-opus-5-5"]["web_search"] is True
    assert models["gemini-3.1-pro-preview"]["web_search"] is True
    assert models["claude-haiku-4-5"]["web_search"] is False
    assert models["gpt-5.5"]["web_search"] is False
    assert all(isinstance(m["web_search"], bool) for m in models.values())


# -- web search ---------------------------------------------------------------------------


async def test_chat_turns_on_search_for_a_capable_model_and_lists_web_sources_last(
    client: AsyncClient, env_key: str, company: Company, db_session: AsyncSession
) -> None:
    ticker = company.ticker
    cites = [Citation("https://news.test/a", "News A"), Citation("javascript:x", "bad")]
    fake = install_provider(
        [
            tool_turn(
                ToolCall("c1", "price_summary", {"ticker": ticker}),
                web_searches=1,
                citations=cites[:1],
            ),
            text_turn(
                f"{ticker} last closed at 31.9 (source: price_summary). Press coverage "
                "mentions a new product line.",
                citations=[Citation("https://news.test/a", "News A")],
                web_searches=1,
                cost="0.012",
            ),
        ]
    )
    events = await post_stream(
        client, "/chat", {"message": "Any news and the latest close?", "ticker": ticker}
    )
    meta = first(events, "meta")
    assert meta["web_search"] is True and meta["model"] == "claude-sonnet-5-5"
    assert [c.web_search for c in fake.calls] == [True, True]
    assert [c.max_web_searches for c in fake.calls] == [3, 2]
    system = fake.calls[0].messages[0].content or ""
    assert "Web search is available" in system
    assert "Web search is not available" not in system
    answer = first(events, "answer")
    assert answer["general"] is False and answer["verified"] is True
    assert answer["sources"][-1] == {"tool": "web", "url": "https://news.test/a", "title": "News A"}
    assert answer["sources"][:-1] == [
        {"tool": "company_overview", "ticker": ticker},
        {"tool": "price_summary", "ticker": ticker},
    ]
    stored = (
        await db_session.execute(select(AiMessage).where(AiMessage.role == "assistant"))
    ).scalar_one()
    assert stored.prompt_version == "assistant-1.2"
    assert {"name": "web", "url": "https://news.test/a", "title": "News A"} in stored.tool_calls


async def test_a_model_without_search_is_told_news_was_not_checked(
    client: AsyncClient, env_key: str, company: Company
) -> None:
    fake = install_provider([text_turn("Hello, I can explain terms.")])
    events = await post_stream(
        client, "/chat", {"message": "hello", "model": "claude-haiku-4-5", "ticker": company.ticker}
    )
    assert first(events, "meta")["web_search"] is False
    assert fake.calls[0].web_search is False
    system = fake.calls[0].messages[0].content or ""
    assert "Web search is not available" in system and "news was not checked" in system


async def test_web_figures_do_not_pass_the_number_check(
    client: AsyncClient, env_key: str, company: Company
) -> None:
    ticker = company.ticker
    lie = text_turn(
        f"{ticker} rose 7.5% after the announcement.",
        citations=[Citation("https://news.test/a", "Shares jump 7.5% on the announcement")],
        web_searches=1,
    )
    install_provider([tool_turn(ToolCall("c1", "price_summary", {"ticker": ticker})), lie, lie])
    events = await post_stream(client, "/chat", {"message": "news?", "ticker": ticker})
    unverified = first(events, "unverified")
    assert any("7.5" in u for u in unverified["unverified"])
    assert "answer" not in names(events)
    title = "Shares jump 7.5% on the announcement"
    web = {"tool": "web", "url": "https://news.test/a", "title": title}
    assert web in unverified["sources"]


# -- general answers (B8) -----------------------------------------------------------------


async def test_a_general_answer_with_figures_passes_labelled_and_unchecked(
    client: AsyncClient, env_key: str, db_session: AsyncSession
) -> None:
    await make_company(db_session, sector="Banks")  # companies exist; none is named
    fake = install_provider(
        [
            text_turn(
                "A price-to-earnings ratio compares a share price with earnings per share. "
                "Textbooks often quote 15 as a rough market average, 8.4 for value stocks."
            )
        ]
    )
    events = await post_stream(client, "/chat", {"message": "What does a P/E ratio measure?"})
    answer = first(events, "answer")
    assert answer["general"] is True and answer["verified"] is True and answer["checked"] == 0
    assert answer["sources"] == []
    assert "verifying" not in _statuses(events)
    assert len(fake.calls) == 1  # no retry: nothing was checked
    stored = (
        await db_session.execute(select(AiMessage).where(AiMessage.role == "assistant"))
    ).scalar_one()
    assert stored.status == "answered"
    assert stored.verification == {"general": True, "news": "not_offered"}
    assert "8.4" in stored.content


async def test_an_answer_naming_a_known_ticker_with_an_invented_number_is_still_blocked(
    client: AsyncClient, env_key: str, db_session: AsyncSession
) -> None:
    co = await make_company(db_session, sector="Banks")
    await seed_prices(db_session, co)
    invented = text_turn(f"{co.ticker} trades at 99.9 and is a bargain.")
    fake = install_provider([invented, invented])
    events = await post_stream(client, "/chat", {"message": "Tell me about a bank stock"})
    assert "answer" not in names(events)
    blocked = first(events, "unverified")
    assert any("99.9" in u for u in blocked["unverified"])
    assert len(fake.calls) == 2  # one retry, as in R49
    stored = (
        await db_session.execute(select(AiMessage).where(AiMessage.role == "assistant"))
    ).scalar_one()
    assert stored.status == "unverified" and stored.content == ""


async def test_naming_the_company_in_the_question_also_keeps_the_check_on(
    client: AsyncClient, env_key: str, db_session: AsyncSession
) -> None:
    co = await make_company(db_session, sector="Banks")
    invented = text_turn("It trades at 99.9 right now.")  # the answer itself names nobody
    install_provider([invented, invented])
    events = await post_stream(client, "/chat", {"message": f"What is {co.ticker} trading at?"})
    assert "unverified" in names(events) and "answer" not in names(events)


async def test_a_turn_that_ran_a_tool_is_never_general(
    client: AsyncClient, env_key: str, db_session: AsyncSession
) -> None:
    co = await make_company(db_session, sector="Banks")
    await seed_prices(db_session, co)
    bad = text_turn("The close was 77.7.")  # no company named, but a company tool ran
    install_provider(
        [tool_turn(ToolCall("c1", "price_summary", {"ticker": co.ticker})), bad, bad]
    )
    events = await post_stream(client, "/chat", {"message": "What was the close?"})
    assert "unverified" in names(events)
    assert "answer" not in names(events)


async def test_a_general_answer_in_arabic_names_no_company(
    client: AsyncClient, env_key: str, db_session: AsyncSession
) -> None:
    await make_company(db_session, sector="Banks")
    install_provider([text_turn("مكرر الربحية يقارن سعر السهم بربحيته. المتوسط النظري 15.")])
    events = await post_stream(
        client, "/chat", {"message": "ما هو مكرر الربحية؟", "lang": "ar"}
    )
    assert first(events, "answer")["general"] is True


# -- explain: data_check --------------------------------------------------------------------


async def test_explain_data_check_runs_the_tool_and_never_shows_a_vendor_figure(
    client: AsyncClient, env_key: str, db_session: AsyncSession
) -> None:
    co = await make_company(db_session, sector="Banks")
    await seed_prices(db_session, co, bars=40)
    await seed_year(db_session, co, 2025, FULL_YEAR, tier="filing", page="12")
    await seed_year(db_session, co, 2025, {"revenue": Decimal("1062.37")}, tier="vendor")
    fake = install_provider([text_turn("One check failed: revenue differs from a second source.")])
    events = await post_stream(
        client, "/explain", {"ticker": co.ticker, "card": "data_check", "lang": "en"}
    )
    meta = first(events, "meta")
    assert meta["conversation_id"] is None and meta["web_search"] is False
    stages = [(d["stage"], d.get("tool")) for n, d in events if n == "status"]
    assert ("tool", "data_check") in stages
    answer = first(events, "answer")
    assert {"tool": "data_check", "ticker": co.ticker} in answer["sources"]
    assert answer["general"] is False
    sent = fake.calls[0]
    assert sent.web_search is False  # explain never searches
    assert sent.messages[2].tool_calls[0].name == "data_check"
    tool_message = sent.messages[3].content or ""
    payload = json.loads(tool_message)
    assert payload["tool"] == "data_check" and len(payload["data"]["checks"]) == 5
    assert "1062.37" not in tool_message
    assert "Web search" not in (sent.messages[0].content or "")  # no search line in explain


async def test_explain_rejects_unknown_cards_still(client: AsyncClient, env_key: str) -> None:
    resp = await client.post("/api/assistant/explain", json={"ticker": "X", "card": "news"})
    assert resp.status_code == 422
