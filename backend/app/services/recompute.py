"""Recompute service (R43 M2): computed company data, never typed in by users.

Every engine snapshot is tied to a fingerprint of its inputs in
``company_compute_state``. A snapshot is stale when no row exists for the
engine's current methodology version or its stored fingerprint differs from the
one derived from today's inputs — so the first-view hook catches any writer
(vendor CLI, intake, approve/reject, pipeline) without timestamps.

- Inline, not queued: per-company compute is pure Python over a few hundred
  lines and bars. Bulk paths use one session per company and commit per company.
- Concurrency: a transaction-scoped advisory lock per company, then a re-check.
- Atomicity: each engine runs in a SAVEPOINT; a failure is recorded as a
  ``failed`` state (with its fingerprint, so it is not retried on every GET),
  dependents are marked ``upstream failed`` and requests are never 500'd.

CLI (backfill)::

    python -m app.services.recompute --all [--engines metrics,score] [--force]
    python -m app.services.recompute COMI SWDY
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import uuid
from collections.abc import Awaitable, Callable, Collection, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.dataquality.scores import METHODOLOGY_VERSION as DQ_METHODOLOGY_VERSION
from app.models.compute import ComputeState
from app.models.market import Company, DailyPrice
from app.models.statements import FinancialStatementLine
from app.repositories.statements import CalculationStatuses
from app.scores.constants import SCORE_METHODOLOGY_VERSION
from app.screening.methodology import DEFAULT_METHODOLOGY
from app.screening.purification import PURIFICATION_VERSION
from app.statements import bridge
from app.statements.bridge import CompanyStatements, load_company_statements
from app.technical.service import TECHNICAL_METHODOLOGY_VERSION
from app.thesis.constants import THESIS_METHODOLOGY_VERSION
from app.valuation.constants import VALUATION_METHODOLOGY_VERSION

logger = logging.getLogger(__name__)


class Engine(StrEnum):
    DQ_FS = "data_quality_fs"
    DQ_PH = "data_quality_ph"
    METRICS = "metrics"
    SHARIAH = "shariah"
    PURIFICATION = "purification"
    TECHNICAL = "technical"
    FAIR_VALUE = "fair_value"
    SCORE = "score"
    THESIS = "thesis"


class Trigger(StrEnum):
    STATEMENT_IMPORT = "statement_import"
    PRICE_SYNC = "price_sync"
    FIRST_VIEW = "first_view"
    ASSUMPTIONS = "assumptions"
    BACKFILL = "backfill"


ENGINE_ORDER: tuple[Engine, ...] = (
    Engine.DQ_FS,
    Engine.DQ_PH,
    Engine.METRICS,
    Engine.SHARIAH,
    Engine.PURIFICATION,
    Engine.TECHNICAL,
    Engine.FAIR_VALUE,
    Engine.SCORE,
    Engine.THESIS,
)

DEPENDS_ON: dict[Engine, tuple[Engine, ...]] = {
    Engine.DQ_FS: (),
    Engine.DQ_PH: (),
    Engine.METRICS: (),
    Engine.TECHNICAL: (),
    Engine.SHARIAH: (),
    Engine.PURIFICATION: (Engine.SHARIAH,),
    Engine.FAIR_VALUE: (Engine.METRICS, Engine.DQ_FS, Engine.DQ_PH),
    Engine.SCORE: (Engine.METRICS, Engine.FAIR_VALUE, Engine.DQ_FS, Engine.DQ_PH),
    Engine.THESIS: (
        Engine.METRICS, Engine.FAIR_VALUE, Engine.SCORE, Engine.DQ_FS, Engine.DQ_PH,
    ),
}

OWN_INPUTS: dict[Engine, frozenset[str]] = {
    Engine.DQ_FS: frozenset({"statements"}),
    Engine.METRICS: frozenset({"statements"}),
    Engine.DQ_PH: frozenset({"prices"}),
    Engine.TECHNICAL: frozenset({"prices"}),
    Engine.SHARIAH: frozenset({"statements", "company"}),
    Engine.PURIFICATION: frozenset({"statements", "company"}),
    Engine.FAIR_VALUE: frozenset({"statements", "prices", "company", "assumptions"}),
    Engine.SCORE: frozenset({"statements", "prices", "company"}),
    Engine.THESIS: frozenset({"statements", "prices", "company"}),
}


def _metrics_version() -> str:
    from app.metrics.service import METRICS_INPUT_VERSION

    return METRICS_INPUT_VERSION


ENGINE_VERSION: dict[Engine, str] = {
    Engine.DQ_FS: DQ_METHODOLOGY_VERSION,
    Engine.DQ_PH: DQ_METHODOLOGY_VERSION,
    Engine.METRICS: _metrics_version(),
    Engine.SHARIAH: DEFAULT_METHODOLOGY.version.value,
    Engine.PURIFICATION: f"{DEFAULT_METHODOLOGY.version.value}+{PURIFICATION_VERSION}",
    Engine.TECHNICAL: TECHNICAL_METHODOLOGY_VERSION,
    Engine.FAIR_VALUE: VALUATION_METHODOLOGY_VERSION,
    Engine.SCORE: SCORE_METHODOLOGY_VERSION,
    Engine.THESIS: THESIS_METHODOLOGY_VERSION,
}

#: Engines a statement write can change (technical and price DQ read prices only).
STATEMENT_ENGINES: frozenset[Engine] = frozenset(ENGINE_ORDER) - {Engine.TECHNICAL, Engine.DQ_PH}
#: Engines whose snapshots feed the in-process stance cache.
_STANCE_ENGINES = frozenset({Engine.SHARIAH, Engine.FAIR_VALUE, Engine.SCORE})

FAILED_COMPANIES_CAP = 20

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def upstream_closure(engines: Collection[Engine]) -> set[Engine]:
    out: set[Engine] = set()
    stack = list(engines)
    while stack:
        e = stack.pop()
        if e in out:
            continue
        out.add(e)
        stack.extend(DEPENDS_ON[e])
    return out


@dataclass(frozen=True, slots=True)
class InputStamps:
    statements: str
    prices: str
    company: str
    assumptions: str
    price_as_of: date | None


@dataclass(frozen=True, slots=True)
class EngineOutcome:
    engine: Engine
    status: str  # "computed" | "fresh" | "failed"
    error: str | None

    def as_dict(self) -> dict[str, str | None]:
        return {"engine": self.engine.value, "status": self.status, "error": self.error}


@dataclass(frozen=True, slots=True)
class RecomputeReport:
    company_id: uuid.UUID
    trigger: Trigger
    outcomes: tuple[EngineOutcome, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "company_id": str(self.company_id),
            "trigger": self.trigger.value,
            "outcomes": [o.as_dict() for o in self.outcomes],
        }

    @property
    def computed(self) -> list[Engine]:
        return [o.engine for o in self.outcomes if o.status == "computed"]


@dataclass
class BatchReport:
    """Totals over a batch; ``per_engine`` keeps the per-step counts."""

    companies: int = 0
    computed: dict[str, int] = field(default_factory=dict)
    fresh: int = 0
    failed: int = 0
    failed_companies: list[dict[str, str]] = field(default_factory=list)
    per_engine: dict[str, dict[str, int]] = field(default_factory=dict)

    def _bump(self, engine: str, status: str) -> None:
        counts = self.per_engine.setdefault(engine, {"computed": 0, "fresh": 0, "failed": 0})
        counts[status] = counts.get(status, 0) + 1

    def add(self, report: RecomputeReport, ticker: str) -> None:
        self.companies += 1
        for o in report.outcomes:
            self._bump(o.engine.value, o.status)
            if o.status == "computed":
                self.computed[o.engine.value] = self.computed.get(o.engine.value, 0) + 1
            elif o.status == "fresh":
                self.fresh += 1
            else:
                self.failed += 1
                self._failure(ticker, o.engine.value, o.error or "")

    def add_company_failure(self, ticker: str, error: str) -> None:
        self.companies += 1
        self.failed += 1
        self._failure(ticker, "all", error)

    def _failure(self, ticker: str, engine: str, error: str) -> None:
        if len(self.failed_companies) < FAILED_COMPANIES_CAP:
            self.failed_companies.append({"ticker": ticker, "engine": engine, "error": error})

    def engine_counts(self, engine: Engine) -> dict[str, int]:
        return dict(self.per_engine.get(engine.value, {"computed": 0, "fresh": 0, "failed": 0}))

    def as_dict(self) -> dict[str, Any]:
        return {
            "companies": self.companies,
            "computed": dict(self.computed),
            "fresh": self.fresh,
            "failed": self.failed,
            "failed_companies": list(self.failed_companies),
        }

    def summary(self) -> str:
        computed = ", ".join(f"{k}={v}" for k, v in sorted(self.computed.items())) or "none"
        lines = [
            f"Recompute: {self.companies} companies; computed {computed}; "
            f"{self.fresh} fresh; {self.failed} failed."
        ]
        lines += [
            f"  failed {f['ticker']} [{f['engine']}]: {f['error']}" for f in self.failed_companies
        ]
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class EngineMeta:
    period_end: date | None = None
    source_tier: str | None = None
    price_as_of: date | None = None


@dataclass
class _Context:
    session: AsyncSession
    company: Company
    trigger: Trigger
    stamps: InputStamps
    _statements: CompanyStatements | None = None

    async def statements(self) -> CompanyStatements:
        if self._statements is None:
            self._statements = await load_company_statements(self.session, self.company.id)
        return self._statements


def _bundle_meta(st: CompanyStatements, sources: Sequence[bridge.LineValue] | None = None,
                 price_as_of: date | None = None) -> EngineMeta:
    latest = st.latest()
    used = list(sources) if sources is not None else (list(latest.lines.values()) if latest else [])
    return EngineMeta(
        period_end=max((lv.period_end for lv in used), default=None),
        source_tier=bridge.tier_of(used),
        price_as_of=price_as_of,
    )


# --- engine runners -----------------------------------------------------------


async def _run_dq_fs(ctx: _Context) -> EngineMeta:
    from app.dataquality.service import DataQualityService

    await DataQualityService(ctx.session).assess(ctx.company.id, "financial_statements")
    return _bundle_meta(await ctx.statements())


async def _run_dq_ph(ctx: _Context) -> EngineMeta:
    from app.dataquality.service import DataQualityService

    await DataQualityService(ctx.session).assess(ctx.company.id, "price_history")
    return EngineMeta(price_as_of=ctx.stamps.price_as_of)


async def _run_metrics(ctx: _Context) -> EngineMeta:
    from app.metrics.service import MetricService

    st = await ctx.statements()
    outputs = await MetricService(ctx.session).compute_and_persist(st)
    used = [lv for o in outputs for _, lv in o.inputs]
    return _bundle_meta(st, used)


async def _run_shariah(ctx: _Context) -> EngineMeta:
    from app.repositories.screening import ScreeningRepository
    from app.screening.service import ShariahScreeningService
    from app.screening.statement_input import (
        NO_STATEMENTS_REASON,
        build_screening_input_from_statements,
        name_missing_lines,
        statement_sources,
    )

    st = await ctx.statements()
    latest = st.latest()
    output = await ShariahScreeningService(ctx.session).screen_company(
        build_screening_input_from_statements(ctx.company, st)
    )
    rules = name_missing_lines(output.rule_results, latest)
    is_compliant = output.is_compliant
    overall = output.overall_reason
    if latest is None and is_compliant is not False:
        is_compliant, overall = None, NO_STATEMENTS_REASON
    sources = statement_sources(st)
    report_reason = output.report_date_reason
    if output.report_date is None and latest is not None and sources and all(
        lv.source_tier == "vendor" for lv in sources
    ):
        report_reason = (
            f"vendor data has no publication date; period end {latest.period_end.isoformat()}"
        )
    repo = ScreeningRepository(ctx.session)
    result = await repo.upsert_screening_result(
        company_id=ctx.company.id,
        is_compliant=is_compliant,
        methodology_version=output.methodology_version,
        methodology_name=DEFAULT_METHODOLOGY.name,
        overall_reason=overall,
        screened_at=output.screened_at,
        report_date=output.report_date,
        report_date_reason=report_reason,
    )
    await repo.delete_rule_results(result.id)
    for rule in rules:
        await repo.add_rule_result(
            screening_result_id=result.id,
            rule_name=rule.rule_name,
            verdict=rule.verdict.value,
            value=float(rule.value) if rule.value is not None else None,
            threshold=float(rule.threshold) if rule.threshold is not None else None,
            reason=rule.reason,
            missing_input=rule.missing_input,
            source=rule.source,
            source_date=rule.source_date,
        )
    return _bundle_meta(st, sources)


PURIFICATION_RATIO_NOTE = (
    "interest and investment income only (the other 13 impure-income checklist lines "
    "are not in the statement ontology)"
)


def _describe(lines: Sequence[bridge.LineValue]) -> str:
    return "; ".join(
        f"{lv.code} {lv.source_tier} {lv.document_type or 'statement'} FY{lv.fiscal_year}"
        for lv in lines
    )


async def _run_purification(ctx: _Context) -> EngineMeta:
    from app.repositories.screening import ScreeningRepository
    from app.screening.purification import PurificationStatus, estimate_dividend_purification

    st = await ctx.statements()
    p = st.latest()
    repo = ScreeningRepository(ctx.session)
    verdict = await repo.get_screening_result(
        ctx.company.id, DEFAULT_METHODOLOGY.version.value
    )
    dps = bridge.dps(p)
    interest = bridge.line(p, "interest_income")
    revenue = bridge.line(p, "revenue")
    ratio_lines = list(interest.sources + revenue.sources)
    ratio_provenance = PURIFICATION_RATIO_NOTE + (
        f"; {_describe(ratio_lines)}" if ratio_lines else ""
    )
    dps_source = (
        f"{bridge.DPS_LABEL} = {bridge.DPS_DERIVATION}: {_describe(dps.sources)}"
        if dps.available
        else None
    )
    estimate = estimate_dividend_purification(
        ticker=ctx.company.ticker,
        is_compliant=verdict.is_compliant if verdict is not None else None,
        dps=dps.value,
        shares_held=Decimal(1),
        non_permissible_revenue=interest.value,
        total_revenue=revenue.value,
        ratio_provenance=ratio_provenance[:500],
        dps_source=dps_source[:500] if dps_source else None,
        dps_date=p.period_end if p is not None else None,
        ratio_is_partial=True,
    )
    reason, missing = estimate.reason, estimate.missing_input
    if estimate.status == PurificationStatus.INSUFFICIENT_DATA:
        if missing == "dividend_egp" and not dps.available:
            reason, missing = dps.reason, dps.missing_input
        elif missing and ("non_permissible_revenue" in missing or "total_revenue" in missing):
            gaps = [r for r in (interest, revenue) if not r.available]
            if gaps:
                reason = "; ".join(r.reason or "" for r in gaps)
                missing = ", ".join(r.missing_input or "" for r in gaps)
    await repo.upsert_purification_estimate(
        company_id=ctx.company.id,
        methodology_version=DEFAULT_METHODOLOGY.version.value,
        doctrine=estimate.doctrine,
        branch=estimate.branch.value,
        status=estimate.status.value,
        amount_egp=estimate.amount_egp,
        dividend_egp=estimate.dividend_egp,
        ratio=estimate.ratio,
        ratio_provenance=estimate.ratio_provenance,
        dps=estimate.dps,
        dps_source=estimate.dps_source,
        dps_date=estimate.dps_date,
        reason=reason,
        missing_input=missing,
        computed_at=datetime.now(UTC),
    )
    return _bundle_meta(st, list(dps.sources) + ratio_lines)


async def _run_technical(ctx: _Context) -> EngineMeta:
    from app.technical.service import TechnicalService

    _output, price_as_of = await TechnicalService(ctx.session).compute_from_prices(ctx.company.id)
    return EngineMeta(price_as_of=price_as_of)


def _meta_from_provenance(items: Any, price_as_of: date | None) -> EngineMeta:
    rows = [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []
    ends = [date.fromisoformat(str(i["period_end"])) for i in rows if i.get("period_end")]
    tiers = {i.get("source_tier") for i in rows}
    tier = None if not rows else ("vendor" if "vendor" in tiers else "filing")
    return EngineMeta(period_end=max(ends, default=None), source_tier=tier, price_as_of=price_as_of)


async def _run_fair_value(ctx: _Context) -> EngineMeta:
    from app.valuation.service import FairValueService

    payload = await FairValueService(ctx.session).snapshot(ctx.company.id)
    return _meta_from_provenance(payload.get("statement_sources"), ctx.stamps.price_as_of)


async def _run_score(ctx: _Context) -> EngineMeta:
    from app.scores.service import ScoreService

    payload = await ScoreService(ctx.session).assess(ctx.company.id)
    sources = payload.get("inputs_echo", {}).get("sources", {})
    return _meta_from_provenance(sources.get("statements"), ctx.stamps.price_as_of)


async def _run_thesis(ctx: _Context) -> EngineMeta:
    from app.thesis.service import ThesisService

    await ThesisService(ctx.session).auto_assess(ctx.company.id, ctx.trigger.value)
    meta = _bundle_meta(await ctx.statements())
    return EngineMeta(meta.period_end, meta.source_tier, ctx.stamps.price_as_of)


Runner = Callable[[_Context], Awaitable[EngineMeta]]

RUNNERS: dict[Engine, Runner] = {
    Engine.DQ_FS: _run_dq_fs,
    Engine.DQ_PH: _run_dq_ph,
    Engine.METRICS: _run_metrics,
    Engine.SHARIAH: _run_shariah,
    Engine.PURIFICATION: _run_purification,
    Engine.TECHNICAL: _run_technical,
    Engine.FAIR_VALUE: _run_fair_value,
    Engine.SCORE: _run_score,
    Engine.THESIS: _run_thesis,
}


# --- service ------------------------------------------------------------------


class RecomputeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _lock(self, company_id: uuid.UUID) -> None:
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"recompute:{company_id}"},
        )

    async def stamps(self, company_id: uuid.UUID) -> InputStamps:
        line_rows = (
            await self.session.execute(
                select(
                    FinancialStatementLine.id,
                    FinancialStatementLine.value,
                    FinancialStatementLine.ext_status,
                )
                .where(FinancialStatementLine.company_id == company_id)
                .where(FinancialStatementLine.ext_status.in_(CalculationStatuses))
                .order_by(FinancialStatementLine.id)
            )
        ).all()
        statements = (
            hashlib.md5(
                "|".join(f"{i}:{v}:{getattr(s, 'value', s)}" for i, v, s in line_rows).encode(),
                usedforsecurity=False,
            ).hexdigest()
            if line_rows
            else ""
        )
        price_row = (
            await self.session.execute(
                select(DailyPrice.date, DailyPrice.close)
                .where(DailyPrice.company_id == company_id)
                .order_by(DailyPrice.date.desc())
                .limit(1)
            )
        ).first()
        prices = f"{price_row[0].isoformat()}:{price_row[1]}" if price_row else ""
        company = await self.session.get(Company, company_id)
        if company is None:
            raise LookupError(f"company {company_id} not found")
        company_stamp = (
            f"{company.industry or ''}|{company.egx_sector_id or ''}|"
            f"{company.gics_sub_industry_id or ''}"
        )
        from app.repositories.valuation import ValuationProfileRepository
        from app.valuation.assumptions import resolve_assumptions
        from app.valuation.constants import DEFAULT_VALUATION_PROFILE_KEY

        profile = await ValuationProfileRepository(self.session).resolve(
            company.egx_sector_id, company.gics_sub_industry_id
        )
        profile_key = profile.profile_key if profile is not None else DEFAULT_VALUATION_PROFILE_KEY
        assumptions = (await resolve_assumptions(self.session, profile_key)).stamp
        return InputStamps(
            statements=statements,
            prices=prices,
            company=company_stamp,
            assumptions=assumptions,
            price_as_of=price_row[0] if price_row else None,
        )

    @staticmethod
    def fingerprints(stamps: InputStamps) -> dict[Engine, str]:
        out: dict[Engine, str] = {}
        for engine in ENGINE_ORDER:
            material = json.dumps(
                [
                    engine.value,
                    ENGINE_VERSION[engine],
                    {k: getattr(stamps, k) for k in sorted(OWN_INPUTS[engine])},
                    [out[d] for d in DEPENDS_ON[engine]],
                ],
                sort_keys=True,
            )
            out[engine] = hashlib.sha256(material.encode()).hexdigest()
        return out

    async def _stored(self, company_id: uuid.UUID) -> dict[Engine, str]:
        rows = (
            await self.session.execute(
                select(
                    ComputeState.engine,
                    ComputeState.methodology_version,
                    ComputeState.inputs_fingerprint,
                ).where(ComputeState.company_id == company_id)
            )
        ).all()
        out: dict[Engine, str] = {}
        for engine_raw, version, fingerprint in rows:
            try:
                engine = Engine(engine_raw)
            except ValueError:
                continue
            if version == ENGINE_VERSION[engine]:
                out[engine] = fingerprint
        return out

    async def _stored_failed(self, company_id: uuid.UUID) -> set[Engine]:
        """Engines whose stored state (current version) is ``failed``."""
        rows = (
            await self.session.execute(
                select(ComputeState.engine, ComputeState.methodology_version).where(
                    ComputeState.company_id == company_id, ComputeState.status == "failed"
                )
            )
        ).all()
        out: set[Engine] = set()
        for engine_raw, version in rows:
            try:
                engine = Engine(engine_raw)
            except ValueError:
                continue
            if version == ENGINE_VERSION[engine]:
                out.add(engine)
        return out

    async def stale(self, company_id: uuid.UUID, engines: Collection[Engine]) -> list[Engine]:
        """Stale engines in the upstream closure of ``engines``, in ENGINE_ORDER."""
        closure = upstream_closure(engines)
        fps = self.fingerprints(await self.stamps(company_id))
        stored = await self._stored(company_id)
        return [e for e in ENGINE_ORDER if e in closure and stored.get(e) != fps[e]]

    async def state(self, company_id: uuid.UUID, engine: Engine) -> ComputeState | None:
        return (
            await self.session.execute(
                select(ComputeState)
                .where(ComputeState.company_id == company_id)
                .where(ComputeState.engine == engine.value)
                .where(ComputeState.methodology_version == ENGINE_VERSION[engine])
                .execution_options(populate_existing=True)
            )
        ).scalars().first()

    async def _write_state(
        self,
        company_id: uuid.UUID,
        engine: Engine,
        fingerprint: str,
        trigger: Trigger,
        status: str,
        meta: EngineMeta,
        error: str | None,
    ) -> None:
        values: dict[str, Any] = {
            "inputs_fingerprint": fingerprint,
            "status": status,
            "trigger": trigger.value,
            "calculated_at": datetime.now(UTC),
            "price_as_of": meta.price_as_of,
            "period_end": meta.period_end,
            "source_tier": meta.source_tier,
            "provisional": meta.source_tier == "vendor",
            "error": error,
        }
        await self.session.execute(
            pg_insert(ComputeState)
            .values(
                id=uuid.uuid4(),
                company_id=company_id,
                engine=engine.value,
                methodology_version=ENGINE_VERSION[engine],
                **values,
            )
            .on_conflict_do_update(constraint="uq_company_compute_state", set_=values)
        )

    async def recompute_company(
        self,
        company_id: uuid.UUID,
        trigger: Trigger,
        engines: Collection[Engine] | None = None,
        force: bool = False,
    ) -> RecomputeReport:
        """Run the stale engines (upstream closure, ENGINE_ORDER) under the company lock."""
        await self._lock(company_id)
        targets = upstream_closure(engines if engines is not None else ENGINE_ORDER)
        stamps = await self.stamps(company_id)
        fps = self.fingerprints(stamps)
        stored = await self._stored(company_id)
        stored_failed = await self._stored_failed(company_id)
        company = await self.session.get(Company, company_id)
        if company is None:
            raise LookupError(f"company {company_id} not found")
        ctx = _Context(session=self.session, company=company, trigger=trigger, stamps=stamps)
        failed: set[Engine] = set()
        outcomes: list[EngineOutcome] = []
        for engine in ENGINE_ORDER:
            if engine not in targets:
                continue
            if not force and stored.get(engine) == fps[engine]:
                if engine in stored_failed:
                    # A stored failure still poisons its dependents (QA F1).
                    failed.add(engine)
                outcomes.append(EngineOutcome(engine, "fresh", None))
                continue
            upstream = [d for d in DEPENDS_ON[engine] if d in failed]
            if upstream:
                error = f"upstream failed: {upstream[0].value}"
                await self._write_state(
                    company_id, engine, fps[engine], trigger, "failed", EngineMeta(), error
                )
                failed.add(engine)
                outcomes.append(EngineOutcome(engine, "failed", error))
                continue
            try:
                async with self.session.begin_nested():
                    meta = await RUNNERS[engine](ctx)
            except Exception as exc:  # noqa: BLE001 - recorded as failed state, never a 500
                error = f"{type(exc).__name__}: {exc}"
                logger.warning("recompute %s %s failed: %s", company.ticker, engine.value, error)
                await self._write_state(
                    company_id, engine, fps[engine], trigger, "failed", EngineMeta(), error
                )
                failed.add(engine)
                outcomes.append(EngineOutcome(engine, "failed", error))
                continue
            await self._write_state(company_id, engine, fps[engine], trigger, "ok", meta, None)
            outcomes.append(EngineOutcome(engine, "computed", None))
        await self.session.flush()
        if any(o.engine in _STANCE_ENGINES and o.status == "computed" for o in outcomes):
            from app.signals import stance_cache

            stance_cache.clear()
        return RecomputeReport(company_id=company_id, trigger=trigger, outcomes=tuple(outcomes))

    async def ensure_fresh(self, company_id: uuid.UUID, engine: Engine) -> ComputeState | None:
        """First-view hook: compute stale upstream engines, then return this engine's state."""
        if await self.stale(company_id, [engine]):
            # recompute_company takes the lock and re-checks staleness (double-checked).
            await self.recompute_company(company_id, Trigger.FIRST_VIEW, engines=[engine])
        return await self.state(company_id, engine)


