"""Metric service: statement lines -> metric snapshots (R43 bridge).

Inputs come only from approved statement lines through ``app.statements.bridge``
and are passed **explicitly per metric** (no signature introspection). The
legacy FinancialFact path no longer feeds any metric.

- Every ANNUAL period with lines is computed (history powers the score's
  multi-year checks and the thesis).
- A missing required line is INSUFFICIENT_DATA whose reason names the line;
  a missing prior period names the absent year. Zero / negative denominators
  keep the engine's own statuses. Nothing is zero-filled.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, NamedTuple

from sqlalchemy import delete, select

from app.metrics.definitions import ALL_METRICS, MetricDefinition, MetricStatus
from app.metrics.engine import METRIC_CALCULATORS
from app.models.metrics import FinancialMetric, FinancialMetricInput, MetricStatusDB
from app.statements import bridge
from app.statements.bridge import CompanyStatements, LineValue, PeriodLines, Resolved

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

#: Compute-state version of the statement -> metrics mapping (each metric keeps
#: its own ``formula_version``).
METRICS_INPUT_VERSION = "metrics-stmt-1.1"


class MetricCalculationOutput(NamedTuple):
    """Output of a metric calculation."""

    metric_code: str
    display_name: str
    value: Decimal | None
    unit: str
    status: MetricStatus
    reason: str | None
    warnings: list[str] | None
    formula_version: int
    period_id: str
    fiscal_year: int
    period_type: str
    provenance: dict[str, str | None]
    calculated_at: datetime
    inputs: tuple[tuple[str, LineValue], ...] = ()
    source_tier: str | None = None
    provisional: bool = False
    period_end: date | None = None


class _Arg(NamedTuple):
    """One calculator kwarg: its resolved value and whether None is allowed."""

    resolved: Resolved
    optional: bool = False
    prior_code: str | None = None  # set when the kwarg reads the prior period


_InputMap = Callable[[CompanyStatements, PeriodLines], dict[str, _Arg]]


def _prior(bundle: CompanyStatements, p: PeriodLines, code: str, *, optional: bool = False) -> _Arg:
    prior = bundle.prior(p)
    if prior is None:
        return _Arg(
            Resolved(
                None, "INSUFFICIENT_DATA",
                f"no prior period: FY{p.fiscal_year - 1} has no {code}", code,
            ),
            optional=optional,
            prior_code=code,
        )
    resolved = bridge.line(prior, code)
    if not resolved.available:
        resolved = Resolved(
            None, "INSUFFICIENT_DATA",
            f"no prior period: FY{p.fiscal_year - 1} has no {code}", code,
        )
    return _Arg(resolved, optional=optional, prior_code=code)


def _prior_eps(bundle: CompanyStatements, p: PeriodLines) -> _Arg:
    prior = bundle.prior(p)
    resolved = bridge.eps(prior) if prior is not None else None
    if resolved is None or not resolved.available:
        return _Arg(
            Resolved(
                None, "INSUFFICIENT_DATA",
                f"no prior period: FY{p.fiscal_year - 1} has no eps", "eps",
            ),
            prior_code="eps",
        )
    return _Arg(resolved, prior_code="eps")


def _ln(p: PeriodLines, code: str, *, optional: bool = False) -> _Arg:
    return _Arg(bridge.line(p, code), optional=optional)


#: Metric code -> explicit calculator kwargs (R43 section 1.5 table).
METRIC_INPUTS: dict[str, _InputMap] = {
    "revenue_growth_yoy": lambda b, p: {
        "current_revenue": _ln(p, "revenue"),
        "previous_revenue": _prior(b, p, "revenue"),
    },
    "net_income_growth_yoy": lambda b, p: {
        "current_net_income": _ln(p, "net_income"),
        "previous_net_income": _prior(b, p, "net_income"),
    },
    "eps_growth_yoy": lambda b, p: {
        "current_eps": _Arg(bridge.eps(p)),
        "previous_eps": _prior_eps(b, p),
    },
    "gross_margin": lambda b, p: {
        "gross_profit": _ln(p, "gross_profit"),
        "revenue": _ln(p, "revenue"),
    },
    "operating_margin": lambda b, p: {
        "operating_income": _ln(p, "operating_profit"),
        "revenue": _ln(p, "revenue"),
    },
    "net_margin": lambda b, p: {
        "net_income": _ln(p, "net_income"),
        "revenue": _ln(p, "revenue"),
    },
    "roe": lambda b, p: {
        "net_income": _ln(p, "net_income"),
        "current_equity": _ln(p, "total_equity"),
        "previous_equity": _prior(b, p, "total_equity"),
    },
    "roa": lambda b, p: {
        "net_income": _ln(p, "net_income"),
        "current_assets": _ln(p, "total_assets"),
        "previous_assets": _prior(b, p, "total_assets"),
    },
    "debt_to_equity": lambda b, p: {
        "total_debt": _ln(p, "interest_bearing_debt"),
        "total_equity": _ln(p, "total_equity"),
    },
    "debt_to_assets": lambda b, p: {
        "total_debt": _ln(p, "interest_bearing_debt"),
        "total_assets": _ln(p, "total_assets"),
    },
    "current_ratio": lambda b, p: {
        "current_assets": _ln(p, "current_assets"),
        "current_liabilities": _ln(p, "current_liabilities"),
    },
    "quick_ratio": lambda b, p: {
        "current_assets": _ln(p, "current_assets"),
        "current_liabilities": _ln(p, "current_liabilities"),
        "inventory": _ln(p, "inventory"),
    },
    "operating_cash_flow_margin": lambda b, p: {
        "operating_cash_flow": _ln(p, "cfo"),
        "revenue": _ln(p, "revenue"),
    },
    "free_cash_flow": lambda b, p: {
        "operating_cash_flow": _ln(p, "cfo"),
        "capex": _Arg(bridge.capex_magnitude(p)),
    },
    "free_cash_flow_margin": lambda b, p: {
        "operating_cash_flow": _ln(p, "cfo"),
        "capex": _Arg(bridge.capex_magnitude(p)),
        "revenue": _ln(p, "revenue"),
    },
    "eps": lambda b, p: {"eps_basic": _Arg(bridge.eps(p))},
    "book_value_per_share": lambda b, p: {
        "total_equity": _ln(p, "total_equity"),
        "shares_outstanding": _ln(p, "shares_outstanding"),
    },
}


def _status_enum(raw: MetricStatus) -> MetricStatus:
    return raw if isinstance(raw, MetricStatus) else MetricStatus(raw)


class MetricService:
    """Calculate and persist financial metrics from statement lines."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def calculate_from_statements(
        self, bundle: CompanyStatements
    ) -> list[MetricCalculationOutput]:
        """Every metric for every ANNUAL period in the bundle (pure, no I/O)."""
        out: list[MetricCalculationOutput] = []
        for period in bundle.periods:
            for metric in ALL_METRICS.values():
                out.append(self._calculate(bundle, period, metric))
        return out

    def _calculate(
        self, bundle: CompanyStatements, p: PeriodLines, metric: MetricDefinition
    ) -> MetricCalculationOutput:
        now = datetime.now(UTC)

        def result(
            value: Decimal | None,
            status: MetricStatus,
            reason: str | None,
            warnings: list[str] | None,
            inputs: tuple[tuple[str, LineValue], ...],
        ) -> MetricCalculationOutput:
            tier = bridge.tier_of(lv for _, lv in inputs)
            return MetricCalculationOutput(
                metric_code=metric.code,
                display_name=metric.display_name,
                value=value,
                unit=metric.unit,
                status=status,
                reason=reason,
                warnings=warnings,
                formula_version=metric.formula_version,
                period_id=str(p.period_id),
                fiscal_year=p.fiscal_year,
                period_type=p.period_type,
                provenance={role: str(lv.line_id) for role, lv in inputs},
                calculated_at=now,
                inputs=inputs,
                source_tier=tier,
                provisional=tier == "vendor",
                period_end=p.period_end,
            )

        mapper = METRIC_INPUTS.get(metric.code)
        calc = METRIC_CALCULATORS.get(metric.code)
        if mapper is None or calc is None:
            return result(
                None, MetricStatus.NOT_APPLICABLE,
                "No calculator implemented for this metric", None, (),
            )
        args = mapper(bundle, p)
        for arg in args.values():
            if not arg.optional and not arg.resolved.available:
                return result(None, MetricStatus.INSUFFICIENT_DATA, arg.resolved.reason, None, ())
        kwargs = {name: arg.resolved.value for name, arg in args.items()}
        inputs: list[tuple[str, LineValue]] = []
        seen: set[tuple[str, uuid.UUID]] = set()
        for name, arg in args.items():
            for lv in arg.resolved.sources:
                if (name, lv.line_id) not in seen:
                    seen.add((name, lv.line_id))
                    inputs.append((name, lv))
        try:
            calc_result = calc(**kwargs)
        except (ArithmeticError, TypeError, ValueError) as exc:
            logger.error("Error calculating %s: %s", metric.code, exc)
            return result(
                None, MetricStatus.INVALID, f"Calculation error: {exc}", None, tuple(inputs)
            )
        return result(
            calc_result.value,
            _status_enum(calc_result.status),
            calc_result.reason,
            calc_result.warnings,
            tuple(inputs),
        )

    async def replace_company_metrics(
        self, company_id: uuid.UUID, outputs: list[MetricCalculationOutput]
    ) -> int:
        """Replace this company's metric rows (every formula version of these codes)."""
        # All versions: a formula bump must not leave older-version rows behind
        # for readers that pick "the latest" per metric.
        await self.session.execute(
            delete(FinancialMetric).where(
                FinancialMetric.company_id == company_id,
                FinancialMetric.metric_code.in_(list(ALL_METRICS)),
            )
        )
        for output in outputs:
            row = FinancialMetric(
                company_id=company_id,
                period_id=uuid.UUID(output.period_id),
                metric_code=output.metric_code,
                display_name=output.display_name,
                value=output.value,
                unit=output.unit,
                status=MetricStatusDB(output.status.value),
                reason=output.reason,
                warnings="; ".join(output.warnings) if output.warnings else None,
                formula_version=output.formula_version,
                source_tier=output.source_tier,
                provisional=output.provisional,
                calculated_at=output.calculated_at,
            )
            self.session.add(row)
            await self.session.flush()
            for role, lv in output.inputs:
                self.session.add(
                    FinancialMetricInput(
                        metric_id=row.id, statement_line_id=lv.line_id, input_role=role
                    )
                )
        await self.session.flush()
        return len(outputs)

    async def compute_and_persist(self, bundle: CompanyStatements) -> list[MetricCalculationOutput]:
        outputs = self.calculate_from_statements(bundle)
        await self.replace_company_metrics(bundle.company_id, outputs)
        return outputs

    async def input_provenance(
        self, metric_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[dict[str, str | int | bool | None]]]:
        """Provenance (section 1.4 shape + ``input_role``) of each metric's input lines."""
        if not metric_ids:
            return {}
        from app.models.financial import FinancialDocument, FinancialPeriod
        from app.models.statements import ExtractionMethod, FinancialStatementLine

        rows = (
            await self.session.execute(
                select(FinancialMetricInput, FinancialStatementLine, FinancialPeriod)
                .join(
                    FinancialStatementLine,
                    FinancialMetricInput.statement_line_id == FinancialStatementLine.id,
                )
                .join(FinancialPeriod, FinancialStatementLine.period_id == FinancialPeriod.id)
                .where(FinancialMetricInput.metric_id.in_(metric_ids))
                .order_by(FinancialMetricInput.input_role)
            )
        ).all()
        doc_ids = {ln.source_document_id for _, ln, _ in rows if ln.source_document_id}
        docs: dict[uuid.UUID, FinancialDocument] = {}
        if doc_ids:
            docs = {
                d.id: d
                for d in (
                    await self.session.execute(
                        select(FinancialDocument).where(FinancialDocument.id.in_(doc_ids))
                    )
                ).scalars().all()
            }
        out: dict[uuid.UUID, list[dict[str, str | int | bool | None]]] = {}
        for inp, ln, period in rows:
            doc = docs.get(ln.source_document_id) if ln.source_document_id else None
            lv = LineValue(
                code=ln.ontology_code,
                value=Decimal(ln.value) if ln.value is not None else Decimal(0),
                line_id=ln.id,
                period_id=ln.period_id,
                fiscal_year=int(period.fiscal_year),
                period_end=period.end_date,
                source_tier=(
                    "vendor"
                    if ln.extraction_method == ExtractionMethod.vendor_aggregator
                    else "filing"
                ),
                document_id=ln.source_document_id,
                document_type=doc.document_type if doc else None,
                document_url=doc.document_url if doc else None,
                source_label_reported=ln.source_label_reported,
                source_page=ln.source_page,
                published_date=ln.published_date,
            )
            item: dict[str, str | int | bool | None] = {
                "statement_line_id": str(ln.id),
                "input_role": inp.input_role,
            }
            item.update(bridge.provenance(lv))
            if ln.value is None:
                item["value"] = None
            out.setdefault(inp.metric_id, []).append(item)
        return out
