"""API endpoints for technical analysis (R43: computed server-side from stored prices)."""

import dataclasses
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.company import CompanyRepository
from app.repositories.price import PriceRepository
from app.repositories.technical import TechnicalRepository
from app.services.recompute import Engine, RecomputeService, compute_meta
from app.technical.cone_calibration import calibrate_cached
from app.technical.pattern_backtest import patterns_for_company
from app.technical.service import TECHNICAL_METHODOLOGY_VERSION
from app.technical.volatility_cone import volatility_cone

router = APIRouter(prefix="/api/technical", tags=["technical"])

#: Newest stored bars read for the cone and its calibration (about 5.5 years of sessions).
CONE_HISTORY_BARS = 1400


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


@router.get("/companies/{company_id}/volatility-cone")
async def get_volatility_cone(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Range of typical moves if past volatility continues (R47 P3). Read-only, not a forecast.

    Computed on read from the stored daily closes: the cone uses the last 252 sessions, the
    calibration back-tests it on the stock's own stored history (per-horizon hit rates).
    INSUFFICIENT_DATA with a reason when too few prices exist. 404 for an unknown company.
    """
    if await CompanyRepository(session).get_by_id(company_id) is None:
        raise HTTPException(status_code=404, detail="Company not found")
    rows = await PriceRepository(session).get_last(company_id, CONE_HISTORY_BARS)
    bars = [(r.date, r.close) for r in rows]
    cone = volatility_cone(bars)
    payload: dict[str, Any] = jsonable_encoder(dataclasses.asdict(cone))
    payload["calibration"] = jsonable_encoder(
        dataclasses.asdict(calibrate_cached(str(company_id), bars))
    )
    payload["company_id"] = str(company_id)
    return payload


@router.get("/companies/{company_id}/patterns")
async def get_patterns(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Confirmed chart patterns of the last year plus their measured EGX odds (R47 P4).

    Display only, not a prediction. 404 for an unknown company; INSUFFICIENT_DATA with a reason
    when the stock has too little price history.
    """
    payload = await patterns_for_company(session, company_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return payload