def compute_meta(state: ComputeState | None) -> dict[str, Any]:
    """The compute meta block merged into every computed GET payload (section 3.1)."""
    if state is None:
        return {
            "calculated_at": None,
            "methodology_version": None,
            "trigger": None,
            "compute_status": "failed",
            "compute_error": "no compute state recorded",
            "source_tier": None,
            "provisional": False,
            "period_end": None,
            "price_as_of": None,
        }
    meta: dict[str, Any] = {
        "calculated_at": state.calculated_at.isoformat(),
        "methodology_version": state.methodology_version,
        "trigger": state.trigger,
        "compute_status": state.status,
        "source_tier": state.source_tier,
        "provisional": bool(state.provisional),
        "period_end": state.period_end.isoformat() if state.period_end else None,
        "price_as_of": state.price_as_of.isoformat() if state.price_as_of else None,
    }
    if state.status == "failed":
        meta["compute_error"] = state.error
    return meta


# --- batch entry points -------------------------------------------------------


def _default_session_factory() -> AbstractAsyncContextManager[AsyncSession]:
    from app.db.session import async_session_factory

    return async_session_factory()


async def recompute_many(
    company_ids: Sequence[uuid.UUID],
    trigger: Trigger,
    engines: Collection[Engine] | None = None,
    session_factory: SessionFactory | None = None,
    force: bool = False,
) -> BatchReport:
    """One session and one commit per company: a failure loses one company, not the batch."""
    factory = session_factory or _default_session_factory
    report = BatchReport()
    for company_id in company_ids:
        ticker = str(company_id)
        try:
            async with factory() as session:
                company = await session.get(Company, company_id)
                ticker = company.ticker if company is not None else ticker
                result = await RecomputeService(session).recompute_company(
                    company_id, trigger, engines, force
                )
                await session.commit()
            report.add(result, ticker)
        except Exception as exc:  # noqa: BLE001 - one company never stops the batch
            logger.warning("recompute %s failed: %s", ticker, exc)
            report.add_company_failure(ticker, f"{type(exc).__name__}: {exc}")
    return report


