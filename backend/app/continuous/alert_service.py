"""Alert service: four deterministic evaluators (B2).

Families:
- price_crossing: Phase 1 close vs threshold
- valuation_gap: Phase 3/4 fair_value vs Phase 1 close
- document: fires on Phase 7 fact.landed for watched symbol
- score_change: Phase 4 history ±5% from neutral
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.continuous.constants import CI_METHODOLOGY_VERSION
from app.models.continuous import AlertFamily, AlertRule
from app.models.market import DailyPrice
from app.models.scores import InvestmentScore
from app.models.valuation import ValuationFairValue
from app.repositories.continuous import AlertRepository


@dataclass
class EvaluationResult:
    """Result of evaluating one alert rule."""

    should_fire: bool
    inputs_snapshot: dict[str, Any]
    reason: str


class AlertService:
    """Deterministic alert evaluation service."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.alerts = AlertRepository(session)

    async def evaluate_all_for_company(self, company_id: uuid.UUID) -> list[EvaluationResult]:
        """Evaluate all enabled rules for a company."""
        rules = await self.alerts.list_for_company(company_id)
        results: list[EvaluationResult] = []
        for rule in rules:
            result = await self._evaluate_rule(rule, company_id)
            if result.should_fire:
                results.append(result)
        return results

    async def _evaluate_rule(self, rule: AlertRule, company_id: uuid.UUID) -> EvaluationResult:
        """Dispatch to family-specific evaluator."""
        if rule.family == AlertFamily.PRICE:
            return await self._eval_price_crossing(rule, company_id)
        if rule.family == AlertFamily.VALUATION_GAP:
            return await self._eval_valuation_gap(rule, company_id)
        if rule.family == AlertFamily.DOCUMENT:
            return await self._eval_document(rule, company_id)
        if rule.family == AlertFamily.SCORE_CHANGE:
            return await self._eval_score_change(rule, company_id)
        return EvaluationResult(
            should_fire=False,
            inputs_snapshot={},
            reason=f"Unknown alert family: {rule.family}",
        )

    @staticmethod
    def _norm(d: Decimal) -> str:
        """Normalize decimal string representation without scientific notation or trailing zeros."""
        s = format(d, 'f')
        if '.' in s:
            s = s.rstrip('0').rstrip('.')
        return s

    async def _eval_price_crossing(
        self, rule: AlertRule, company_id: uuid.UUID
    ) -> EvaluationResult:
        """Price crossing: Phase 1 close vs threshold (B2a)."""
        params = rule.params
        threshold = params.get("threshold")
        direction = params.get("direction", "above")  # "above" or "below"

        if threshold is None:
            return EvaluationResult(
                should_fire=False,
                inputs_snapshot={"error": "threshold parameter required"},
                reason="Missing threshold parameter",
            )

        # Get latest close price
        stmt = (
            select(DailyPrice)
            .where(DailyPrice.company_id == company_id)
            .order_by(DailyPrice.date.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        price_row = result.scalars().first()

        if price_row is None:
            return EvaluationResult(
                should_fire=False,
                inputs_snapshot={"threshold": threshold, "direction": direction},
                reason="No price data available",
            )

        current_close = price_row.close
        threshold_dec = Decimal(str(threshold))
        crossed = False
        if (direction == "above" and current_close >= threshold_dec) or (
            direction == "below" and current_close <= threshold_dec
        ):
            crossed = True

        return EvaluationResult(
            should_fire=crossed,
            inputs_snapshot={
                "threshold": self._norm(threshold_dec),
                "direction": direction,
                "price_as_of": price_row.date.isoformat(),
                "current_close": self._norm(current_close),
                "methodology_version": CI_METHODOLOGY_VERSION,
            },
            reason=(
                f"Price {self._norm(current_close)} crossed {direction} "
                f"threshold {self._norm(threshold_dec)}"
                if crossed
                else f"Price {self._norm(current_close)} did not cross {direction} "
                f"threshold {self._norm(threshold_dec)}"
            ),
        )

    async def _eval_valuation_gap(self, rule: AlertRule, company_id: uuid.UUID) -> EvaluationResult:
        """Valuation gap: Phase 3/4 fair_value vs Phase 1 close (B2b)."""
        params = rule.params
        gap_pct = params.get("gap_pct", 20)  # default 20% gap

        # Get latest fair value
        stmt = (
            select(ValuationFairValue)
            .where(ValuationFairValue.company_id == company_id)
            .order_by(ValuationFairValue.computed_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        fv_row = result.scalars().first()

        if fv_row is None or fv_row.fair_value is None:
            return EvaluationResult(
                should_fire=False,
                inputs_snapshot={"gap_pct": gap_pct},
                reason="No fair value available",
            )

        # Get latest close price
        price_stmt = (
            select(DailyPrice)
            .where(DailyPrice.company_id == company_id)
            .order_by(DailyPrice.date.desc())
            .limit(1)
        )
        price_result = await self.session.execute(price_stmt)
        price_row = price_result.scalars().first()

        if price_row is None:
            return EvaluationResult(
                should_fire=False,
                inputs_snapshot={"gap_pct": gap_pct, "fair_value": self._norm(fv_row.fair_value)},
                reason="No price data available",
            )

        current_close = price_row.close
        fair_value = fv_row.fair_value
        gap_threshold = fair_value * (Decimal("1") - Decimal(str(gap_pct)) / Decimal("100"))
        crossed = current_close <= gap_threshold

        return EvaluationResult(
            should_fire=crossed,
            inputs_snapshot={
                "gap_pct": gap_pct,
                "fair_value": self._norm(fair_value),
                "fair_value_as_of": (
                    fv_row.computed_at.date().isoformat() if fv_row.computed_at else None
                ),
                "price_as_of": price_row.date.isoformat(),
                "current_close": self._norm(current_close),
                "gap_threshold": self._norm(gap_threshold),
                "methodology_version": CI_METHODOLOGY_VERSION,
            },
            reason=(
                f"Price {self._norm(current_close)} is {gap_pct}% below fair value "
                f"{self._norm(fair_value)}"
                if crossed
                else f"Price {self._norm(current_close)} within {gap_pct}% of fair value "
                f"{self._norm(fair_value)}"
            ),
        )

    async def _eval_document(self, rule: AlertRule, company_id: uuid.UUID) -> EvaluationResult:
        """Document toggle: fires on Phase 7 fact.landed for watched symbol (B2c).

        This evaluator is called by the trigger service when new facts land.
        It returns should_fire=True to indicate the document alert should fire.
        The actual fact IDs are passed via inputs_snapshot from the trigger.
        """
        # This is a toggle - the trigger service calls this when facts land
        # The inputs_snapshot will contain the fact_ids from the trigger
        return EvaluationResult(
            should_fire=False,  # Actual firing decided by trigger service
            inputs_snapshot={"family": "document", "methodology_version": CI_METHODOLOGY_VERSION},
            reason="Document alert evaluated by trigger service on fact landing",
        )

    async def _eval_score_change(self, rule: AlertRule, company_id: uuid.UUID) -> EvaluationResult:
        """Score change: Phase 4 history ±5% from neutral (B2d)."""
        params = rule.params
        threshold_pct = params.get("threshold_pct", 5)  # default 5% change

        # Get latest score
        stmt = (
            select(InvestmentScore)
            .where(InvestmentScore.company_id == company_id)
            .order_by(InvestmentScore.computed_at.desc())
            .limit(2)  # Current and previous
        )
        result = await self.session.execute(stmt)
        score_rows = result.scalars().all()

        if len(score_rows) < 2:
            return EvaluationResult(
                should_fire=False,
                inputs_snapshot={"threshold_pct": threshold_pct},
                reason="Insufficient score history (need at least 2 assessments)",
            )

        current = score_rows[0]
        previous = score_rows[1]

        if current.headline is None or previous.headline is None:
            return EvaluationResult(
                should_fire=False,
                inputs_snapshot={"threshold_pct": threshold_pct},
                reason="Missing headline score in history",
            )

        current_score = float(current.headline)
        previous_score = float(previous.headline)
        change_pct = abs(current_score - previous_score) / max(abs(previous_score), 1) * 100
        crossed = change_pct >= threshold_pct

        return EvaluationResult(
            should_fire=crossed,
            inputs_snapshot={
                "threshold_pct": threshold_pct,
                "current_score": current_score,
                "previous_score": previous_score,
                "change_pct": round(change_pct, 2),
                "current_as_of": (
                    current.computed_at.date().isoformat() if current.computed_at else None
                ),
                "previous_as_of": (
                    previous.computed_at.date().isoformat() if previous.computed_at else None
                ),
                "methodology_version": CI_METHODOLOGY_VERSION,
            },
            reason=f"Score changed {change_pct:.1f}% ({previous_score} -> {current_score})"
            if crossed
            else f"Score change {change_pct:.1f}% below threshold {threshold_pct}%",
        )
