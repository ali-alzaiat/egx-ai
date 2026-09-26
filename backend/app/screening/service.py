"""Shariah screening service.

Orchestrates the screening process:
1. Load company financial data
2. Apply screening rules
3. Determine overall compliance
4. Persist results with methodology version
"""

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.screening.methodology import DEFAULT_METHODOLOGY, ShariahMethodology
from app.screening.rules import (
    ScreeningRuleResult,
    ScreeningVerdict,
    screen_cash_and_securities,
    screen_debt_ratio,
    screen_industry,
    screen_interest_income,
)

logger = logging.getLogger(__name__)


class ScreeningInput(NamedTuple):
    """Input data for Shariah screening."""
    company_id: str
    ticker: str
    industry: str | None
    total_debt: Decimal | None
    total_assets: Decimal | None
    interest_income: Decimal | None
    total_revenue: Decimal | None
    cash_and_securities: Decimal | None


class ScreeningOutput(NamedTuple):
    """Output of Shariah screening."""
    company_id: str
    ticker: str
    is_compliant: bool
    methodology_version: str
    rule_results: list[ScreeningRuleResult]
    overall_reason: str
    screened_at: datetime


class ShariahScreeningService:
    """Service for Shariah compliance screening."""

    def __init__(
        self,
        session: AsyncSession,
        methodology: ShariahMethodology = DEFAULT_METHODOLOGY,
    ) -> None:
        self.session = session
        self.methodology = methodology

    async def screen_company(self, screening_input: ScreeningInput) -> ScreeningOutput:
        """Screen a single company for Shariah compliance.

        Args:
            screening_input: Company financial data for screening

        Returns:
            ScreeningOutput with compliance status and rule results
        """
        rule_results: list[ScreeningRuleResult] = []

        # Screen debt ratio
        debt_result = screen_debt_ratio(
            total_debt=screening_input.total_debt,
            total_assets=screening_input.total_assets,
            threshold=self.methodology.debt_to_assets_threshold,
        )
        rule_results.append(debt_result)

        # Screen interest income
        interest_result = screen_interest_income(
            interest_income=screening_input.interest_income,
            total_revenue=screening_input.total_revenue,
            threshold=self.methodology.interest_income_to_revenue_threshold,
        )
        rule_results.append(interest_result)

        # Screen cash and securities
        cash_result = screen_cash_and_securities(
            cash_and_securities=screening_input.cash_and_securities,
            total_assets=screening_input.total_assets,
            threshold=self.methodology.cash_and_securities_to_assets_threshold,
        )
        rule_results.append(cash_result)

        # Screen industry
        prohibited = tuple(i.value for i in self.methodology.prohibited_industries)
        industry_result = screen_industry(
            industry=screening_input.industry,
            prohibited_industries=prohibited,
        )
        rule_results.append(industry_result)

        # Determine overall compliance
        is_compliant, overall_reason = self._determine_compliance(rule_results)

        return ScreeningOutput(
            company_id=screening_input.company_id,
            ticker=screening_input.ticker,
            is_compliant=is_compliant,
            methodology_version=self.methodology.version.value,
            rule_results=rule_results,
            overall_reason=overall_reason,
            screened_at=datetime.now(UTC),
        )

    def _determine_compliance(
        self,
        rule_results: list[ScreeningRuleResult],
    ) -> tuple[bool, str]:
        """Determine overall Shariah compliance from rule results.

        A company is Shariah-compliant if:
        - All applicable rules PASS
        - No rules FAIL
        - Rules with INSUFFICIENT_DATA are noted but don't cause failure
        """
        failed_rules = [r for r in rule_results if r.verdict == ScreeningVerdict.FAIL]
        insufficient = [r for r in rule_results if r.verdict == ScreeningVerdict.INSUFFICIENT_DATA]

        if failed_rules:
            failed_names = [r.rule_name for r in failed_rules]
            return False, f"Failed rules: {', '.join(failed_names)}"

        if insufficient:
            insufficient_names = [r.rule_name for r in insufficient]
            return False, f"Insufficient data for: {', '.join(insufficient_names)}"

        return True, "All screening rules passed"
