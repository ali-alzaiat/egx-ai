"""R49 assistant tables: encrypted provider keys, settings, conversations and messages."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AiProviderKey(Base):
    """A provider API key saved from the UI: Fernet ciphertext plus the last four characters."""

    __tablename__ = "ai_provider_keys"

    provider: Mapped[str] = mapped_column(String(20), primary_key=True)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    set_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AiSettings(Base):
    """Single-row assistant settings (id is always 1)."""

    __tablename__ = "ai_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    default_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    #: USD per calendar month (UTC); NULL = no cap.
    monthly_cap_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    #: Providers whose key is on a free tier (R49 A10): their calls cost $0 and skip the cap.
    free_tier_providers: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)), nullable=False, server_default="{}"
    )

    __table_args__ = (CheckConstraint("id = 1", name="ck_ai_settings_single_row"),)


class AiConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_ai_conversations_updated_at", "updated_at"),)


class AiMessage(Base):
    """One message. ``conversation_id`` is NULL for explain calls (and for spend-only rows)."""

    __tablename__ = "ai_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    tool_calls: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    verification: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="answered")
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_ai_messages_role"),
        CheckConstraint(
            "status IN ('answered', 'unverified', 'error', 'cap_reached')",
            name="ck_ai_messages_status",
        ),
        Index("ix_ai_messages_conversation", "conversation_id", "created_at"),
        Index("ix_ai_messages_created_at", "created_at"),
    )
