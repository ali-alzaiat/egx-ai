"""API endpoints for AI analysis."""

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.analyzer import AIAnalyzer, AnalysisRequest
from app.ai.document_indexer import DocumentIndexer
from app.db.session import get_session
from app.models.ai import AnalysisTypeDB
from app.repositories.company import CompanyRepository

router = APIRouter(prefix="/api/ai", tags=["ai"])


MAX_QUERY_CHARS = 2000


class AnalyzeRequest(BaseModel):
    """Request body for AI analysis.

    The model label is provenance, so it is set server-side, never by the caller.
    """
    analysis_type: str = Field(max_length=64)
    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)


class IndexRequest(BaseModel):
    """Request body for indexing company data."""
    pass


@router.post("/companies/{company_id}/analyze")
async def analyze_company(
    company_id: uuid.UUID,
    request: AnalyzeRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Perform AI analysis on a company."""
    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    try:
        analysis_type = AnalysisTypeDB(request.analysis_type)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid analysis type: {request.analysis_type}. "
                   f"Valid types: {[t.value for t in AnalysisTypeDB]}",
        ) from e

    analyzer = AIAnalyzer(session)
    result = await analyzer.analyze(AnalysisRequest(
        company_id=company_id,
        analysis_type=analysis_type,
        query=request.query,
    ))

    await session.commit()

    return {
        "analysis_id": str(result.analysis_id),
        "company_id": str(company_id),
        "summary": result.summary,
        "detailed_analysis": result.detailed_analysis,
        "sources": result.sources,
        "confidence_score": result.confidence_score,
        "disclaimer": result.disclaimer,
        "status": result.status,
    }


@router.post("/companies/{company_id}/index")
async def index_company_data(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Index a company's financial data for RAG retrieval."""
    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    indexer = DocumentIndexer(session)
    counts = await indexer.index_company(company_id)
    await session.commit()

    return {
        "company_id": str(company_id),
        "indexed": counts,
        "total_chunks": sum(counts.values()),
    }


@router.get("/companies/{company_id}/analyses")
async def get_analyses(
    company_id: uuid.UUID,
    analysis_type: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Get AI analyses for a company."""
    from sqlalchemy import select

    from app.models.ai import AIAnalysis

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    query = select(AIAnalysis).where(AIAnalysis.company_id == company_id)
    if analysis_type:
        try:
            type_enum = AnalysisTypeDB(analysis_type)
            query = query.where(AIAnalysis.analysis_type == type_enum)
        except ValueError as e:
            msg = f"Invalid analysis type: {analysis_type}"
            raise HTTPException(status_code=400, detail=msg) from e

    query = query.order_by(AIAnalysis.created_at.desc())
    result = await session.execute(query)
    analyses = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "company_id": str(a.company_id),
            "analysis_type": a.analysis_type.value,
            "summary": a.summary,
            "detailed_analysis": a.detailed_analysis,
            "source_chunk_ids": json.loads(a.source_chunk_ids) if a.source_chunk_ids else [],
            "confidence_score": float(a.confidence_score) if a.confidence_score else None,
            "disclaimer": a.disclaimer,
            "status": a.status.value,
            "model_used": a.model_used,
            "created_at": a.created_at.isoformat(),
        }
        for a in analyses
    ]
