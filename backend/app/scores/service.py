"""Investment-score service: I/O, input resolution, persistence."""

import dataclasses
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dataquality.service import DataQualityService
from app.models.market import DailyPrice
from app.models.metrics import FinancialMetric, MetricStatusDB
from app.models.scores import InvestmentScore
from app.repositories.company import CompanyRepository
from app.repositories.industry import IndustryRepository
from app.repositories.scores import ScoreProfileRepository, ScoreRepository
from app.repositories.valuation import FairValueRepository
from app.scores import checks as engine
from app.scores.checks import ComponentStatus, ScoreInputs
from app.scores.constants import (
    DEFAULT_MARGIN_OF_SAFETY,
    DEFAULT_SCORE_PROFILE_KEY,
    SCORE_DISCLAIMER,
    SCORE_METHODOLOGY_VERSION,
    SCORE_SCALE,
)
from app.statements import bridge
from app.statements.bridge import LineValue, Resolved, load_company_statements
from app.valuation.constants import VALUATION_METHODOLOGY_VERSION

# Metric codes read from the latest AVAILABLE rows; stored 0-100 % values
# below are converted to fractions, ratios are used as-is.
_PCT_METRICS = (
    "eps_growth_yoy",
    "revenue_growth_yoy",
    "roe",
    "roa",
)


def _to_decimal(raw: str | None, *, percent: bool) -> Decimal | None:
    if raw is None:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return value / Decimal("100") if percent else value


def _rebuild_components(
    components: dict[str, Any],
) -> dict[str, engine.ComponentResult]:
    """Rebuild engine components from the persisted ``as_dict`` JSONB shape.

    Only status/score feed ``headline_score``; counts/reason round-trip for
    fidelity, checks stay empty (the persisted per-check dicts are served
    as-is and never re-parsed here).
    """
    rebuilt: dict[str, engine.ComponentResult] = {}
    for key, raw in components.items():
        if not isinstance(raw, dict):
            continue
        try:
            status = engine.ComponentStatus(str(raw.get("status")))
        except ValueError:
            status = ComponentStatus.INSUFFICIENT_DATA
        score_raw = raw.get("score")
        score = (
            float(score_raw) if isinstance(score_raw, (int, float)) else None
        )
        passes_raw = raw.get("passes")
        ran_raw = raw.get("ran")
        total_raw = raw.get("total")
        rebuilt[key] = engine.ComponentResult(
            key=str(raw.get("key", key)),
            status=status,
            score=score,
            passes=passes_raw if isinstance(passes_raw, int) else 0,
            ran=ran_raw if isinstance(ran_raw, int) else 0,
            total=total_raw if isinstance(total_raw, int) else 0,
            reason=str(raw.get("reason", "")),
        )
    return rebuilt


