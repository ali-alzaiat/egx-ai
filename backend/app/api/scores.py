"""API endpoints for investment scores (R43: computed on read, no caller inputs)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.company import CompanyRepository
from app.scores.service import ScoreService
from app.services.recompute import Engine, RecomputeService, compute_meta

router = APIRouter(prefix="/api/scores", tags=["scores"])


@router.get("/companies/{company_id}")
async def get_score(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Investment score under the current methodology, computed on first view.

    404 for an unknown company. ``assessment`` is null only when the compute
    failed and no earlier snapshot exists (``compute_status: failed``).
    """
    if await CompanyRepository(session).get_by_id(company_id) is None:
        raise HTTPException(status_code=404, detail="Company not found")
    state = await RecomputeService(session).ensure_fresh(company_id, Engine.SCORE)
    payload = await ScoreService(session).latest_payload(company_id)
    meta = compute_meta(state)
    meta.pop("methodology_version", None)
    payload.update(meta)
    return payload
