"""Metric service for orchestrating metric calculations.

Responsibilities:
- Load financial facts for a company and period
- Resolve metric dependencies
- Call calculation functions
- Handle missing data
- Persist results
- Return metric results with provenance
"""

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.metrics.definitions import (
    ALL_METRICS,
    MetricDefinition,
    MetricStatus,
    PeriodRequirement,
    get_metric,
)
from app.metrics.engine import METRIC_CALCULATORS
from app.metrics.period_selector import PeriodSelector
from app.models.financial import FinancialPeriod
from app.repositories.financial import FinancialFactRepository, FinancialPeriodRepository

logger = logging.getLogger(__name__)


class MetricCalculationInput(NamedTuple):
    """Input for a metric calculation."""
    metric: MetricDefinition
    facts: dict[str, Decimal | None]
    period: FinancialPeriod
    previous_period: FinancialPeriod | None = None
    previous_facts: dict[str, Decimal | None] | None = None
    shares_outstanding: Decimal | None = None


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


class MetricService:
    """Service for calculating financial metrics."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.period_repo = FinancialPeriodRepository(session)
        self.fact_repo = FinancialFactRepository(session)
        self.period_selector = PeriodSelector()

    def _get_period_type_value(self, period: FinancialPeriod) -> str:
        """Safely get period_type value whether it's an enum or string."""
        if hasattr(period.period_type, 'value'):
            return period.period_type.value
        return str(period.period_type)

    async def calculate_metrics_for_period(
        self,
        company_id: str,
        period_id: str,
        metric_codes: list[str] | None = None,
        as_of_date: date | None = None,
    ) -> list[MetricCalculationOutput]:
        """Calculate all metrics for a specific period.

        Args:
            company_id: Company UUID
            period_id: Financial period UUID
            metric_codes: Optional list of specific metrics to calculate
            as_of_date: If provided, only use facts published before this date

        Returns:
            List of metric calculation outputs
        """
        # Get the target period
        import uuid
        period = await self.period_repo.get_by_id(uuid.UUID(period_id))
        if not period:
            raise ValueError(f"Period {period_id} not found")

        # Get all periods for this company
        period_type_value = self._get_period_type_value(period)
        all_periods = await self.period_repo.list_periods(
            company_id=uuid.UUID(company_id),
            period_type=period_type_value,
        )

        # Select comparable periods (convert Sequence to list)
        period_pair = self.period_selector.select_comparable_periods(
            list(all_periods), period, as_of_date
        )

        # Get facts for current period
        current_facts = await self._get_facts_dict(company_id, period_id)

        # Get facts for previous period if available
        previous_facts = None
        if period_pair.previous:
            previous_facts = await self._get_facts_dict(
                company_id, str(period_pair.previous.id)
            )

        # Get company shares outstanding
        shares_outstanding = await self._get_shares_outstanding(company_id)

        # Determine which metrics to calculate
        metrics_to_calculate = []
        if metric_codes:
            for code in metric_codes:
                metric = get_metric(code)
                if metric:
                    metrics_to_calculate.append(metric)
        else:
            metrics_to_calculate = list(ALL_METRICS.values())

        # Calculate each metric
        results = []
        for metric in metrics_to_calculate:
            result = await self._calculate_single_metric(
                metric=metric,
                facts=current_facts,
                period=period,
                previous_period=period_pair.previous,
                previous_facts=previous_facts,
                shares_outstanding=shares_outstanding,
            )
            if result:
                results.append(result)

        return results

    async def calculate_all_metrics_for_company(
        self,
        company_id: str,
        fiscal_year: int | None = None,
        as_of_date: date | None = None,
    ) -> dict[str, list[MetricCalculationOutput]]:
        """Calculate all metrics for all periods of a company.

        Returns:
            Dictionary mapping period_id to list of metric results
        """
        import uuid

        # Get all periods
        periods = await self.period_repo.list_periods(
            company_id=uuid.UUID(company_id),
        )

        # Filter by fiscal year if specified
        if fiscal_year:
            periods = [p for p in periods if p.fiscal_year == fiscal_year]

        # Calculate metrics for each period
        results = {}
        for period in periods:
            period_results = await self.calculate_metrics_for_period(
                company_id=company_id,
                period_id=str(period.id),
                as_of_date=as_of_date,
            )
            results[str(period.id)] = period_results

        return results

    async def _calculate_single_metric(
        self,
        metric: MetricDefinition,
        facts: dict[str, Decimal | None],
        period: FinancialPeriod,
        previous_period: FinancialPeriod | None,
        previous_facts: dict[str, Decimal | None] | None,
        shares_outstanding: Decimal | None,
    ) -> MetricCalculationOutput | None:
        """Calculate a single metric."""
        # Check if required facts are available
        missing_facts = []
        for fact_label in metric.required_fact_labels:
            if fact_label not in facts or facts[fact_label] is None:
                missing_facts.append(fact_label)

        # For metrics requiring comparable periods, check previous facts
        if (
            metric.period_requirement == PeriodRequirement.COMPARABLE
            and (previous_period is None or previous_facts is None)
        ):
            # Check if this metric needs previous period facts
            needs_previous = any(
                label in metric.required_fact_labels
                for label in ["total_equity", "total_assets"]
            )
            if needs_previous and not previous_facts:
                return MetricCalculationOutput(
                    metric_code=metric.code,
                    display_name=metric.display_name,
                    value=None,
                    unit=metric.unit,
                    status=MetricStatus.INSUFFICIENT_DATA,
                    reason="Previous comparable period is unavailable",
                        warnings=None,
                        formula_version=metric.formula_version,
                        period_id=str(period.id),
                        fiscal_year=period.fiscal_year,
                        period_type=self._get_period_type_value(period),
                        provenance={},
                        calculated_at=datetime.now(UTC),
                    )

        # If required facts are missing, return insufficient data
        if missing_facts:
            return MetricCalculationOutput(
                metric_code=metric.code,
                display_name=metric.display_name,
                value=None,
                unit=metric.unit,
                status=MetricStatus.INSUFFICIENT_DATA,
                reason=f"Missing required facts: {', '.join(missing_facts)}",
                warnings=None,
                formula_version=metric.formula_version,
                period_id=str(period.id),
                fiscal_year=period.fiscal_year,
                period_type=self._get_period_type_value(period),
                provenance={},
                calculated_at=datetime.now(UTC),
            )

        # Get the calculation function
        calc_func = METRIC_CALCULATORS.get(metric.code)
        if not calc_func:
            return MetricCalculationOutput(
                metric_code=metric.code,
                display_name=metric.display_name,
                value=None,
                unit=metric.unit,
                status=MetricStatus.NOT_APPLICABLE,
                reason="No calculator implemented for this metric",
                warnings=None,
                formula_version=metric.formula_version,
                period_id=str(period.id),
                fiscal_year=period.fiscal_year,
                period_type=self._get_period_type_value(period),
                provenance={},
                calculated_at=datetime.now(UTC),
            )

        # Prepare calculation inputs
        calc_input = self._prepare_calculation_input(
            metric=metric,
            facts=facts,
            previous_facts=previous_facts,
            shares_outstanding=shares_outstanding,
        )

        # Call the calculation function
        try:
            result = calc_func(**calc_input)
        except Exception as e:
            logger.error("Error calculating %s: %s", metric.code, e)
            return MetricCalculationOutput(
                metric_code=metric.code,
                display_name=metric.display_name,
                value=None,
                unit=metric.unit,
                status=MetricStatus.INVALID,
                reason=f"Calculation error: {str(e)}",
                warnings=None,
                formula_version=metric.formula_version,
                period_id=str(period.id),
                fiscal_year=period.fiscal_year,
                period_type=self._get_period_type_value(period),
                provenance={},
                calculated_at=datetime.now(UTC),
            )

        # Build provenance
        provenance = self._build_provenance(metric, facts, previous_facts)

        return MetricCalculationOutput(
            metric_code=metric.code,
            display_name=metric.display_name,
            value=result.value,
            unit=metric.unit,
            status=result.status,
            reason=result.reason,
            warnings=result.warnings,
            formula_version=metric.formula_version,
            period_id=str(period.id),
            fiscal_year=period.fiscal_year,
            period_type=self._get_period_type_value(period),
            provenance=provenance,
            calculated_at=datetime.now(UTC),
        )

    def _prepare_calculation_input(
        self,
        metric: MetricDefinition,
        facts: dict[str, Decimal | None],
        previous_facts: dict[str, Decimal | None] | None,
        shares_outstanding: Decimal | None,
    ) -> dict:
        """Prepare inputs for the calculation function."""
        calc_func = METRIC_CALCULATORS.get(metric.code)
        if not calc_func:
            return {}

        import inspect
        sig = inspect.signature(calc_func)
        params = list(sig.parameters.keys())

        inputs = {}
        for param in params:
            if param in facts:
                inputs[param] = facts[param]
            elif param.startswith("previous_") and previous_facts:
                base_label = param[9:]  # Remove "previous_" prefix
                inputs[param] = previous_facts.get(base_label)
            elif param == "shares_outstanding":
                inputs[param] = shares_outstanding
            elif param == "current_equity":
                inputs[param] = facts.get("total_equity")
            elif param == "previous_equity" and previous_facts:
                inputs[param] = previous_facts.get("total_equity")
            elif param == "current_assets":
                inputs[param] = facts.get("total_assets")
            elif param == "previous_assets" and previous_facts:
                inputs[param] = previous_facts.get("total_assets")
            elif param == "inventory":
                inputs[param] = facts.get("inventory")
            elif param == "prepaid_expenses":
                inputs[param] = facts.get("prepaid_expenses")

        return inputs

    def _build_provenance(
        self,
        metric: MetricDefinition,
        facts: dict[str, Decimal | None],
        previous_facts: dict[str, Decimal | None] | None,
    ) -> dict[str, str | None]:
        """Build provenance information for a metric."""
        provenance: dict[str, str | None] = {}
        for fact_label in metric.required_fact_labels:
            if fact_label in facts:
                provenance[fact_label] = f"value={facts[fact_label]}"
            else:
                provenance[fact_label] = None

        return provenance

    async def _get_facts_dict(
        self,
        company_id: str,
        period_id: str,
    ) -> dict[str, Decimal | None]:
        """Get financial facts as a dictionary mapping normalized_label to value."""
        import uuid

        facts = await self.fact_repo.list_facts(
            company_id=uuid.UUID(company_id),
        )

        # Filter to facts for this period and build dictionary
        facts_dict = {}
        for fact in facts:
            if str(fact.period_id) == period_id:
                label = fact.normalized_label or fact.reported_label
                facts_dict[label] = (
                    fact.reported_value if fact.normalized_value is None else fact.normalized_value
                )

        return facts_dict

    async def _get_shares_outstanding(
        self,
        company_id: str,
    ) -> Decimal | None:
        """Get shares outstanding for a company."""
        import uuid

        from app.repositories.company import CompanyRepository

        company_repo = CompanyRepository(self.session)
        company = await company_repo.get_by_id(uuid.UUID(company_id))
        if company:
            return company.shares_outstanding
        return None
