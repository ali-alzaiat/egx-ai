"""Pydantic schemas for Phase-8 Continuous Intelligence API (R38 B1–B6)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WatchlistCreate(BaseModel):
    """Create a watchlist."""

    name: str = Field(..., min_length=1, max_length=200)


class WatchlistRead(BaseModel):
    """Watchlist read response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    created_at: datetime


class WatchlistEntryCreate(BaseModel):
    """Add an entry to a watchlist."""

    company_id: uuid.UUID
    group: str | None = Field(None, max_length=100)
    note: str | None = None
    thesis_link: uuid.UUID | None = None


class WatchlistEntryUpdate(BaseModel):
    """Update a watchlist entry."""

    group: str | None = Field(None, max_length=100)
    note: str | None = None
    thesis_link: uuid.UUID | None = None


class BadgeValue(BaseModel):
    """Computed badge value with INSUFFICIENT_DATA handling."""

    value: str | None = None
    status: str = "INSUFFICIENT_DATA"
    reason: str | None = None


class WatchlistEntryRead(BaseModel):
    """Watchlist entry read response with computed badges."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    watchlist_id: uuid.UUID
    company_id: uuid.UUID
    group: str | None
    note: str | None
    thesis_link: uuid.UUID | None
    created_at: datetime

    # Computed badges (populated by service)
    price: BadgeValue | None = None
    change: BadgeValue | None = None
    as_of: BadgeValue | None = None
    staleness: BadgeValue | None = None
    score: BadgeValue | None = None
    shariah_state: BadgeValue | None = None
    thesis_link_badge: BadgeValue | None = None

    # Company info for display
    company_ticker: str | None = None
    company_name: str | None = None


class AlertRuleCreate(BaseModel):
    """Create an alert rule."""

    family: str
    params: dict[str, Any] = Field(default_factory=dict)
    watchlist_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    """Update an alert rule."""

    params: dict[str, Any] | None = None
    enabled: bool | None = None


class AlertRuleRead(BaseModel):
    """Alert rule read response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    watchlist_id: uuid.UUID | None
    company_id: uuid.UUID | None
    family: str
    params: dict[str, Any]
    methodology_version: str
    enabled: bool
    created_at: datetime


class AlertFiredRead(BaseModel):
    """Fired alert read response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_id: uuid.UUID
    company_id: uuid.UUID
    inputs_snapshot: dict[str, Any]
    fired_at: datetime
    acked_at: datetime | None


class AlertAckRequest(BaseModel):
    """Acknowledge fired alert request (empty body)."""


class TriggerEvaluateRequest(BaseModel):
    """Internal trigger evaluation request."""

    company_id: uuid.UUID
    fact_ids: list[uuid.UUID] = Field(default_factory=list)
    price_as_of: date | None = None
    price_value: Decimal | None = None


class TriggerEvaluateResponse(BaseModel):
    """Trigger evaluation response."""

    evaluated: bool
    alerts_fired: int
    checks_run: int
    ledger_rows: int
    message: str


class EventFilter(BaseModel):
    """Event filter parameters."""

    symbol: uuid.UUID | None = None
    type: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class EventRead(BaseModel):
    """Event read response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ts: datetime
    actor_type: str
    actor_id: uuid.UUID
    rule_version: str
    type: str
    symbols: list[uuid.UUID]
    inputs_snapshot: dict[str, Any]
    reason: str
    supersedes_id: uuid.UUID | None


class EventExport(BaseModel):
    """Event export response."""

    events: list[EventRead]
    total: int
    filters: EventFilter
