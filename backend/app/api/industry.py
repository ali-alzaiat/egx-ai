"""API endpoints for industry intelligence (peers + peer percentiles)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.industry.service import IndustryService

router = APIRouter(prefix="/api/industry", tags=["industry"])


class PeerOverrideBody(BaseModel):
    peer_company_ids: list[uuid.UUID] = Field(default_factory=list)


@router.get("/companies/{company_id}")
async def get_company_industry(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Peers + per-metric peer percentiles + metric-profile version."""
    service = IndustryService(session)
    return await service.peer_snapshot(company_id)


@router.put("/companies/{company_id}/peers")
async def put_company_peers(
    company_id: uuid.UUID,
    body: PeerOverrideBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Persist an editable peer-list override; later GETs use it."""
    service = IndustryService(session)
    return await service.set_peer_override(company_id, body.peer_company_ids)
