"""Ops review queue endpoints: approve extraction candidates, reject with reason."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.statements import ExtStatus
from app.repositories.company import CompanyRepository
from app.repositories.statements import StatementLineRepository
from app.schemas.statements import (
    ReviewDecisionRead,
    ReviewDecisionRequest,
    ReviewQueueItemRead,
)
from app.statements.intake import ManualLine, intake_checklist, record_manual_filing
from app.statements.ontology import STATEMENT_LINES
from app.statements.service import StatementService

router = APIRouter(prefix="/api/statements", tags=["statements"])


def _queue_item(line_row: Any, document: Any) -> ReviewQueueItemRead:
    return ReviewQueueItemRead(
        id=line_row.id,
        company_id=line_row.company_id,
        period_id=line_row.period_id,
        ontology_code=line_row.ontology_code,
        ontology_version=line_row.ontology_version,
        value=str(line_row.value) if line_row.value is not None else None,
        currency=line_row.currency,
        source_label_reported=line_row.source_label_reported,
        source_label_en=line_row.source_label_en,
        source_label_ar=line_row.source_label_ar,
        source_page=line_row.source_page,
        extraction_method=line_row.extraction_method.value
        if hasattr(line_row.extraction_method, "value")
        else str(line_row.extraction_method),
        published_date=line_row.published_date,
        document_url=document.document_url,
        document_type=document.document_type,
    )


@router.get("/review-queue")
async def review_queue(
    company_id: uuid.UUID | str | None = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
) -> list[ReviewQueueItemRead]:
    """Candidates awaiting ops approval (extraction_candidate only)."""
    repo = StatementLineRepository(session)
    effective_company_id: uuid.UUID | None
    if company_id is None:
        effective_company_id = None
    else:
        effective_company_id = (
            uuid.UUID(company_id) if isinstance(company_id, str) else company_id
        )
    rows = await repo.list_candidates(effective_company_id, limit=limit)
    return [_queue_item(line_row, document) for line_row, document in rows]


@router.post("/lines/{line_id}/approve", response_model=ReviewDecisionRead)
async def approve_line(
    line_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ReviewDecisionRead | JSONResponse:
    repo = StatementLineRepository(session)
    line_row = await repo.get(line_id)
    if line_row is None:
        return JSONResponse(status_code=404, content={"detail": "line not found"})
    if line_row.ext_status == ExtStatus.approved:
        return JSONResponse(
            status_code=409,
            content={"detail": "line already approved"},
        )
    approved = await repo.set_status(line_row, ExtStatus.approved, None)
    await session.commit()
    return ReviewDecisionRead(
        id=approved.id,
        ontology_code=approved.ontology_code,
        ext_status=approved.ext_status.value,
        ext_reason=approved.ext_reason,
    )


@router.post("/lines/{line_id}/reject", response_model=ReviewDecisionRead)
async def reject_line(
    line_id: uuid.UUID,
    body: ReviewDecisionRequest,
    session: AsyncSession = Depends(get_session),
) -> ReviewDecisionRead | JSONResponse:
    repo = StatementLineRepository(session)
    line_row = await repo.get(line_id)
    if line_row is None:
        return JSONResponse(status_code=404, content={"detail": "line not found"})
    rejected = await repo.set_status(line_row, ExtStatus.rejected, body.reason)
    await session.commit()
    return ReviewDecisionRead(
        id=rejected.id,
        ontology_code=rejected.ontology_code,
        ext_status=rejected.ext_status.value,
        ext_reason=rejected.ext_reason,
    )


@router.get("/companies/{ticker}/statements")
async def company_statements(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    company_obj = await CompanyRepository(session).get_by_ticker(ticker)
    if company_obj is None:
        return JSONResponse(status_code=404, content={"detail": "company not found"})
    bundle = await StatementService(session).company_statements(company_obj.id)
    return JSONResponse(status_code=200, content=bundle.model_dump(mode="json"))


@router.get("/companies/{ticker}/ratios")
async def company_ratios(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    company_obj = await CompanyRepository(session).get_by_ticker(ticker)
    if company_obj is None:
        return JSONResponse(status_code=404, content={"detail": "company not found"})
    bundle = await StatementService(session).company_ratios(company_obj.id)
    return JSONResponse(status_code=200, content=bundle.model_dump(mode="json"))


class ManualLineBody(BaseModel):
    code: str = Field(max_length=64)
    value: Decimal
    page: str = Field(min_length=1, max_length=32)


class ManualFilingBody(BaseModel):
    """Numbers copied from an official filing; every value carries its page."""

    ticker: str = Field(max_length=20)
    fiscal_year: int = Field(ge=1990, le=2100)
    period_end: date
    document_url: str = Field(max_length=500)
    publication_date: date | None = None
    currency: str = Field("EGP", min_length=3, max_length=3)
    lines: list[ManualLineBody] = Field(min_length=1, max_length=len(STATEMENT_LINES))


@router.get("/intake")
async def filings_intake(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Priority checklist: EGX33 Shariah members + 30 most traded, missing work first."""
    rows = await intake_checklist(session)
    return {
        "items": [
            {
                "company_id": str(r.company_id),
                "ticker": r.ticker,
                "name": r.name,
                "reasons": r.reasons,
                "filing_years": r.filing_years,
                "vendor_years": r.vendor_years,
                "target_year": r.target_year,
                "status": r.status,
                "disclosure_url": r.disclosure_url,
            }
            for r in rows
        ],
        "lines": [
            {"code": code, "label_en": sl.label_en, "label_ar": sl.label_ar, "section": sl.section}
            for code, sl in STATEMENT_LINES.items()
        ],
    }


@router.post("/manual-filings")
async def record_filing(
    body: ManualFilingBody, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    """Record an official filing entered by hand; lines run through the validator."""
    try:
        result = await record_manual_filing(
            session,
            ticker=body.ticker,
            fiscal_year=body.fiscal_year,
            period_end=body.period_end,
            document_url=body.document_url,
            publication_date=body.publication_date,
            currency=body.currency,
            lines=[ManualLine(code=x.code, value=x.value, page=x.page) for x in body.lines],
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await session.commit()
    return {
        "document_id": str(result.document_id),
        "period_id": str(result.period_id),
        "lines": result.lines,
    }
