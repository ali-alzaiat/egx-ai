"""R43 coverage report (AC-9): per-engine non-null headline coverage. Read-only.

    python -m app.services.coverage_report

Population: companies with at least one approved/auto-validated statement line
and at least one price bar. For each engine it prints the share with a
non-null headline, the share that is provisional (vendor data) and the top
INSUFFICIENT reasons. Nothing is written.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.models.compute import ComputeState
from app.models.financial import FinancialPeriod
from app.models.market import DailyPrice
from app.models.metrics import FinancialMetric, MetricStatusDB
from app.models.scores import InvestmentScore
from app.models.screening import ScreeningPurificationEstimate, ShariahScreeningResult
from app.models.statements import FinancialStatementLine
from app.models.technical import IndicatorStatusDB, TechnicalIndicator
from app.models.thesis import InvestmentThesis
from app.models.valuation import ValuationFairValue
from app.repositories.statements import CalculationStatuses

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class EngineCoverage:
    name: str
    population: int
    with_headline: int = 0
    provisional: int = 0
    reasons: Counter[str] = field(default_factory=Counter)
    distribution: Counter[str] = field(default_factory=Counter)

    def lines(self) -> list[str]:
        pct = (100.0 * self.with_headline / self.population) if self.population else 0.0
        prov = (100.0 * self.provisional / self.population) if self.population else 0.0
        out = [
            f"{self.name:<13} non-null {self.with_headline}/{self.population} ({pct:.1f}%), "
            f"provisional {prov:.1f}%"
        ]
        if self.distribution:
            out.append(
                "    distribution: "
                + ", ".join(f"{k}={v}" for k, v in self.distribution.most_common())
            )
        for reason, n in self.reasons.most_common(5):
            out.append(f"    {n:>4} x {reason[:140]}")
        return out


async def _population(session: AsyncSession) -> list[uuid.UUID]:
    with_lines = select(FinancialStatementLine.company_id).where(
        FinancialStatementLine.ext_status.in_(CalculationStatuses)
    )
    with_prices = select(DailyPrice.company_id)
    result = (
        await session.execute(
            select(func.distinct(FinancialStatementLine.company_id))
            .where(FinancialStatementLine.company_id.in_(with_lines))
            .where(FinancialStatementLine.company_id.in_(with_prices))
        )
    )
    rows: list[uuid.UUID] = list(result.scalars().all())
    return list(rows)


async def build_report(session: AsyncSession) -> list[EngineCoverage]:
    ids = await _population(session)
    n = len(ids)
    states = (
        await session.execute(select(ComputeState).where(ComputeState.company_id.in_(ids)))
    ).scalars().all()
    provisional: dict[str, set[uuid.UUID]] = {}
    for st in states:
        if st.provisional:
            provisional.setdefault(st.engine, set()).add(st.company_id)

    def cov(name: str, engine: str) -> EngineCoverage:
        return EngineCoverage(name, n, provisional=len(provisional.get(engine, set())))

    metrics = cov("metrics", "metrics")
    latest_end = (
        select(FinancialMetric.company_id, func.max(FinancialPeriod.end_date).label("end"))
        .join(FinancialPeriod, FinancialMetric.period_id == FinancialPeriod.id)
        .where(FinancialMetric.company_id.in_(ids))
        .group_by(FinancialMetric.company_id)
        .subquery()
    )
    metric_rows = (
        await session.execute(
            select(FinancialMetric.company_id, FinancialMetric.status, FinancialMetric.reason)
            .join(FinancialPeriod, FinancialMetric.period_id == FinancialPeriod.id)
            .join(
                latest_end,
                (latest_end.c.company_id == FinancialMetric.company_id)
                & (latest_end.c.end == FinancialPeriod.end_date),
            )
        )
    ).all()
    available = {cid for cid, status, _ in metric_rows if status == MetricStatusDB.AVAILABLE}
    metrics.with_headline = len(available)
    metrics.reasons.update(r for _, s, r in metric_rows if s != MetricStatusDB.AVAILABLE and r)

    fair = cov("fair_value", "fair_value")
    for row in (
        await session.execute(
            select(ValuationFairValue).where(ValuationFairValue.company_id.in_(ids))
        )
    ).scalars():
        if row.fair_value is not None:
            fair.with_headline += 1
        else:
            echo = row.inputs_echo if isinstance(row.inputs_echo, dict) else {}
            payload = echo.get("payload") if isinstance(echo.get("payload"), dict) else {}
            reason = (payload or {}).get("fair_value", {}).get("reason")
            fair.reasons[str(reason)] += 1

    score = cov("score", "score")
    for srow in (
        await session.execute(select(InvestmentScore).where(InvestmentScore.company_id.in_(ids)))
    ).scalars():
        if srow.headline is not None:
            score.with_headline += 1
        else:
            score.reasons[srow.headline_status] += 1

    shariah = cov("shariah", "shariah")
    for res in (
        await session.execute(
            select(ShariahScreeningResult).where(ShariahScreeningResult.company_id.in_(ids))
        )
    ).scalars():
        shariah.distribution[res.status.value] += 1
        if res.is_compliant is not None:
            shariah.with_headline += 1
        else:
            shariah.reasons[res.overall_reason] += 1

    purification = cov("purification", "purification")
    for est in (
        await session.execute(
            select(ScreeningPurificationEstimate).where(
                ScreeningPurificationEstimate.company_id.in_(ids)
            )
        )
    ).scalars():
        if est.status == "OK":
            purification.with_headline += 1
        else:
            purification.reasons[str(est.reason)] += 1

    technical = cov("technical", "technical")
    tech_ok = (
        await session.execute(
            select(func.count(func.distinct(TechnicalIndicator.company_id)))
            .where(TechnicalIndicator.company_id.in_(ids))
            .where(TechnicalIndicator.status == IndicatorStatusDB.AVAILABLE)
        )
    ).scalar_one()
    technical.with_headline = int(tech_ok)

    thesis = cov("thesis", "thesis")
    thesis.with_headline = int(
        (
            await session.execute(
                select(func.count(InvestmentThesis.id)).where(
                    InvestmentThesis.company_id.in_(ids)
                )
            )
        ).scalar_one()
    )

    failed = Counter(st.engine for st in states if st.status == "failed")
    for item in (metrics, fair, score, shariah, purification, technical, thesis):
        if failed.get(item.name):
            item.reasons["computation failed (see company_compute_state.error)"] = failed[
                item.name
            ]
    return [metrics, fair, score, shariah, purification, technical, thesis]


def main() -> int:  # pragma: no cover - CLI wrapper
    async def _run() -> list[EngineCoverage]:
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            return await build_report(session)

    report = asyncio.run(_run())
    population = report[0].population if report else 0
    print(f"R43 coverage over {population} companies with statement lines and prices")
    for item in report:
        print("\n".join(item.lines()))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
