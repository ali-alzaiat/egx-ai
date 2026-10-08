"""Tests for period selection logic."""

import uuid
from datetime import date

from app.metrics.period_selector import PeriodSelector
from app.models.financial import FinancialDocument, FinancialPeriod, ReportingPeriodType


def create_period(
    fiscal_year: int,
    period_type: ReportingPeriodType = ReportingPeriodType.ANNUAL,
    publication_date: date | None = None,
) -> FinancialPeriod:
    """Create a test financial period.

    If publication_date is given, the period gets one source document with
    that publication date; otherwise it has no documents.
    """
    period = FinancialPeriod(
        id=uuid.uuid4(),
        company_id=uuid.uuid4(),
        period_type=period_type,
        fiscal_year=fiscal_year,
        fiscal_quarter=None,
        start_date=date(fiscal_year, 1, 1),
        end_date=date(fiscal_year, 12, 31),
    )
    if publication_date is not None:
        period.documents = [
            FinancialDocument(
                period_id=period.id,
                source_id=uuid.uuid4(),
                document_type="ANNUAL_REPORT",
                publication_date=publication_date,
            )
        ]
    return period


class TestPeriodSelector:
    def setup_method(self):
        self.selector = PeriodSelector()

    def test_select_comparable_periods_finds_previous(self):
        periods = [
            create_period(2025),
            create_period(2024),
            create_period(2023),
        ]
        target = periods[0]  # 2025

        pair = self.selector.select_comparable_periods(periods, target)

        assert pair.current == target
        assert pair.previous is not None
        assert pair.previous.fiscal_year == 2024

    def test_select_comparable_periods_no_previous(self):
        periods = [
            create_period(2025),
        ]
        target = periods[0]

        pair = self.selector.select_comparable_periods(periods, target)

        assert pair.current == target
        assert pair.previous is None

    def test_select_comparable_periods_same_type_only(self):
        periods = [
            create_period(2025, ReportingPeriodType.ANNUAL),
            create_period(2024, ReportingPeriodType.Q1),
            create_period(2023, ReportingPeriodType.ANNUAL),
        ]
        target = periods[0]  # 2025 ANNUAL

        pair = self.selector.select_comparable_periods(periods, target)

        assert pair.current == target
        assert pair.previous is not None
        assert pair.previous.fiscal_year == 2023
        assert pair.previous.period_type == ReportingPeriodType.ANNUAL

    def test_get_previous_comparable(self):
        periods = [
            create_period(2025),
            create_period(2024),
        ]
        target = periods[0]

        previous = self.selector.get_previous_comparable(periods, target)

        assert previous is not None
        assert previous.fiscal_year == 2024

    def test_validate_period_compatibility(self):
        period1 = create_period(2025, ReportingPeriodType.ANNUAL)
        period2 = create_period(2024, ReportingPeriodType.ANNUAL)
        period3 = create_period(2025, ReportingPeriodType.Q1)

        assert self.selector.validate_period_compatibility(period1, period2) is True
        assert self.selector.validate_period_compatibility(period1, period3) is False

    def test_get_periods_for_metric_single(self):
        periods = [
            create_period(2025),
            create_period(2024),
            create_period(2023),
        ]

        # For single-period metrics, all periods should be returned
        result = self.selector.get_periods_for_metric(periods, "gross_margin")
        assert len(result) == 3

    def test_get_periods_for_metric_comparable(self):
        periods = [
            create_period(2025),
            create_period(2024),
            create_period(2023),
        ]

        # For comparable metrics, only periods with comparables should be returned
        result = self.selector.get_periods_for_metric(periods, "roe")
        assert len(result) == 2  # 2025 and 2024 have comparables, 2023 doesn't

    def test_as_of_date_excludes_later_publications(self):
        target = create_period(2023, publication_date=date(2024, 4, 15))
        late = create_period(2022, publication_date=date(2024, 8, 15))

        pair = self.selector.select_comparable_periods(
            [target, late], target, as_of_date=date(2024, 7, 1)
        )

        assert pair.current == target
        assert pair.previous is None

    def test_as_of_date_includes_earlier_publications(self):
        target = create_period(2023, publication_date=date(2024, 4, 15))
        earlier = create_period(2022, publication_date=date(2024, 7, 1))

        pair = self.selector.select_comparable_periods(
            [target, earlier], target, as_of_date=date(2024, 7, 1)
        )

        assert pair.current == target
        assert pair.previous == earlier

    def test_period_without_documents_excluded_when_as_of_given(self):
        target = create_period(2023, publication_date=date(2024, 4, 15))
        docless = create_period(2022)

        pair = self.selector.select_comparable_periods(
            [target, docless], target, as_of_date=date(2024, 7, 1)
        )

        assert pair.current == target
        assert pair.previous is None

    def test_no_as_of_date_keeps_current_behaviour(self):
        target = create_period(2024)
        earlier = create_period(2023)

        pair = self.selector.select_comparable_periods([target, earlier], target)

        assert pair.current == target
        assert pair.previous == earlier

    def test_target_without_qualifying_documents_yields_no_previous(self):
        # Target has no documents; earlier period fully qualifies but the
        # target failing the publication filter collapses previous to None.
        target = create_period(2023)
        earlier = create_period(2022, publication_date=date(2024, 5, 20))

        pair = self.selector.select_comparable_periods(
            [target, earlier], target, as_of_date=date(2024, 7, 1)
        )

        assert pair.current == target
        assert pair.previous is None
