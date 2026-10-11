"""Database models for Phase-8 Continuous Intelligence (R38 B1–B6).

Five tables in migration 018: ``watchlists`` (user-owned lists), ``watchlist_entries``
(per-list company entries with group/note/thesis_link), ``alert_rules`` (four families:
price, valuation_gap, document, score_change), ``alert_fired`` (fired alert instances
with inputs snapshot), and ``events`` (append-only ledger for audit/review).
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.market import Company
    from app.models.thesis import InvestmentThesis


class AlertFamily(enum.StrEnum):
    """Alert rule families (B2)."""

    PRICE = "price"
    VALUATION_GAP = "valuation_gap"
    DOCUMENT = "document"
    SCORE_CHANGE = "score_change"


class EventType(enum.StrEnum):
    """Event ledger types (B6)."""

    WATCHLIST_ADD = "watchlist.add"
    WATCHLIST_REMOVE = "watchlist.remove"
    ALERT_CREATED = "alert.created"
    ALERT_FIRED = "alert.fired"
    ALERT_ACKED = "alert.acked"
    FACT_LANDED = "fact.landed"
    CHECK_EVALUATED = "check.evaluated"
    RESTATEMENT_DETECTED = "restatement.detected"
    THESIS_UPDATED = "thesis.updated"
    RULE_CHANGED = "rule.changed"
    NOTE_ADDED = "note.added"


class ActorType(enum.StrEnum):
    """Event actor types (B6)."""

    USER = "user"
    SYSTEM = "system"


class Watchlist(Base):
    """User-owned watchlist."""

    __tablename__ = "watchlists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    entries: Mapped[list["WatchlistEntry"]] = relationship(
        "WatchlistEntry", back_populates="watchlist", lazy="selectin", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_watchlists_user_id", "user_id"),)


class WatchlistEntry(Base):
    """One company entry within a watchlist."""

    __tablename__ = "watchlist_entries"
    __allow_unmapped__ = True

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    thesis_link: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investment_theses.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    watchlist: Mapped["Watchlist"] = relationship("Watchlist", back_populates="entries")
    company: Mapped["Company"] = relationship("Company")
    thesis: Mapped["InvestmentThesis | None"] = relationship("InvestmentThesis")

    __table_args__ = (
        Index("ix_watchlist_entries_watchlist_id", "watchlist_id"),
        Index("ix_watchlist_entries_company_id", "company_id"),
    )


class AlertRule(Base):
    """User-defined alert rule (B2)."""

    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    watchlist_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("watchlists.id", ondelete="SET NULL"), nullable=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True
    )
    family: Mapped[AlertFamily] = mapped_column(
        Enum(
            AlertFamily,
            name="alert_family",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    methodology_version: Mapped[str] = mapped_column(String(20), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_alert_rules_user_id", "user_id"),
        Index("ix_alert_rules_watchlist_id", "watchlist_id"),
        Index("ix_alert_rules_company_id", "company_id"),
        Index("ix_alert_rules_family", "family"),
    )


class AlertFired(Base):
    """Fired alert instance with inputs snapshot (B2/B3)."""

    __tablename__ = "alert_fired"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    inputs_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    fired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_alert_fired_rule_id", "rule_id"),
        Index("ix_alert_fired_company_id", "company_id"),
        Index("ix_alert_fired_fired_at", "fired_at"),
    )


class Event(Base):
    """Append-only event ledger (B6)."""

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(
            ActorType,
            name="actor_type",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(20), nullable=False)
    type: Mapped[EventType] = mapped_column(
        Enum(
            EventType,
            name="event_type",
            create_constraint=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    symbols: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False)
    inputs_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id", ondelete="SET NULL"), nullable=True
    )

    supersedes: Mapped["Event | None"] = relationship("Event", remote_side=[id])

    __table_args__ = (
        Index("ix_events_ts", "ts"),
        Index("ix_events_actor_type_id", "actor_type", "actor_id"),
        Index("ix_events_type", "type"),
        Index("ix_events_symbols", "symbols", postgresql_using="gin"),
    )
