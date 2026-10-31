"""Assistant persistence: settings, monthly spend and cap, conversations and messages."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.catalog import CATALOG, PROVIDER_LABELS, PROVIDERS, get_model
from app.ai.keys import KeyStore, secrets_key_set
from app.models.assistant import AiConversation, AiMessage, AiSettings
from app.models.market import Company

MAX_TITLE_CHARS = 60
MAX_CAP_USD = Decimal("99999999")


def month_start(now: datetime | None = None) -> datetime:
    """First instant of the current calendar month, UTC."""
    moment = now or datetime.now(UTC)
    return datetime(moment.year, moment.month, 1, tzinfo=UTC)


def make_title(message: str) -> str:
    collapsed = " ".join(message.split())
    return collapsed[:MAX_TITLE_CHARS] or "Conversation"


def _plain(value: Decimal) -> str:
    """A decimal without padding zeros and never in exponent form: 0.0000 -> "0", 10.00 -> "10"."""
    return format(value.normalize(), "f")


@dataclass(frozen=True)
class ConversationSummary:
    id: uuid.UUID
    title: str
    ticker: str | None
    updated_at: datetime


class AssistantService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # -- settings ---------------------------------------------------------------------------

    async def settings_row(self) -> AiSettings:
        """The single settings row, created on first use."""
        await self.session.execute(
            pg_insert(AiSettings).values(id=1).on_conflict_do_nothing(index_elements=["id"])
        )
        row = await self.session.get(AiSettings, 1)
        assert row is not None
        await self.session.refresh(row)
        return row

    async def update_settings(
        self,
        *,
        default_model: str | None,
        cap: Decimal | None,
        set_model: bool,
        set_cap: bool,
        free_tier: Sequence[str] | None = None,
    ) -> AiSettings:
        row = await self.settings_row()
        if set_model:
            row.default_model = default_model
        if set_cap:
            row.monthly_cap_usd = cap
        if free_tier is not None:
            row.free_tier_providers = [p for p in PROVIDERS if p in free_tier]
        await self.session.flush()
        return row

    async def effective_default_model(self, available: set[str] | None = None) -> str | None:
        """The model a chat uses when none is named: the saved default if its provider has a
        key, else the first catalog model that has one, else None."""
        row = await self.settings_row()
        providers = available if available is not None else await self._providers()
        saved = get_model(row.default_model) if row.default_model else None
        if saved is not None and saved.provider in providers:
            return saved.id
        return next((m.id for m in CATALOG if m.provider in providers), None)

    async def _providers(self) -> set[str]:
        return await KeyStore(self.session).available_providers()

    async def settings_payload(self) -> dict[str, Any]:
        keys = KeyStore(self.session)
        row = await self.settings_row()
        free_tier = set(row.free_tier_providers)
        providers = []
        for provider in PROVIDERS:
            st = await keys.status(provider)
            providers.append(
                {
                    "provider": provider,
                    "label": PROVIDER_LABELS[provider],
                    "configured": st.configured,
                    "source": st.source,
                    "last4": st.last4,
                    "set_at": st.set_at.isoformat() if st.set_at else None,
                    "free_tier": provider in free_tier,
                }
            )
        return {
            "providers": providers,
            # The saved choice as chosen (even before its provider has a key), else the fallback.
            "default_model": (
                row.default_model
                if row.default_model and get_model(row.default_model) is not None
                else await self.effective_default_model()
            ),
            "monthly_cap_usd": (
                _plain(row.monthly_cap_usd) if row.monthly_cap_usd is not None else None
            ),
            "month_spend_usd": str(await self.month_spend()),
            "secrets_key_set": secrets_key_set(),
        }

    async def models_payload(self) -> dict[str, Any]:
        available = await self._providers()
        return {
            "default_model": await self.effective_default_model(available),
            "models": [
                {
                    "id": m.id,
                    "label": m.label,
                    "provider": m.provider,
                    "available": m.provider in available,
                    "web_search": m.web_search,
                }
                for m in CATALOG
            ],
        }

    # -- spend and cap ----------------------------------------------------------------------

    async def month_spend(self) -> Decimal:
        """Sum of priced calls this calendar month (UTC); unpriced calls are not counted."""
        total = (
            await self.session.execute(
                select(func.sum(AiMessage.cost_usd)).where(AiMessage.created_at >= month_start())
            )
        ).scalar()
        return Decimal(total) if total is not None else Decimal(0)

    async def is_free_tier(self, provider: str) -> bool:
        return provider in (await self.settings_row()).free_tier_providers

    async def cap_allows(self, turn_cost: Decimal) -> bool:
        """False once this month's spend (plus this turn's so far) has reached the cap."""
        cap = (await self.settings_row()).monthly_cap_usd
        if cap is None:
            return True
        return await self.month_spend() + turn_cost < cap

    # -- conversations ----------------------------------------------------------------------

    async def create_conversation(self, title: str, company_id: uuid.UUID | None) -> AiConversation:
        now = datetime.now(UTC)
        conv = AiConversation(
            id=uuid.uuid4(), title=title, company_id=company_id, created_at=now, updated_at=now
        )
        self.session.add(conv)
        await self.session.flush()
        return conv

    async def get_conversation(self, conversation_id: uuid.UUID) -> AiConversation | None:
        return await self.session.get(AiConversation, conversation_id)

    async def ticker_of(self, conv: AiConversation) -> str | None:
        if conv.company_id is None:
            return None
        company = await self.session.get(Company, conv.company_id)
        return company.ticker if company else None

    async def list_conversations(self, limit: int) -> list[ConversationSummary]:
        rows = (
            await self.session.execute(
                select(AiConversation, Company.ticker)
                .outerjoin(Company, Company.id == AiConversation.company_id)
                .order_by(AiConversation.updated_at.desc())
                .limit(limit)
            )
        ).all()
        return [ConversationSummary(c.id, c.title, ticker, c.updated_at) for c, ticker in rows]

    async def messages(self, conversation_id: uuid.UUID) -> Sequence[AiMessage]:
        return (
            (
                await self.session.execute(
                    select(AiMessage)
                    .where(AiMessage.conversation_id == conversation_id)
                    .order_by(AiMessage.created_at, AiMessage.role.desc())
                )
            )
            .scalars()
            .all()
        )

    async def delete_conversation(self, conversation_id: uuid.UUID) -> bool:
        """Delete a conversation and its text. Priced calls stay as content-free spend rows,
        so deleting history never lowers this month's spend (the cap stays honest)."""
        conv = await self.get_conversation(conversation_id)
        if conv is None:
            return False
        await self.session.execute(
            update(AiMessage)
            .where(AiMessage.conversation_id == conversation_id, AiMessage.cost_usd.is_not(None))
            .values(conversation_id=None, content="", tool_calls=None, verification=None)
        )
        await self.session.execute(
            delete(AiConversation).where(AiConversation.id == conversation_id)
        )
        await self.session.flush()
        self.session.expire_all()
        return True

    async def add_message(
        self,
        *,
        conversation_id: uuid.UUID | None,
        role: str,
        content: str,
        status: str = "answered",
        provider: str | None = None,
        model: str | None = None,
        prompt_version: str | None = None,
        tool_calls: Any | None = None,
        verification: Any | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cost_usd: Decimal | None = None,
    ) -> AiMessage:
        now = datetime.now(UTC)
        message = AiMessage(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            status=status,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            tool_calls=tool_calls,
            verification=verification,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            created_at=now,
        )
        self.session.add(message)
        if conversation_id is not None:
            await self.session.execute(
                update(AiConversation)
                .where(AiConversation.id == conversation_id)
                .values(updated_at=now)
            )
        await self.session.flush()
        return message
