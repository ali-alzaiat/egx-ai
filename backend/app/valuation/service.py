"""Valuation service for orchestrating valuation calculations."""

import dataclasses
import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, NamedTuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dataquality.service import DataQualityService
from app.models.financial import FinancialPeriod
from app.models.market import DailyPrice
from app.models.metrics import FinancialMetric, MetricStatusDB
from app.repositories.company import CompanyRepository
from app.repositories.industry import IndustryRepository
from app.repositories.valuation import FairValueRepository, ValuationProfileRepository
from app.statements import bridge
from app.statements.bridge import LineValue, Resolved, load_company_statements
from app.valuation.assumptions import AssumptionSet, resolve_assumptions
from app.valuation.constants import (
    DEFAULT_VALUATION_PROFILE_KEY,
    PROFILE_WEIGHTS,
    RANGE_NOTE,
    SENSITIVITY_DISCOUNT_STEPS,
    SENSITIVITY_GROWTH_STEPS,
    VALUATION_METHODOLOGY_VERSION,
    VALUATION_PROFILES,
)
from app.valuation.fairvalue import (
    TikrInputs,
    confidence_for_dq,
    scenario_inputs,
    verdict_for,
    weighted_fair_value,
)
from app.valuation.models import (
    ValuationModel,
    ValuationResult,
    ValuationStatus,
    calculate_affo_2stage,
    calculate_ddm,
    calculate_excess_returns,
    calculate_fcfe_2stage,
    select_preferred_multiple,
)

logger = logging.getLogger(__name__)

PRIMARY_MODEL_MEMBERS: dict[str, ValuationModel] = {
    "fcfe_two_stage": ValuationModel.FCFE_2STAGE,
    "dividend_discount": ValuationModel.DDM,
    "excess_returns": ValuationModel.EXCESS_RETURNS,
    "affo_two_stage": ValuationModel.AFFO_2STAGE,
}


class FairValueInput(NamedTuple):
    """Inputs for a weighted fair-value computation. All optional.

    Missing inputs degrade to INSUFFICIENT_DATA — never zero-filled, never
    guessed. TIKR-3-inputs (revenue_growth, operating_margin, exit_multiple)
    take precedence over their raw counterparts with the fallback disclosed
    per input in the response.
    """

    free_cash_flow: Decimal | None = None
    growth_rate: Decimal | None = None
    stable_growth: Decimal | None = None
    discount_rate: Decimal | None = None
    terminal_growth_rate: Decimal | None = None
    #: Terminal-stage cost of equity (R45 M5); the two-stage models need it.
    long_run_cost_of_equity: Decimal | None = None
    expected_dps: Decimal | None = None
    stable_roe: Decimal | None = None
    affo: Decimal | None = None
    ffo: Decimal | None = None
    earnings_per_share: Decimal | None = None
    pe_ratio: Decimal | None = None
    revenue_per_share: Decimal | None = None
    ps_ratio: Decimal | None = None
    book_value_per_share: Decimal | None = None
    pb_ratio: Decimal | None = None
    shares_outstanding: Decimal | None = None
    revenue_growth: Decimal | None = None
    operating_margin: Decimal | None = None
    exit_multiple: Decimal | None = None


@dataclass
class _ResolvedPipeline:
    """One fully-resolved pass through the intrinsic + relative pipeline."""

    growth_high: Decimal | None
    discount_rate: Decimal | None
    terminal_growth: Decimal | None
    stable_growth: Decimal | None
    long_run_ke: Decimal | None
    fcf: Decimal | None
    fcf_scale: Decimal
    dps: Decimal | None
    roe: Decimal | None
    roe_shift: Decimal
    affo: Decimal | None
    affo_source: str
    eps: Decimal | None
    pe_target: Decimal | None
    rps: Decimal | None
    ps_target: Decimal | None
    bvps: Decimal | None
    pb_target: Decimal | None
    shares: Decimal | None
    primary_key: str