class ScoreService:
    """Deterministic investment scores over resolved (never invented) inputs."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.companies = CompanyRepository(session)
        self.profiles = ScoreProfileRepository(session)
        self.snapshots = ScoreRepository(session)
        self.industry = IndustryRepository(session)
        self.data_quality = DataQualityService(session)
        self.fair_values = FairValueRepository(session)

    async def _metric(
        self, company_id: uuid.UUID, code: str, *, percent: bool
    ) -> tuple[Decimal | None, str | None]:
        """Latest AVAILABLE metric as Decimal (fraction for %), plus raw text."""
        values = await self.industry.latest_metric_values([company_id], code)
        raw, _unit = values.get(company_id, (None, None))
        return (_to_decimal(raw, percent=percent), raw)

    async def _latest_price(
        self, company_id: uuid.UUID
    ) -> tuple[Decimal | None, date | None]:
        row = (
            await self.session.execute(
                select(DailyPrice)
                .where(DailyPrice.company_id == company_id)
                .order_by(DailyPrice.date.desc())
                .limit(1)
            )
        ).scalars().first()
        if row is None:
            return (None, None)
        return (row.close, row.date)

    async def _metric_by_period(
        self, company_id: uuid.UUID, code: str
    ) -> dict[uuid.UUID, str]:
        """AVAILABLE metric values keyed by period id (stored text)."""
        rows = (
            await self.session.execute(
                select(FinancialMetric.period_id, FinancialMetric.value)
                .where(FinancialMetric.company_id == company_id)
                .where(FinancialMetric.metric_code == code)
                .where(FinancialMetric.status == MetricStatusDB.AVAILABLE)
            )
        ).all()
        return {pid: str(value) for pid, value in rows if value is not None}

    async def _resolve_inputs(
        self, company_id: uuid.UUID
    ) -> tuple[ScoreInputs, dict[str, Any]]:
        """Inputs from statement lines, metrics and the FV snapshot (R43). Never invented."""
        pct: dict[str, tuple[Decimal | None, str | None]] = {}
        for code in _PCT_METRICS:
            pct[code] = await self._metric(company_id, code, percent=True)
        de_now, de_raw = await self._metric(company_id, "debt_to_equity", percent=False)

        price, price_as_of = await self._latest_price(company_id)
        fv_row = await self.fair_values.get_snapshot(company_id)
        fair_value = fv_row.fair_value if fv_row is not None else None

        eps_g, _ = pct["eps_growth_yoy"]
        rev_g, _ = pct["revenue_growth_yoy"]
        roe, _ = pct["roe"]
        roa, _ = pct["roa"]

        statements = await load_company_statements(self.session, company_id)
        latest = statements.latest()
        used: list[LineValue] = []

        def val(resolved: Resolved) -> Decimal | None:
            if not resolved.available:
                return None
            used.extend(resolved.sources)
            return resolved.value

        eps_now = val(bridge.eps(latest))
        five_back = statements.years_back(latest, 5) if latest is not None else None
        eps_5y = val(bridge.eps(five_back)) if five_back is not None else None
        bvps = val(bridge.book_value_per_share(latest))

        # Five-year average EPS growth: mean of the yearly values over the last
        # five periods, only with at least three of them (else unknown).
        eps_growth_by_period = await self._metric_by_period(company_id, "eps_growth_yoy")
        recent = statements.periods[:5]
        yearly = [
            Decimal(eps_growth_by_period[p.period_id]) / Decimal("100")
            for p in recent
            if p.period_id in eps_growth_by_period
        ]
        eps_growth_5y_avg = (
            sum(yearly, Decimal("0")) / Decimal(len(yearly)) if len(yearly) >= 3 else None
        )
        de_by_period = await self._metric_by_period(company_id, "debt_to_equity")
        de_5y = (
            Decimal(de_by_period[five_back.period_id])
            if five_back is not None and five_back.period_id in de_by_period
            else None
        )

        # R45 M4: the derived "cash dividends paid per share" is timing-noisy and
        # skips non-paying years, so it never feeds the dividend history checks
        # (dividend_stability / dividend_growing stay NOT_RUN until a declared-DPS
        # source exists). It is used once, as cash paid / EPS of the same year.
        dps_latest = bridge.dps(latest)
        earnings_payout = (
            dps_latest.value / eps_now
            if dps_latest.available
            and dps_latest.value is not None
            and eps_now is not None
            and eps_now > 0
            else None
        )

        pe_ratio = (
            price / eps_now
            if price is not None and eps_now is not None and eps_now > 0
            else None
        )
        pb_ratio = price / bvps if price is not None and bvps is not None and bvps > 0 else None

        merged = ScoreInputs(
            current_price=price,
            fair_value=fair_value,
            pe_ratio=pe_ratio,
            pb_ratio=pb_ratio,
            eps_growth_1y=eps_g,
            eps_now=eps_now,
            eps_5y_ago=eps_5y,
            eps_growth_now=eps_g,
            eps_growth_5y_avg=eps_growth_5y_avg,
            roe_now=roe,
            roa_now=roa,
            st_assets=val(bridge.line(latest, "current_assets")),
            st_liabilities=val(bridge.line(latest, "current_liabilities")),
            lt_liabilities=val(bridge.long_term_liabilities(latest)),
            de_ratio_now=de_now,
            de_ratio_5y_ago=de_5y,
            operating_cash_flow=val(bridge.line(latest, "cfo")),
            total_debt=val(bridge.line(latest, "interest_bearing_debt")),
            total_assets=val(bridge.line(latest, "total_assets")),
            total_equity=val(bridge.line(latest, "total_equity")),
            earnings_payout=earnings_payout,
            hist_earnings_growth=eps_g,
            hist_revenue_growth=rev_g,
        )
        metrics_used = {code: raw for code, (_v, raw) in pct.items() if raw is not None}
        if de_raw is not None:
            metrics_used["debt_to_equity"] = de_raw
        statement_lines = bridge.unique_sources(used)
        sources: dict[str, Any] = {
            "current_price": str(price) if price is not None else None,
            "price_as_of": price_as_of.isoformat() if price_as_of is not None else None,
            "fair_value": str(fair_value) if fair_value is not None else None,
            "fair_value_methodology_version": (
                fv_row.methodology_version if fv_row is not None else None
            ),
            "fair_value_computed_at": (
                fv_row.computed_at.isoformat() if fv_row is not None else None
            ),
            "metrics_used": metrics_used,
            "statements": [bridge.provenance(lv) for lv in statement_lines],
            "dps_derivation": bridge.DPS_DERIVATION,
            "dps_label": bridge.DPS_LABEL,
            "earnings_payout_basis": "cash dividends paid / EPS (same fiscal year)",
            "dps_history_checks": (
                "dividend_stability and dividend_growing not run: no declared-DPS source"
            ),
            "pe_pb_basis": (
                "price / latest annual EPS and BVPS (period-end shares); the price is "
                "current, the statement period is the age shown"
            ),
            "statement_period_end": (
                latest.period_end.isoformat() if latest is not None else None
            ),
            "statement_age_days": (
                (datetime.now(UTC).date() - latest.period_end).days
                if latest is not None
                else None
            ),
        }
        return (merged, sources)

    async def assess(
        self,
        company_id: uuid.UUID,
        margin_of_safety: Decimal = DEFAULT_MARGIN_OF_SAFETY,
    ) -> dict[str, Any]:
        """Resolve inputs (no caller overrides), compute, snapshot, serialize."""
        company = await self.companies.get_by_id(company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        as_of = datetime.now(UTC)

        profile_row = await self.profiles.resolve(
            company.egx_sector_id, company.gics_sub_industry_id
        )
        profile_key = (
            profile_row.profile_key
            if profile_row is not None
            else DEFAULT_SCORE_PROFILE_KEY
        )
        health_track = (
            profile_row.health_track
            if profile_row is not None
            else ("banks" if profile_key == "banks" else "standard")
        )

        dq_fs = await self.data_quality.latest(company_id, "financial_statements")
        dq_ph = await self.data_quality.latest(company_id, "price_history")

        merged, sources = await self._resolve_inputs(company_id)
        sources["dq_financial_statements"] = (
            {
                "score": dq_fs.score,
                "status": dq_fs.status.value,
                "as_of": dq_fs.as_of.isoformat(),
                "methodology_version": dq_fs.methodology_version,
            }
            if dq_fs is not None
            else None
        )
        sources["dq_price_history"] = (
            {
                "score": dq_ph.score,
                "status": dq_ph.status.value,
                "as_of": dq_ph.as_of.isoformat(),
                "methodology_version": dq_ph.methodology_version,
            }
            if dq_ph is not None
            else None
        )

        results = engine.run_checks(merged, health_track=health_track)
        components = engine.score_all_components(results)
        headline, headline_reason = engine.headline_score(components)
        n_run = sum(c.ran for c in components.values())

        present = [s.score for s in (dq_fs, dq_ph) if s is not None]
        dq_min = min(present) if present else None
        capped = (
            dq_fs is None
            or dq_ph is None
            or dq_fs.status.value == "MISSING"
            or dq_ph.status.value == "MISSING"
        )
        confidence = engine.confidence_for(dq_min, capped, n_run, len(results))
        zone = engine.buy_zone(merged.fair_value, merged.current_price, margin_of_safety)

        payload = self._payload(
            company_id=company.id,
            ticker=company.ticker,
            as_of=as_of,
            profile_key=profile_key,
            profile_version=(
                profile_row.methodology_version
                if profile_row is not None
                else SCORE_METHODOLOGY_VERSION
            ),
            health_track=health_track,
            headline=headline,
            headline_reason=headline_reason,
            components=components,
            results=results,
            n_run=n_run,
            confidence=confidence,
            zone=zone,
            margin_of_safety=margin_of_safety,
            merged=merged,
            sources=sources,
        )

        await self.snapshots.upsert_snapshot(
            company_id=company.id,
            profile_key=profile_key,
            headline=Decimal(str(headline)) if headline is not None else None,
            headline_status=payload["headline"]["status"],
            components=payload["components"],
            checks=payload["checks"],
            confidence=payload["confidence"],
            buy_zone=payload["buy_zone"],
            n_with_data=n_run,
            margin_of_safety=margin_of_safety,
            inputs_echo=payload["inputs_echo"],
            computed_at=as_of,
        )
        await self.session.flush()
        return payload

    async def latest_payload(self, company_id: uuid.UUID) -> dict[str, Any]:
        """Latest snapshot under the current methodology; null when unassessed."""
        company = await self.companies.get_by_id(company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")
        row = await self.snapshots.get_snapshot(company_id)
        assessment = (
            await self._payload_from_row(row, ticker=company.ticker)
            if row is not None
            else None
        )
        return {
            "company_id": str(company.id),
            "ticker": company.ticker,
            "assessment": assessment,
            "methodology_version": SCORE_METHODOLOGY_VERSION,
            "scale": SCORE_SCALE,
            "disclaimer": SCORE_DISCLAIMER,
        }

    def _payload(
        self,
        company_id: uuid.UUID,
        ticker: str,
        as_of: datetime,
        profile_key: str,
        profile_version: str,
        health_track: str,
        headline: float | None,
        headline_reason: str,
        components: dict[str, engine.ComponentResult],
        results: tuple[engine.CheckResult, ...],
        n_run: int,
        confidence: engine.Confidence,
        zone: dict[str, object],
        margin_of_safety: Decimal,
        merged: ScoreInputs,
        sources: dict[str, Any],
    ) -> dict[str, Any]:
        copy = engine.headline_label(headline)
        component_dicts = {k: components[k].as_dict() for k in engine.COMPONENT_ORDER}
        check_dicts = [r.as_dict() for r in results]
        echo_inputs: dict[str, Any] = {}
        for f in dataclasses.fields(merged):
            value = getattr(merged, f.name)
            if isinstance(value, tuple):
                echo_inputs[f.name] = [str(v) for v in value]
            elif value is None:
                echo_inputs[f.name] = None
            else:
                echo_inputs[f.name] = str(value)
        return {
            "company_id": str(company_id),
            "ticker": ticker,
            "as_of": as_of.date().isoformat(),
            "computed_at": as_of.isoformat(),
            "methodology_version": SCORE_METHODOLOGY_VERSION,
            "valuation_methodology_version": VALUATION_METHODOLOGY_VERSION,
            "profile": {
                "profile_id": profile_key,
                "methodology_version": profile_version,
                "health_track": health_track,
            },
            "headline": {
                "value": headline,
                "status": (
                    ComponentStatus.AVAILABLE.value
                    if headline is not None
                    else ComponentStatus.INSUFFICIENT_DATA.value
                ),
                "reason": headline_reason,
                "detail": copy["detail"],
            },
            "components": component_dicts,
            "checks": check_dicts,
            "checks_not_run": [
                r.check_key for r in results if r.status is engine.CheckStatus.NOT_RUN
            ],
            "n_with_data": n_run,
            "n_checks_total": len(results),
            "confidence": confidence.as_dict(),
            "buy_zone": dict(zone),
            "inputs_echo": {"inputs": echo_inputs, "sources": sources},
            "scale": SCORE_SCALE,
            "disclaimer": SCORE_DISCLAIMER,
        }

    async def _payload_from_row(
        self, row: InvestmentScore, *, ticker: str
    ) -> dict[str, Any]:
        checks = row.checks if isinstance(row.checks, list) else []
        not_run = [
            str(c.get("check_key"))
            for c in checks
            if isinstance(c, dict) and c.get("status") == "NOT_RUN"
        ]
        headline = float(row.headline) if row.headline is not None else None
        copy = engine.headline_label(headline)
        components = row.components if isinstance(row.components, dict) else {}
        # No migration: headline.reason is a pure function of the persisted
        # components, so re-derive it with the same engine call as assess().
        _, headline_reason = engine.headline_score(_rebuild_components(components))
        # Prefer the profile lookup keyed by the persisted profile_key; fall
        # back to which health checks ran, then to the assess() default.
        profile = await self.profiles.get_by_key(row.profile_key)
        if profile is not None:
            health_track = profile.health_track
        else:
            keys = {
                str(c.get("check_key"))
                for c in checks
                if isinstance(c, dict)
            }
            if any(k.startswith("bank_") for k in keys):
                health_track = "banks"
            elif any(k.startswith("health_") for k in keys):
                health_track = "standard"
            else:
                health_track = (
                    "banks" if row.profile_key == "banks" else "standard"
                )
        return {
            "company_id": str(row.company_id),
            "ticker": ticker,
            "as_of": row.computed_at.date().isoformat(),
            "computed_at": row.computed_at.isoformat(),
            "methodology_version": row.methodology_version,
            "valuation_methodology_version": VALUATION_METHODOLOGY_VERSION,
            "profile": {
                "profile_id": row.profile_key,
                "methodology_version": row.methodology_version,
                "health_track": health_track,
            },
            "headline": {
                "value": headline,
                "status": row.headline_status,
                "reason": headline_reason,
                "detail": copy["detail"],
            },
            "components": components,
            "checks": checks,
            "checks_not_run": not_run,
            "n_with_data": row.n_with_data,
            "n_checks_total": len(checks),
            "confidence": row.confidence if isinstance(row.confidence, dict) else {},
            "buy_zone": row.buy_zone if isinstance(row.buy_zone, dict) else {},
            "inputs_echo": row.inputs_echo if isinstance(row.inputs_echo, dict) else {},
            "scale": SCORE_SCALE,
            "disclaimer": SCORE_DISCLAIMER,
        }
