"""Investment-thesis service: I/O, cross-phase composition, persistence.

Consumes Phase-3 weighted fair value + scenarios + sensitivity
(``FairValueService``), Phase-4 score + confidence (``ScoreService``), and
Phase-1 data quality (``DataQualityService``, null when unassessed).

Deterministic throughout: thesis text is a template over stored rows, never
LLM output (rule 6); triggers force documented reassessment, never a sale
(rules 9/10); copy stays hedged (rule 10).
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dataquality.service import DataQualityService
from app.models.thesis import (
    InvestmentThesis,
    ThesisCatalyst,
    ThesisInvalidation,
    ThesisLedger,
)
from app.repositories.company import CompanyRepository
from app.repositories.industry import IndustryRepository
from app.repositories.thesis import ThesisRepository
from app.scores.service import ScoreService
from app.thesis import thesis as engine
from app.thesis.constants import (
    CATALYST_LABELS,
    CATALYST_OUTCOMES,
    INVALIDATION_DIRECTIONS,
    LEDGER_CLASSIFICATIONS,
    MANDATED_EVIDENCE_SOURCES,
    MAX_BULL_BEAR_CASES,
    MAX_HORIZON_YEARS,
    MIN_HORIZON_YEARS,
    PRECOMMITTED_ACTION,
    THESIS_DISCLAIMER,
    THESIS_METHODOLOGY_VERSION,
)
from app.valuation.constants import RANGE_NOTE, VALUATION_METHODOLOGY_VERSION
from app.valuation.service import FairValueInput, FairValueService

_SCENARIO_NAMES = ("bear", "base", "bull")


@dataclass
class AssumptionInput:
    """One labelled assumption; value stays free text, never parsed."""

    metric: str
    value: str | None
    horizon: str | None
    source: str
    author: str


@dataclass
class InvalidationInput:
    """One caller-supplied invalidation condition (action is server-set)."""

    metric: str
    threshold: Decimal
    direction: str
    period: str
    evidence_source: str


@dataclass
class CatalystInput:
    """One caller-supplied catalyst record."""

    event: str
    date_from: date | None
    date_to: date | None
    window: str | None
    variable: str | None
    expectation: str | None
    outcome: str
    provenance: str
    label: str


@dataclass
class AssessInput:
    """Thesis assess input: Phase-3 leg inputs plus thesis rows.

    Leg inputs left out resolve inside Phase-3 (historical metrics, never
    consensus) or degrade to INSUFFICIENT_DATA; the three TIKR inputs double
    as the scenario anchors.
    """

    horizon_years: int
    is_shareholder: bool | None
    fv: FairValueInput
    assumptions: list[AssumptionInput]
    bulls: list[str]
    bears: list[str]
    invalidations: list[InvalidationInput]
    catalysts: list[CatalystInput]


@dataclass
class UpdateInvalidation:
    """A status transition for one stored condition."""

    metric: str
    status: str


@dataclass
class UpdateCatalyst:
    """An outcome update for one stored catalyst."""

    catalyst_id: uuid.UUID
    outcome: str


@dataclass
class UpdateInput:
    """A documented update: rationale is required, everything else optional."""

    rationale: str
    reviewer: str | None
    classification: str
    invalidations: list[UpdateInvalidation]
    catalysts: list[UpdateCatalyst]


def _fail(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail)


class ThesisService:
    """Deterministic investment theses over resolved (never invented) inputs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.companies = CompanyRepository(session)
        self.theses = ThesisRepository(session)
        self.industry = IndustryRepository(session)
        self.data_quality = DataQualityService(session)
        self.fair_values = FairValueService(session)
        self.scores = ScoreService(session)

    async def _latest_decimal(
        self, company_id: uuid.UUID, metric: str
    ) -> Decimal | None:
        """Latest AVAILABLE metric as Decimal in its stored unit, else None."""
        values = await self.industry.latest_metric_values([company_id], metric)
        raw, _unit = values.get(company_id, (None, None))
        if raw is None:
            return None
        try:
            return Decimal(raw)
        except InvalidOperation:
            return None

    def _validate_assess(self, body: AssessInput) -> list[engine.InvalidationSpec]:
        """Reject bad assess input before any write; returns padded specs."""
        if body.horizon_years < MIN_HORIZON_YEARS or body.horizon_years > MAX_HORIZON_YEARS:
            raise _fail(400, "horizon_years must satisfy 1 <= horizon <= 30")
        for label, cases in (("bulls", body.bulls), ("bears", body.bears)):
            if len(cases) > MAX_BULL_BEAR_CASES:
                raise _fail(400, f"At most 3 {label} cases per thesis")
            if any(not c.strip() for c in cases):
                raise _fail(400, f"{label} cases must be non-empty strings")
        for assumption in body.assumptions:
            if not assumption.metric.strip():
                raise _fail(400, "Assumption metric must be non-empty")
            if not assumption.source.strip():
                raise _fail(400, "Assumption source must be a filing citation")
        specs: list[engine.InvalidationSpec] = []
        seen: set[str] = set()
        for spec in body.invalidations:
            if not spec.metric.strip():
                raise _fail(400, "Invalidation metric must be non-empty")
            if spec.metric in seen:
                raise _fail(400, f"Duplicate invalidation metric {spec.metric!r}")
            seen.add(spec.metric)
            if spec.direction not in INVALIDATION_DIRECTIONS:
                raise _fail(400, "Invalidation direction must be 'below' or 'above'")
            if not spec.period.strip():
                raise _fail(400, "Invalidation period must be non-empty")
            if spec.evidence_source not in MANDATED_EVIDENCE_SOURCES:
                raise _fail(
                    400,
                    f"Invalidation evidence_source must be one of "
                    f"{', '.join(MANDATED_EVIDENCE_SOURCES)}",
                )
            specs.append(
                engine.InvalidationSpec(
                    metric=spec.metric,
                    threshold=spec.threshold,
                    direction=spec.direction,
                    period=spec.period,
                    evidence_source=spec.evidence_source,
                )
            )
        try:
            padded = engine.pad_invalidation_specs(specs)
        except ValueError as exc:
            raise _fail(400, str(exc)) from exc
        for catalyst in body.catalysts:
            self._validate_catalyst(catalyst)
        return padded

    def _validate_catalyst(self, catalyst: CatalystInput) -> None:
        if not catalyst.event.strip():
            raise _fail(400, "Catalyst event must be non-empty")
        if catalyst.outcome not in CATALYST_OUTCOMES:
            raise _fail(
                400,
                f"Catalyst outcome must be one of {', '.join(CATALYST_OUTCOMES)}",
            )
        if catalyst.label not in CATALYST_LABELS:
            raise _fail(
                400,
                f"Catalyst label must be one of {', '.join(CATALYST_LABELS)}",
            )
        if not catalyst.provenance.startswith("http"):
            raise _fail(400, "Catalyst provenance must be a source URL")
        try:
            engine.check_catalyst_label(catalyst.event, catalyst.label)
        except ValueError as exc:
            raise _fail(400, str(exc)) from exc

    async def assess(
        self, company_id: uuid.UUID, body: AssessInput
    ) -> dict[str, Any]:
        """Compute, snapshot, and hand-serialize the investment thesis."""
        company = await self.companies.get_by_id(company_id)
        if company is None:
            raise _fail(404, "Company not found")
        specs = self._validate_assess(body)
        as_of = datetime.now(UTC)

        fair = await self.fair_values.fair_value(company_id, body.fv)
        sensitivity = await self._per_scenario_sensitivity(company_id, fair, body.fv)

        dq_fs = await self.data_quality.latest(company_id, "financial_statements")
        dq_ph = await self.data_quality.latest(company_id, "price_history")
        score_payload = await self.scores.latest_payload(company_id)
        score_assessment = score_payload["assessment"]
        confidence = engine.thesis_confidence_for(
            dq_fs.score if dq_fs is not None else None,
            dq_fs.status.value if dq_fs is not None else None,
            score_assessment is not None,
        )

        previous = await self.theses.get_thesis(company_id)
        previous_by_metric: dict[str, ThesisInvalidation] = {}
        if previous is not None:
            for row in await self.theses.list_invalidations(previous.id):
                previous_by_metric[row.metric] = row

        evaluated: list[tuple[engine.InvalidationSpec, str, str, int, bool, bool]] = []
        for spec in specs:
            old = previous_by_metric.get(spec.metric)
            changed = (
                old is None
                or Decimal(old.threshold) != spec.threshold
                or old.direction != spec.direction
                or old.period != spec.period
                or old.evidence_source != spec.evidence_source
            )
            version = 1 if old is None else (old.version + 1 if changed else old.version)
            amended = old is not None and changed
            if old is not None and old.status == "Reassessed" and not changed:
                evaluated.append(
                    (spec, "Reassessed", "Previously reassessed; spec unchanged.",
                     version, False, amended)
                )
                continue
            latest = await self._latest_decimal(company_id, spec.metric)
            breached, note = engine.evaluate_breach(latest, spec.threshold, spec.direction)
            status = "Triggered" if breached else "Active"
            transitioned = breached and (old is None or old.status != "Triggered")
            evaluated.append((spec, status, note, version, transitioned, amended))

        needs_reassessment = any(status == "Triggered" for _, status, _, _, _, _ in evaluated)
        extraction = engine.extraction_confidence_for(
            dq_fs.status.value if dq_fs is not None else None
        )

        dq_payload = {
            "financial_statements": self._dq_payload(dq_fs),
            "price_history": self._dq_payload(dq_ph),
        }
        score_payload_small = self._score_payload(score_assessment)
        scenarios_payload = self._scenarios_payload(fair)
        confidence_payload = {
            "level": confidence.level,
            "required_discount": str(confidence.required_discount),
            "dq_score": confidence.dq_score,
            "dq_status": confidence.dq_status,
            "reason": confidence.reason,
            "methodology_version": THESIS_METHODOLOGY_VERSION,
        }
        assumptions_payload = [
            {
                "metric": a.metric,
                "value": a.value,
                "horizon": a.horizon,
                "source": a.source,
                "author": a.author,
            }
            for a in body.assumptions
        ]
        narrative = engine.render_narrative(
            ticker=company.ticker,
            horizon_years=body.horizon_years,
            is_shareholder=body.is_shareholder,
            fair_value=fair["fair_value"]["value"],
            fair_value_status=fair["fair_value"]["status"],
            fair_value_reason=fair["fair_value"]["reason"],
            fair_value_version=VALUATION_METHODOLOGY_VERSION,
            fair_value_sources=self._source_line(fair),
            assumptions=[
                engine.AssumptionRow(
                    metric=a.metric,
                    value=a.value,
                    horizon=a.horizon,
                    source=a.source,
                    author=a.author,
                )
                for a in body.assumptions
            ],
            bulls=body.bulls,
            bears=body.bears,
            scenarios={
                name: fair["scenarios"].get(name, {}).get("value")
                if isinstance(fair["scenarios"].get(name), dict)
                else None
                for name in _SCENARIO_NAMES
            },
            scenario_statuses={
                name: fair["scenarios"].get(name, {}).get("status", "INSUFFICIENT_DATA")
                if isinstance(fair["scenarios"].get(name), dict)
                else "INSUFFICIENT_DATA"
                for name in _SCENARIO_NAMES
            },
            scenarios_note=str(fair["scenarios"].get("note", RANGE_NOTE)),
            invalidations=[
                engine.InvalidationView(
                    metric=spec.metric,
                    threshold=spec.threshold,
                    direction=spec.direction,
                    period=spec.period,
                    evidence_source=spec.evidence_source,
                    status=status,
                    extraction_confidence=extraction,
                )
                for spec, status, _note, _version, _tr, _am in evaluated
            ],
            catalysts=[
                *engine.skeleton_catalysts(),
                *(
                    engine.CatalystView(
                        event=c.event,
                        window=c.window or self._window(c.date_from, c.date_to),
                        variable=c.variable,
                        expectation=c.expectation,
                        outcome=c.outcome,
                        label=c.label,
                        provenance=c.provenance,
                    )
                    for c in body.catalysts
                ),
            ],
            dq_summary=self._dq_summary(dq_fs, dq_ph, score_assessment),
            confidence_level=confidence.level,
            confidence_reason=confidence.reason,
        )

        fair_value = fair["fair_value"]["value"]
        thesis = await self.theses.upsert_thesis(
            company_id=company.id,
            horizon_years=body.horizon_years,
            is_shareholder=body.is_shareholder,
            fair_value=Decimal(fair_value) if fair_value is not None else None,
            fair_value_status=fair["fair_value"]["status"],
            assumptions=assumptions_payload,
            bulls=body.bulls,
            bears=body.bears,
            scenarios=scenarios_payload,
            sensitivity=sensitivity,
            narrative=narrative,
            confidence=confidence_payload,
            dq=dq_payload,
            score=score_payload_small,
            needs_reassessment=needs_reassessment,
            computed_at=as_of,
        )
        for spec, status, _note, version, _tr, _am in evaluated:
            await self.theses.upsert_invalidation(
                thesis_id=thesis.id,
                metric=spec.metric,
                threshold=spec.threshold,
                direction=spec.direction,
                period=spec.period,
                evidence_source=spec.evidence_source,
                action=PRECOMMITTED_ACTION,
                status=status,
                extraction_confidence=extraction,
                version=version,
            )
        await self.theses.replace_catalysts(
            thesis.id,
            [
                {
                    "event": c.event,
                    "date_from": None,
                    "date_to": None,
                    "window": c.window,
                    "variable": c.variable,
                    "expectation": c.expectation,
                    "outcome": c.outcome,
                    "provenance": c.provenance,
                    "label": c.label,
                }
                for c in engine.skeleton_catalysts()
            ]
            + [
                {
                    "event": c.event,
                    "date_from": c.date_from,
                    "date_to": c.date_to,
                    "window": c.window or self._window(c.date_from, c.date_to),
                    "variable": c.variable,
                    "expectation": c.expectation,
                    "outcome": c.outcome,
                    "provenance": c.provenance,
                    "label": c.label,
                }
                for c in body.catalysts
            ],
        )
        n_triggered = sum(1 for _, s, _, _, tr, _ in evaluated if s == "Triggered")
        await self.theses.append_ledger(
            thesis_id=thesis.id,
            classification="New",
            variable="thesis",
            action="assessed",
            rationale=(
                f"Thesis assessed for {company.ticker}: "
                f"{len(evaluated)} invalidation conditions "
                f"({n_triggered} triggered), "
                f"{len(body.catalysts)} caller catalysts plus skeleton."
            ),
            evidence={"fair_value": fair_value, "needs_reassessment": needs_reassessment},
            reviewer=None,
        )
        for spec, _status, note, version, transitioned, amended in evaluated:
            old = previous_by_metric.get(spec.metric)
            if amended and old is not None:
                await self.theses.append_ledger(
                    thesis_id=thesis.id,
                    classification="New",
                    variable=spec.metric,
                    action="amended",
                    rationale=(
                        f"Invalidation condition amended to version {version}: "
                        f"{spec.metric} {spec.direction} {spec.threshold} "
                        f"over {spec.period} (evidence: {spec.evidence_source})."
                    ),
                    evidence={
                        "previous": {
                            "threshold": str(old.threshold),
                            "direction": old.direction,
                            "period": old.period,
                            "evidence_source": old.evidence_source,
                            "version": old.version,
                        }
                    },
                    reviewer=None,
                )
            if transitioned:
                latest = await self._latest_decimal(company_id, spec.metric)
                await self.theses.append_ledger(
                    thesis_id=thesis.id,
                    classification="Challenged",
                    variable=spec.metric,
                    action=PRECOMMITTED_ACTION,
                    rationale=(
                        f"Threshold firing: {note} Documented reassessment "
                        f"required; never an automatic sale."
                    ),
                    evidence={
                        "latest_value": str(latest) if latest is not None else None,
                        "threshold": str(spec.threshold),
                        "direction": spec.direction,
                        "period": spec.period,
                        "evidence_source": spec.evidence_source,
                    },
                    reviewer=None,
                )
        await self.session.flush()
        return await self._payload_from_rows(thesis, ticker=company.ticker)

    async def _per_scenario_sensitivity(
        self,
        company_id: uuid.UUID,
        base_fair: dict[str, Any],
        base_inputs: FairValueInput,
    ) -> dict[str, Any]:
        """1-D sensitivity per scenario by re-centering the Phase-3 run.

        Each scenario's labelled TIKR inputs become the base of a fresh
        Phase-3 computation whose own ±discount/±growth sensitivity rows then
        describe that scenario. Missing scenario inputs degrade to
        INSUFFICIENT_DATA instead of guessed curves. These extra runs refresh
        the Phase-3 snapshot (last-writer-wins); the thesis stores only the
        per-scenario rows.
        """
        out: dict[str, Any] = {"methodology_version": THESIS_METHODOLOGY_VERSION}
        scenarios = base_fair.get("scenarios")
        if not isinstance(scenarios, dict):
            scenarios = {}
        for name in _SCENARIO_NAMES:
            entry = scenarios.get(name)
            if not isinstance(entry, dict) or not isinstance(entry.get("inputs"), dict):
                reason = (
                    entry.get("reason")
                    if isinstance(entry, dict) and entry.get("reason")
                    else "Scenario inputs are unavailable; nothing is assumed."
                )
                out[name] = {"status": "INSUFFICIENT_DATA", "reason": reason, "rows": []}
                continue
            try:
                centered = base_inputs._replace(
                    revenue_growth=Decimal(str(entry["inputs"]["revenue_growth"])),
                    operating_margin=Decimal(str(entry["inputs"]["operating_margin"])),
                    exit_multiple=Decimal(str(entry["inputs"]["exit_multiple"])),
                )
            except (KeyError, InvalidOperation, TypeError, ValueError):
                out[name] = {
                    "status": "INSUFFICIENT_DATA",
                    "reason": "Scenario inputs are unavailable; nothing is assumed.",
                    "rows": [],
                }
                continue
            rerun = await self.fair_values.fair_value(company_id, centered)
            rows = rerun.get("sensitivity")
            rows = rows if isinstance(rows, list) else []
            if not rows:
                out[name] = {
                    "status": "INSUFFICIENT_DATA",
                    "reason": (
                        "Sensitivity needs a discount rate and growth input; "
                        "nothing is assumed."
                    ),
                    "rows": [],
                }
            else:
                out[name] = {"status": "AVAILABLE", "reason": None, "rows": rows}
        return out

    async def latest_payload(self, company_id: uuid.UUID) -> dict[str, Any]:
        """Latest thesis under the current methodology; null when unassessed."""
        company = await self.companies.get_by_id(company_id)
        if company is None:
            raise _fail(404, "Company not found")
        thesis = await self.theses.get_thesis(company_id)
        return {
            "company_id": str(company.id),
            "ticker": company.ticker,
            "assessment": (
                await self._payload_from_rows(thesis, ticker=company.ticker)
                if thesis is not None
                else None
            ),
            "methodology_version": THESIS_METHODOLOGY_VERSION,
            "disclaimer": THESIS_DISCLAIMER,
        }

    async def update(
        self, company_id: uuid.UUID, body: UpdateInput
    ) -> dict[str, Any]:
        """Apply a documented update: status/outcome changes + ledger rows."""
        company = await self.companies.get_by_id(company_id)
        if company is None:
            raise _fail(404, "Company not found")
        thesis = await self.theses.get_thesis(company_id)
        if thesis is None:
            raise _fail(404, "No thesis on file — assess first")
        if not body.rationale.strip():
            raise _fail(400, "Update rationale is required: reassessment must be documented")
        if body.classification not in LEDGER_CLASSIFICATIONS:
            raise _fail(
                400,
                f"Ledger classification must be one of {', '.join(LEDGER_CLASSIFICATIONS)}",
            )
        try:
            engine.validate_statuses(tuple(u.status for u in body.invalidations))
        except ValueError as exc:
            raise _fail(400, str(exc)) from exc
        for outcome in [u.outcome for u in body.catalysts]:
            if outcome not in CATALYST_OUTCOMES:
                raise _fail(
                    400,
                    f"Catalyst outcome must be one of {', '.join(CATALYST_OUTCOMES)}",
                )

        rows = await self.theses.list_invalidations(thesis.id)
        by_metric = {row.metric: row for row in rows}
        for change in body.invalidations:
            row = by_metric.get(change.metric)
            if row is None:
                raise _fail(400, f"Unknown invalidation metric {change.metric!r}")
            await self.theses.upsert_invalidation(
                thesis_id=thesis.id,
                metric=row.metric,
                threshold=Decimal(row.threshold),
                direction=row.direction,
                period=row.period,
                evidence_source=row.evidence_source,
                action=row.action,
                status=change.status,
                extraction_confidence=row.extraction_confidence,
                version=row.version,
            )
            await self.theses.append_ledger(
                thesis_id=thesis.id,
                classification=body.classification,
                variable=change.metric,
                action="status_update",
                rationale=f"{row.metric} marked {change.status}: {body.rationale}",
                evidence={"previous_status": row.status, "status": change.status},
                reviewer=body.reviewer,
            )

        catalysts = await self.theses.list_catalysts(thesis.id)
        by_id = {cat.id: cat for cat in catalysts}
        for cat_change in body.catalysts:
            cat = by_id.get(cat_change.catalyst_id)
            if cat is None:
                raise _fail(400, f"Unknown catalyst id {cat_change.catalyst_id}")
            previous_outcome = cat.outcome
            cat.outcome = cat_change.outcome
            await self.session.flush()
            await self.theses.append_ledger(
                thesis_id=thesis.id,
                classification=body.classification,
                variable=cat.event,
                action="catalyst_update",
                rationale=f"Catalyst {cat.event!r} outcome {cat_change.outcome}: {body.rationale}",
                evidence={"previous_outcome": previous_outcome, "outcome": cat_change.outcome},
                reviewer=body.reviewer,
            )

        if not body.invalidations and not body.catalysts:
            await self.theses.append_ledger(
                thesis_id=thesis.id,
                classification=body.classification,
                variable="thesis",
                action="note",
                rationale=body.rationale,
                evidence={},
                reviewer=body.reviewer,
            )

        fresh = await self.theses.list_invalidations(thesis.id)
        thesis.needs_reassessment = any(row.status == "Triggered" for row in fresh)
        stored_catalysts = await self.theses.list_catalysts(thesis.id)
        thesis.narrative = engine.refresh_stored_lines(
            thesis.narrative,
            [
                engine.InvalidationView(
                    metric=row.metric,
                    threshold=Decimal(row.threshold),
                    direction=row.direction,
                    period=row.period,
                    evidence_source=row.evidence_source,
                    status=row.status,
                    extraction_confidence=row.extraction_confidence,
                )
                for row in fresh
            ],
            [
                engine.CatalystView(
                    event=row.event,
                    window=row.window,
                    variable=row.variable,
                    expectation=row.expectation,
                    outcome=row.outcome,
                    label=row.label,
                    provenance=row.provenance,
                )
                for row in stored_catalysts
            ],
        )
        await self.session.flush()
        return await self._payload_from_rows(thesis, ticker=company.ticker)

    def _dq_payload(self, score: Any) -> dict[str, Any] | None:
        if score is None:
            return None
        return {
            "score": score.score,
            "status": score.status.value,
            "as_of": score.as_of.isoformat(),
            "methodology_version": score.methodology_version,
        }

    def _score_payload(self, assessment: dict[str, Any] | None) -> dict[str, Any] | None:
        if assessment is None:
            return None
        return {
            "headline": assessment.get("headline"),
            "confidence": assessment.get("confidence"),
            "profile": assessment.get("profile"),
            "methodology_version": assessment.get("methodology_version"),
        }

    def _scenarios_payload(self, fair: dict[str, Any]) -> dict[str, Any]:
        scenarios = fair.get("scenarios")
        payload = dict(scenarios) if isinstance(scenarios, dict) else {}
        sources = fair.get("input_sources")
        payload["prefill_source"] = {
            key: (sources.get(key) if isinstance(sources, dict) else None)
            for key in ("revenue_growth", "operating_margin", "exit_multiple")
        }
        payload["methodology_version"] = VALUATION_METHODOLOGY_VERSION
        return payload

    def _source_line(self, fair: dict[str, Any]) -> str:
        sources = fair.get("input_sources")
        if not isinstance(sources, dict):
            return "sources unstated"
        parts = [f"{key} via {value}" for key, value in sources.items() if value]
        if not parts:
            return "no inputs resolved; INSUFFICIENT_DATA"
        return "inputs " + ", ".join(parts)

    def _dq_summary(
        self,
        dq_fs: Any,
        dq_ph: Any,
        score_assessment: dict[str, Any] | None,
    ) -> str:
        fs = (
            f"financial-statements {dq_fs.score:.1f}/{dq_fs.status.value} "
            f"as of {dq_fs.as_of.isoformat()}"
            if dq_fs is not None
            else "financial-statements unassessed"
        )
        ph = (
            f"price-history {dq_ph.score:.1f}/{dq_ph.status.value} "
            f"as of {dq_ph.as_of.isoformat()}"
            if dq_ph is not None
            else "price-history unassessed"
        )
        if score_assessment is None:
            score = "investment score unassessed"
        else:
            headline = score_assessment.get("headline", {})
            score = f"investment score {headline.get('value')} [{headline.get('status')}]"
        return f"{fs}; {ph}; {score}"

    @staticmethod
    def _window(date_from: date | None, date_to: date | None) -> str | None:
        if date_from is None and date_to is None:
            return None
        start = date_from.isoformat() if date_from is not None else "open"
        end = date_to.isoformat() if date_to is not None else "open"
        return f"{start}..{end}"

    async def _payload_from_rows(
        self, thesis: InvestmentThesis, *, ticker: str
    ) -> dict[str, Any]:
        invalidations = await self.theses.list_invalidations(thesis.id)
        ledger = await self.theses.list_ledger(thesis.id)
        catalysts = await self.theses.list_catalysts(thesis.id)
        return {
            "company_id": str(thesis.company_id),
            "ticker": ticker,
            "as_of": thesis.computed_at.date().isoformat(),
            "computed_at": thesis.computed_at.isoformat(),
            "methodology_version": thesis.methodology_version,
            "valuation_methodology_version": VALUATION_METHODOLOGY_VERSION,
            "header": {
                "fair_value": {
                    "value": str(thesis.fair_value)
                    if thesis.fair_value is not None
                    else None,
                    "status": thesis.fair_value_status,
                },
                "horizon_years": thesis.horizon_years,
                "is_shareholder": thesis.is_shareholder,
            },
            "narrative": thesis.narrative,
            "assumptions": thesis.assumptions if isinstance(thesis.assumptions, list) else [],
            "bulls": thesis.bulls if isinstance(thesis.bulls, list) else [],
            "bears": thesis.bears if isinstance(thesis.bears, list) else [],
            "scenarios": thesis.scenarios if isinstance(thesis.scenarios, dict) else {},
            "sensitivity": thesis.sensitivity
            if isinstance(thesis.sensitivity, dict)
            else {},
            "invalidations": [
                {
                    "metric": row.metric,
                    "threshold": str(row.threshold),
                    "direction": row.direction,
                    "period": row.period,
                    "evidence_source": row.evidence_source,
                    "action": row.action,
                    "status": row.status,
                    "extraction_confidence": row.extraction_confidence,
                    "version": row.version,
                    "methodology_version": row.methodology_version,
                }
                for row in invalidations
            ],
            "ledger": [
                self._ledger_payload(row) for row in ledger
            ],
            "catalysts": [
                self._catalyst_payload(row) for row in catalysts
            ],
            "confidence": thesis.confidence
            if isinstance(thesis.confidence, dict)
            else {},
            "dq": thesis.dq if isinstance(thesis.dq, dict) else {},
            "score": thesis.score,
            "needs_reassessment": thesis.needs_reassessment,
            "disclaimer": THESIS_DISCLAIMER,
        }

    @staticmethod
    def _ledger_payload(row: ThesisLedger) -> dict[str, Any]:
        return {
            "classification": row.classification,
            "variable": row.variable,
            "action": row.action,
            "rationale": row.rationale,
            "evidence": row.evidence if isinstance(row.evidence, dict) else {},
            "reviewer": row.reviewer,
            "created_at": row.created_at.isoformat() if row.created_at is not None else None,
            "methodology_version": row.methodology_version,
        }

    @staticmethod
    def _catalyst_payload(row: ThesisCatalyst) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "event": row.event,
            "date_from": row.date_from.isoformat() if row.date_from is not None else None,
            "date_to": row.date_to.isoformat() if row.date_to is not None else None,
            "window": row.window,
            "variable": row.variable,
            "expectation": row.expectation,
            "outcome": row.outcome,
            "provenance": row.provenance,
            "label": row.label,
            "methodology_version": row.methodology_version,
        }
