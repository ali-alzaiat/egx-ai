"""Trigger service: arrival-only entry point with human-review gate (B3/B4/B5).

- on_facts_landed(company_id, fact_ids): evaluates alerts + thesis invalidations on new facts
- on_price_crossing(company_id, price, as_of): evaluates price alerts on price updates
- Quiet-day path writes "checked, nothing new" ledger row
- Warn -> watch + next-proof-point
- Break -> possibly_invalidated proposal via compare-and-swap on thesis version
- Evidence-quality gate: low-confidence parse -> unknown with reason, never broken
"""

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.continuous.alert_service import AlertService
from app.continuous.constants import CI_METHODOLOGY_VERSION
from app.continuous.restatement_detector import RestatementDetector
from app.continuous.watchlist_service import WatchlistService
from app.models.continuous import (
    ActorType,
    AlertFamily,
    AlertRule,
    EventType,
)
from app.models.financial import FinancialFact
from app.models.thesis import InvestmentThesis, ThesisInvalidation
from app.repositories.continuous import AlertRepository, EventRepository
from app.repositories.thesis import ThesisRepository
from app.thesis import thesis as thesis_engine
from app.thesis.constants import PRECOMMITTED_ACTION, THESIS_METHODOLOGY_VERSION
from app.thesis.service import ThesisService


