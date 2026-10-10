"""Valuation service for orchestrating valuation calculations."""

import dataclasses
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, NamedTuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dataquality.service import DataQualityService
from app.models.market import DailyPrice
from app.repositories.company import CompanyRepository
from app.repositories.industry import IndustryRepository
from app.repositories.valuation import FairValueRepository, ValuationProfileRepository
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
    calculate_dcf_valuation,
    calculate_ddm,
    calculate_ev_ebitda_valuation,
    calculate_excess_returns,
    calculate_fcfe_2stage,
    calculate_pb_valuation,
    calculate_pe_valuation,
    select_preferred_multiple,
)

logger = logging.getLogger(__name__)

PRIMARY_MODEL_MEMBERS: dict[str, ValuationModel] = {
    "fcfe_two_stage": ValuationModel.FCFE_2STAGE,
    "dividend_discount": ValuationModel.DDM,
    "excess_returns": ValuationModel.EXCESS_RETURNS,
    "affo_two_stage": ValuationModel.AFFO_2STAGE,
}


class ValuationInput(NamedTuple):
    """Input data for valuation."""
    company_id: str
    ticker: str
    # P/E inputs
    earnings_per_share: Decimal | None
    pe_ratio: Decimal | None
    # P/B inputs
    book_value_per_share: Decimal | None
    pb_ratio: Decimal | None
    # EV/EBITDA inputs
    ebitda: Decimal | None
    ev_ebitda_ratio: Decimal | None
    net_debt: Decimal | None
    shares_outstanding: Decimal | None
    # DCF inputs
    free_cash_flow: Decimal | None
    growth_rate: Decimal | None
    discount_rate: Decimal | None
    terminal_growth_rate: Decimal | None


class ValuationOutput(NamedTuple):
    """Output of valuation calculation."""
    company_id: str
    ticker: str
    results: list[ValuationResult]
    calculated_at: datetime