@dataclass
class ResolvedFairValueInputs:
    """What ``snapshot`` feeds ``compute``: inputs plus their provenance strings."""

    inputs: FairValueInput
    sources: dict[str, str | None]
    assumptions: AssumptionSet
    statement_sources: list[LineValue]
    profile_key: str
    #: Statement-derived input -> why it is unavailable (names the missing line).
    gaps: dict[str, str] = field(default_factory=dict)


#: Stored assumption keys each primary model needs (R44 (b) + R45 M5 + F13). The
#: growth cap (``nominal_gdp_growth``) is only needed by the growth-stage models.
_INTRINSIC_KEYS: dict[str, tuple[str, ...]] = {
    "excess_returns": (
        "risk_free_rate",
        "equity_risk_premium",
        "long_run_inflation",
        "long_run_cost_of_equity",
    ),
}
_DEFAULT_INTRINSIC_KEYS = (
    "risk_free_rate",
    "equity_risk_premium",
    "long_run_inflation",
    "long_run_cost_of_equity",
    "nominal_gdp_growth",
)
_RELATIVE_KEYS = ("target_pe", "target_ps", "target_pb")


def _gap(keys: Sequence[str], assumptions: AssumptionSet | None = None) -> str:
    if assumptions is not None:
        return assumptions.gap(keys)
    return (
        f"no sourced {', '.join(keys)} in valuation assumptions "
        f"{VALUATION_METHODOLOGY_VERSION}"
    )


def _apply_assumption_gaps(
    primary: ValuationResult,
    relative: ValuationResult,
    primary_key: str,
    missing: Sequence[str],
    assumptions: AssumptionSet | None = None,
) -> tuple[ValuationResult, ValuationResult, str | None]:
    """Name the missing (or stale) sourced assumption on legs it left INSUFFICIENT."""
    reasons: list[str] = []
    needed = [
        k for k in _INTRINSIC_KEYS.get(primary_key, _DEFAULT_INTRINSIC_KEYS) if k in missing
    ]
    if (
        primary.value is None
        and needed
        and not (primary.reason or "").startswith("No intrinsic")
    ):
        primary = _insufficient(primary.model, _gap(needed, assumptions))
        reasons.append(_gap(needed, assumptions))
    if (
        relative.value is None
        and all(k in missing for k in _RELATIVE_KEYS)
        and not (relative.reason or "").startswith("No relative")
    ):
        relative = _insufficient(relative.model, _gap(_RELATIVE_KEYS, assumptions))
        reasons.append(_gap(_RELATIVE_KEYS, assumptions))
    return primary, relative, "; ".join(reasons) if reasons else None


def _leg_payload(result: ValuationResult) -> dict[str, Any]:
    return {
        "model": result.model.value,
        "value": str(result.value) if result.value is not None else None,
        "status": result.status.value,
        "reason": result.reason,
        "assumptions": result.assumptions,
    }


def _insufficient(model: ValuationModel, reason: str) -> ValuationResult:
    return ValuationResult(
        value=None,
        status=ValuationStatus.INSUFFICIENT_DATA,
        model=model,
        assumptions={},
        reason=reason,
    )


