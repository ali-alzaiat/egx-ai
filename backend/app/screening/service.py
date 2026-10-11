"""Shariah screening service.

Orchestrates the screening process:
1. Load company financial data
2. Apply screening rules
3. Determine overall compliance
4. Persist results with methodology version
"""

import logging
from dataclasses import replace
from datetime import UTC, date, datetime
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

#: Rules whose inputs come from dated filings (balance sheet + income
#: statement). Only these feed report_date; the industry rule is undated.
RATIO_RULE_NAMES: tuple[str, ...] = (
    "debt_ratio",
    "interest_income_ratio",
    "cash_securities_ratio",
)


class RuleProvenance(NamedTuple):
    """Filing provenance for one rule's inputs (R32 B2)."""
    source: str | None
    source_date: date | None


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
    provenance: dict[str, RuleProvenance] | None = None


class ScreeningOutput(NamedTuple):
    """Output of Shariah screening."""
    company_id: str
    ticker: str
    is_compliant: bool | None  # None = insufficient data, not a pass/fail
    methodology_version: str
    rule_results: list[ScreeningRuleResult]
    overall_reason: str
    screened_at: datetime
    report_date: date | None
    report_date_reason: str | None


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

        rule_results = self._stamp_provenance(rule_results, screening_input.provenance)
        report_date, report_date_reason = self._derive_report_date(rule_results)

        return ScreeningOutput(
            company_id=screening_input.company_id,
            ticker=screening_input.ticker,
            is_compliant=is_compliant,
            methodology_version=self.methodology.version.value,
            rule_results=rule_results,
            overall_reason=overall_reason,
            screened_at=datetime.now(UTC),
            report_date=report_date,
            report_date_reason=report_date_reason,
        )

    @staticmethod
    def _stamp_provenance(
        rule_results: list[ScreeningRuleResult],
        provenance: dict[str, RuleProvenance] | None,
    ) -> list[ScreeningRuleResult]:
        """Stamp each rule with its filing source + date (R32 B2).

        Provenance comes from the caller (cited filings); rules never invent
        it. Rules without provenance keep source/source_date None.
        """
        if not provenance:
            return rule_results
        stamped: list[ScreeningRuleResult] = []
        for result in rule_results:
            prov = provenance.get(result.rule_name)
            if prov is None:
                stamped.append(result)
            else:
                stamped.append(
                    replace(result, source=prov.source, source_date=prov.source_date)
                )
        return stamped

    @staticmethod
    def _derive_report_date(
        rule_results: list[ScreeningRuleResult],
    ) -> tuple[date | None, str | None]:
        """Derive report_date as the latest filing date behind ratio rules.

        Returns (None, reason) when unknown — never a synthesized date.
        """
        dated = [
            r.source_date
            for r in rule_results
            if r.rule_name in RATIO_RULE_NAMES and r.source_date is not None
        ]
        if dated:
            return max(dated), None
        backed = [
            r.rule_name for r in rule_results
            if r.rule_name in RATIO_RULE_NAMES and r.source is not None
        ]
        if backed:
            return None, (
                "Filing dates unknown for backing documents: "
                f"{', '.join(backed)}."
            )
        return None, "No financial facts: report_date unknown."

    def _determine_compliance(
        self,
        rule_results: list[ScreeningRuleResult],
    ) -> tuple[bool | None, str]:
        """Determine overall Shariah compliance from rule results.

        A company is Shariah-compliant if:
        - All applicable rules PASS
        - No rules FAIL
        - Rules with INSUFFICIENT_DATA are noted but don't cause failure

        Returns ``(None, reason)`` when no rule FAILs but data is missing:
        insufficient data is not a pass and not a fail.
        """
        failed_rules = [r for r in rule_results if r.verdict == ScreeningVerdict.FAIL]
        insufficient = [r for r in rule_results if r.verdict == ScreeningVerdict.INSUFFICIENT_DATA]

        if failed_rules:
            failed_names = [r.rule_name for r in failed_rules]
            return False, f"Failed rules: {', '.join(failed_names)}"

        if insufficient:
            insufficient_names = [r.rule_name for r in insufficient]
            return None, f"Insufficient data for: {', '.join(insufficient_names)}"

        return True, "All screening rules passed"