class ValuationService:
    """Service for calculating valuations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def calculate_valuations(
        self,
        valuation_input: ValuationInput,
        models: list[ValuationModel] | None = None,
    ) -> ValuationOutput:
        """Calculate valuations for a company.

        Args:
            valuation_input: Company financial data
            models: Specific models to calculate (default: all)

        Returns:
            ValuationOutput with results for each model
        """
        if models is None:
            models = list(ValuationModel)

        results: list[ValuationResult] = []

        # P/E Valuation
        if ValuationModel.PE in models:
            pe_result = calculate_pe_valuation(
                earnings_per_share=valuation_input.earnings_per_share,
                pe_ratio=valuation_input.pe_ratio,
            )
            results.append(pe_result)

        # P/B Valuation
        if ValuationModel.PB in models:
            pb_result = calculate_pb_valuation(
                book_value_per_share=valuation_input.book_value_per_share,
                pb_ratio=valuation_input.pb_ratio,
            )
            results.append(pb_result)

        # EV/EBITDA Valuation
        if ValuationModel.EV_EBITDA in models:
            ev_result = calculate_ev_ebitda_valuation(
                ebitda=valuation_input.ebitda,
                ev_ebitda_ratio=valuation_input.ev_ebitda_ratio,
                net_debt=valuation_input.net_debt,
                shares_outstanding=valuation_input.shares_outstanding,
            )
            results.append(ev_result)

        # DCF Valuation
        if ValuationModel.DCF in models:
            dcf_result = calculate_dcf_valuation(
                free_cash_flow=valuation_input.free_cash_flow,
                growth_rate=valuation_input.growth_rate,
                discount_rate=valuation_input.discount_rate,
                terminal_growth_rate=valuation_input.terminal_growth_rate,
                shares_outstanding=valuation_input.shares_outstanding,
            )
            results.append(dcf_result)

        return ValuationOutput(
            company_id=valuation_input.company_id,
            ticker=valuation_input.ticker,
            results=results,
            calculated_at=datetime.now(UTC),
        )


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
        if p.primary_key == "excess_returns":
            roe = p.roe + p.roe_shift if p.roe is not None else None
            return calculate_excess_returns(p.bvps, roe, p.discount_rate, p.terminal_growth)
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
            )
        fcf = p.fcf * p.fcf_scale if p.fcf is not None else None
        return calculate_fcfe_2stage(
            fcf,
            p.growth_high,
            p.stable_growth,
            p.discount_rate,
            p.terminal_growth,
            shares_outstanding=p.shares,
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

    async def _metric_decimal(self, company_id: uuid.UUID, metric_code: str) -> Decimal | None:
        """Latest AVAILABLE metric as a fraction (stored values are 0-100 %)."""
        values = await self.industry.latest_metric_values([company_id], metric_code)
        raw, _unit = values.get(company_id, (None, None))
        if raw is None:
            return None
        try:
            return Decimal(raw) / Decimal("100")
        except InvalidOperation:
            return None

    async def fair_value(
        self, company_id: uuid.UUID, inputs: FairValueInput
    ) -> dict[str, Any]:
        """Compute, snapshot, and hand-serialize the weighted fair value."""
        company = await self.companies.get_by_id(company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        as_of = datetime.now(UTC)

        dq_fs = await self.data_quality.latest(company_id, "financial_statements")
        dq_ph = await self.data_quality.latest(company_id, "price_history")
        fs_missing = dq_fs is not None and dq_fs.status.value == "MISSING"
        ph_missing = dq_ph is not None and dq_ph.status.value == "MISSING"

        profile_row = await self.profiles.resolve(
            company.egx_sector_id, company.gics_sub_industry_id
        )
        profile_key = (
            profile_row.profile_key
            if profile_row is not None
            else DEFAULT_VALUATION_PROFILE_KEY
        )
        shape = VALUATION_PROFILES.get(
            profile_key, VALUATION_PROFILES[DEFAULT_VALUATION_PROFILE_KEY]
        )
        assert shape["primary_model"] is not None
        assert shape["fallback_model"] is not None
        primary_key = shape["primary_model"]
        weights = PROFILE_WEIGHTS.get(
            profile_key, PROFILE_WEIGHTS[DEFAULT_VALUATION_PROFILE_KEY]
        )

        # TIKR-3-input resolution: caller-supplied wins, then our own computed
        # metrics (historical extrapolation, never consensus), else missing.
        sources: dict[str, str | None] = {}
        revenue_growth = inputs.revenue_growth
        sources["revenue_growth"] = "caller" if revenue_growth is not None else None
        if revenue_growth is None:
            revenue_growth = await self._metric_decimal(company_id, "revenue_growth_yoy")
            if revenue_growth is not None:
                sources["revenue_growth"] = "metric:revenue_growth_yoy"
        operating_margin = inputs.operating_margin
        sources["operating_margin"] = "caller" if operating_margin is not None else None
        if operating_margin is None:
            operating_margin = await self._metric_decimal(company_id, "operating_margin")
            if operating_margin is not None:
                sources["operating_margin"] = "metric:operating_margin"
        stable_roe = inputs.stable_roe
        sources["stable_roe"] = "caller" if stable_roe is not None else None
        if stable_roe is None:
            stable_roe = await self._metric_decimal(company_id, "roe")
            if stable_roe is not None:
                sources["stable_roe"] = "metric:roe"

        growth_high = revenue_growth if revenue_growth is not None else inputs.growth_rate
        if revenue_growth is not None:
            sources["growth_high"] = sources["revenue_growth"]
        elif inputs.growth_rate is not None:
            sources["growth_high"] = "caller:growth_rate"
        else:
            sources["growth_high"] = None
        pe_target = inputs.exit_multiple if inputs.exit_multiple is not None else inputs.pe_ratio
        if inputs.exit_multiple is not None:
            sources["pe_target"] = "caller:exit_multiple"
        elif inputs.pe_ratio is not None:
            sources["pe_target"] = "caller:pe_ratio"
        else:
            sources["pe_target"] = None
        shares = inputs.shares_outstanding
        sources["shares_outstanding"] = "caller" if shares is not None else None
        if shares is None and company.shares_outstanding is not None:
            shares = company.shares_outstanding
            sources["shares_outstanding"] = "company"

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
            fallback = calculate_ddm(
                inputs.expected_dps, inputs.discount_rate, inputs.terminal_growth_rate
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
                    else "No model leg produced a value from the supplied inputs."
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

        await self.snapshots.upsert_snapshot(
            company_id=company.id,
            profile_key=profile_key,
            fair_value=fair_value,
            fair_value_status=payload["fair_value"]["status"],
            legs=legs,
            weights=weights_payload,
            scenarios=scenarios,
            sensitivity=sensitivity,
            confidence=confidence_payload,
            verdict=verdict,
            inputs_echo={"inputs": inputs_payload, "input_sources": sources},
            current_price=current_price,
            price_as_of=price_as_of,
            computed_at=as_of,
        )
        await self.session.flush()

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