async def after_statement_import(
    company_ids: Sequence[uuid.UUID], session_factory: SessionFactory | None = None
) -> BatchReport:
    """Hook after a statement writer: every engine except the price-only ones."""
    report = await recompute_many(
        company_ids, Trigger.STATEMENT_IMPORT, STATEMENT_ENGINES, session_factory
    )
    from app.signals import stance_cache

    stance_cache.clear()
    return report


@dataclass
class PriceSyncRecompute:
    technical: dict[str, int]
    signals: dict[str, Any]
    fair_value: dict[str, int]
    score: dict[str, int]
    thesis: dict[str, int]
    failed_companies: list[dict[str, str]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "technical": self.technical,
            "signals": self.signals,
            "fair_value": self.fair_value,
            "score": self.score,
            "thesis": self.thesis,
            "failed_companies": self.failed_companies,
        }


async def after_price_sync(
    company_ids: Sequence[uuid.UUID], session_factory: SessionFactory | None = None
) -> PriceSyncRecompute:
    """Technicals -> one universe signals run -> fair value, score, thesis -> clear stance cache."""
    factory = session_factory or _default_session_factory
    technical = await recompute_many(
        company_ids, Trigger.PRICE_SYNC, {Engine.TECHNICAL}, factory
    )

    signals: dict[str, Any] = {"ran": False, "as_of": None, "scored": 0, "error": None}
    try:
        from app.signals.engine import SignalEngine

        async with factory() as session:
            async with session.begin_nested():
                run = await SignalEngine(session).run(persist=True)
            await session.commit()
        signals = {
            "ran": True,
            "as_of": run.as_of.isoformat(),
            "scored": run.scored_count,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 - recorded, never fails the job
        signals["error"] = f"{type(exc).__name__}: {exc}"

    rest = await recompute_many(
        company_ids,
        Trigger.PRICE_SYNC,
        {Engine.FAIR_VALUE, Engine.SCORE, Engine.THESIS},
        factory,
    )
    from app.signals import stance_cache

    stance_cache.clear()
    return PriceSyncRecompute(
        technical=technical.engine_counts(Engine.TECHNICAL),
        signals=signals,
        fair_value=rest.engine_counts(Engine.FAIR_VALUE),
        score=rest.engine_counts(Engine.SCORE),
        thesis=rest.engine_counts(Engine.THESIS),
        failed_companies=(technical.failed_companies + rest.failed_companies)[
            :FAILED_COMPANIES_CAP
        ],
    )


async def company_ids_for_tickers(session: AsyncSession, tickers: Sequence[str]) -> list[uuid.UUID]:
    if not tickers:
        return []
    rows = (
        await session.execute(
            select(Company.id).where(Company.ticker.in_([t.upper() for t in tickers]))
        )
    ).scalars().all()
    return list(rows)


def main() -> int:  # pragma: no cover - CLI wrapper
    parser = argparse.ArgumentParser(description="Recompute company snapshots (backfill)")
    parser.add_argument("tickers", nargs="*")
    parser.add_argument("--all", action="store_true", help="every company")
    parser.add_argument("--engines", help="comma-separated engines (default: all)")
    parser.add_argument("--force", action="store_true", help="recompute even when fresh")
    args = parser.parse_args()
    if not args.all and not args.tickers:
        parser.error("pass --all or one or more tickers")
    engines = (
        {Engine(e.strip()) for e in args.engines.split(",") if e.strip()}
        if args.engines
        else None
    )

    async def _run() -> BatchReport:
        async with _default_session_factory() as session:
            if args.all:
                ids = list((await session.execute(select(Company.id))).scalars().all())
            else:
                ids = await company_ids_for_tickers(session, args.tickers)
        return await recompute_many(ids, Trigger.BACKFILL, engines, force=args.force)

    print(asyncio.run(_run()).summary())
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
