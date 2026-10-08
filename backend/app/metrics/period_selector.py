"""Period selection logic for financial metrics.

Handles:
- Selecting comparable periods for growth/average calculations
- Ensuring period compatibility (annual vs quarterly)
- Publication date awareness
- Look-ahead bias prevention
"""

from datetime import date
from typing import NamedTuple

from app.models.financial import FinancialPeriod


class PeriodPair(NamedTuple):
    """A pair of comparable periods (current and previous)."""
    current: FinancialPeriod
    previous: FinancialPeriod | None


class PeriodSelector:
    """Selects comparable financial periods for metric calculations."""

    def select_comparable_periods(
        self,
        periods: list[FinancialPeriod],
        target_period: FinancialPeriod,
        as_of_date: date | None = None,
    ) -> PeriodPair:
        """Select the target period and its comparable previous period.

        Args:
            periods: All available periods for the company
            target_period: The period we want to calculate metrics for
            as_of_date: If provided, only include periods with publication_date <= as_of_date

        Returns:
            PeriodPair with current and previous comparable period
        """
        # Drop periods not published as of as_of_date (look-ahead prevention).
        # target_period itself is never dropped from the returned pair.
        if as_of_date is not None:
            periods = self.filter_by_publication_date(periods, as_of_date)

        # Filter to same period type
        same_type = [
            p for p in periods
            if p.period_type == target_period.period_type
        ]

        # Sort by fiscal year descending
        same_type.sort(key=lambda p: p.fiscal_year, reverse=True)

        # Find the target period index
        target_idx = None
        for idx, period in enumerate(same_type):
            if period.id == target_period.id:
                target_idx = idx
                break

        if target_idx is None:
            return PeriodPair(current=target_period, previous=None)

        # Previous period is the next one in the sorted list (lower fiscal year)
        previous = same_type[target_idx + 1] if target_idx + 1 < len(same_type) else None

        return PeriodPair(current=target_period, previous=previous)

    def get_previous_comparable(
        self,
        periods: list[FinancialPeriod],
        target_period: FinancialPeriod,
    ) -> FinancialPeriod | None:
        """Get just the previous comparable period."""
        pair = self.select_comparable_periods(periods, target_period)
        return pair.previous

    def get_periods_for_metric(
        self,
        periods: list[FinancialPeriod],
        metric_code: str,
        as_of_date: date | None = None,
    ) -> list[FinancialPeriod]:
        """Get all periods relevant for a specific metric.

        For single-period metrics, returns all matching periods.
        For comparable metrics, returns periods that have comparables.
        """
        from app.metrics.definitions import PeriodRequirement, get_metric

        metric = get_metric(metric_code)
        if metric is None:
            return []

        if metric.period_requirement == PeriodRequirement.SINGLE:
            return periods

        # For comparable metrics, filter to periods that have comparables
        result = []
        for period in periods:
            pair = self.select_comparable_periods(periods, period, as_of_date)
            if pair.previous is not None:
                result.append(period)

        return result

    def filter_by_publication_date(
        self,
        periods: list[FinancialPeriod],
        as_of_date: date,
    ) -> list[FinancialPeriod]:
        """Filter periods to only those published before or on as_of_date.

        This prevents look-ahead bias in backtesting. Periods with no
        documents are excluded: without a source we cannot prove the
        information was available by as_of_date.
        """
        result = []
        for period in periods:
            # Keep the period if any document for it was published by as_of_date
            if hasattr(period, 'documents') and period.documents:
                for doc in period.documents:
                    if doc.publication_date and doc.publication_date <= as_of_date:
                        result.append(period)
                        break

        return result

    def validate_period_compatibility(
        self,
        period1: FinancialPeriod,
        period2: FinancialPeriod,
    ) -> bool:
        """Check if two periods are comparable (same type)."""
        return period1.period_type == period2.period_type
