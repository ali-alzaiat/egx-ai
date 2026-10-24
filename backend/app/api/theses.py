"""API endpoints for investment theses (Phase 5, R30; R43: assessed automatically)."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.company import CompanyRepository
from app.services.recompute import Engine, RecomputeService, compute_meta
from app.thesis.constants import THESIS_METHODOLOGY_VERSION
from app.thesis.service import (
    ThesisService,
    UpdateCatalyst,
    UpdateInput,
    UpdateInvalidation,
)

router = APIRouter(prefix="/api/theses", tags=["theses"])


class UpdateInvalidationBody(BaseModel):
    """A status transition for one stored condition."""

    metric: str
    status: str


class UpdateCatalystBody(BaseModel):
    """An outcome update for one stored catalyst."""

    catalyst_id: uuid.UUID
    outcome: str


class ThesisUpdateBody(BaseModel):
    """A documented update: rationale is required, changes optional."""

    rationale: str = ""
    reviewer: str | None = None
    classification: str = "Pending"
    invalidations: list[UpdateInvalidationBody] = Field(default_factory=list)
    catalysts: list[UpdateCatalystBody] = Field(default_factory=list)


def _to_update(body: ThesisUpdateBody) -> UpdateInput:
    return UpdateInput(
        rationale=body.rationale,
        reviewer=body.reviewer,
        classification=body.classification,
        invalidations=[
            UpdateInvalidation(metric=u.metric, status=u.status)
            for u in body.invalidations
        ],
        catalysts=[
            UpdateCatalyst(catalyst_id=u.catalyst_id, outcome=u.outcome)
            for u in body.catalysts
        ],
    )


@router.get("/companies/{company_id}")
async def get_thesis(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Investment thesis under the current methodology, assessed on first view.

    Horizon is the methodology default; assumptions, cases, invalidations and
    catalysts carry over from the stored thesis. 404 for an unknown company.
    """
    if await CompanyRepository(session).get_by_id(company_id) is None:
        raise HTTPException(status_code=404, detail="Company not found")
    state = await RecomputeService(session).ensure_fresh(company_id, Engine.THESIS)
    payload = await ThesisService(session).latest_payload(company_id)
    meta = compute_meta(state)
    meta.pop("methodology_version", None)
    payload.update(meta)
    return payload


@router.post("/companies/{company_id}/update")
async def update_thesis(
    company_id: uuid.UUID,
    body: ThesisUpdateBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Apply a documented update (admin): status/outcome changes plus ledger rows.

    Rationale is required — a trigger forces documented reassessment, never
    an automatic sale. 404 for an unknown company or when no thesis is on file.
    """
    service = ThesisService(session)
    return await service.update(company_id, _to_update(body))


def methodology_version() -> str:
    """Re-exported for contract tests pinning the version echo."""
    return THESIS_METHODOLOGY_VERSION
