"""API endpoints for data-quality assessments."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dataquality.scores import METHODOLOGY_VERSION
from app.dataquality.service import DataQualityService
from app.db.session import get_session
from app.repositories.company import CompanyRepository

SCALE = "0-100; higher is better; status MISSING|DEGRADED|POOR|OK"
DISCLAIMER = "Data quality describes the available inputs. It is not an assessment of the company."

router = APIRouter(prefix="/api/data-quality", tags=["data-quality"])


async def _ensure_company_exists(session: AsyncSession, company_id: uuid.UUID) -> None:
    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")


@router.get("/companies/{company_id}")
async def get_data_quality_assessments(
    company_id: uuid.UUID,
    scope: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    await _ensure_company_exists(session, company_id)
    service = DataQualityService(session)

    scopes = [scope] if scope else ["price_history", "company_profile", "financial_statements"]
    items = []
    for s in scopes:
        result = await service.latest(company_id, s, methodology_version=METHODOLOGY_VERSION)
        if result is not None:
            items.append(result.as_dict())

    return {
        "items": items,
        "methodology_version": METHODOLOGY_VERSION,
        "scale": SCALE,
        "disclaimer": DISCLAIMER,
    }


@router.post("/companies/{company_id}/assess")
async def assess_data_quality(
    company_id: uuid.UUID,
    scope: str = Query(...),
    as_of: date | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    await _ensure_company_exists(session, company_id)
    service = DataQualityService(session)
    result = await service.assess(company_id, scope=scope, as_of=as_of)
    return result.as_dict() | {"scale": SCALE, "disclaimer": DISCLAIMER}
