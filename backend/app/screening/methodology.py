"""Shariah screening methodology configuration.

This module defines the Shariah screening methodology with:
- Explicit rules (no AI decisions)
- Configurable thresholds
- Source-backed references (AAOIFI standards)
- Versioned methodology
- Auditable screening logic

References:
- AAOIFI Shariah Standard No. 21 (Financial Papers)
- AAOIFI Shariah Standard No. 17 (Investment Sukuk)
- S&P Shariah Indices methodology
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class ShariahMethodologyVersion(Enum):
    """Versioned methodology for auditability."""
    V1_0 = "1.0"
    V1_1 = "1.1"


class ProhibitedIndustry(Enum):
    """Industries prohibited under Shariah guidelines."""
    ALCOHOL = "alcohol"
    GAMBLING = "gambling"
    PORK = "pork"
    TOBACCO = "tobacco"
    ADULT_ENTERTAINMENT = "adult_entertainment"
    WEAPONS = "weapons"
    CONVENTIONAL_BANKING = "conventional_banking"
    CONVENTIONAL_INSURANCE = "conventional_insurance"
    ENTERTAINMENT = "entertainment"


@dataclass(frozen=True)
class ShariahMethodology:
    """Shariah screening methodology configuration.

    All thresholds are based on AAOIFI standards and can be configured
    for different screening approaches.
    """
    version: ShariahMethodologyVersion
    name: str
    description: str
    source_reference: str

    # Financial ratio thresholds
    debt_to_assets_threshold: Decimal = Decimal("0.33")
    interest_income_to_revenue_threshold: Decimal = Decimal("0.05")
    cash_and_securities_to_assets_threshold: Decimal = Decimal("0.33")

    # Prohibited industries
    prohibited_industries: tuple[ProhibitedIndustry, ...] = field(
        default_factory=lambda: tuple(ProhibitedIndustry)
    )

    def is_industry_prohibited(self, industry: str | None) -> bool:
        """Check if an industry is prohibited."""
        if industry is None:
            return False
        industry_lower = industry.lower()
        return any(
            industry_lower in prohibited.value
            for prohibited in self.prohibited_industries
        )


# Default methodology based on AAOIFI standards
DEFAULT_METHODOLOGY = ShariahMethodology(
    version=ShariahMethodologyVersion.V1_0,
    name="AAOIFI-based Shariah Screening",
    description=(
        "Shariah compliance screening based on AAOIFI standards. "
        "Screens companies based on financial ratios and prohibited industries."
    ),
    source_reference=(
        "AAOIFI Shariah Standard No. 21 (Financial Papers), "
        "S&P Shariah Indices Methodology"
    ),
    debt_to_assets_threshold=Decimal("0.33"),
    interest_income_to_revenue_threshold=Decimal("0.05"),
    cash_and_securities_to_assets_threshold=Decimal("0.33"),
)
