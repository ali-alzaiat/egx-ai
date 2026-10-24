"""API endpoints for financial metrics (R43: computed on read from statement lines)."""

import uuid
from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.metrics.service import METRICS_INPUT_VERSION, MetricService
from app.models.financial import FinancialPeriod
from app.models.metrics import FinancialMetric
from app.repositories.company import CompanyRepository
from app.repositories.metrics import MetricRepository
from app.services.recompute import Engine, RecomputeService, compute_meta

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


async def _fresh_meta(session: AsyncSession, company_id: uuid.UUID) -> dict[str, Any]:
    if await CompanyRepository(session).get_by_id(company_id) is None:
        raise HTTPException(status_code=404, detail="Company not found")
    state = await RecomputeService(session).ensure_fresh(company_id, Engine.METRICS)
    return compute_meta(state)


async def _rows(
    session: AsyncSession, metrics: Sequence[FinancialMetric], meta: dict[str, Any]
) -> list[dict[str, Any]]:
    if not metrics and meta.get("compute_status") == "failed":
        # No snapshot to serve: say so (section 3.1) instead of an empty list.
        placeholder = dict(meta)
        placeholder.update(
            {
                "id": None,
                "company_id": None,
                "period_id": None,
                "fiscal_year": None,
                "period_type": None,
                "period_end": None,
                "metric_code": None,
                "display_name": None,
                "value": None,
                "unit": None,
                "status": "INSUFFICIENT_DATA",
                "reason": f"computation failed: {meta.get('compute_error') or 'no snapshot'}",
                "warnings": None,
                "formula_version": None,
                "methodology_version": METRICS_INPUT_VERSION,
                "inputs": [],
            }
        )
        return [placeholder]
    period_ids = {m.period_id for m in metrics}
    periods: dict[uuid.UUID, FinancialPeriod] = {}
    if period_ids:
        periods = {
            p.id: p
            for p in (
                await session.execute(
                    select(FinancialPeriod).where(FinancialPeriod.id.in_(period_ids))
                )
            ).scalars().all()
        }
    inputs = await MetricService(session).input_provenance([m.id for m in metrics])
    out: list[dict[str, Any]] = []
    for m in metrics:
        period = periods.get(m.period_id)
        row = dict(meta)
        row.update(
            {
                "id": str(m.id),
                "company_id": str(m.company_id),
                "period_id": str(m.period_id),
                "fiscal_year": period.fiscal_year if period else None,
                "period_type": (
                    period.period_type.value
                    if period is not None and hasattr(period.period_type, "value")
                    else (str(period.period_type) if period else None)
                ),
                "period_end": period.end_date.isoformat() if period else None,
                "metric_code": m.metric_code,
                "display_name": m.display_name,
                "value": str(m.value) if m.value is not None else None,
                "unit": m.unit,
                "status": m.status.value,
                "reason": m.reason,
                "warnings": m.warnings,
                "formula_version": m.formula_version,
                "methodology_version": METRICS_INPUT_VERSION,
                "source_tier": m.source_tier,
                "provisional": bool(m.provisional),
                "calculated_at": m.calculated_at.isoformat(),
                "created_at": m.created_at.isoformat(),
                "inputs": inputs.get(m.id, []),
            }
        )
        out.append(row)
    out.sort(key=lambda r: (-(r["fiscal_year"] or 0), r["metric_code"]))
    return out


@router.get("/companies/{company_id}")
async def list_company_metrics(
    company_id: uuid.UUID,
    fiscal_year: int | None = Query(None),
    metric_code: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """All metrics for a company, every ANNUAL period, computed on first view."""
    meta = await _fresh_meta(session, company_id)
    metrics = await MetricRepository(session).list_metrics_for_company(
        company_id=company_id, metric_code=metric_code, fiscal_year=fiscal_year
    )
    return await _rows(session, metrics, meta)


@router.get("/companies/{company_id}/periods/{period_id}")
async def list_period_metrics(
    company_id: uuid.UUID,
    period_id: uuid.UUID,
    metric_code: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """All metrics for one period."""
    meta = await _fresh_meta(session, company_id)
    metrics = await MetricRepository(session).list_metrics_for_period(
        company_id=company_id, period_id=period_id, metric_code=metric_code
    )
    return await _rows(session, metrics, meta)


@router.get("/companies/{company_id}/periods/{period_id}/{metric_code}")
async def get_specific_metric(
    company_id: uuid.UUID,
    period_id: uuid.UUID,
    metric_code: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """One metric with its statement-line provenance."""
    meta = await _fresh_meta(session, company_id)
    metrics = await MetricRepository(session).list_metrics_for_period(
        company_id=company_id, period_id=period_id, metric_code=metric_code
    )
    if not metrics:
        raise HTTPException(status_code=404, detail="Metric not found")
    rows = await _rows(session, metrics[:1], meta)
    row = rows[0]
    row["provenance"] = row["inputs"]
    return row
