"""Chat and explain streams: resolve model and key, run the turn, persist, emit SSE frames.

Both streams end with ``done``. Errors found before any model call (no key, unknown model,
cap reached, nothing to explain) are ``error`` events, not HTTP errors: the request itself was
valid. The answer is only emitted after verification (R49 A3).
"""

import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.catalog import CatalogModel, get_model
from app.ai.constants import (
    AI_PROMPT_VERSION,
    MAX_HISTORY_MESSAGES,
    STATUS_ANSWERED,
    STATUS_CAP_REACHED,
    STATUS_ERROR,
    STATUS_UNVERIFIED,
)
from app.ai.gateway.base import ChatMessage, ChatProvider, ToolCall
from app.ai.keys import KeyStore, ResolvedKey
from app.ai.orchestrator import Progress, ToolRecord, TurnResult, Usage, run_turn
from app.ai.prompts import EXPLAIN_PROMPTS, LANGUAGE_NAMES, SCOPE_CONTEXT, SYSTEM_PROMPT
from app.ai.redact import scrub
from app.ai.service import AssistantService, make_title
from app.ai.sse import format_event
from app.ai.tools import CARD_TOOLS, TOOLS, execute_tool, to_json, tool_specs
from app.models.assistant import AiConversation
from app.models.market import Company

logger = logging.getLogger(__name__)


def _system_prompt(lang: str) -> str:
    name = LANGUAGE_NAMES.get(lang, "English")
    return f"{SYSTEM_PROMPT}\nReply in {name} unless the user writes in another language."


def _tool_calls_json(records: list[ToolRecord]) -> list[dict[str, Any]]:
    return [
        {"name": r.name, "arguments": r.arguments, "ok": r.ok, "ticker": r.ticker} for r in records
    ]


def _done_frame(usage: Usage, month_spend: Decimal | None) -> str:
    unused = usage.calls == 0
    cost = None if usage.cost_usd is None else str(usage.cost_usd)
    return format_event(
        "done",
        {
            "input_tokens": 0 if unused else usage.input_tokens,
            "output_tokens": 0 if unused else usage.output_tokens,
            "cost_usd": "0" if unused else cost,
            "month_spend_usd": str(month_spend) if month_spend is not None else None,
        },
    )


def _error_frames(code: str, detail: str, month_spend: Decimal | None) -> list[str]:
    return [
        format_event("error", {"code": code, "detail": detail}),
        _done_frame(Usage(), month_spend),
    ]


@dataclass(frozen=True)
class ModelChoice:
    entry: CatalogModel
    key: ResolvedKey


@dataclass(frozen=True)
class ChoiceError:
    code: str
    detail: str


async def _resolve_model(svc: AssistantService, model_id: str | None) -> ModelChoice | ChoiceError:
    """The model and the key to call it with, or the error event to send instead."""
    if model_id:
        entry = get_model(model_id)
        if entry is None:
            return ChoiceError("UNKNOWN_MODEL", "That model is not in the supported list.")
    else:
        default = await svc.effective_default_model()
        entry = get_model(default) if default else None
        if entry is None:
            return ChoiceError(
                "NO_KEY", "No AI provider key is set. Add one in Admin > AI settings."
            )
    key = await KeyStore(svc.session).resolve(entry.provider)
    if key is None:
        return ChoiceError(
            "NO_KEY", f"No API key is set for {entry.provider}. Add one in Admin > AI settings."
        )
    return ModelChoice(entry, key)


async def _history(svc: AssistantService, conversation: AiConversation) -> list[ChatMessage]:
    rows = await svc.messages(conversation.id)
    usable = [
        ChatMessage("user" if r.role == "user" else "assistant", r.content)
        for r in rows
        if r.role == "user" or (r.status == STATUS_ANSWERED and r.content)
    ]
    return usable[-MAX_HISTORY_MESSAGES:]


async def stream_chat(
    session: AsyncSession,
    provider: ChatProvider,
    *,
    message: str,
    conversation: AiConversation | None,
    model: str | None,
    company: Company | None,
    lang: str,
) -> AsyncIterator[str]:
    """The /chat stream. ``conversation`` is None for a new one."""
    svc = AssistantService(session)
    resolved = await _resolve_model(svc, model)
    if isinstance(resolved, ChoiceError):
        for frame in _error_frames(resolved.code, resolved.detail, await svc.month_spend()):
            yield frame
        return
    entry, key = resolved.entry, resolved.key

    messages: list[ChatMessage] = [ChatMessage("system", _system_prompt(lang))]
    seed: list[ToolRecord] = []
    if company is not None:
        arguments = {"ticker": company.ticker}
        scoped = await execute_tool(session, "company_overview", arguments)
        if scoped.ok:
            record = ToolRecord(
                "scope", "company_overview", arguments, scoped.output, True, company.ticker
            )
            seed.append(record)
            messages.append(
                ChatMessage(
                    "system",
                    SCOPE_CONTEXT.format(
                        ticker=company.ticker, overview_json=to_json(scoped.output)
                    ),
                )
            )
    if conversation is None:
        conversation = await svc.create_conversation(
            make_title(message), company.id if company else None
        )
    else:
        messages.extend(await _history(svc, conversation))
    messages.append(ChatMessage("user", message))
    await svc.add_message(conversation_id=conversation.id, role="user", content=message)
    await session.commit()

    async for frame in _run(
        svc,
        provider,
        entry=entry,
        key=key,
        conversation_id=conversation.id,
        messages=messages,
        user_text=message,
        seed=seed,
    ):
        yield frame


