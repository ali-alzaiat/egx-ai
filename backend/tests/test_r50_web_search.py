"""R50 web search: catalog flags, request building, citations, search fees, orchestrator budget.

No network: LiteLLM's ``acompletion`` is replaced by a scripted stream, and the orchestrator
runs against the fake provider.
"""

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import pytest

from app.ai.catalog import CATALOG, get_model
from app.ai.constants import MAX_WEB_SEARCHES
from app.ai.gateway.base import ChatMessage, Citation, Done, TextDelta, ToolCall, ToolSpec
from app.ai.gateway.fake import FakeChatProvider, text_turn, tool_turn
from app.ai.gateway.litellm_provider import (
    ANTHROPIC_WEB_SEARCH_TOOL,
    LiteLLMProvider,
    citations_from_delta,
    load_litellm,
    safe_citation,
)
from app.ai.orchestrator import Progress, TurnResult, run_turn
from app.ai.tools import ToolOutcome

SECRET = "sk-ant-SECRETVALUE1234567890"
FN = ToolSpec("valuation", "d", {"type": "object"})
LITELLM_WARNING = "ignore:Item 'summary' on TypedDict:UserWarning"


# -- catalog ------------------------------------------------------------------------------


def test_web_search_flags_follow_the_contract() -> None:
    searchable = {m.id for m in CATALOG if m.web_search}
    assert searchable == {
        "claude-sonnet-5-5",
        "claude-opus-5-5",
        "gemini-3.1-pro-preview",
        "gemini-3.5-flash-lite",
    }
    for entry in CATALOG:
        if entry.provider == "openai" or entry.id == "claude-haiku-4-5":
            assert entry.web_search is False


@pytest.mark.parametrize("entry", [m for m in CATALOG if m.web_search], ids=lambda m: m.id)
def test_every_web_search_model_supports_web_search_options_in_litellm(entry: Any) -> None:
    litellm = load_litellm()
    params = litellm.get_supported_openai_params(
        model=entry.id, custom_llm_provider=entry.provider
    )
    assert "web_search_options" in params
    # A search fee must be priceable, or the turn cost would be unknown.
    price = litellm.model_cost[entry.cost_key]["search_context_cost_per_query"]
    assert Decimal(str(price["search_context_size_medium"])) > 0


# -- request building ---------------------------------------------------------------------


class _Capture:
    def __init__(self, chunks: list[Any]) -> None:
        self.chunks = chunks
        self.kwargs: dict[str, Any] = {}

    async def __call__(self, **kwargs: Any) -> AsyncIterator[Any]:
        self.kwargs = kwargs
        chunks = self.chunks

        async def gen() -> AsyncIterator[Any]:
            for chunk in chunks:
                yield chunk

        return gen()


def _stream_chunk(**delta: Any) -> Any:
    from litellm.types.utils import Delta, ModelResponseStream, StreamingChoices

    return ModelResponseStream(choices=[StreamingChoices(delta=Delta(**delta))])


def _usage_chunk(prompt: int, completion: int, **usage: Any) -> Any:
    from litellm.types.utils import ModelResponseStream, Usage

    return ModelResponseStream(
        choices=[],
        usage=Usage(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
            **usage,
        ),
    )


async def _events(
    monkeypatch: pytest.MonkeyPatch,
    model: str,
    chunks: list[Any],
    *,
    web_search: bool,
    max_searches: int = 3,
) -> tuple[list[Any], dict[str, Any]]:
    litellm = load_litellm()
    capture = _Capture(chunks)
    monkeypatch.setattr(litellm, "acompletion", capture)
    events = [
        e
        async for e in LiteLLMProvider().stream(
            model,
            SECRET,
            [ChatMessage("user", "news?")],
            [FN],
            1500,
            web_search=web_search,
            max_web_searches=max_searches,
        )
    ]
    return events, capture.kwargs


