"""Repository for Shariah screening persistence."""

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.screening import (
    ScreeningEgxMembership,
    ScreeningPurificationEstimate,
    ScreeningRuleResultDB,
    ScreeningStatusDB,
    ShariahScreeningResult,
)


class ScreeningRepository:
    """Repository for Shariah screening CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_screening_result(
        self,
        company_id: uuid.UUID,
        is_compliant: bool | None,
        methodology_version: str,
        methodology_name: str,
        overall_reason: str,
        screened_at: datetime,
        report_date: date | None = None,
        report_date_reason: str | None = None,
    ) -> ShariahScreeningResult:
        """Create or update a screening result (last-writer-wins per version)."""
        if is_compliant is None:
            status = ScreeningStatusDB.INSUFFICIENT_DATA
        elif is_compliant:
            status = ScreeningStatusDB.COMPLIANT
        else:
            status = ScreeningStatusDB.NON_COMPLIANT

        stmt = (
            pg_insert(ShariahScreeningResult)
            .values(
                company_id=company_id,
                is_compliant=is_compliant,
                status=status,
                methodology_version=methodology_version,
                methodology_name=methodology_name,
                overall_reason=overall_reason,
                screened_at=screened_at,
                report_date=report_date,
                report_date_reason=report_date_reason,
            )
            .on_conflict_do_update(
                constraint="uq_shariah_screening_result",
                set_={
                    "is_compliant": is_compliant,
                    "status": status,
                    "overall_reason": overall_reason,
                    "screened_at": screened_at,
                    "report_date": report_date,
                    "report_date_reason": report_date_reason,
                },
            )
            .returning(ShariahScreeningResult)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def delete_rule_results(self, screening_result_id: uuid.UUID) -> None:
        """Remove a result's rule rows so a re-screen replaces, never appends."""
        from sqlalchemy import delete

        await self.session.execute(
            delete(ScreeningRuleResultDB).where(
                ScreeningRuleResultDB.screening_result_id == screening_result_id
            )
        )
        await self.session.flush()

    async def add_rule_result(
        self,
        screening_result_id: uuid.UUID,
        rule_name: str,
        verdict: str,
        value: float | None,
        threshold: float | None,
        reason: str | None,
        missing_input: str | None = None,
        source: str | None = None,
        source_date: date | None = None,
    ) -> ScreeningRuleResultDB:
        """Add a rule result to a screening result."""
        rule = ScreeningRuleResultDB(
            id=uuid.uuid4(),
            screening_result_id=screening_result_id,
            rule_name=rule_name,
            verdict=verdict,
            value=value,
            threshold=threshold,
            reason=reason,
            missing_input=missing_input,
            source=source,
            source_date=source_date,
        )
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def get_screening_result(
        self,
        company_id: uuid.UUID,
        methodology_version: str | None = None,
    ) -> ShariahScreeningResult | None:
        """Get the latest screening result for a company."""
        query = select(ShariahScreeningResult).where(
            ShariahScreeningResult.company_id == company_id,
        )
        if methodology_version:
            query = query.where(
                ShariahScreeningResult.methodology_version == methodology_version
            )
        query = query.order_by(ShariahScreeningResult.screened_at.desc()).execution_options(
            populate_existing=True
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def list_screened_companies(
        self,
        is_compliant: bool | None = None,
        methodology_version: str | None = None,
    ) -> Sequence[ShariahScreeningResult]:
        """List all screening results, optionally filtered."""
        query = select(ShariahScreeningResult)

        if is_compliant is not None:
            query = query.where(ShariahScreeningResult.is_compliant == is_compliant)

        if methodology_version:
            query = query.where(
                ShariahScreeningResult.methodology_version == methodology_version
            )

        query = query.order_by(ShariahScreeningResult.screened_at.desc())
        result = await self.session.execute(query)
        return result.scalars().all()

    async def upsert_purification_estimate(
        self,
        company_id: uuid.UUID,
        methodology_version: str,
        doctrine: str,
        branch: str,
        status: str,
        amount_egp: Decimal | None,
        dividend_egp: Decimal | None,
        ratio: Decimal | None,
        ratio_provenance: str | None,
        dps: Decimal | None,
        dps_source: str | None,
        dps_date: date | None,
        reason: str | None,
        missing_input: str | None,
        computed_at: datetime,
    ) -> ScreeningPurificationEstimate:
        """Create or update a purification estimate (last-writer-wins per version)."""
        stmt = (
            pg_insert(ScreeningPurificationEstimate)
            .values(
                company_id=company_id,
                methodology_version=methodology_version,
                doctrine=doctrine,
                branch=branch,
                status=status,
                amount_egp=amount_egp,
                dividend_egp=dividend_egp,
                ratio=ratio,
                ratio_provenance=ratio_provenance,
                dps=dps,
                dps_source=dps_source,
                dps_date=dps_date,
                reason=reason,
                missing_input=missing_input,
                computed_at=computed_at,
            )
            .on_conflict_do_update(
                constraint="uq_screening_purification_estimate",
                set_={
                    "doctrine": doctrine,
                    "branch": branch,
                    "status": status,
                    "amount_egp": amount_egp,
                    "dividend_egp": dividend_egp,
                    "ratio": ratio,
                    "ratio_provenance": ratio_provenance,
                    "dps": dps,
                    "dps_source": dps_source,
                    "dps_date": dps_date,
                    "reason": reason,
                    "missing_input": missing_input,
                    "computed_at": computed_at,
                },
            )
            .returning(ScreeningPurificationEstimate)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_purification_estimate(
        self,
        company_id: uuid.UUID,
        methodology_version: str | None = None,
    ) -> ScreeningPurificationEstimate | None:
        """Get the latest purification estimate for a company."""
        query = select(ScreeningPurificationEstimate).where(
            ScreeningPurificationEstimate.company_id == company_id,
        )
        if methodology_version:
            query = query.where(
                ScreeningPurificationEstimate.methodology_version == methodology_version
            )
        query = query.order_by(ScreeningPurificationEstimate.computed_at.desc()).execution_options(
            populate_existing=True
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def upsert_egx_membership(
        self,
        company_id: uuid.UUID,
        methodology_version: str,
        member: bool,
        review_cycle: str,
        effective_date: date | None,
        source: str,
        note: str | None,
    ) -> ScreeningEgxMembership:
        """Record a dated EGX33 membership catalyst (idempotent per cycle)."""
        stmt = (
            pg_insert(ScreeningEgxMembership)
            .values(
                company_id=company_id,
                methodology_version=methodology_version,
                member=member,
                review_cycle=review_cycle,
                effective_date=effective_date,
                source=source,
                note=note,
            )
            .on_conflict_do_update(
                constraint="uq_screening_egx_membership",
                set_={
                    "methodology_version": methodology_version,
                    "member": member,
                    "effective_date": effective_date,
                    "source": source,
                    "note": note,
                },
            )
            .returning(ScreeningEgxMembership)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def list_egx_memberships(
        self, company_id: uuid.UUID
    ) -> Sequence[ScreeningEgxMembership]:
        """List a company's EGX33 membership records, newest cycle first."""
        query = (
            select(ScreeningEgxMembership)
            .where(ScreeningEgxMembership.company_id == company_id)
            .order_by(ScreeningEgxMembership.review_cycle.desc())
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def latest_egx_memberships(
        self, company_ids: Sequence[uuid.UUID] | None = None
    ) -> dict[uuid.UUID, ScreeningEgxMembership]:
        """Each company's newest EGX33 membership record (by review cycle).

        Per company, not per global cycle: a single newer per-company record
        must never change any other company's status.
        """
        query = select(ScreeningEgxMembership).order_by(
            ScreeningEgxMembership.review_cycle.desc()
        )
        if company_ids is not None:
            if not company_ids:
                return {}
            query = query.where(ScreeningEgxMembership.company_id.in_(company_ids))
        result = await self.session.execute(query)
        latest: dict[uuid.UUID, ScreeningEgxMembership] = {}
        for row in result.scalars().all():
            latest.setdefault(row.company_id, row)
        return latest

    async def latest_results_by_company(
        self, company_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, ShariahScreeningResult]:
        """Newest screening verdict per company for the given companies."""
        if not company_ids:
            return {}
        query = (
            select(ShariahScreeningResult)
            .where(ShariahScreeningResult.company_id.in_(company_ids))
            .order_by(ShariahScreeningResult.screened_at.desc())
        )
        result = await self.session.execute(query)
        latest: dict[uuid.UUID, ShariahScreeningResult] = {}
        for row in result.scalars().all():
            latest.setdefault(row.company_id, row)
        return latest
