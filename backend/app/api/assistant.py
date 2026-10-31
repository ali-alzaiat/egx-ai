"""R49 AI assistant API: models, settings, provider keys, chat/explain streams, conversations.

The legacy ``/api/ai`` router is untouched. Keys are write-only: they are encrypted at rest,
never returned, and never logged. Settings and key responses are ``Cache-Control: no-store``.
"""

import ipaddress
import uuid
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, SecretStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.catalog import PROVIDER_LABELS, PROVIDERS, get_model
from app.ai.gateway.base import ChatProvider
from app.ai.gateway.litellm_provider import LiteLLMProvider
from app.ai.keycheck import check_key
from app.ai.keys import KeyStore, SecretsKeyMissing, secrets_key_set
from app.ai.runner import stream_chat, stream_explain
from app.ai.service import MAX_CAP_USD, AssistantService
from app.core.config import settings
from app.db.session import get_session
from app.repositories.company import CompanyRepository

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

_STREAM_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


async def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def get_chat_provider() -> ChatProvider:
    """The model gateway. Tests override this dependency with the fake provider."""
    return LiteLLMProvider()


def _is_local_client(host: str | None) -> bool:
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


async def key_change_guard(request: Request) -> None:
    """Reject a cross-origin browser request, and key traffic over plain HTTP from afar (A7)."""
    origin = request.headers.get("origin")
    if origin is not None and origin not in settings.CORS_ORIGINS:
        raise api_error(403, "ORIGIN_NOT_ALLOWED", "This origin may not change AI settings.")
    if request.url.scheme != "https":
        host = request.client.host if request.client else None
        if not _is_local_client(host):
            raise api_error(
                403,
                "INSECURE_TRANSPORT",
                "AI keys are only accepted over HTTPS or from a local or private network.",
            )


def _provider_or_404(provider: str) -> str:
    if provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown provider")
    return provider


async def _provider_row(session: AsyncSession, provider: str) -> dict[str, Any]:
    st = await KeyStore(session).status(provider)
    return {
        "provider": provider,
        "label": PROVIDER_LABELS[provider],
        "configured": st.configured,
        "source": st.source,
        "last4": st.last4,
        "set_at": st.set_at.isoformat() if st.set_at else None,
    }


# -- models and settings -------------------------------------------------------------------


