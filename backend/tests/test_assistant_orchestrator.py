"""Tool loop with the fake provider: tool rounds, verify, retry once, withhold, cap, errors."""

from decimal import Decimal
from typing import Any

from app.ai.constants import MAX_OUTPUT_TOKENS, MAX_TOOL_ROUNDS
from app.ai.gateway.base import ChatMessage, ProviderError, ToolCall, ToolSpec
from app.ai.gateway.fake import FakeChatProvider, text_turn, tool_turn
from app.ai.orchestrator import Progress, TurnResult, run_turn
from app.ai.tools import ToolOutcome

SPEC = ToolSpec("price_summary", "d", {"type": "object"})
PRICE = {"tool": "price_summary", "ticker": "COMI", "data": {"latest": {"close": "84.50"}}}


async def _execute(name: str, arguments: dict[str, Any]) -> ToolOutcome:
    if name == "price_summary":
        return ToolOutcome(PRICE, True, "COMI")
    return ToolOutcome({"error": "UNKNOWN_TOOL", "detail": name}, False, None)


async def _allow(_cost: Decimal) -> bool:
    return True


async def _run(
    provider: FakeChatProvider, *, allow: Any = _allow, user_text: str = "price?"
) -> tuple[list[Progress], TurnResult]:
    progress: list[Progress] = []
    result: TurnResult | None = None
    async for item in run_turn(
        provider=provider,
        model="claude-sonnet-5-5",
        api_key="k-test-1234",
        messages=[ChatMessage("system", "s"), ChatMessage("user", user_text)],
        tools=[SPEC],
        execute=_execute,
        allow_call=allow,
        user_text=user_text,
    ):
        if isinstance(item, Progress):
            progress.append(item)
        else:
            result = item
    assert result is not None
    return progress, result


def _call(call_id: str = "c1", name: str = "price_summary") -> ToolCall:
    return ToolCall(call_id, name, {"ticker": "COMI"})


async def test_tool_round_then_verified_answer() -> None:
    fake = FakeChatProvider(
        [tool_turn(_call()), text_turn("COMI last closed at 84.50 (source: price_summary).")]
    )
    progress, result = await _run(fake)
    assert result.status == "answered" and result.text.startswith("COMI last closed")
    assert result.verification is not None and result.verification.checked == 1
    assert result.sources == [{"tool": "price_summary", "ticker": "COMI"}]
    assert [p.stage for p in progress] == ["thinking", "tool", "thinking", "verifying"]
    assert progress[1].tool == "price_summary"
    # The second call saw the assistant tool call and the tool result.
    second = fake.calls[1].messages
    assert second[-2].tool_calls[0].name == "price_summary"
    assert second[-1].role == "tool" and "84.50" in (second[-1].content or "")
    assert all(c.max_tokens == MAX_OUTPUT_TOKENS and c.api_key == "k-test-1234" for c in fake.calls)
    assert result.usage.calls == 2
    assert result.usage.cost_usd == Decimal("0.002")


async def test_unverified_answer_is_retried_once_with_the_numbers_listed() -> None:
    fake = FakeChatProvider(
        [
            tool_turn(_call()),
            text_turn("It closed at 99.99."),
            text_turn("It closed at 84.50."),
        ]
    )
    progress, result = await _run(fake)
    assert result.status == "answered" and result.retried
    assert "retrying" in [p.stage for p in progress]
    retry_messages = fake.calls[2].messages
    assert retry_messages[-2].content == "It closed at 99.99."
    assert "99.99" in (retry_messages[-1].content or "")
    assert len(fake.calls) == 3


async def test_second_failure_withholds_the_answer() -> None:
    fake = FakeChatProvider(
        [tool_turn(_call()), text_turn("It closed at 99.99."), text_turn("It closed at 77.7.")]
    )
    _, result = await _run(fake)
    assert result.status == "unverified"
    assert result.text == ""  # withheld, never shown
    assert result.verification is not None and result.verification.unverified == ["77.7"]
    assert len(fake.calls) == 3  # exactly one retry


async def test_answer_with_no_figures_passes_with_zero_checked() -> None:
    fake = FakeChatProvider([text_turn("The price data is not available for this company.")])
    _, result = await _run(fake)
    assert result.status == "answered"
    assert result.verification is not None and result.verification.checked == 0


async def test_user_supplied_numbers_do_not_need_a_tool() -> None:
    fake = FakeChatProvider([text_turn("You asked about 500 shares.")])
    _, result = await _run(fake, user_text="what about my 500 shares?")
    assert result.status == "answered"


async def test_cap_reached_makes_no_provider_call() -> None:
    async def deny(_cost: Decimal) -> bool:
        return False

    fake = FakeChatProvider([text_turn("never")])
    _, result = await _run(fake, allow=deny)
    assert result.status == "cap_reached" and result.error_code == "CAP_REACHED"
    assert fake.calls == []


async def test_cap_is_checked_before_every_call_with_the_turn_cost_so_far() -> None:
    seen: list[Decimal] = []

    async def allow_once(cost: Decimal) -> bool:
        seen.append(cost)
        return len(seen) == 1

    fake = FakeChatProvider([tool_turn(_call()), text_turn("84.50")])
    _, result = await _run(fake, allow=allow_once)
    assert result.status == "cap_reached"
    assert len(fake.calls) == 1
    assert seen == [Decimal(0), Decimal("0.001")]


async def test_provider_error_becomes_a_generic_error_without_provider_text() -> None:
    fake = FakeChatProvider([ProviderError("auth", "bad key sk-LEAKYLEAKY123456")])
    _, result = await _run(fake)
    assert result.status == "error" and result.error_code == "PROVIDER_ERROR"
    assert "sk-LEAKY" not in (result.error_detail or "")


async def test_tool_rounds_are_capped_then_a_final_call_has_no_tools() -> None:
    turns = [tool_turn(_call(f"c{i}")) for i in range(MAX_TOOL_ROUNDS)]
    turns.append(text_turn("Done: 84.50."))
    fake = FakeChatProvider(turns)
    _, result = await _run(fake)
    assert result.status == "answered"
    assert len(fake.calls) == MAX_TOOL_ROUNDS + 1
    assert fake.calls[-1].tools == []
    assert all(c.tools for c in fake.calls[:-1])


async def test_unknown_tool_is_reported_to_the_model_not_raised() -> None:
    fake = FakeChatProvider(
        [tool_turn(_call(name="drop_tables")), text_turn("I could not fetch that.")]
    )
    _, result = await _run(fake)
    assert result.status == "answered"
    tool_msg = fake.calls[1].messages[-1]
    assert "UNKNOWN_TOOL" in (tool_msg.content or "")
    assert result.sources == []  # failed tool calls are not sources


async def test_empty_model_answer_is_an_error() -> None:
    fake = FakeChatProvider([text_turn("")])
    _, result = await _run(fake)
    assert result.status == "error"