class FairValueService:
    """Weighted fair value with profile routing, scenarios, and confidence."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.companies = CompanyRepository(session)
        self.profiles = ValuationProfileRepository(session)
        self.snapshots = FairValueRepository(session)
        self.industry = IndustryRepository(session)
        self.data_quality = DataQualityService(session)

    def _compute_primary(self, p: _ResolvedPipeline) -> ValuationResult:
        if p.long_run_ke is None:
            model = {
                "excess_returns": ValuationModel.EXCESS_RETURNS,
                "affo_two_stage": ValuationModel.AFFO_2STAGE,
            }.get(p.primary_key, ValuationModel.FCFE_2STAGE)
            return _insufficient(
                model, "Missing long-run cost of equity (terminal discount rate)"
            )
        if p.primary_key == "excess_returns":
            roe = p.roe + p.roe_shift if p.roe is not None else None
            return calculate_excess_returns(
                p.bvps, roe, p.discount_rate, p.terminal_growth,
                terminal_discount_rate=p.long_run_ke,
            )
        if p.primary_key == "affo_two_stage":
            fcf = p.affo * p.fcf_scale if p.affo is not None else None
            return calculate_affo_2stage(
                fcf,
                p.growth_high,
                p.stable_growth,
                p.discount_rate,
                p.terminal_growth,
                shares_outstanding=p.shares,
                cash_flow_source=p.affo_source,
                terminal_discount_rate=p.long_run_ke,
            )
        fcf = p.fcf * p.fcf_scale if p.fcf is not None else None
        return calculate_fcfe_2stage(
            fcf,
            p.growth_high,
            p.stable_growth,
            p.discount_rate,
            p.terminal_growth,
            shares_outstanding=p.shares,
            terminal_discount_rate=p.long_run_ke,
        )

    def _compute_relative(self, p: _ResolvedPipeline) -> ValuationResult:
        return select_preferred_multiple(
            p.eps, p.pe_target, p.rps, p.ps_target, p.bvps, p.pb_target
        )

    def _pipeline_fv(
        self, p: _ResolvedPipeline, weights: dict[str, Decimal]
    ) -> tuple[ValuationResult, ValuationResult, Decimal | None, int]:
        primary = self._compute_primary(p)
        relative = self._compute_relative(p)
        value, n = weighted_fair_value(
            {"intrinsic": primary.value, "relative": relative.value}, weights
        )
        return (primary, relative, value, n)

    async def _metric_decimal(
        self, company_id: uuid.UUID, metric_code: str
    ) -> tuple[Decimal | None, int | None]:
        """Newest-period metric as a fraction (stored values are 0-100 %).

        Only the newest period counts: when it is not AVAILABLE the result is
        ``(None, None)``, never an older period's value (R43 analyst F9).
        """
        row = (
            await self.session.execute(
                select(
                    FinancialMetric.value, FinancialPeriod.fiscal_year, FinancialMetric.status
                )
                .join(FinancialPeriod, FinancialMetric.period_id == FinancialPeriod.id)
                .where(FinancialMetric.company_id == company_id)
                .where(FinancialMetric.metric_code == metric_code)
                .order_by(
                    FinancialPeriod.end_date.desc(), FinancialMetric.calculated_at.desc()
                )
                .limit(1)
            )
        ).first()
        if row is None or row[0] is None or row[2] != MetricStatusDB.AVAILABLE:
            return (None, None)
        try:
            return (Decimal(row[0]) / Decimal("100"), int(row[1]))
        except InvalidOperation:
            return (None, None)

    async def _profile(self, company: Any) -> tuple[Any, str]:
        profile_row = await self.profiles.resolve(
            company.egx_sector_id, company.gics_sub_industry_id
        )
        key = (
            profile_row.profile_key
            if profile_row is not None
            else DEFAULT_VALUATION_PROFILE_KEY
        )
        return profile_row, key

    async def resolve_inputs(self, company_id: uuid.UUID) -> ResolvedFairValueInputs:
        """Inputs from the statement bridge + the sourced assumption record (R43)."""
        company = await self.companies.get_by_id(company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        _row, profile_key = await self._profile(company)
        assumptions = await resolve_assumptions(self.session, profile_key)
        statements = await load_company_statements(self.session, company_id)
        latest = statements.latest()

        sources: dict[str, str | None] = {}
        gaps: dict[str, str] = {}
        used: list[LineValue] = []

        def take(key: str, resolved: Resolved) -> Decimal | None:
            if not resolved.available:
                sources[key] = None
                gaps[key] = resolved.reason or f"missing statement line: {resolved.missing_input}"
                return None
            used.extend(resolved.sources)
            codes = ",".join(dict.fromkeys(lv.code for lv in resolved.sources))
            fy = resolved.sources[0].fiscal_year if resolved.sources else None
            tier = bridge.tier_of(resolved.sources)
            sources[key] = f"statement:{codes} FY{fy} ({tier})"
            return resolved.value

        def assume(key: str, assumption_key: str) -> Decimal | None:
            item = assumptions.items.get(assumption_key)
            sources[key] = item.provenance() if item is not None else None
            return item.value if item is not None else None

        def derived(key: str, value: Decimal | None) -> Decimal | None:
            sources[key] = assumptions.provenance_of(key)
            return value

        cagr = bridge.revenue_cagr_3y(statements, latest)
        cap = assumptions.value("nominal_gdp_growth")
        growth: Decimal | None = None
        sources["revenue_growth"] = None
        if not cagr.available or cagr.value is None:
            gaps["revenue_growth"] = cagr.reason or "revenue CAGR unavailable"
        elif cap is not None:
            used.extend(cagr.sources)
            growth = min(cagr.value, cap)
            fy = cagr.sources[-1].fiscal_year
            tier = bridge.tier_of(cagr.sources)
            sources["revenue_growth"] = (
                f"statement:revenue 3y CAGR FY{fy - 3}-FY{fy} ({tier}) = {cagr.value:.6f}"
                + (
                    f"; capped at {assumptions.provenance_of('nominal_gdp_growth')}"
                    if cagr.value > cap
                    else f"; below cap {assumptions.provenance_of('nominal_gdp_growth')}"
                )
            )

        inputs = FairValueInput(
            revenue_growth=growth,
            free_cash_flow=take("free_cash_flow", bridge.free_cash_flow(latest)),
            earnings_per_share=take("earnings_per_share", bridge.eps(latest)),
            book_value_per_share=take(
                "book_value_per_share", bridge.book_value_per_share(latest)
            ),
            revenue_per_share=take("revenue_per_share", bridge.revenue_per_share(latest)),
            shares_outstanding=take(
                "shares_outstanding", bridge.line(latest, "shares_outstanding")
            ),
            discount_rate=derived("discount_rate", assumptions.discount_rate),
            terminal_growth_rate=derived(
                "terminal_growth_rate", assumptions.terminal_growth_rate
            ),
            stable_growth=derived("stable_growth", assumptions.terminal_growth_rate),
            long_run_cost_of_equity=assume(
                "long_run_cost_of_equity", "long_run_cost_of_equity"
            ),
            pe_ratio=assume("pe_ratio", "target_pe"),
            exit_multiple=assume("exit_multiple", "target_pe"),
            ps_ratio=assume("ps_ratio", "target_ps"),
            pb_ratio=assume("pb_ratio", "target_pb"),
            expected_dps=None,
        )
        # Historical DPS is not an *expected* DPS: the DDM leg stays INSUFFICIENT.
        sources["expected_dps"] = None
        return ResolvedFairValueInputs(
            inputs=inputs,
            sources=sources,
            assumptions=assumptions,
            statement_sources=bridge.unique_sources(used),
            profile_key=profile_key,
            gaps=gaps,
        )

    async def snapshot(self, company_id: uuid.UUID) -> dict[str, Any]:
        """Resolve inputs, compute, and upsert the one snapshot row (R43 FAIR_VALUE)."""
        resolved = await self.resolve_inputs(company_id)
        payload = await self.compute(
            company_id,
            resolved.inputs,
            input_sources=resolved.sources,
            missing_assumptions=resolved.assumptions.missing,
            assumptions=resolved.assumptions,
            input_gaps=resolved.gaps,
        )
        payload["assumptions"] = resolved.assumptions.payload()
        payload["statement_sources"] = [
            bridge.provenance(lv) for lv in resolved.statement_sources
        ]
        tier = bridge.tier_of(resolved.statement_sources)
        payload["source_tier"] = tier
        payload["provisional"] = tier == "vendor"
        payload["period_end"] = (
            max(lv.period_end for lv in resolved.statement_sources).isoformat()
            if resolved.statement_sources
            else None
        )
        fv = payload["fair_value"]["value"]
        price = payload["current_price"]
        await self.snapshots.upsert_snapshot(
            company_id=company_id,
            profile_key=payload["profile"]["profile_id"],
            fair_value=Decimal(fv) if fv is not None else None,
            fair_value_status=payload["fair_value"]["status"],
            legs=payload["legs"],
            weights=payload["weights"],
            scenarios=payload["scenarios"],
            sensitivity=payload["sensitivity"],
            confidence=payload["confidence"],
            verdict=payload["verdict"],
            inputs_echo={
                "inputs": payload["inputs"],
                "input_sources": payload["input_sources"],
                "payload": payload,
            },
            current_price=Decimal(price["value"]) if price["value"] is not None else None,
            price_as_of=date.fromisoformat(price["as_of"]) if price["as_of"] else None,
            computed_at=datetime.fromisoformat(payload["computed_at"]),
        )
        await self.session.flush()
        return payload

    async def latest_payload(self, company_id: uuid.UUID) -> dict[str, Any] | None:
        """The stored snapshot payload under the current methodology (never recomputes)."""
        row = await self.snapshots.get_snapshot(company_id)
        if row is None:
            return None
        echo = row.inputs_echo if isinstance(row.inputs_echo, dict) else {}
        stored = echo.get("payload")
        return dict(stored) if isinstance(stored, dict) else None

    async def compute(
        self,
        company_id: uuid.UUID,
        inputs: FairValueInput,
        *,
        input_sources: dict[str, str | None] | None = None,
        missing_assumptions: Sequence[str] = (),
        assumptions: AssumptionSet | None = None,
        input_gaps: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Compute and hand-serialize the weighted fair value. Never persists."""
        company = await self.companies.get_by_id(company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        as_of = datetime.now(UTC)
        given = dict(input_sources or {})

        dq_fs = await self.data_quality.latest(company_id, "financial_statements")
        dq_ph = await self.data_quality.latest(company_id, "price_history")
        fs_missing = dq_fs is not None and dq_fs.status.value == "MISSING"
        ph_missing = dq_ph is not None and dq_ph.status.value == "MISSING"

        profile_row, profile_key = await self._profile(company)
        shape = VALUATION_PROFILES.get(
            profile_key, VALUATION_PROFILES[DEFAULT_VALUATION_PROFILE_KEY]
        )
        assert shape["primary_model"] is not None
        assert shape["fallback_model"] is not None
        primary_key = shape["primary_model"]
        weights = PROFILE_WEIGHTS.get(
            profile_key, PROFILE_WEIGHTS[DEFAULT_VALUATION_PROFILE_KEY]
        )

        # TIKR-3-input resolution: a resolved input wins, then our own computed
        # metrics (historical extrapolation, never consensus), else missing.
        sources: dict[str, str | None] = {}

        async def prefill(
            key: str, supplied: Decimal | None, metric_code: str
        ) -> Decimal | None:
            if supplied is not None:
                sources[key] = given.get(key) or "input"
                return supplied
            value, fy = await self._metric_decimal(company_id, metric_code)
            sources[key] = f"metric:{metric_code} FY{fy}" if value is not None else None
            return value

        # Stage-1 growth is the capped 3-year revenue CAGR supplied by ``resolve_inputs``
        # (owner ruling F13); the single-year metric is never a fallback.
        revenue_growth = inputs.revenue_growth
        sources["revenue_growth"] = (
            given.get("revenue_growth") or "input:revenue_growth"
            if revenue_growth is not None
            else None
        )
        operating_margin = await prefill(
            "operating_margin", inputs.operating_margin, "operating_margin"
        )
        stable_roe = await prefill("stable_roe", inputs.stable_roe, "roe")

        growth_high = revenue_growth if revenue_growth is not None else inputs.growth_rate
        if revenue_growth is not None:
            sources["growth_high"] = sources["revenue_growth"]
        elif inputs.growth_rate is not None:
            sources["growth_high"] = given.get("growth_rate") or "input:growth_rate"
        else:
            sources["growth_high"] = None
        pe_target = inputs.exit_multiple if inputs.exit_multiple is not None else inputs.pe_ratio
        if inputs.exit_multiple is not None:
            sources["pe_target"] = given.get("exit_multiple") or "input:exit_multiple"
        elif inputs.pe_ratio is not None:
            sources["pe_target"] = given.get("pe_ratio") or "input:pe_ratio"
        else:
            sources["pe_target"] = None
        shares = inputs.shares_outstanding
        for key, value in given.items():
            sources.setdefault(key, value)

        affo, affo_source = inputs.affo, "affo"
        if affo is None:
            affo, affo_source = inputs.ffo, "ffo"
        if affo is None:
            affo, affo_source = inputs.free_cash_flow, "fcf"

        base = _ResolvedPipeline(
            growth_high=growth_high,
            discount_rate=inputs.discount_rate,
            terminal_growth=inputs.terminal_growth_rate,
            stable_growth=inputs.stable_growth,
            long_run_ke=inputs.long_run_cost_of_equity,
            fcf=inputs.free_cash_flow,
            fcf_scale=Decimal("1"),
            dps=inputs.expected_dps,
            roe=stable_roe,
            roe_shift=Decimal("0"),
            affo=affo,
            affo_source=affo_source,
            eps=inputs.earnings_per_share,
            pe_target=pe_target,
            rps=inputs.revenue_per_share,
            ps_target=inputs.ps_ratio,
            bvps=inputs.book_value_per_share,
            pb_target=inputs.pb_ratio,
            shares=shares,
            primary_key=primary_key,
        )

        fs_reason = (
            "No intrinsic value: financial-statements data-quality "
            "assessment is MISSING, so filings cannot support a cash-flow model."
        )
        if fs_missing:
            primary_member = PRIMARY_MODEL_MEMBERS.get(
                primary_key, ValuationModel.FCFE_2STAGE
            )
            primary = _insufficient(primary_member, fs_reason)
            fallback = _insufficient(ValuationModel.DDM, fs_reason)
            relative = (
                _insufficient(
                    ValuationModel.PE,
                    "No relative value: price-history data-quality "
                    "assessment is MISSING.",
                )
                if ph_missing
                else self._compute_relative(base)
            )
            fair_value: Decimal | None = None
            n_with_data = 0
            if not ph_missing and relative.value is not None:
                # Relative leg alone never becomes a headline fair value when
                # intrinsics are MISSING: honest null, never a default FV.
                n_with_data = 0
        else:
            primary, relative, fair_value, n_with_data = self._pipeline_fv(base, weights)
            if ph_missing:
                relative = _insufficient(
                    ValuationModel.PE,
                    "No relative value: price-history data-quality "
                    "assessment is MISSING.",
                )
                fair_value, n_with_data = weighted_fair_value(
                    {"intrinsic": primary.value, "relative": None}, weights
                )
            if inputs.expected_dps is not None and inputs.long_run_cost_of_equity is None:
                fallback = _insufficient(
                    ValuationModel.DDM,
                    "Missing long-run cost of equity (terminal discount rate)",
                )
            else:
                fallback = calculate_ddm(
                    inputs.expected_dps,
                    inputs.discount_rate,
                    inputs.terminal_growth_rate,
                    terminal_discount_rate=inputs.long_run_cost_of_equity,
                )

        growth_gap = (input_gaps or {}).get("revenue_growth")
        if (
            growth_gap
            and primary_key != "excess_returns"
            and primary.value is None
            and primary.status == ValuationStatus.INSUFFICIENT_DATA
            and growth_high is None
            and not (primary.reason or "").startswith("No intrinsic")
        ):
            primary = _insufficient(primary.model, f"Missing stage-1 growth: {growth_gap}")
        fcf_gap = (input_gaps or {}).get("free_cash_flow")
        if (
            fcf_gap
            and primary_key != "excess_returns"
            and primary.value is None
            and primary.status == ValuationStatus.INSUFFICIENT_DATA
            and affo is None
            and not (primary.reason or "").startswith("No intrinsic")
        ):
            # Name the missing statement line (cfo / capex), not generic engine text.
            primary = _insufficient(primary.model, f"Missing free cash flow: {fcf_gap}")
        primary, relative, gap_reason = _apply_assumption_gaps(
            primary, relative, primary_key, missing_assumptions, assumptions
        )

        price_row = (
            await self.session.execute(
                select(DailyPrice)
                .where(DailyPrice.company_id == company_id)
                .order_by(DailyPrice.date.desc())
                .limit(1)
            )
        ).scalars().first()
        current_price = price_row.close if price_row is not None else None
        price_as_of = price_row.date if price_row is not None else None

        confidence = confidence_for_dq(
            dq_fs.score if dq_fs is not None else None,
            dq_fs.status.value if dq_fs is not None else None,
        )
        verdict = verdict_for(fair_value, current_price, confidence.required_discount)

        scenarios = self._scenarios(
            base, weights, revenue_growth, operating_margin, inputs.exit_multiple,
            fs_missing, ph_missing,
        )
        sensitivity = self._sensitivity(base, weights, fair_value, fs_missing)

        def opt(value: Decimal | None) -> str | None:
            return str(value) if value is not None else None

        legs = {
            "intrinsic": _leg_payload(primary),
            "relative": _leg_payload(relative),
            "fallback": _leg_payload(fallback),
        }
        weights_payload = {k: str(v) for k, v in weights.items()}
        confidence_payload = {
            "level": confidence.level,
            "required_discount": str(confidence.required_discount),
            "dq_score": confidence.dq_score,
            "dq_status": confidence.dq_status,
            "reason": confidence.reason,
            "methodology_version": VALUATION_METHODOLOGY_VERSION,
        }
        inputs_payload = {
            "free_cash_flow": opt(inputs.free_cash_flow),
            "growth_rate": opt(inputs.growth_rate),
            "stable_growth": opt(inputs.stable_growth),
            "discount_rate": opt(inputs.discount_rate),
            "terminal_growth_rate": opt(inputs.terminal_growth_rate),
            "long_run_cost_of_equity": opt(inputs.long_run_cost_of_equity),
            "expected_dps": opt(inputs.expected_dps),
            "stable_roe": opt(inputs.stable_roe),
            "affo": opt(inputs.affo),
            "ffo": opt(inputs.ffo),
            "earnings_per_share": opt(inputs.earnings_per_share),
            "pe_ratio": opt(inputs.pe_ratio),
            "revenue_per_share": opt(inputs.revenue_per_share),
            "ps_ratio": opt(inputs.ps_ratio),
            "book_value_per_share": opt(inputs.book_value_per_share),
            "pb_ratio": opt(inputs.pb_ratio),
            "shares_outstanding": opt(inputs.shares_outstanding),
            "revenue_growth": opt(inputs.revenue_growth),
            "operating_margin": opt(inputs.operating_margin),
            "exit_multiple": opt(inputs.exit_multiple),
            "resolved_growth_high": opt(growth_high),
            "resolved_pe_target": opt(pe_target),
            "resolved_affo_source": affo_source,
        }

        payload: dict[str, Any] = {
            "company_id": str(company.id),
            "ticker": company.ticker,
            "as_of": as_of.date().isoformat(),
            "computed_at": as_of.isoformat(),
            "methodology_version": VALUATION_METHODOLOGY_VERSION,
            "profile": {
                "profile_id": profile_key,
                "methodology_version": profile_row.methodology_version
                if profile_row is not None
                else VALUATION_METHODOLOGY_VERSION,
                "primary_model": primary_key,
                "fallback_model": shape["fallback_model"],
                "preferred_multiple": shape["preferred_multiple"],
            },
            "inputs": inputs_payload,
            "input_sources": sources,
            "legs": legs,
            "weights": weights_payload,
            "n_with_data": n_with_data,
            "fair_value": {
                "value": opt(fair_value),
                "status": "AVAILABLE" if fair_value is not None else "INSUFFICIENT_DATA",
                "reason": None
                if fair_value is not None
                else (
                    fs_reason
                    if fs_missing
                    else gap_reason
                    or "No model leg produced a value from the resolved inputs."
                ),
            },
            "current_price": {
                "value": opt(current_price),
                "as_of": price_as_of.isoformat() if price_as_of is not None else None,
            },
            "scenarios": scenarios,
            "sensitivity": sensitivity,
            "confidence": confidence_payload,
            "verdict": verdict,
        }

        return payload

    def _scenarios(
        self,
        base: _ResolvedPipeline,
        weights: dict[str, Decimal],
        revenue_growth: Decimal | None,
        operating_margin: Decimal | None,
        exit_multiple: Decimal | None,
        fs_missing: bool,
        ph_missing: bool,
    ) -> dict[str, Any]:
        """Bull/base/bear from the TIKR-3-inputs with fixed deltas."""

        missing_note = (
            "Scenarios need revenue growth, operating margin, and exit "
            "multiple (caller-supplied or pre-filled from historical metrics); "
            "nothing is assumed."
        )
        if fs_missing:
            na = {
                "value": None,
                "status": "INSUFFICIENT_DATA",
                "reason": "Financial-statements data-quality assessment is MISSING.",
            }
            return {
                "bull": na,
                "base": na,
                "bear": na,
                "note": RANGE_NOTE,
            }
        if revenue_growth is None or operating_margin is None or exit_multiple is None:
            na = {
                "value": None,
                "status": "INSUFFICIENT_DATA",
                "reason": missing_note,
            }
            return {"bull": na, "base": na, "bear": na, "note": RANGE_NOTE}
        tikr_base = TikrInputs(revenue_growth, operating_margin, exit_multiple)
        out: dict[str, Any] = {}
        for name, direction in (("bear", -1), ("base", 0), ("bull", 1)):
            tikr = scenario_inputs(tikr_base, direction)
            margin_delta = tikr.operating_margin - tikr_base.operating_margin
            p = dataclasses.replace(
                base,
                growth_high=tikr.revenue_growth,
                fcf_scale=Decimal("1") + margin_delta,
                roe_shift=margin_delta,
                pe_target=tikr.exit_multiple,
            )
            primary, relative, value, _n = self._pipeline_fv(p, weights)
            if ph_missing:
                relative = _insufficient(
                    ValuationModel.PE,
                    "No relative value: price-history data-quality "
                    "assessment is MISSING.",
                )
                value, _n = weighted_fair_value(
                    {"intrinsic": primary.value, "relative": None}, weights
                )
            out[name] = {
                "value": str(value) if value is not None else None,
                "status": "AVAILABLE" if value is not None else "INSUFFICIENT_DATA",
                "reason": None
                if value is not None
                else "Scenario legs produced no value from the scenario inputs.",
                "inputs": {
                    "revenue_growth": str(tikr.revenue_growth),
                    "operating_margin": str(tikr.operating_margin),
                    "exit_multiple": str(tikr.exit_multiple),
                },
                "intrinsic": _leg_payload(primary),
                "relative": _leg_payload(relative),
            }
        out["note"] = RANGE_NOTE
        return out

    def _sensitivity(
        self,
        base: _ResolvedPipeline,
        weights: dict[str, Decimal],
        base_fv: Decimal | None,
        fs_missing: bool,
    ) -> list[dict[str, Any]]:
        """Minimal 1-D sensitivity: ±discount and ±growth around the base."""

        rows: list[dict[str, Any]] = []
        if fs_missing or base.discount_rate is None or base.growth_high is None:
            return rows
        for step in SENSITIVITY_DISCOUNT_STEPS:
            p = dataclasses.replace(base, discount_rate=base.discount_rate + step)
            _primary, _relative, value, _n = self._pipeline_fv(p, weights)
            rows.append(
                self._sensitivity_row(
                    "discount_rate", base.discount_rate + step, value, base_fv
                )
            )
        for step in SENSITIVITY_GROWTH_STEPS:
            p = dataclasses.replace(base, growth_high=base.growth_high + step)
            _primary, _relative, value, _n = self._pipeline_fv(p, weights)
            rows.append(
                self._sensitivity_row(
                    "revenue_growth", base.growth_high + step, value, base_fv
                )
            )
        return rows

    @staticmethod
    def _sensitivity_row(
        parameter: str,
        value: Decimal,
        fair_value: Decimal | None,
        base_fv: Decimal | None,
    ) -> dict[str, Any]:
        if fair_value is None or base_fv is None or base_fv == 0:
            return {
                "parameter": parameter,
                "value": str(value),
                "fair_value": str(fair_value) if fair_value is not None else None,
                "change_from_base": None,
            }
        change = (fair_value - base_fv) / abs(base_fv) * Decimal("100")
        return {
            "parameter": parameter,
            "value": str(value),
            "fair_value": str(fair_value),
            "change_from_base": f"{change:.2f}%",
        }