@pytest.mark.filterwarnings(LITELLM_WARNING)
async def test_anthropic_gets_the_hosted_search_tool_capped_at_three(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, kwargs = await _events(monkeypatch, "claude-sonnet-5-5", [], web_search=True)
    hosted = [t for t in kwargs["tools"] if t.get("type") == ANTHROPIC_WEB_SEARCH_TOOL]
    assert hosted == [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
    assert kwargs["tools"][0]["function"]["name"] == "valuation"  # our own tools stay
    assert "web_search_options" not in kwargs

    _, fewer = await _events(
        monkeypatch, "claude-opus-5-5", [], web_search=True, max_searches=1
    )
    assert fewer["tools"][-1]["max_uses"] == 1


@pytest.mark.filterwarnings(LITELLM_WARNING)
async def test_litellm_keeps_the_hosted_tool_and_its_cap_in_the_anthropic_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    litellm = load_litellm()
    _, kwargs = await _events(monkeypatch, "claude-sonnet-5-5", [], web_search=True)
    params = litellm.utils.get_optional_params(
        model="claude-sonnet-5-5",
        custom_llm_provider="anthropic",
        tools=kwargs["tools"],
        max_tokens=100,
        stream=True,
    )
    tools = params["tools"]
    assert {"type": "web_search_20250305", "name": "web_search", "max_uses": 3} in tools
    assert any(t.get("name") == "valuation" for t in tools)


@pytest.mark.filterwarnings(LITELLM_WARNING)
async def test_gemini_gets_web_search_options_and_the_server_side_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    litellm = load_litellm()
    _, kwargs = await _events(monkeypatch, "gemini-3.1-pro-preview", [], web_search=True)
    assert isinstance(kwargs["web_search_options"], dict)
    assert kwargs["include_server_side_tool_invocations"] is True
    # Without that flag LiteLLM silently drops the search tool next to function tools.
    params = litellm.utils.get_optional_params(
        model="gemini-3.1-pro-preview",
        custom_llm_provider="gemini",
        tools=kwargs["tools"],
        web_search_options=kwargs["web_search_options"],
        include_server_side_tool_invocations=True,
        max_tokens=100,
        stream=True,
    )
    assert {"googleSearch": {}} in params["tools"]
    assert any("function_declarations" in t for t in params["tools"])


@pytest.mark.filterwarnings(LITELLM_WARNING)
@pytest.mark.parametrize(
    ("model", "flag"),
    [
        ("claude-sonnet-5-5", False),  # not asked to search
        ("claude-haiku-4-5", True),  # cannot search
        ("gpt-5.5", True),
        ("gpt-5.4-mini", True),
    ],
)
async def test_no_search_request_unless_asked_and_supported(
    monkeypatch: pytest.MonkeyPatch, model: str, flag: bool
) -> None:
    _, kwargs = await _events(monkeypatch, model, [], web_search=flag)
    assert "web_search_options" not in kwargs
    assert "include_server_side_tool_invocations" not in kwargs
    assert not any("web_search" in str(t.get("type", "")) for t in kwargs["tools"])
    assert get_model(model) is not None


# -- citations ----------------------------------------------------------------------------


def test_safe_citation_accepts_only_http_and_https() -> None:
    assert safe_citation("https://news.test/a?x=1", "Title") == Citation(
        "https://news.test/a?x=1", "Title"
    )
    assert safe_citation("http://news.test/a", None) == Citation("http://news.test/a", "news.test")
    for bad in (
        "javascript:alert(1)",
        "data:text/html;base64,AAAA",
        "ftp://x.test/a",
        "file:///etc/passwd",
        "//news.test/a",
        "https://",
        "",
        "   ",
        None,
        12,
        "https://x.test/" + "a" * 2100,
    ):
        assert safe_citation(bad, "t") is None


@pytest.mark.filterwarnings(LITELLM_WARNING)
def test_citations_from_both_vendor_shapes_and_ignores_unrelated_fields() -> None:
    from litellm.types.utils import Delta

    anthropic = Delta(
        content="x",
        provider_specific_fields={
            "citation": {
                "type": "web_search_result_location",
                "url": "https://a.test/1",
                "title": "A one",
                "cited_text": "text the model saw",
            }
        },
    )
    assert citations_from_delta(anthropic) == [Citation("https://a.test/1", "A one")]
    gemini = Delta(
        content="x",
        annotations=[
            {"type": "url_citation", "url_citation": {"url": "https://g.test/2", "title": "G"}},
            {"type": "url_citation", "url_citation": {"url": "javascript:x", "title": "bad"}},
            {"type": "something_else", "url_citation": {"url": "https://no.test", "title": "n"}},
        ],
    )
    assert citations_from_delta(gemini) == [Citation("https://g.test/2", "G")]
    assert citations_from_delta(Delta(content="see https://in-the-text.test")) == []
    other_fields = Delta(content="x", provider_specific_fields={"thinking_blocks": []})
    assert citations_from_delta(other_fields) == []


@pytest.mark.filterwarnings(LITELLM_WARNING)
async def test_stream_emits_deduplicated_citations_and_the_reported_search_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from litellm.types.utils import ServerToolUse

    cite = {"type": "web_search_result_location", "url": "https://a.test/1", "title": "A"}
    chunks = [
        _stream_chunk(content="News ", provider_specific_fields={"citation": cite}),
        _stream_chunk(content="said.", provider_specific_fields={"citation": cite}),
        _stream_chunk(
            content=None,
            provider_specific_fields={
                "citation": {"url": "https://b.test/2", "title": "B"},
            },
        ),
        _usage_chunk(1000, 100, server_tool_use=ServerToolUse(web_search_requests=2)),
    ]
    events, _ = await _events(monkeypatch, "claude-sonnet-5-5", chunks, web_search=True)
    citations = [e for e in events if isinstance(e, Citation)]
    assert citations == [Citation("https://a.test/1", "A"), Citation("https://b.test/2", "B")]
    assert [e.text for e in events if isinstance(e, TextDelta)] == ["News ", "said."]
    done = events[-1]
    assert isinstance(done, Done) and done.web_searches == 2
    # 1000 * 2e-6 + 100 * 1e-5 tokens, plus 2 searches at $0.01 from LiteLLM's cost map.
    assert done.cost_usd == Decimal("0.023")


@pytest.mark.filterwarnings(LITELLM_WARNING)
async def test_citations_are_ignored_when_the_call_did_not_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cite = {"url": "https://a.test/1", "title": "A"}
    chunks = [_stream_chunk(content="x", provider_specific_fields={"citation": cite})]
    events, _ = await _events(monkeypatch, "claude-sonnet-5-5", chunks, web_search=False)
    assert not [e for e in events if isinstance(e, Citation)]


@pytest.mark.filterwarnings(LITELLM_WARNING)
async def test_gemini_annotations_and_search_fee(monkeypatch: pytest.MonkeyPatch) -> None:
    from litellm.types.utils import PromptTokensDetailsWrapper

    chunks = [
        _stream_chunk(
            content="Hi",
            annotations=[
                {"type": "url_citation", "url_citation": {"url": "https://g.test/1", "title": ""}}
            ],
        ),
        _usage_chunk(
            1000,
            100,
            prompt_tokens_details=PromptTokensDetailsWrapper(web_search_requests=1),
        ),
    ]
    events, _ = await _events(monkeypatch, "gemini-3.1-pro-preview", chunks, web_search=True)
    assert [e for e in events if isinstance(e, Citation)] == [
        Citation("https://g.test/1", "g.test")  # no title: the site, not model text
    ]
    done = events[-1]
    assert isinstance(done, Done) and done.web_searches == 1
    # 1000 * 2e-6 + 100 * 1.2e-5 tokens + 1 search at $0.014.
    assert done.cost_usd == Decimal("0.0172")


@pytest.mark.filterwarnings(LITELLM_WARNING)
async def test_a_search_turn_without_fees_reported_costs_tokens_only_when_nothing_was_cited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chunks = [_stream_chunk(content="No search needed."), _usage_chunk(1000, 100)]
    events, _ = await _events(monkeypatch, "claude-sonnet-5-5", chunks, web_search=True)
    done = events[-1]
    assert isinstance(done, Done) and done.web_searches is None
    assert done.cost_usd == Decimal("0.003")  # no search usage and no citation: none ran


@pytest.mark.filterwarnings(LITELLM_WARNING)
async def test_unknown_search_count_or_price_makes_the_cost_unknown_never_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Cited sources but no reported count: searches happened, how many is unknown.
    cite = {"url": "https://a.test/1", "title": "A"}
    chunks = [
        _stream_chunk(content="x", provider_specific_fields={"citation": cite}),
        _usage_chunk(1000, 100),
    ]
    events, _ = await _events(monkeypatch, "claude-sonnet-5-5", chunks, web_search=True)
    done = events[-1]
    assert isinstance(done, Done) and done.cost_usd is None

    # Searches reported but the model has no search price in the cost map.
    from litellm.types.utils import ServerToolUse

    litellm = load_litellm()
    entry = dict(litellm.model_cost["claude-sonnet-5-5"])
    del entry["search_context_cost_per_query"]
    monkeypatch.setitem(litellm.model_cost, "claude-sonnet-5-5", entry)
    chunks = [
        _stream_chunk(content="x"),
        _usage_chunk(1000, 100, server_tool_use=ServerToolUse(web_search_requests=1)),
    ]
    events, _ = await _events(monkeypatch, "claude-sonnet-5-5", chunks, web_search=True)
    done = events[-1]
    assert isinstance(done, Done) and done.web_searches == 1 and done.cost_usd is None


# -- orchestrator -------------------------------------------------------------------------

PRICE = {"tool": "price_summary", "ticker": "COMI", "data": {"latest": {"close": "84.50"}}}


async def _execute(name: str, arguments: dict[str, Any]) -> ToolOutcome:
    return ToolOutcome(PRICE, True, "COMI")


async def _allow(_cost: Decimal) -> bool:
    return True


async def _run(
    provider: FakeChatProvider, *, web_search: bool = True, user_text: str = "COMI news?"
) -> TurnResult:
    result: TurnResult | None = None
    async for item in run_turn(
        provider=provider,
        model="claude-sonnet-5-5",
        api_key="k-test-1234",
        messages=[ChatMessage("system", "s"), ChatMessage("user", user_text)],
        tools=[ToolSpec("price_summary", "d", {"type": "object"})],
        execute=_execute,
        allow_call=_allow,
        user_text=user_text,
        web_search=web_search,
    ):
        if not isinstance(item, Progress):
            result = item
    assert result is not None
    return result


def _call() -> ToolCall:
    return ToolCall("c1", "price_summary", {"ticker": "COMI"})


async def test_citations_become_web_sources_after_the_tool_sources() -> None:
    fake = FakeChatProvider(
        [
            tool_turn(_call(), citations=[Citation("https://a.test/1", "A")], web_searches=1),
            text_turn(
                "COMI last closed at 84.50. News mentions a new plant.",
                citations=[Citation("https://a.test/1", "A"), Citation("https://b.test/2", "B")],
                web_searches=1,
            ),
        ]
    )
    result = await _run(fake)
    assert result.status == "answered"
    assert result.sources == [
        {"tool": "price_summary", "ticker": "COMI"},
        {"tool": "web", "url": "https://a.test/1", "title": "A"},
        {"tool": "web", "url": "https://b.test/2", "title": "B"},
    ]
    assert result.usage.web_searches == 2


async def test_a_figure_that_only_appears_in_a_citation_is_not_verified() -> None:
    cited = Citation("https://a.test/1", "Shares jump 7.5% on strong demand")
    fake = FakeChatProvider(
        [
            tool_turn(_call()),
            text_turn("COMI rose 7.5% on the news.", citations=[cited], web_searches=1),
            text_turn("COMI rose 7.5% on the news.", citations=[cited], web_searches=0),
        ]
    )
    result = await _run(fake)
    assert result.status == "unverified"  # citations are never in the verify pool (B4)
    assert result.verification is not None and "7.5%" in result.verification.unverified


async def test_search_budget_is_three_per_turn_across_rounds() -> None:
    assert MAX_WEB_SEARCHES == 3
    fake = FakeChatProvider(
        [
            tool_turn(_call(), web_searches=2),
            text_turn("COMI last closed at 84.50.", web_searches=1),
        ]
    )
    await _run(fake)
    first, second = fake.calls
    assert (first.web_search, first.max_web_searches) == (True, 3)
    assert (second.web_search, second.max_web_searches) == (True, 1)  # 3 - 2 used

    spent = FakeChatProvider(
        [
            tool_turn(_call(), web_searches=3),
            text_turn("COMI last closed at 84.50."),
        ]
    )
    await _run(spent)
    assert spent.calls[0].web_search is True
    assert spent.calls[1].web_search is False  # the budget is used up


async def test_web_search_is_off_unless_the_caller_enables_it() -> None:
    fake = FakeChatProvider([text_turn("Hello.")])
    await _run(fake, web_search=False, user_text="hi")
    assert fake.calls[0].web_search is False


async def test_search_fees_in_done_are_added_to_the_turn_cost() -> None:
    fake = FakeChatProvider(
        [
            tool_turn(_call(), cost="0.011", web_searches=1),
            text_turn("COMI last closed at 84.50.", cost="0.002"),
        ]
    )
    result = await _run(fake)
    assert result.usage.cost_usd == Decimal("0.013")
