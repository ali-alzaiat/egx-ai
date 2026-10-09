import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.financial import (
    DocumentStatus,
    FactStatus,
    FactType,
    ReportingPeriodType,
)
from app.repositories.company import CompanyRepository
from app.repositories.financial import (
    FinancialDocumentRepository,
    FinancialFactRepository,
    FinancialPeriodRepository,
)

router = APIRouter(prefix="/api/financial", tags=["financial"])


@router.get("/periods/{company_id}")
async def list_financial_periods(
    company_id: uuid.UUID,
    period_type: ReportingPeriodType | None = Query(None),
    fiscal_year: int | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List financial periods for a company."""
    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    period_repo = FinancialPeriodRepository(session)
    periods = await period_repo.list_periods(
        company_id=company_id,
        period_type=period_type.value if period_type else None,
        fiscal_year=fiscal_year,
    )

    return [
        {
            "id": str(p.id),
            "company_id": str(p.company_id),
            "period_type": p.period_type.value,
            "fiscal_year": p.fiscal_year,
            "fiscal_quarter": p.fiscal_quarter,
            "start_date": p.start_date.isoformat(),
            "end_date": p.end_date.isoformat(),
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat(),
        }
        for p in periods
    ]


@router.get("/documents/{period_id}")
async def list_financial_documents(
    period_id: uuid.UUID,
    document_status: DocumentStatus | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List financial documents for a period."""
    period_repo = FinancialPeriodRepository(session)
    period = await period_repo.get_by_id(period_id)
    if not period:
        raise HTTPException(status_code=404, detail="Financial period not found")

    doc_repo = FinancialDocumentRepository(session)
    documents = await doc_repo.list_documents(
        period_id=period_id,
        document_status=document_status.value if document_status else None,
    )

    return [
        {
            "id": str(d.id),
            "period_id": str(d.period_id),
            "source_id": str(d.source_id),
            "document_status": d.document_status.value,
            "document_type": d.document_type,
            "document_url": d.document_url,
            "filing_date": d.filing_date.isoformat() if d.filing_date else None,
            "publication_date": d.publication_date.isoformat() if d.publication_date else None,
            "fiscal_year_end": d.fiscal_year_end.isoformat() if d.fiscal_year_end else None,
            "notes": d.notes,
            "created_at": d.created_at.isoformat(),
        }
        for d in documents
    ]


@router.get("/facts/{company_id}")
async def list_financial_facts(
    company_id: uuid.UUID,
    fact_type: FactType | None = Query(None),
    reported_label: str | None = Query(None),
    normalized_label: str | None = Query(None),
    status: FactStatus | None = Query(None),
    fiscal_year: int | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List financial facts for a company."""
    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    fact_repo = FinancialFactRepository(session)
    facts = await fact_repo.list_facts(
        company_id=company_id,
        fact_type=fact_type.value if fact_type else None,
        reported_label=reported_label,
        normalized_label=normalized_label,
        status=status.value if status else None,
        fiscal_year=fiscal_year,
    )

    return [
        {
            "id": str(f.id),
            "period_id": str(f.period_id),
            "document_id": str(f.document_id),
            "company_id": str(f.company_id),
            "fact_type": f.fact_type.value,
            "reported_label": f.reported_label,
            "normalized_label": f.normalized_label,
            "reported_value": str(f.reported_value) if f.reported_value else None,
            "normalized_value": str(f.normalized_value) if f.normalized_value else None,
            "currency": f.currency,
            "unit": f.unit,
            "scale": f.scale,
            "status": f.status.value,
            "source_page": f.source_page,
            "source_line": f.source_line,
            "reported_at": f.reported_at.isoformat() if f.reported_at else None,
            "normalized_at": f.normalized_at.isoformat() if f.normalized_at else None,
            "created_at": f.created_at.isoformat(),
        }
        for f in facts
    ]


@router.get("/facts/{company_id}/latest")
async def get_latest_financial_facts(
    company_id: uuid.UUID,
    fact_type: FactType | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Get the latest financial facts for a company (most recent fiscal year)."""
    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    fact_repo = FinancialFactRepository(session)
    facts = await fact_repo.list_facts(
        company_id=company_id,
        fact_type=fact_type.value if fact_type else None,
    )

    if not facts:
        return []

    # Group by fiscal year and get the latest
    from app.repositories.financial import FinancialPeriodRepository
    period_repo = FinancialPeriodRepository(session)

    latest_year = 0
    for fact in facts:
        period = await period_repo.get_by_id(fact.period_id)
        if period and period.fiscal_year > latest_year:
            latest_year = period.fiscal_year

    # Get facts from the latest year
    latest_facts = []
    for fact in facts:
        period = await period_repo.get_by_id(fact.period_id)
        if period and period.fiscal_year == latest_year:
            latest_facts.append(fact)

    return [
        {
            "id": str(f.id),
            "period_id": str(f.period_id),
            "document_id": str(f.document_id),
            "company_id": str(f.company_id),
            "fact_type": f.fact_type.value,
            "reported_label": f.reported_label,
            "normalized_label": f.normalized_label,
            "reported_value": str(f.reported_value) if f.reported_value else None,
            "normalized_value": str(f.normalized_value) if f.normalized_value else None,
            "currency": f.currency,
            "unit": f.unit,
            "scale": f.scale,
            "status": f.status.value,
            "source_page": f.source_page,
            "source_line": f.source_line,
            "reported_at": f.reported_at.isoformat() if f.reported_at else None,
            "normalized_at": f.normalized_at.isoformat() if f.normalized_at else None,
            "created_at": f.created_at.isoformat(),
        }
        for f in latest_facts
    ]
