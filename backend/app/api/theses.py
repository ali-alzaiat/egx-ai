"""API endpoints for investment theses (Phase 5, R30)."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.thesis.constants import DEFAULT_HORIZON_YEARS, THESIS_METHODOLOGY_VERSION
from app.thesis.service import (
    AssessInput,
    AssumptionInput,
    CatalystInput,
    InvalidationInput,
    ThesisService,
    UpdateCatalyst,
    UpdateInput,
    UpdateInvalidation,
)
from app.valuation.service import FairValueInput

router = APIRouter(prefix="/api/theses", tags=["theses"])


class AssumptionBody(BaseModel):
    """One labelled assumption row: every number cites a filing source."""

    metric: str
    value: str | None = None
    horizon: str | None = None
    source: str = ""
    author: str = "caller"


class InvalidationBody(BaseModel):
    """One stored invalidation condition; the action is always server-set."""

    metric: str
    threshold: float
    direction: str = "below"
    period: str = ""
    evidence_source: str = ""


class CatalystBody(BaseModel):
    """One catalyst record; provenance URL and label are required."""

    event: str
    date_from: date | None = None
    date_to: date | None = None
    window: str | None = None
    variable: str | None = None
    expectation: str | None = None
    outcome: str = "Pending"
    provenance: str = ""
    label: str = "Tentative"


class ThesisAssessBody(BaseModel):
    """Thesis assess input; every field optional except via server defaults.

    Valuation leg inputs left out resolve inside Phase-3 (historical metrics,
    never consensus) or degrade to INSUFFICIENT_DATA; the three TIKR inputs
    double as the scenario anchors.
    """

    horizon_years: int = DEFAULT_HORIZON_YEARS
    is_shareholder: bool | None = None
    free_cash_flow: float | None = None
    growth_rate: float | None = None
    stable_growth: float | None = None
    discount_rate: float | None = None
    terminal_growth_rate: float | None = None
    expected_dps: float | None = None
    stable_roe: float | None = None
    affo: float | None = None
    ffo: float | None = None
    earnings_per_share: float | None = None
    pe_ratio: float | None = None
    revenue_per_share: float | None = None
    ps_ratio: float | None = None
    book_value_per_share: float | None = None
    pb_ratio: float | None = None
    shares_outstanding: float | None = None
    revenue_growth: float | None = None
    operating_margin: float | None = None
    exit_multiple: float | None = None
    assumptions: list[AssumptionBody] = Field(default_factory=list)
    bulls: list[str] = Field(default_factory=list)
    bears: list[str] = Field(default_factory=list)
    invalidations: list[InvalidationBody] = Field(default_factory=list)
    catalysts: list[CatalystBody] = Field(default_factory=list)


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


def _dec(value: float | None) -> Decimal | None:
    """Body float to Decimal; None stays None and zero stays zero."""
    return Decimal(str(value)) if value is not None else None


def _to_assess(body: ThesisAssessBody) -> AssessInput:
    return AssessInput(
        horizon_years=body.horizon_years,
        is_shareholder=body.is_shareholder,
        fv=FairValueInput(
            free_cash_flow=_dec(body.free_cash_flow),
            growth_rate=_dec(body.growth_rate),
            stable_growth=_dec(body.stable_growth),
            discount_rate=_dec(body.discount_rate),
            terminal_growth_rate=_dec(body.terminal_growth_rate),
            expected_dps=_dec(body.expected_dps),
            stable_roe=_dec(body.stable_roe),
            affo=_dec(body.affo),
            ffo=_dec(body.ffo),
            earnings_per_share=_dec(body.earnings_per_share),
            pe_ratio=_dec(body.pe_ratio),
            revenue_per_share=_dec(body.revenue_per_share),
            ps_ratio=_dec(body.ps_ratio),
            book_value_per_share=_dec(body.book_value_per_share),
            pb_ratio=_dec(body.pb_ratio),
            shares_outstanding=_dec(body.shares_outstanding),
            revenue_growth=_dec(body.revenue_growth),
            operating_margin=_dec(body.operating_margin),
            exit_multiple=_dec(body.exit_multiple),
        ),
        assumptions=[
            AssumptionInput(
                metric=a.metric,
                value=a.value,
                horizon=a.horizon,
                source=a.source,
                author=a.author,
            )
            for a in body.assumptions
        ],
        bulls=list(body.bulls),
        bears=list(body.bears),
        invalidations=[
            InvalidationInput(
                metric=i.metric,
                threshold=Decimal(str(i.threshold)),
                direction=i.direction,
                period=i.period,
                evidence_source=i.evidence_source,
            )
            for i in body.invalidations
        ],
        catalysts=[
            CatalystInput(
                event=c.event,
                date_from=c.date_from,
                date_to=c.date_to,
                window=c.window,
                variable=c.variable,
                expectation=c.expectation,
                outcome=c.outcome,
                provenance=c.provenance,
                label=c.label,
            )
            for c in body.catalysts
        ],
    )


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
    """Latest investment thesis under the current methodology version.

    Read-only: 404 for an unknown company; a known but unassessed company
    returns ``assessment: null`` (never a default thesis).
    """
    service = ThesisService(session)
    return await service.latest_payload(company_id)


@router.post("/companies/{company_id}/assess")
async def assess_thesis(
    company_id: uuid.UUID,
    body: ThesisAssessBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Compute, snapshot, and return the investment thesis for a company.

    Last-writer-wins: the thesis key is company + methodology version, so a
    re-assess overwrites the single thesis row (the ledger stays append-only
    and removed conditions are preserved, never silently deleted). Assessing
    refreshes the Phase-3 fair-value snapshot as a side effect. 404 for an
    unknown company.
    """
    service = ThesisService(session)
    return await service.assess(company_id, _to_assess(body))


@router.post("/companies/{company_id}/update")
async def update_thesis(
    company_id: uuid.UUID,
    body: ThesisUpdateBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Apply a documented update: status/outcome changes plus ledger rows.

    Rationale is required — a trigger forces documented reassessment, never
    an automatic sale. 404 for an unknown company or when no thesis is on
    file (assess first).
    """
    service = ThesisService(session)
    return await service.update(company_id, _to_update(body))


def methodology_version() -> str:
    """Re-exported for contract tests pinning the version echo."""
    return THESIS_METHODOLOGY_VERSION
