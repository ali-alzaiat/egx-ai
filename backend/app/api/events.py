"""Event ledger API endpoints (B6)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.continuous import EventRepository
from app.schemas.continuous import EventExport, EventFilter, EventRead

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=list[EventRead])
async def list_events(
    symbol: uuid.UUID | None = Query(None, description="Filter by company symbol"),
    type: str | None = Query(None, description="Filter by event type"),
    date_from: date | None = Query(None, description="Filter from date (inclusive)"),
    date_to: date | None = Query(None, description="Filter to date (inclusive)"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_session),
) -> list[EventRead]:
    """List events with optional filters."""
    repo = EventRepository(session)

    event_type = None
    if type is not None:
        from app.models.continuous import EventType
        try:
            event_type = EventType(type)
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Invalid event type: {type}") from None

    events = await repo.filter(
        symbol=symbol,
        type=event_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return [EventRead.model_validate(e) for e in events]


@router.get("/export", response_model=EventExport)
async def export_events(
    symbol: uuid.UUID | None = Query(None, description="Filter by company symbol"),
    type: str | None = Query(None, description="Filter by event type"),
    date_from: date | None = Query(None, description="Filter from date (inclusive)"),
    date_to: date | None = Query(None, description="Filter to date (inclusive)"),
    session: AsyncSession = Depends(get_session),
) -> EventExport:
    """Export filtered events as JSON."""
    repo = EventRepository(session)

    event_type = None
    if type is not None:
        from app.models.continuous import EventType
        try:
            event_type = EventType(type)
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Invalid event type: {type}") from None

    events_data = await repo.export_json(
        symbol=symbol,
        type=event_type,
        date_from=date_from,
        date_to=date_to,
    )
    total = await repo.count(
        symbol=symbol,
        type=event_type,
        date_from=date_from,
        date_to=date_to,
    )

    filters = EventFilter(
        symbol=symbol,
        type=type,
        date_from=date_from,
        date_to=date_to,
    )

    events = [EventRead(**e) for e in events_data]
    return EventExport(events=events, total=total, filters=filters)
