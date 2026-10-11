"""Watchlist API endpoints (B1)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.continuous.watchlist_service import WatchlistService
from app.db.session import get_session
from app.repositories.company import CompanyRepository
from app.repositories.continuous import WatchlistRepository
from app.schemas.continuous import (
    WatchlistCreate,
    WatchlistEntryCreate,
    WatchlistEntryRead,
    WatchlistEntryUpdate,
    WatchlistRead,
)

router = APIRouter(prefix="/api/watchlists", tags=["watchlists"])


def _to_badge(value: str | None, status: str, reason: str | None) -> dict[str, Any]:
    """Convert to badge format."""
    return {"value": value, "status": status, "reason": reason}


@router.post("", response_model=WatchlistRead, status_code=status.HTTP_201_CREATED)
async def create_watchlist(
    body: WatchlistCreate,
    session: AsyncSession = Depends(get_session),
) -> WatchlistRead:
    """Create a new watchlist."""
    repo = WatchlistRepository(session)
    # Use a fixed user_id for now (in real impl, get from auth)
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    watchlist = await repo.create(user_id=user_id, name=body.name)
    return WatchlistRead.model_validate(watchlist)


@router.get("", response_model=list[WatchlistRead])
async def list_watchlists(
    session: AsyncSession = Depends(get_session),
) -> list[WatchlistRead]:
    """List all watchlists for the current user."""
    repo = WatchlistRepository(session)
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    watchlists = await repo.list_for_user(user_id)
    return [WatchlistRead.model_validate(w) for w in watchlists]


@router.get("/{watchlist_id}", response_model=WatchlistRead)
async def get_watchlist(
    watchlist_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> WatchlistRead:
    """Get a watchlist by ID."""
    repo = WatchlistRepository(session)
    watchlist = await repo.get(watchlist_id)
    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return WatchlistRead.model_validate(watchlist)


@router.post(
    "/{watchlist_id}/entries",
    response_model=WatchlistEntryRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_entry(
    watchlist_id: uuid.UUID,
    body: WatchlistEntryCreate,
    session: AsyncSession = Depends(get_session),
) -> WatchlistEntryRead:
    """Add a company entry to a watchlist."""
    repo = WatchlistRepository(session)
    watchlist = await repo.get(watchlist_id)
    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    # Verify company exists
    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(body.company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    # Verify thesis_link if provided
    if body.thesis_link is not None:
        from app.repositories.thesis import ThesisRepository
        thesis_repo = ThesisRepository(session)
        thesis = await thesis_repo.get_thesis_by_id(body.thesis_link)
        if thesis is None:
            raise HTTPException(status_code=404, detail="Thesis not found")

    entry = await repo.add_entry(
        watchlist_id=watchlist_id,
        company_id=body.company_id,
        group=body.group,
        note=body.note,
        thesis_link=body.thesis_link,
    )

    # Populate badges
    service = WatchlistService(session)
    await service.populate_badges([entry])

    return _entry_to_read(entry, company)


@router.get("/{watchlist_id}/entries", response_model=list[WatchlistEntryRead])
async def list_entries(
    watchlist_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[WatchlistEntryRead]:
    """List all entries for a watchlist with badges populated."""
    repo = WatchlistRepository(session)
    watchlist = await repo.get(watchlist_id)
    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    entries = await repo.list_entries(watchlist_id)
    if not entries:
        return []

    company_ids = [e.company_id for e in entries]
    companies = {c.id: c for c in await CompanyRepository(session).list_by_ids(company_ids)}

    # Populate badges
    service = WatchlistService(session)
    await service.populate_badges(entries)

    return [_entry_to_read(e, companies.get(e.company_id)) for e in entries]


@router.patch("/{watchlist_id}/entries/{entry_id}", response_model=WatchlistEntryRead)
async def update_entry(
    watchlist_id: uuid.UUID,
    entry_id: uuid.UUID,
    body: WatchlistEntryUpdate,
    session: AsyncSession = Depends(get_session),
) -> WatchlistEntryRead:
    """Update a watchlist entry."""
    repo = WatchlistRepository(session)
    entry = await repo.get_entry(entry_id)
    if entry is None or entry.watchlist_id != watchlist_id:
        raise HTTPException(status_code=404, detail="Entry not found")

    # Verify thesis_link if provided
    if body.thesis_link is not None:
        from app.repositories.thesis import ThesisRepository
        thesis_repo = ThesisRepository(session)
        thesis = await thesis_repo.get_thesis_by_id(body.thesis_link)
        if thesis is None:
            raise HTTPException(status_code=404, detail="Thesis not found")

    updated = await repo.update_entry(
        entry_id=entry_id,
        group=body.group,
        note=body.note,
        thesis_link=body.thesis_link,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Entry not found")

    # Populate badges
    service = WatchlistService(session)
    await service.populate_badges([updated])

    company = await CompanyRepository(session).get_by_id(updated.company_id)
    return _entry_to_read(updated, company)


@router.delete("/{watchlist_id}/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    watchlist_id: uuid.UUID,
    entry_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a watchlist entry."""
    repo = WatchlistRepository(session)
    entry = await repo.get_entry(entry_id)
    if entry is None or entry.watchlist_id != watchlist_id:
        raise HTTPException(status_code=404, detail="Entry not found")

    deleted = await repo.delete_entry(entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entry not found")

    # Log event
    from app.continuous.constants import CI_METHODOLOGY_VERSION
    from app.models.continuous import ActorType, EventType
    from app.repositories.continuous import EventRepository
    event_repo = EventRepository(session)
    await event_repo.append(
        actor_type=ActorType.USER,
        actor_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        rule_version=CI_METHODOLOGY_VERSION,
        type=EventType.WATCHLIST_REMOVE,
        symbols=[entry.company_id],
        inputs_snapshot={"entry_id": str(entry_id), "watchlist_id": str(watchlist_id)},
        reason=f"Removed entry from watchlist {watchlist_id}",
    )


def _entry_to_read(entry: Any, company: Any | None) -> WatchlistEntryRead:
    """Convert entry with badges to WatchlistEntryRead."""
    data = {
        "id": entry.id,
        "watchlist_id": entry.watchlist_id,
        "company_id": entry.company_id,
        "group": entry.group,
        "note": entry.note,
        "thesis_link": entry.thesis_link,
        "created_at": entry.created_at,
        "price": getattr(entry, "price", None),
        "change": getattr(entry, "change", None),
        "as_of": getattr(entry, "as_of", None),
        "staleness": getattr(entry, "staleness", None),
        "score": getattr(entry, "score", None),
        "shariah_state": getattr(entry, "shariah_state", None),
        "thesis_link_badge": getattr(entry, "thesis_link_badge", None),
        "company_ticker": company.ticker if company else None,
        "company_name": company.name if company else None,
    }
    return WatchlistEntryRead.model_validate(data)