@router.get("/models", dependencies=[Depends(no_store)])
async def list_models(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    return await AssistantService(session).models_payload()


@router.get("/settings", dependencies=[Depends(no_store)])
async def get_settings(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    return await AssistantService(session).settings_payload()


class SettingsBody(BaseModel):
    default_model: str | None = None
    monthly_cap_usd: Decimal | None = None
    #: The full list of free-tier providers (A10); leaving it out keeps the current list.
    free_tier_providers: list[str] | None = None


@router.put("/settings", dependencies=[Depends(key_change_guard), Depends(no_store)])
async def put_settings(
    body: SettingsBody, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    fields = body.model_fields_set
    if body.default_model is not None and get_model(body.default_model) is None:
        raise HTTPException(status_code=422, detail="Unknown model")
    cap = body.monthly_cap_usd
    if cap is not None and (not cap.is_finite() or cap < 0 or cap > MAX_CAP_USD):
        raise HTTPException(
            status_code=422, detail="monthly_cap_usd must be between 0 and 99999999"
        )
    free_tier = body.free_tier_providers
    if free_tier is not None and any(p not in PROVIDERS for p in free_tier):
        raise HTTPException(status_code=422, detail="Unknown provider in free_tier_providers")
    svc = AssistantService(session)
    await svc.update_settings(
        default_model=body.default_model,
        cap=cap,
        set_model="default_model" in fields,
        set_cap="monthly_cap_usd" in fields,
        free_tier=free_tier,
    )
    await session.commit()
    return await svc.settings_payload()


# -- provider keys -------------------------------------------------------------------------


class KeyBody(BaseModel):
    api_key: SecretStr = Field(min_length=8, max_length=400)


@router.put(
    "/keys/{provider}", dependencies=[Depends(key_change_guard), Depends(no_store)]
)
async def put_key(
    provider: str,
    # Parsed by hand: FastAPI's 422 body would echo the submitted value back.
    payload: dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_session),
    gateway: ChatProvider = Depends(get_chat_provider),
) -> dict[str, Any]:
    _provider_or_404(provider)
    try:
        body = KeyBody.model_validate(payload)
    except ValidationError:
        raise HTTPException(
            status_code=422, detail="api_key must be 8 to 400 characters"
        ) from None
    api_key = body.api_key.get_secret_value().strip()
    if len(api_key) < 8:
        raise HTTPException(status_code=422, detail="api_key must be 8 to 400 characters")
    if not secrets_key_set():
        raise api_error(
            503,
            "AI_SECRETS_KEY_MISSING",
            "AI_SECRETS_KEY is not set on the server, so keys cannot be saved from the UI. "
            "Set it in .env or put the provider key in .env directly.",
        )
    check = await check_key(gateway, provider, api_key)
    if check.outcome == "rejected":
        raise api_error(422, "KEY_REJECTED", check.detail)
    if check.outcome == "error":
        raise api_error(502, "PROVIDER_ERROR", check.detail)
    try:
        await KeyStore(session).save(provider, api_key)
    except SecretsKeyMissing:
        raise api_error(503, "AI_SECRETS_KEY_MISSING", "AI_SECRETS_KEY is not usable.") from None
    await session.commit()
    return await _provider_row(session, provider)


@router.post("/keys/{provider}/test", dependencies=[Depends(no_store)])
async def test_key(
    provider: str,
    session: AsyncSession = Depends(get_session),
    gateway: ChatProvider = Depends(get_chat_provider),
) -> dict[str, Any]:
    _provider_or_404(provider)
    resolved = await KeyStore(session).resolve(provider)
    if resolved is None:
        return {"ok": False, "detail": "No key is set for this provider."}
    check = await check_key(gateway, provider, resolved.api_key)
    return {"ok": check.outcome == "ok", "detail": check.detail}


@router.delete(
    "/keys/{provider}", dependencies=[Depends(key_change_guard), Depends(no_store)]
)
async def delete_key(
    provider: str, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    _provider_or_404(provider)
    await KeyStore(session).delete(provider)
    await session.commit()
    return await _provider_row(session, provider)


# -- streams -------------------------------------------------------------------------------


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None
    model: str | None = Field(default=None, max_length=100)
    ticker: str | None = Field(default=None, max_length=20)
    lang: Literal["en", "ar"] = "en"


class ExplainBody(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    card: Literal["score", "valuation", "stance", "shariah"]
    model: str | None = Field(default=None, max_length=100)
    lang: Literal["en", "ar"] = "en"


@router.post("/chat")
async def chat(
    body: ChatBody,
    session: AsyncSession = Depends(get_session),
    gateway: ChatProvider = Depends(get_chat_provider),
) -> StreamingResponse:
    company = None
    if body.ticker:
        company = await CompanyRepository(session).get_by_ticker(body.ticker.strip())
        if company is None:
            raise HTTPException(status_code=404, detail=f"Company '{body.ticker}' not found")
    conversation = None
    if body.conversation_id is not None:
        conversation = await AssistantService(session).get_conversation(body.conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    stream = stream_chat(
        session,
        gateway,
        message=body.message,
        conversation=conversation,
        model=body.model,
        company=company,
        lang=body.lang,
    )
    return StreamingResponse(stream, media_type="text/event-stream", headers=_STREAM_HEADERS)


@router.post("/explain")
async def explain(
    body: ExplainBody,
    session: AsyncSession = Depends(get_session),
    gateway: ChatProvider = Depends(get_chat_provider),
) -> StreamingResponse:
    company = await CompanyRepository(session).get_by_ticker(body.ticker.strip())
    if company is None:
        raise HTTPException(status_code=404, detail=f"Company '{body.ticker}' not found")
    stream = stream_explain(
        session, gateway, company=company, card=body.card, model=body.model, lang=body.lang
    )
    return StreamingResponse(stream, media_type="text/event-stream", headers=_STREAM_HEADERS)


# -- conversations -------------------------------------------------------------------------


@router.get("/conversations")
async def list_conversations(
    limit: int = Query(20, ge=1, le=50), session: AsyncSession = Depends(get_session)
) -> list[dict[str, Any]]:
    rows = await AssistantService(session).list_conversations(limit)
    return [
        {
            "id": str(r.id),
            "title": r.title,
            "ticker": r.ticker,
            "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    svc = AssistantService(session)
    conv = await svc.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = await svc.messages(conversation_id)
    return {
        "id": str(conv.id),
        "title": conv.title,
        "ticker": await svc.ticker_of(conv),
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "status": m.status,
                "model": m.model,
                "verification": m.verification,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    if not await AssistantService(session).delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    await session.commit()
    return Response(status_code=204)

