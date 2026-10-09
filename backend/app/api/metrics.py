"""API endpoints for financial metrics."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.metrics.service import MetricService
from app.models.metrics import MetricStatusDB
from app.repositories.metrics import MetricRepository

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/companies/{company_id}")
async def list_company_metrics(
    company_id: uuid.UUID,
    fiscal_year: int | None = Query(None),
    metric_code: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List all metrics for a company."""
    from app.repositories.company import CompanyRepository

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    metric_repo = MetricRepository(session)
    metrics = await metric_repo.list_metrics_for_company(
        company_id=company_id,
        metric_code=metric_code,
        fiscal_year=fiscal_year,
    )

    return [
        {
            "id": str(m.id),
            "company_id": str(m.company_id),
            "period_id": str(m.period_id),
            "metric_code": m.metric_code,
            "display_name": m.display_name,
            "value": str(m.value) if m.value is not None else None,
            "unit": m.unit,
            "status": m.status.value,
            "reason": m.reason,
            "warnings": m.warnings,
            "formula_version": m.formula_version,
            "calculated_at": m.calculated_at.isoformat(),
            "created_at": m.created_at.isoformat(),
        }
        for m in metrics
    ]


@router.get("/companies/{company_id}/periods/{period_id}")
async def list_period_metrics(
    company_id: uuid.UUID,
    period_id: uuid.UUID,
    metric_code: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List all metrics for a specific period."""
    from app.repositories.company import CompanyRepository

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    metric_repo = MetricRepository(session)
    metrics = await metric_repo.list_metrics_for_period(
        company_id=company_id,
        period_id=period_id,
        metric_code=metric_code,
    )

    return [
        {
            "id": str(m.id),
            "company_id": str(m.company_id),
            "period_id": str(m.period_id),
            "metric_code": m.metric_code,
            "display_name": m.display_name,
            "value": str(m.value) if m.value is not None else None,
            "unit": m.unit,
            "status": m.status.value,
            "reason": m.reason,
            "warnings": m.warnings,
            "formula_version": m.formula_version,
            "calculated_at": m.calculated_at.isoformat(),
            "created_at": m.created_at.isoformat(),
        }
        for m in metrics
    ]


@router.get("/companies/{company_id}/periods/{period_id}/{metric_code}")
async def get_specific_metric(
    company_id: uuid.UUID,
    period_id: uuid.UUID,
    metric_code: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get a specific metric for a period."""
    from app.repositories.company import CompanyRepository

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    metric_repo = MetricRepository(session)
    metrics = await metric_repo.list_metrics_for_period(
        company_id=company_id,
        period_id=period_id,
        metric_code=metric_code,
    )

    if not metrics:
        raise HTTPException(status_code=404, detail="Metric not found")

    m = metrics[0]

    # Get provenance
    inputs = await metric_repo.get_metric_inputs(m.id)

    return {
        "id": str(m.id),
        "company_id": str(m.company_id),
        "period_id": str(m.period_id),
        "metric_code": m.metric_code,
        "display_name": m.display_name,
        "value": str(m.value) if m.value is not None else None,
        "unit": m.unit,
        "status": m.status.value,
        "reason": m.reason,
        "warnings": m.warnings,
        "formula_version": m.formula_version,
        "calculated_at": m.calculated_at.isoformat(),
        "created_at": m.created_at.isoformat(),
        "provenance": [
            {
                "fact_id": str(inp.fact_id),
                "input_role": inp.input_role,
            }
            for inp in inputs
        ],
    }


@router.post("/companies/{company_id}/calculate")
async def calculate_metrics(
    company_id: uuid.UUID,
    fiscal_year: int | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Calculate and persist all metrics for a company."""
    from app.repositories.company import CompanyRepository

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    service = MetricService(session)
    metric_repo = MetricRepository(session)

    # Calculate metrics for all periods
    results = await service.calculate_all_metrics_for_company(
        company_id=str(company_id),
        fiscal_year=fiscal_year,
    )

    # Persist results
    persisted_count = 0
    for period_id, metrics in results.items():
        for metric_output in metrics:
            # Upsert metric
            await metric_repo.upsert_metric(
                company_id=company_id,
                period_id=uuid.UUID(period_id),
                metric_code=metric_output.metric_code,
                display_name=metric_output.display_name,
                value=float(metric_output.value) if metric_output.value is not None else None,
                unit=metric_output.unit,
                status=MetricStatusDB(metric_output.status.value),
                reason=metric_output.reason,
                warnings=str(metric_output.warnings) if metric_output.warnings else None,
                formula_version=metric_output.formula_version,
                calculated_at=metric_output.calculated_at,
            )
            persisted_count += 1

    await session.commit()

    return {
        "company_id": str(company_id),
        "periods_calculated": len(results),
        "metrics_persisted": persisted_count,
    }


@router.post("/companies/{company_id}/periods/{period_id}/calculate")
async def calculate_period_metrics(
    company_id: uuid.UUID,
    period_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Calculate and persist metrics for a specific period."""
    from app.repositories.company import CompanyRepository

    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    service = MetricService(session)
    metric_repo = MetricRepository(session)

    # Calculate metrics for the specific period
    results = await service.calculate_metrics_for_period(
        company_id=str(company_id),
        period_id=str(period_id),
    )

    # Persist results
    persisted_count = 0
    for metric_output in results:
        await metric_repo.upsert_metric(
            company_id=company_id,
            period_id=period_id,
            metric_code=metric_output.metric_code,
            display_name=metric_output.display_name,
            value=float(metric_output.value) if metric_output.value is not None else None,
            unit=metric_output.unit,
            status=MetricStatusDB(metric_output.status.value),
            reason=metric_output.reason,
            warnings=str(metric_output.warnings) if metric_output.warnings else None,
            formula_version=metric_output.formula_version,
            calculated_at=metric_output.calculated_at,
        )
        persisted_count += 1

    await session.commit()

    return {
        "company_id": str(company_id),
        "period_id": str(period_id),
        "metrics_persisted": persisted_count,
    }
