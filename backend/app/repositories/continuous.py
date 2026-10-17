"""Repositories for Phase-8 Continuous Intelligence (R38 B1–B6)."""

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.continuous import (
    ActorType,
    AlertFamily,
    AlertFired,
    AlertRule,
    Event,
    EventType,
    Watchlist,
    WatchlistEntry,
)


class WatchlistRepository:
    """Persistence for watchlists and entries."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, user_id: uuid.UUID, name: str
    ) -> Watchlist:
        """Create a new watchlist."""
        row = Watchlist(
            id=uuid.uuid4(),
            user_id=user_id,
            name=name,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, watchlist_id: uuid.UUID) -> Watchlist | None:
        """Get a watchlist by ID."""
        result = await self.session.execute(
            select(Watchlist).where(Watchlist.id == watchlist_id)
        )
        return result.scalars().first()

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[Watchlist]:
        """List all watchlists for a user."""
        result = await self.session.execute(
            select(Watchlist)
            .where(Watchlist.user_id == user_id)
            .order_by(Watchlist.created_at.desc())
        )
        return result.scalars().all()

    async def update(self, watchlist_id: uuid.UUID, name: str) -> Watchlist | None:
        """Update watchlist name."""
        watchlist = await self.get(watchlist_id)
        if watchlist is None:
            return None
        watchlist.name = name
        await self.session.flush()
        return watchlist

    async def delete(self, watchlist_id: uuid.UUID) -> bool:
        """Delete a watchlist (cascades to entries)."""
        watchlist = await self.get(watchlist_id)
        if watchlist is None:
            return False
        await self.session.delete(watchlist)
        await self.session.flush()
        return True

    async def add_entry(
        self,
        watchlist_id: uuid.UUID,
        company_id: uuid.UUID,
        group: str | None,
        note: str | None,
        thesis_link: uuid.UUID | None,
    ) -> WatchlistEntry:
        """Add a company entry to a watchlist."""
        row = WatchlistEntry(
            id=uuid.uuid4(),
            watchlist_id=watchlist_id,
            company_id=company_id,
            group=group,
            note=note,
            thesis_link=thesis_link,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_entry(self, entry_id: uuid.UUID) -> WatchlistEntry | None:
        """Get a watchlist entry by ID."""
        result = await self.session.execute(
            select(WatchlistEntry).where(WatchlistEntry.id == entry_id)
        )
        return result.scalars().first()

    async def list_entries(self, watchlist_id: uuid.UUID) -> Sequence[WatchlistEntry]:
        """List all entries for a watchlist."""
        result = await self.session.execute(
            select(WatchlistEntry)
            .where(WatchlistEntry.watchlist_id == watchlist_id)
            .order_by(WatchlistEntry.created_at)
        )
        return result.scalars().all()

    async def update_entry(
        self,
        entry_id: uuid.UUID,
        group: str | None = None,
        note: str | None = None,
        thesis_link: uuid.UUID | None = None,
    ) -> WatchlistEntry | None:
        """Update a watchlist entry."""
        entry = await self.get_entry(entry_id)
        if entry is None:
            return None
        if group is not None:
            entry.group = group
        if note is not None:
            entry.note = note
        if thesis_link is not None:
            entry.thesis_link = thesis_link
        await self.session.flush()
        return entry

    async def delete_entry(self, entry_id: uuid.UUID) -> bool:
        """Delete a watchlist entry."""
        entry = await self.get_entry(entry_id)
        if entry is None:
            return False
        await self.session.delete(entry)
        await self.session.flush()
        return True

    async def get_with_entries(self, watchlist_id: uuid.UUID) -> Watchlist | None:
        """Get watchlist with entries populated (for badge population)."""
        result = await self.session.execute(
            select(Watchlist)
            .where(Watchlist.id == watchlist_id)
            .options(
                # No selectinload here; callers will load entries separately
            )
        )
        return result.scalars().first()


class AlertRepository:
    """Persistence for alert rules and fired alerts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_rule(
        self,
        user_id: uuid.UUID,
        family: AlertFamily,
        params: dict[str, Any],
        methodology_version: str,
        watchlist_id: uuid.UUID | None = None,
        company_id: uuid.UUID | None = None,
        enabled: bool = True,
    ) -> AlertRule:
        """Create a new alert rule."""
        row = AlertRule(
            id=uuid.uuid4(),
            user_id=user_id,
            watchlist_id=watchlist_id,
            company_id=company_id,
            family=family,
            params=params,
            methodology_version=methodology_version,
            enabled=enabled,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_rule(self, rule_id: uuid.UUID) -> AlertRule | None:
        """Get an alert rule by ID."""
        result = await self.session.execute(
            select(AlertRule).where(AlertRule.id == rule_id)
        )
        return result.scalars().first()

    async def list_rules(
        self,
        user_id: uuid.UUID,
        watchlist_id: uuid.UUID | None = None,
        company_id: uuid.UUID | None = None,
        family: AlertFamily | None = None,
    ) -> Sequence[AlertRule]:
        """List alert rules with optional filters."""
        stmt = select(AlertRule).where(AlertRule.user_id == user_id)
        if watchlist_id is not None:
            stmt = stmt.where(AlertRule.watchlist_id == watchlist_id)
        if company_id is not None:
            stmt = stmt.where(AlertRule.company_id == company_id)
        if family is not None:
            stmt = stmt.where(AlertRule.family == family)
        stmt = stmt.order_by(AlertRule.created_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_for_company(self, company_id: uuid.UUID) -> Sequence[AlertRule]:
        """List enabled rules applying to a company (for evaluation).

        Company-scoped, list-scoped (watchlist contains the company), or
        scope-free (whole universe) — mirrors TriggerService scope matching
        so manual evaluation and arrival evaluation agree.
        """
        member_of = (
            await self.session.execute(
                select(WatchlistEntry.watchlist_id).where(
                    WatchlistEntry.company_id == company_id
                )
            )
        ).scalars().all()
        scope = [AlertRule.company_id == company_id]
        if member_of:
            scope.append(AlertRule.watchlist_id.in_(member_of))
        scope.append(
            AlertRule.company_id.is_(None) & AlertRule.watchlist_id.is_(None)
        )
        result = await self.session.execute(
            select(AlertRule)
            .where(AlertRule.enabled.is_(True))
            .where(or_(*scope))
        )
        return result.scalars().all()

    async def update_rule(
        self,
        rule_id: uuid.UUID,
        params: dict[str, Any] | None = None,
        enabled: bool | None = None,
    ) -> AlertRule | None:
        """Update an alert rule."""
        rule = await self.get_rule(rule_id)
        if rule is None:
            return None
        if params is not None:
            rule.params = params
        if enabled is not None:
            rule.enabled = enabled
        await self.session.flush()
        return rule

    async def delete_rule(self, rule_id: uuid.UUID) -> bool:
        """Delete an alert rule."""
        rule = await self.get_rule(rule_id)
        if rule is None:
            return False
        await self.session.delete(rule)
        await self.session.flush()
        return True

    async def mark_fired(
        self,
        rule_id: uuid.UUID,
        company_id: uuid.UUID,
        inputs_snapshot: dict[str, Any],
    ) -> AlertFired:
        """Record a fired alert with inputs snapshot."""
        row = AlertFired(
            id=uuid.uuid4(),
            rule_id=rule_id,
            company_id=company_id,
            inputs_snapshot=inputs_snapshot,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_fired(self, fired_id: uuid.UUID) -> AlertFired | None:
        """Get a fired alert by ID."""
        result = await self.session.execute(
            select(AlertFired).where(AlertFired.id == fired_id)
        )
        return result.scalars().first()

    async def list_fired(
        self,
        user_id: uuid.UUID,
        rule_id: uuid.UUID | None = None,
        company_id: uuid.UUID | None = None,
        acked: bool | None = None,
    ) -> Sequence[AlertFired]:
        """List fired alerts for a user's rules."""
        # Join through alert_rules to filter by user_id
        stmt = (
            select(AlertFired)
            .join(AlertRule, AlertFired.rule_id == AlertRule.id)
            .where(AlertRule.user_id == user_id)
        )
        if rule_id is not None:
            stmt = stmt.where(AlertFired.rule_id == rule_id)
        if company_id is not None:
            stmt = stmt.where(AlertFired.company_id == company_id)
        if acked is not None:
            if acked:
                stmt = stmt.where(AlertFired.acked_at.is_not(None))
            else:
                stmt = stmt.where(AlertFired.acked_at.is_(None))
        stmt = stmt.order_by(AlertFired.fired_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def ack_fired(self, fired_id: uuid.UUID) -> AlertFired | None:
        """Acknowledge a fired alert."""
        fired = await self.get_fired(fired_id)
        if fired is None:
            return None
        fired.acked_at = datetime.now()
        await self.session.flush()
        return fired


class EventRepository:
    """Persistence for the append-only event ledger."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(
        self,
        actor_type: ActorType,
        actor_id: uuid.UUID,
        rule_version: str,
        type: EventType,
        symbols: list[uuid.UUID],
        inputs_snapshot: dict[str, Any],
        reason: str,
        supersedes_id: uuid.UUID | None = None,
    ) -> Event:
        """Append a new event row (never updated)."""
        row = Event(
            id=uuid.uuid4(),
            actor_type=actor_type,
            actor_id=actor_id,
            rule_version=rule_version,
            type=type,
            symbols=symbols,
            inputs_snapshot=inputs_snapshot,
            reason=reason,
            supersedes_id=supersedes_id,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def filter(
        self,
        symbol: uuid.UUID | None = None,
        type: EventType | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Event]:
        """Filter events with optional criteria."""
        stmt = select(Event).order_by(Event.ts.desc())
        if symbol is not None:
            # Use PostgreSQL array overlap operator (&&)
            stmt = stmt.where(Event.symbols.op("&&")([symbol]))
        if type is not None:
            stmt = stmt.where(Event.type == type)
        if date_from is not None:
            stmt = stmt.where(Event.ts >= date_from)
        if date_to is not None:
            stmt = stmt.where(Event.ts <= date_to)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def export_json(
        self,
        symbol: uuid.UUID | None = None,
        type: EventType | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> list[dict[str, Any]]:
        """Export filtered events as JSON-serializable dicts."""
        rows = await self.filter(symbol, type, date_from, date_to, limit=10000, offset=0)
        return [
            {
                "id": str(r.id),
                "ts": r.ts.isoformat(),
                "actor_type": r.actor_type.value,
                "actor_id": str(r.actor_id),
                "rule_version": r.rule_version,
                "type": r.type.value,
                "symbols": [str(s) for s in r.symbols],
                "inputs_snapshot": r.inputs_snapshot,
                "reason": r.reason,
                "supersedes_id": str(r.supersedes_id) if r.supersedes_id else None,
            }
            for r in rows
        ]

    async def count(
        self,
        symbol: uuid.UUID | None = None,
        type: EventType | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> int:
        """Count filtered events."""
        stmt = select(func.count()).select_from(Event)
        if symbol is not None:
            # Use PostgreSQL array overlap operator (&&)
            stmt = stmt.where(Event.symbols.op("&&")([symbol]))
        if type is not None:
            stmt = stmt.where(Event.type == type)
        if date_from is not None:
            stmt = stmt.where(Event.ts >= date_from)
        if date_to is not None:
            stmt = stmt.where(Event.ts <= date_to)
        result = await self.session.execute(stmt)
        return result.scalar_one()