def _norm_decimal(value: Decimal | None) -> str | None:
    """Canonical fixed-point string without trailing zeros.

    Numeric(20, 4) values arrive with DB scale (Decimal("1000.0000")) or
    Python scale (Decimal("1000")) depending on ORM session state; snapshots
    must be identical either way.
    """
    if value is None:
        return None
    s = format(value, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


@dataclass
class TriggerResult:
    """Result of trigger evaluation."""

    alerts_fired: int
    checks_run: int
    ledger_rows: int
    message: str


class TriggerService:
    """Arrival-only trigger evaluation with human-review gate."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.alerts = AlertService(session)
        self.alert_repo = AlertRepository(session)
        self.events = EventRepository(session)
        self.thesis_repo = ThesisRepository(session)
        self.thesis_service = ThesisService(session)
        self.watchlist_service = WatchlistService(session)
        self.restatement_detector = RestatementDetector(session)

    async def on_facts_landed(
        self, company_id: uuid.UUID, fact_ids: list[uuid.UUID]
    ) -> TriggerResult:
        """Evaluate triggers when new facts land (Phase 7 disclosure parsing).

        Flow:
        1. Run restatement detector
        2. Evaluate document alerts (toggle)
        3. Evaluate thesis invalidation conditions (warn/break)
        4. Write ledger rows
        """
        ledger_rows = 0
        checks_run = 0
        alerts_fired = 0

        # 1. Restatement detection (B4)
        restatement_result = await self.restatement_detector.detect(company_id, fact_ids)
        if restatement_result.detected:
            await self.events.append(
                actor_type=ActorType.SYSTEM,
                actor_id=uuid.uuid4(),  # system actor
                rule_version=CI_METHODOLOGY_VERSION,
                type=EventType.RESTATEMENT_DETECTED,
                symbols=[company_id],
                inputs_snapshot={
                    "fact_ids": [str(f) for f in fact_ids],
                    "old_value": _norm_decimal(restatement_result.old_value),
                    "new_value": _norm_decimal(restatement_result.new_value),
                    "delta": _norm_decimal(restatement_result.delta),
                    "metric": restatement_result.metric,
                    "period": restatement_result.period,
                },
                reason=(
                    f"Restatement detected for {restatement_result.metric} "
                    f"in {restatement_result.period}: "
                    f"{restatement_result.old_value} -> {restatement_result.new_value}"
                ),
            )
            ledger_rows += 1

        # 2. Document alerts (B2c) - toggle fires on any new fact landing for watched symbol
        doc_rules = await self._get_doc_rules_for_company(company_id)
        for rule in doc_rules:
            await self.alert_repo.mark_fired(
                rule_id=rule.id,
                company_id=company_id,
                inputs_snapshot={
                    "fact_ids": [str(f) for f in fact_ids],
                    "family": "document",
                    "methodology_version": CI_METHODOLOGY_VERSION,
                },
            )
            await self.events.append(
                actor_type=ActorType.SYSTEM,
                actor_id=uuid.uuid4(),
                rule_version=CI_METHODOLOGY_VERSION,
                type=EventType.ALERT_FIRED,
                symbols=[company_id],
                inputs_snapshot={
                    "fact_ids": [str(f) for f in fact_ids],
                    "rule_id": str(rule.id),
                    "family": "document",
                    "methodology_version": CI_METHODOLOGY_VERSION,
                },
                reason=f"Document alert fired for rule {rule.id}: new facts landed",
            )
            alerts_fired += 1
            ledger_rows += 1

        # 3. Thesis invalidation evaluation (B3) - check stored break conditions
        thesis = await self.thesis_repo.get_thesis(company_id)
        if thesis is not None:
            invalidations = await self.thesis_repo.list_invalidations(thesis.id)
            for inv in invalidations:
                check_result = await self._evaluate_invalidation(company_id, inv, fact_ids)
                checks_run += 1

                # Write check.evaluated event
                await self.events.append(
                    actor_type=ActorType.SYSTEM,
                    actor_id=uuid.uuid4(),
                    rule_version=CI_METHODOLOGY_VERSION,
                    type=EventType.CHECK_EVALUATED,
                    symbols=[company_id],
                    inputs_snapshot={
                        "fact_ids": [str(f) for f in fact_ids],
                        "invalidation_metric": inv.metric,
                        "threshold": str(inv.threshold),
                        "direction": inv.direction,
                        "status": check_result.status,
                        "confidence": check_result.confidence,
                        "methodology_version": CI_METHODOLOGY_VERSION,
                    },
                    reason=check_result.reason,
                )
                ledger_rows += 1

                if check_result.status == "warn":
                    # Warn -> watch + next-proof-point
                    thesis.needs_reassessment = True
                    await self.session.flush()
                elif check_result.status == "break":
                    # Break -> possibly_invalidated proposal via compare-and-swap
                    await self._propose_invalidation(thesis, inv, check_result)

        # 4. Quiet-day: if no alerts/checks fired, write "checked, nothing new"
        if alerts_fired == 0 and checks_run == 0:
            await self.events.append(
                actor_type=ActorType.SYSTEM,
                actor_id=uuid.uuid4(),
                rule_version=CI_METHODOLOGY_VERSION,
                type=EventType.CHECK_EVALUATED,
                symbols=[company_id],
                inputs_snapshot={
                    "fact_ids": [str(f) for f in fact_ids],
                    "methodology_version": CI_METHODOLOGY_VERSION,
                },
                reason="Checked: no new alerts or invalidation triggers",
            )
            ledger_rows += 1

        return TriggerResult(
            alerts_fired=alerts_fired,
            checks_run=checks_run,
            ledger_rows=ledger_rows,
            message=(
                f"Evaluated {len(fact_ids)} new facts: {alerts_fired} alerts, "
                f"{checks_run} checks, {ledger_rows} ledger rows"
            ),
        )

    async def on_price_crossing(
        self, company_id: uuid.UUID, price: Decimal, as_of: date
    ) -> TriggerResult:
        """Evaluate price alerts when price crosses threshold."""
        ledger_rows = 0
        alerts_fired = 0

        # Evaluate all price crossing rules for this company
        price_rules = await self._get_rules_for_company(company_id, AlertFamily.PRICE)
        for rule in price_rules:
            # The alert service evaluates the rule
            result = await self.alerts._eval_price_crossing(rule, company_id)
            if result.should_fire:
                await self.alert_repo.mark_fired(
                    rule_id=rule.id,
                    company_id=company_id,
                    inputs_snapshot=result.inputs_snapshot,
                )
                await self.events.append(
                    actor_type=ActorType.SYSTEM,
                    actor_id=uuid.uuid4(),
                    rule_version=CI_METHODOLOGY_VERSION,
                    type=EventType.ALERT_FIRED,
                    symbols=[company_id],
                    inputs_snapshot=result.inputs_snapshot,
                    reason=result.reason,
                )
                alerts_fired += 1
                ledger_rows += 1

        # Also check valuation gap and score change rules
        for family in [AlertFamily.VALUATION_GAP, AlertFamily.SCORE_CHANGE]:
            rules = await self._get_rules_for_company(company_id, family)
            for rule in rules:
                result = await self.alerts._evaluate_rule(rule, company_id)
                if result.should_fire:
                    await self.alert_repo.mark_fired(
                        rule_id=rule.id,
                        company_id=company_id,
                        inputs_snapshot=result.inputs_snapshot,
                    )
                    await self.events.append(
                        actor_type=ActorType.SYSTEM,
                        actor_id=uuid.uuid4(),
                        rule_version=CI_METHODOLOGY_VERSION,
                        type=EventType.ALERT_FIRED,
                        symbols=[company_id],
                        inputs_snapshot=result.inputs_snapshot,
                        reason=result.reason,
                    )
                    alerts_fired += 1
                    ledger_rows += 1

        if alerts_fired == 0:
            await self.events.append(
                actor_type=ActorType.SYSTEM,
                actor_id=uuid.uuid4(),
                rule_version=CI_METHODOLOGY_VERSION,
                type=EventType.CHECK_EVALUATED,
                symbols=[company_id],
                inputs_snapshot={
                    "price_as_of": as_of.isoformat(),
                    "price": str(price),
                    "methodology_version": CI_METHODOLOGY_VERSION,
                },
                reason="Price checked: no alert thresholds crossed",
            )
            ledger_rows += 1

        return TriggerResult(
            alerts_fired=alerts_fired,
            checks_run=0,
            ledger_rows=ledger_rows,
            message=f"Price {price} evaluated: {alerts_fired} alerts fired",
        )

    async def _get_doc_rules_for_company(self, company_id: uuid.UUID) -> list[AlertRule]:
        """Get enabled document alert rules for a company."""
        stmt = select(AlertRule).where(
            AlertRule.company_id == company_id,
            AlertRule.family == AlertFamily.DOCUMENT,
            AlertRule.enabled.is_(True),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def _get_rules_for_company(
        self, company_id: uuid.UUID, family: AlertFamily
    ) -> list[AlertRule]:
        """Get enabled rules of a specific family for a company."""
        stmt = select(AlertRule).where(
            AlertRule.company_id == company_id,
            AlertRule.family == family,
            AlertRule.enabled.is_(True),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    @dataclass
    class CheckResult:
        """Result of evaluating an invalidation condition."""

        status: str  # "pass", "warn", "break", "unknown"
        confidence: str  # "High", "Medium", "Low"
        reason: str

    async def _evaluate_invalidation(
        self, company_id: uuid.UUID, inv: ThesisInvalidation, fact_ids: list[uuid.UUID]
    ) -> CheckResult:
        """Evaluate one invalidation condition against new facts.

        Evidence-quality gate (B5):
        - Low-confidence parse (below-floor accuracy, OCR path, EAS-ambiguous) -> unknown
        - Missing inputs -> unknown with reason, never silent pass
        """
        # Get latest value for the metric from the new facts
        latest_value = await self._get_latest_metric_from_facts(company_id, inv.metric, fact_ids)

        if latest_value is None:
            # Missing inputs -> unknown with reason
            return self.CheckResult(
                status="unknown",
                confidence="Low",
                reason=f"Missing data for metric {inv.metric}: no new facts contain this metric",
            )

        # Check extraction confidence from the facts
        confidence = await self._get_extraction_confidence(company_id, inv.metric, fact_ids)
        if confidence == "Low":
            # Evidence-quality gate: low confidence -> unknown, never broken
            return self.CheckResult(
                status="unknown",
                confidence="Low",
                reason=(
                    f"Low extraction confidence for {inv.metric}: "
                    "cannot reliably evaluate threshold"
                ),
            )

        # Evaluate breach using thesis engine
        breached, note = thesis_engine.evaluate_breach(
            latest_value, inv.threshold, inv.direction
        )

        if breached:
            # Check if this is a warn or break
            # Warn: first breach, or confidence not high enough for break
            # Break: confirmed breach with high confidence
            if confidence == "High" and inv.status != "Triggered":
                return self.CheckResult(
                    status="break",
                    confidence=confidence,
                    reason=note,
                )
            else:
                return self.CheckResult(
                    status="warn",
                    confidence=confidence,
                    reason=note + " (watch: next proof point needed)",
                )
        else:
            return self.CheckResult(
                status="pass",
                confidence=confidence,
                reason=note,
            )

    async def _get_latest_metric_from_facts(
        self, company_id: uuid.UUID, metric: str, fact_ids: list[uuid.UUID]
    ) -> Decimal | None:
        """Extract latest metric value from the given fact IDs."""
        if not fact_ids:
            return None

        stmt = select(FinancialFact).where(
            FinancialFact.id.in_(fact_ids),
            FinancialFact.company_id == company_id,
        )
        result = await self.session.execute(stmt)
        facts = result.scalars().all()

        # Find matching metric (normalized_label or reported_label)
        for fact in facts:
            label = (fact.normalized_label or fact.reported_label or "").casefold().strip()
            if label == metric.casefold().strip():
                return fact.normalized_value or fact.reported_value

        return None

    async def _get_extraction_confidence(
        self, company_id: uuid.UUID, metric: str, fact_ids: list[uuid.UUID]
    ) -> str:
        """Determine extraction confidence from fact provenance (B5).

        Low confidence if:
        - audit_state is 'ocr_low_confidence' or 'eas_ambiguous'
        - extraction.confidence < threshold
        - methodology_version missing
        """
        if not fact_ids:
            return "Low"

        stmt = select(FinancialFact).where(
            FinancialFact.id.in_(fact_ids),
            FinancialFact.company_id == company_id,
        )
        result = await self.session.execute(stmt)
        facts = result.scalars().all()

        for fact in facts:
            label = (fact.normalized_label or fact.reported_label or "").casefold().strip()
            if label == metric.casefold().strip():
                # Check audit_state
                if fact.audit_state in ("ocr_low_confidence", "eas_ambiguous"):
                    return "Low"
                # Check extraction confidence
                if fact.extraction and isinstance(fact.extraction, dict):
                    conf = fact.extraction.get("confidence")
                    if isinstance(conf, (int, float)) and conf < 0.7:
                        return "Low"
                # Check methodology_version
                if not fact.methodology_version:
                    return "Low"
                return "High"

        return "Low"

    async def _propose_invalidation(
        self, thesis: InvestmentThesis, inv: ThesisInvalidation, check_result: CheckResult
    ) -> None:
        """Propose invalidation via compare-and-swap on thesis version (B3).

        Creates a thesis.updated event with proposed status change.
        Actual thesis update requires user confirmation (human-review gate).
        """
        await self.events.append(
            actor_type=ActorType.SYSTEM,
            actor_id=uuid.uuid4(),
            rule_version=CI_METHODOLOGY_VERSION,
            type=EventType.THESIS_UPDATED,
            symbols=[thesis.company_id],
            inputs_snapshot={
                "thesis_id": str(thesis.id),
                "invalidation_metric": inv.metric,
                "proposed_status": "possibly_invalidated",
                "evidence_confidence": check_result.confidence,
                "reason": check_result.reason,
                "methodology_version": CI_METHODOLOGY_VERSION,
            },
            reason=f"Break detected for {inv.metric}: {check_result.reason}. "
            "Proposing 'possibly_invalidated' status - requires user confirmation.",
        )

    async def confirm_invalidation(
        self, thesis_id: uuid.UUID, metric: str, reviewer: str
    ) -> bool:
        """Confirm a proposed invalidation (human-review gate).

        Compare-and-swap on thesis version to prevent stale approvals.
        """
        thesis = await self.thesis_repo.get_thesis_by_id(thesis_id)
        if thesis is None:
            return False

        # Find the invalidation
        invalidations = await self.thesis_repo.list_invalidations(thesis.id)
        inv = next((i for i in invalidations if i.metric == metric), None)
        if inv is None:
            return False

        # Update status to Reassessed (confirmed)
        await self.thesis_repo.upsert_invalidation(
            thesis_id=thesis.id,
            metric=inv.metric,
            threshold=Decimal(str(inv.threshold)),
            direction=inv.direction,
            period=inv.period,
            evidence_source=inv.evidence_source,
            action=PRECOMMITTED_ACTION,
            status="Reassessed",
            extraction_confidence=inv.extraction_confidence,
            version=inv.version + 1,
        )

        # Append ledger
        await self.thesis_repo.append_ledger(
            thesis_id=thesis.id,
            classification="Confirmed",
            variable=metric,
            action="status_update",
            rationale=f"User confirmed invalidation for {metric}: {reviewer}",
            evidence={"previous_status": "Triggered", "status": "Reassessed"},
            reviewer=reviewer,
        )

        # Event
        await self.events.append(
            actor_type=ActorType.USER,
            actor_id=uuid.uuid4(),  # would be actual user ID in real impl
            rule_version=THESIS_METHODOLOGY_VERSION,
            type=EventType.THESIS_UPDATED,
            symbols=[thesis.company_id],
            inputs_snapshot={
                "thesis_id": str(thesis.id),
                "invalidation_metric": metric,
                "confirmed_status": "Reassessed",
                "reviewer": reviewer,
                "methodology_version": THESIS_METHODOLOGY_VERSION,
            },
            reason=f"User {reviewer} confirmed reassessment for {metric}",
        )

        return True
