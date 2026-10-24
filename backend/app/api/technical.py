"""API endpoints for technical analysis (R43: computed server-side from stored prices)."""

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.company import CompanyRepository
from app.repositories.technical import TechnicalRepository
from app.services.recompute import Engine, RecomputeService, compute_meta
from app.technical.service import TECHNICAL_METHODOLOGY_VERSION

router = APIRouter(prefix="/api/technical", tags=["technical"])


@router.get("/companies/{company_id}")
async def get_indicators(
    company_id: uuid.UUID,
    indicator_type: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """The latest indicator set, computed on first view from stored prices."""
    if await CompanyRepository(session).get_by_id(company_id) is None:
        raise HTTPException(status_code=404, detail="Company not found")
    state = await RecomputeService(session).ensure_fresh(company_id, Engine.TECHNICAL)
    meta = compute_meta(state)
    rows = await TechnicalRepository(session).latest_set(company_id)
    out: list[dict[str, Any]] = []
    for r in rows:
        if indicator_type and r.indicator_type.value != indicator_type:
            continue
        row = dict(meta)
        row.update(
            {
                "id": str(r.id),
                "company_id": str(r.company_id),
                "indicator_type": r.indicator_type.value,
                "value": str(r.value) if r.value is not None else None,
                "status": r.status.value,
                "parameters": json.loads(r.parameters) if r.parameters else None,
                "reason": r.reason,
                "calculated_at": r.calculated_at.isoformat(),
                "created_at": r.created_at.isoformat(),
                "methodology_version": TECHNICAL_METHODOLOGY_VERSION,
                "price_as_of": meta.get("price_as_of"),
            }
        )
        out.append(row)
    if not rows and meta.get("compute_status") == "failed":
        # No snapshot to serve: say so (section 3.1) instead of an empty list.
        placeholder = dict(meta)
        placeholder.update(
            {
                "id": None,
                "company_id": str(company_id),
                "indicator_type": None,
                "value": None,
                "status": "INSUFFICIENT_DATA",
                "parameters": None,
                "reason": f"computation failed: {meta.get('compute_error') or 'no snapshot'}",
                "methodology_version": TECHNICAL_METHODOLOGY_VERSION,
            }
        )
        out.append(placeholder)
    return out