async def stream_explain(
    session: AsyncSession,
    provider: ChatProvider,
    *,
    company: Company,
    card: str,
    model: str | None,
    lang: str,
) -> AsyncIterator[str]:
    """The /explain stream: runs the card's tool, then a fixed explain prompt."""
    svc = AssistantService(session)
    resolved = await _resolve_model(svc, model)
    if isinstance(resolved, ChoiceError):
        for frame in _error_frames(resolved.code, resolved.detail, await svc.month_spend()):
            yield frame
        return
    entry, key = resolved.entry, resolved.key

    tool_name = CARD_TOOLS[card]
    arguments = {"ticker": company.ticker}
    yield format_event("meta", {"conversation_id": None, "model": entry.id})
    yield format_event("status", {"stage": "tool", "tool": tool_name})
    outcome = await execute_tool(session, tool_name, arguments)
    reason = None if outcome.ok else str(outcome.output.get("detail") or "Data unavailable.")
    check = TOOLS[tool_name].insufficient
    if outcome.ok and check is not None:
        reason = check(outcome.output)
    if reason is not None:
        for frame in _error_frames("INSUFFICIENT_DATA", reason, await svc.month_spend()):
            yield frame
        return
    call_id = f"explain_{uuid.uuid4().hex[:8]}"
    record = ToolRecord(call_id, tool_name, arguments, outcome.output, True, company.ticker)
    messages = [
        ChatMessage("system", _system_prompt(lang)),
        ChatMessage("user", EXPLAIN_PROMPTS[card].format(ticker=company.ticker)),
        ChatMessage("assistant", None, tool_calls=[ToolCall(call_id, tool_name, arguments)]),
        ChatMessage("tool", to_json(outcome.output), tool_call_id=call_id),
    ]
    async for frame in _run(
        svc,
        provider,
        entry=entry,
        key=key,
        conversation_id=None,
        messages=messages,
        user_text="",
        seed=[record],
        emit_meta=False,
    ):
        yield frame


async def _run(
    svc: AssistantService,
    provider: ChatProvider,
    *,
    entry: CatalogModel,
    key: ResolvedKey,
    conversation_id: uuid.UUID | None,
    messages: list[ChatMessage],
    user_text: str,
    seed: list[ToolRecord],
    emit_meta: bool = True,
) -> AsyncIterator[str]:
    session = svc.session
    if emit_meta:
        yield format_event(
            "meta",
            {
                "conversation_id": str(conversation_id) if conversation_id else None,
                "model": entry.id,
            },
        )
    result: TurnResult | None = None
    # A free-tier key is not charged (A10): its calls skip the cap and are stored at cost 0.
    free = await svc.is_free_tier(entry.provider)

    async def allow_call(turn_cost: Decimal) -> bool:
        return free or await svc.cap_allows(turn_cost)

    async def tool_runner(name: str, arguments: dict[str, Any]) -> Any:
        return await execute_tool(session, name, arguments)

    try:
        async for item in run_turn(
            provider=provider,
            model=entry.id,
            api_key=key.api_key,
            messages=messages,
            tools=tool_specs(),
            execute=tool_runner,
            allow_call=allow_call,
            user_text=user_text,
            seed_records=seed,
        ):
            if isinstance(item, Progress):
                data: dict[str, Any] = {"stage": item.stage}
                if item.tool:
                    data["tool"] = item.tool
                yield format_event("status", data)
            else:
                result = item
    except Exception as exc:
        logger.error(
            "assistant stream failed (%s): %s",
            type(exc).__name__,
            scrub(str(exc), key.api_key)[:300],
        )
        for frame in _error_frames("PROVIDER_ERROR", "The assistant failed unexpectedly.", None):
            yield frame
        return
    assert result is not None
    if free and result.usage.calls:
        result.usage.cost_usd = Decimal(0)

    await _persist(svc, entry, conversation_id, result)
    await svc.session.commit()
    sources = result.sources
    if result.status == STATUS_ANSWERED:
        assert result.verification is not None
        yield format_event(
            "answer",
            {
                "text": result.text,
                "verified": True,
                "checked": result.verification.checked,
                "sources": sources,
            },
        )
    elif result.status == STATUS_UNVERIFIED:
        assert result.verification is not None
        yield format_event(
            "unverified",
            {
                "checked": result.verification.checked,
                "unverified": result.verification.unverified,
                "sources": sources,
            },
        )
    else:
        yield format_event(
            "error",
            {"code": result.error_code or "PROVIDER_ERROR", "detail": result.error_detail or ""},
        )
    yield _done_frame(result.usage, await svc.month_spend())


async def _persist(
    svc: AssistantService,
    entry: CatalogModel,
    conversation_id: uuid.UUID | None,
    result: TurnResult,
) -> None:
    """Store the assistant row. A withheld or failed answer keeps no text, only its outcome."""
    verification: dict[str, Any] | None = (
        result.verification.as_dict() if result.verification is not None else None
    )
    if result.status in (STATUS_ERROR, STATUS_CAP_REACHED):
        verification = {"error": result.error_code, "detail": result.error_detail}
    if result.retried and verification is not None:
        verification["retried"] = True
    if conversation_id is None and result.usage.calls == 0:
        return  # an explain that never reached the model leaves nothing to store
    await svc.add_message(
        conversation_id=conversation_id,
        role="assistant",
        content=result.text if result.status == STATUS_ANSWERED else "",
        status=result.status,
        provider=entry.provider,
        model=entry.id,
        prompt_version=AI_PROMPT_VERSION,
        tool_calls=json.loads(json.dumps(_tool_calls_json(result.tool_records), default=str)),
        verification=verification,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        cost_usd=result.usage.cost_usd,
    )
