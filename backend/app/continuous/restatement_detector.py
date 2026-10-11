"""Restatement detector v1 (B4).

Same-period-different-value across two DisclosureFiling PDFs -> revision candidate
(old/new/delta), restatement.detected event, re-evaluate affected checks.
EAS-gotcha tags excluded. As-reported vs as-knowable kept separate.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.continuous.constants import CI_METHODOLOGY_VERSION
from app.models.disclosure import DisclosureFactDiff
from app.models.financial import FinancialFact, FinancialPeriod


@dataclass
class RestatementResult:
    """Result of restatement detection."""

    detected: bool
    metric: str | None = None
    period: str | None = None
    old_value: Decimal | None = None
    new_value: Decimal | None = None
    delta: Decimal | None = None
    prior_fact_id: uuid.UUID | None = None
    current_fact_id: uuid.UUID | None = None
    reason: str = ""


class RestatementDetector:
    """Detect restatements by comparing same-period values across filings."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def detect(
        self, company_id: uuid.UUID, new_fact_ids: list[uuid.UUID]
    ) -> RestatementResult:
        """Detect restatements for newly landed facts.

        Compares new facts against prior facts for the same company/period/metric.
        EAS-gotcha tags are excluded before comparison.
        """
        if not new_fact_ids:
            return RestatementResult(detected=False, reason="No new facts to check")

        # Get new facts with their periods and labels
        stmt = (
            select(FinancialFact)
            .where(FinancialFact.id.in_(new_fact_ids))
            .where(FinancialFact.company_id == company_id)
        )
        result = await self.session.execute(stmt)
        new_facts = result.scalars().all()

        for new_fact in new_facts:
            # Skip EAS-gotcha tagged facts
            if new_fact.eas_tags and self._has_eas_gotcha_tag(new_fact.eas_tags):
                continue

            # Skip low confidence facts (audit_state or extraction.confidence)
            if self._is_low_confidence(new_fact):
                continue

            # Find prior fact for same company, period, and metric
            prior_fact = await self._find_prior_fact(
                company_id=company_id,
                period_id=new_fact.period_id,
                metric_label=new_fact.normalized_label or new_fact.reported_label,
                exclude_fact_id=new_fact.id,
            )

            if prior_fact is None:
                continue

            # Skip if prior fact has EAS-gotcha tags
            if prior_fact.eas_tags and self._has_eas_gotcha_tag(prior_fact.eas_tags):
                continue

            # Compare values (use normalized_value, fall back to reported_value)
            old_val = prior_fact.normalized_value or prior_fact.reported_value
            new_val = new_fact.normalized_value or new_fact.reported_value

            if old_val is None or new_val is None:
                continue

            if old_val != new_val:
                delta = new_val - old_val
                period_str = await self._period_to_string(new_fact.period_id)
                metric_label = new_fact.normalized_label or new_fact.reported_label

                # Record in disclosure_fact_diffs
                await self._record_diff(
                    company_id=company_id,
                    metric=metric_label,
                    prior_fact_id=prior_fact.id,
                    current_fact_id=new_fact.id,
                    prior_value=old_val,
                    current_value=new_val,
                    delta=delta,
                    prior_period=period_str,
                    current_period=period_str,
                )

                # Mark new fact as restated
                new_fact.is_restated = True
                new_fact.supersedes_id = prior_fact.id
                await self.session.flush()

                return RestatementResult(
                    detected=True,
                    metric=metric_label,
                    period=period_str,
                    old_value=old_val,
                    new_value=new_val,
                    delta=delta,
                    prior_fact_id=prior_fact.id,
                    current_fact_id=new_fact.id,
                    reason=(
                        f"Restatement detected: {metric_label} in {period_str} "
                        f"changed from {old_val} to {new_val}"
                    ),
                )

        return RestatementResult(detected=False, reason="No restatements found")

    def _has_eas_gotcha_tag(self, eas_tags: list[str]) -> bool:
        """Check if fact has EAS-gotcha tags that should exclude it from restatement detection."""
        gotcha_tags = {
            "eas_reclassification",
            "eas_policy_change",
            "eas_prior_period_adjustment",
            "eas_estimate_change",
            "eas_presentation_change",
        }
        return any(tag in eas_tags for tag in gotcha_tags)

    def _is_low_confidence(self, fact: FinancialFact) -> bool:
        """Check if fact has low confidence (audit_state or extraction.confidence)."""
        # Check audit_state
        if fact.audit_state in ("ocr_low_confidence", "eas_ambiguous"):
            return True
        # Check extraction confidence
        if fact.extraction and isinstance(fact.extraction, dict):
            conf = fact.extraction.get("confidence")
            if isinstance(conf, (int, float)) and conf < 0.7:
                return True
        return False

    async def _find_prior_fact(
        self,
        company_id: uuid.UUID,
        period_id: uuid.UUID,
        metric_label: str,
        exclude_fact_id: uuid.UUID,
    ) -> FinancialFact | None:
        """Find prior fact for same period and metric."""
        stmt = (
            select(FinancialFact)
            .where(FinancialFact.company_id == company_id)
            .where(FinancialFact.period_id == period_id)
            .where(FinancialFact.id != exclude_fact_id)
            .where(
                (FinancialFact.normalized_label == metric_label)
                | (FinancialFact.reported_label == metric_label)
            )
            .order_by(FinancialFact.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def _period_to_string(self, period_id: uuid.UUID) -> str:
        """Convert period ID to human-readable string."""
        stmt = select(FinancialPeriod).where(FinancialPeriod.id == period_id)
        result = await self.session.execute(stmt)
        period = result.scalars().first()
        if period is None:
            return "unknown"
        if period.period_type.value == "ANNUAL":
            return f"FY{period.fiscal_year}"
        return f"{period.period_type.value} FY{period.fiscal_year}"

    async def _record_diff(
        self,
        company_id: uuid.UUID,
        metric: str,
        prior_fact_id: uuid.UUID | None,
        current_fact_id: uuid.UUID | None,
        prior_value: Decimal,
        current_value: Decimal,
        delta: Decimal,
        prior_period: str,
        current_period: str,
    ) -> None:
        """Record restatement in disclosure_fact_diffs."""
        delta_pct = (delta / prior_value * Decimal("100")) if prior_value != 0 else None

        row = DisclosureFactDiff(
            id=uuid.uuid4(),
            company_id=company_id,
            methodology_version=CI_METHODOLOGY_VERSION,
            kind="restatement",
            metric=metric,
            prior_fact_id=prior_fact_id,
            current_fact_id=current_fact_id,
            prior_value=prior_value,
            current_value=current_value,
            delta=delta,
            delta_pct=delta_pct,
            prior_period=prior_period,
            current_period=current_period,
        )
        self.session.add(row)
        await self.session.flush()
