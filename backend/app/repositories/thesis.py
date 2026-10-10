"""Repository for investment-thesis snapshots, invalidations, ledger, catalysts."""

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.thesis import (
    InvestmentThesis,
    ThesisCatalyst,
    ThesisInvalidation,
    ThesisLedger,
)
from app.thesis.constants import THESIS_METHODOLOGY_VERSION


class ThesisRepository:
    """Persistence for the four Phase-5 thesis tables."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_thesis(
        self,
        company_id: uuid.UUID,
        horizon_years: int,
        is_shareholder: bool | None,
        fair_value: Decimal | None,
        fair_value_status: str,
        assumptions: list[dict[str, Any]],
        bulls: list[str],
        bears: list[str],
        scenarios: dict[str, Any],
        sensitivity: dict[str, Any],
        narrative: str,
        confidence: dict[str, Any],
        dq: dict[str, Any],
        score: dict[str, Any] | None,
        needs_reassessment: bool,
        computed_at: datetime,
    ) -> InvestmentThesis:
        """Create or replace the thesis for one company + methodology version.

        Last-writer-wins: the unique key is company + methodology version
        (inputs do not participate), so a re-assess overwrites the single
        row. The ledger is append-only and untouched here.
        """
        stmt = (
            pg_insert(InvestmentThesis)
            .values(
                company_id=company_id,
                methodology_version=THESIS_METHODOLOGY_VERSION,
                horizon_years=horizon_years,
                is_shareholder=is_shareholder,
                fair_value=fair_value,
                fair_value_status=fair_value_status,
                assumptions=assumptions,
                bulls=bulls,
                bears=bears,
                scenarios=scenarios,
                sensitivity=sensitivity,
                narrative=narrative,
                confidence=confidence,
                dq=dq,
                score=score,
                needs_reassessment=needs_reassessment,
                computed_at=computed_at,
            )
            .on_conflict_do_update(
                constraint="uq_investment_thesis",
                set_={
                    "horizon_years": horizon_years,
                    "is_shareholder": is_shareholder,
                    "fair_value": fair_value,
                    "fair_value_status": fair_value_status,
                    "assumptions": assumptions,
                    "bulls": bulls,
                    "bears": bears,
                    "scenarios": scenarios,
                    "sensitivity": sensitivity,
                    "narrative": narrative,
                    "confidence": confidence,
                    "dq": dq,
                    "score": score,
                    "needs_reassessment": needs_reassessment,
                    "computed_at": computed_at,
                },
            )
            .returning(InvestmentThesis)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one()
        # Long-lived sessions (tests, jobs) may already hold this row: reload
        # so the returned object reflects the write, not the identity map.
        await self.session.refresh(row)
        return row

    async def get_thesis(self, company_id: uuid.UUID) -> InvestmentThesis | None:
        """Thesis row for one company under the current methodology."""
        result = await self.session.execute(
            select(InvestmentThesis)
            .where(InvestmentThesis.company_id == company_id)
            .where(
                InvestmentThesis.methodology_version == THESIS_METHODOLOGY_VERSION
            )
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def upsert_invalidation(
        self,
        thesis_id: uuid.UUID,
        metric: str,
        threshold: Decimal,
        direction: str,
        period: str,
        evidence_source: str,
        action: str,
        status: str,
        extraction_confidence: str,
        version: int,
    ) -> ThesisInvalidation:
        """Create or replace one condition keyed by (thesis, metric)."""
        stmt = (
            pg_insert(ThesisInvalidation)
            .values(
                thesis_id=thesis_id,
                methodology_version=THESIS_METHODOLOGY_VERSION,
                metric=metric,
                threshold=threshold,
                direction=direction,
                period=period,
                evidence_source=evidence_source,
                action=action,
                status=status,
                extraction_confidence=extraction_confidence,
                version=version,
            )
            .on_conflict_do_update(
                constraint="uq_thesis_invalidation",
                set_={
                    "threshold": threshold,
                    "direction": direction,
                    "period": period,
                    "evidence_source": evidence_source,
                    "action": action,
                    "status": status,
                    "extraction_confidence": extraction_confidence,
                    "version": version,
                },
            )
            .returning(ThesisInvalidation)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one()
        # Same reload rationale as upsert_thesis: never hand back a stale
        # identity-mapped instance after an overwrite.
        await self.session.refresh(row)
        return row

    async def list_invalidations(
        self, thesis_id: uuid.UUID
    ) -> Sequence[ThesisInvalidation]:
        """Conditions for one thesis under the current methodology, by metric."""
        result = await self.session.execute(
            select(ThesisInvalidation)
            .where(ThesisInvalidation.thesis_id == thesis_id)
            .where(
                ThesisInvalidation.methodology_version == THESIS_METHODOLOGY_VERSION
            )
            .order_by(ThesisInvalidation.metric)
            .execution_options(populate_existing=True)
        )
        return result.scalars().all()

    async def append_ledger(
        self,
        thesis_id: uuid.UUID,
        classification: str,
        variable: str,
        action: str,
        rationale: str,
        evidence: dict[str, Any],
        reviewer: str | None,
    ) -> ThesisLedger:
        """Append one ledger row. Ledger rows are never updated or deleted."""
        row = ThesisLedger(
            id=uuid.uuid4(),
            thesis_id=thesis_id,
            methodology_version=THESIS_METHODOLOGY_VERSION,
            classification=classification,
            variable=variable,
            action=action,
            rationale=rationale,
            evidence=evidence,
            reviewer=reviewer,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_ledger(self, thesis_id: uuid.UUID) -> Sequence[ThesisLedger]:
        """Ledger rows for one thesis, oldest first."""
        result = await self.session.execute(
            select(ThesisLedger)
            .where(ThesisLedger.thesis_id == thesis_id)
            .where(ThesisLedger.methodology_version == THESIS_METHODOLOGY_VERSION)
            .order_by(ThesisLedger.created_at)
            .execution_options(populate_existing=True)
        )
        return result.scalars().all()

    async def add_catalyst(
        self,
        thesis_id: uuid.UUID,
        event: str,
        date_from: date | None,
        date_to: date | None,
        window: str | None,
        variable: str | None,
        expectation: str | None,
        outcome: str,
        provenance: str,
        label: str,
    ) -> ThesisCatalyst:
        """Insert one catalyst record."""
        row = ThesisCatalyst(
            id=uuid.uuid4(),
            thesis_id=thesis_id,
            methodology_version=THESIS_METHODOLOGY_VERSION,
            event=event,
            date_from=date_from,
            date_to=date_to,
            window=window,
            variable=variable,
            expectation=expectation,
            outcome=outcome,
            provenance=provenance,
            label=label,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_catalysts(
        self, thesis_id: uuid.UUID
    ) -> Sequence[ThesisCatalyst]:
        """Catalyst records for one thesis, oldest first."""
        result = await self.session.execute(
            select(ThesisCatalyst)
            .where(ThesisCatalyst.thesis_id == thesis_id)
            .where(ThesisCatalyst.methodology_version == THESIS_METHODOLOGY_VERSION)
            .order_by(ThesisCatalyst.created_at)
            .execution_options(populate_existing=True)
        )
        return result.scalars().all()

    async def replace_catalysts(
        self,
        thesis_id: uuid.UUID,
        rows: list[dict[str, Any]],
    ) -> Sequence[ThesisCatalyst]:
        """Replace the catalyst set on re-assess (ledger keeps the history)."""
        existing = await self.list_catalysts(thesis_id)
        for row in existing:
            await self.session.delete(row)
        await self.session.flush()
        out: list[ThesisCatalyst] = []
        for spec in rows:
            out.append(
                await self.add_catalyst(
                    thesis_id=thesis_id,
                    event=str(spec["event"]),
                    date_from=spec.get("date_from"),
                    date_to=spec.get("date_to"),
                    window=spec.get("window"),
                    variable=spec.get("variable"),
                    expectation=spec.get("expectation"),
                    outcome=str(spec.get("outcome", "Pending")),
                    provenance=str(spec["provenance"]),
                    label=str(spec.get("label", "Tentative")),
                )
            )
        return out
