"""Repository for financial metrics persistence."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metrics import FinancialMetric, FinancialMetricInput, MetricStatusDB


class MetricRepository:
    """Repository for financial metric CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_metric(
        self,
        company_id: uuid.UUID,
        period_id: uuid.UUID,
        metric_code: str,
        display_name: str,
        value: float | None,
        unit: str,
        status: MetricStatusDB,
        reason: str | None,
        warnings: str | None,
        formula_version: int,
        calculated_at: datetime,
    ) -> FinancialMetric:
        """Create or update a financial metric."""
        stmt = (
            pg_insert(FinancialMetric)
            .values(
                company_id=company_id,
                period_id=period_id,
                metric_code=metric_code,
                display_name=display_name,
                value=value,
                unit=unit,
                status=status,
                reason=reason,
                warnings=warnings,
                formula_version=formula_version,
                calculated_at=calculated_at,
            )
            .on_conflict_do_update(
                constraint="uq_financial_metric",
                set_={
                    "value": value,
                    "status": status,
                    "reason": reason,
                    "warnings": warnings,
                    "calculated_at": calculated_at,
                },
            )
            .returning(FinancialMetric)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def upsert_metric_input(
        self,
        metric_id: uuid.UUID,
        fact_id: uuid.UUID,
        input_role: str,
    ) -> FinancialMetricInput:
        """Create or update a metric input (provenance)."""
        stmt = (
            pg_insert(FinancialMetricInput)
            .values(
                metric_id=metric_id,
                fact_id=fact_id,
                input_role=input_role,
            )
            .on_conflict_do_update(
                constraint="uq_financial_metric_input",
                set_={
                    "input_role": input_role,
                },
            )
            .returning(FinancialMetricInput)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_metric_by_id(
        self,
        metric_id: uuid.UUID,
    ) -> FinancialMetric | None:
        """Get a metric by ID."""
        return await self.session.get(FinancialMetric, metric_id)

    async def list_metrics_for_period(
        self,
        company_id: uuid.UUID,
        period_id: uuid.UUID,
        metric_code: str | None = None,
    ) -> Sequence[FinancialMetric]:
        """List all metrics for a specific company and period."""
        query = select(FinancialMetric).where(
            FinancialMetric.company_id == company_id,
            FinancialMetric.period_id == period_id,
        )

        if metric_code:
            query = query.where(FinancialMetric.metric_code == metric_code)

        query = query.order_by(FinancialMetric.metric_code)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def list_metrics_for_company(
        self,
        company_id: uuid.UUID,
        metric_code: str | None = None,
        fiscal_year: int | None = None,
    ) -> Sequence[FinancialMetric]:
        """List all metrics for a company, optionally filtered."""
        from app.models.financial import FinancialPeriod

        query = select(FinancialMetric).where(
            FinancialMetric.company_id == company_id,
        )

        if metric_code:
            query = query.where(FinancialMetric.metric_code == metric_code)

        if fiscal_year:
            query = query.join(FinancialPeriod).where(
                FinancialPeriod.fiscal_year == fiscal_year
            )

        query = query.order_by(FinancialMetric.metric_code)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_metric_inputs(
        self,
        metric_id: uuid.UUID,
    ) -> Sequence[FinancialMetricInput]:
        """Get all input facts for a metric (provenance)."""
        query = select(FinancialMetricInput).where(
            FinancialMetricInput.metric_id == metric_id
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def delete_metrics_for_period(
        self,
        company_id: uuid.UUID,
        period_id: uuid.UUID,
    ) -> int:
        """Delete all metrics for a specific company and period."""
        from sqlalchemy import delete

        # Delete inputs first
        input_delete = delete(FinancialMetricInput).where(
            FinancialMetricInput.metric_id.in_(
                select(FinancialMetric.id).where(
                    FinancialMetric.company_id == company_id,
                    FinancialMetric.period_id == period_id,
                )
            )
        )
        await self.session.execute(input_delete)

        # Delete metrics
        metric_delete = delete(FinancialMetric).where(
            FinancialMetric.company_id == company_id,
            FinancialMetric.period_id == period_id,
        )
        await self.session.execute(metric_delete)
        return 0
