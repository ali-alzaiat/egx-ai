"""API endpoints for valuation (R43: the fair value is computed, never typed in)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.company import CompanyRepository
from app.services.recompute import Engine, RecomputeService, compute_meta
from app.valuation.constants import VALUATION_METHODOLOGY_VERSION
from app.valuation.service import FairValueService

router = APIRouter(prefix="/api/valuation", tags=["valuation"])


@router.get("/companies/{company_id}/fair-value")
async def get_fair_value(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Weighted fair value — an estimate under the stated methodology.

    Inputs come from approved statement lines, our own metrics and the sourced
    valuation-assumption record; caller-supplied inputs are gone (R43). The
    snapshot is computed on first view (or when its inputs changed) and served
    from the stored row.
    """
    company = await CompanyRepository(session).get_by_id(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    state = await RecomputeService(session).ensure_fresh(company_id, Engine.FAIR_VALUE)
    meta = compute_meta(state)
    payload = await FairValueService(session).latest_payload(company_id)
    if payload is None:
        reason = f"computation failed: {meta.get('compute_error') or 'no snapshot'}"
        payload = {
            "company_id": str(company.id),
            "ticker": company.ticker,
            "methodology_version": VALUATION_METHODOLOGY_VERSION,
            "fair_value": {"value": None, "status": "INSUFFICIENT_DATA", "reason": reason},
        }
    out = dict(payload)
    out.update({k: v for k, v in meta.items() if k not in ("methodology_version",)})
    out["methodology_version"] = VALUATION_METHODOLOGY_VERSION
    return out
