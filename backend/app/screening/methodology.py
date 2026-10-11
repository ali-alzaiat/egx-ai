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
    """Versioned methodology for auditability.

    V2 identifiers pin denominator + averaging window + thresholds
    (R32 B1): bare standard names never ship on new verdicts.
    V1_0/V1_1 remain so old rows stay readable via the version filter.
    """
    V1_0 = "1.0"
    V1_1 = "1.1"
    V2_ASSETS_SPOT = "aaoifi-assets-spot/33-33-5"


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

    # Pinned engine semantics (R32 B1): the ratios are computed over spot
    # balance-sheet totals (total_assets) and spot total revenue — an
    # MSCI/FTSE-style denominator, not AAOIFI market-cap averaging.
    denominator: str = "spot_total_assets"
    averaging_window: str = "spot"

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


# Default methodology: v2 pinned identifier (R32 B1). The version string
# carries denominator + window + thresholds (debt 33 / cash+securities 33 /
# impure income 5); bare "AAOIFI" never ships on new verdicts again.
DEFAULT_METHODOLOGY = ShariahMethodology(
    version=ShariahMethodologyVersion.V2_ASSETS_SPOT,
    name="AAOIFI spot-asset screen (debt 33 / cash 33 / impure income 5)",
    description=(
        "Shariah compliance screening with AAOIFI thresholds applied over "
        "spot total_assets and spot total_revenue. "
        "Screens companies based on financial ratios and prohibited industries."
    ),
    source_reference=(
        "AAOIFI Shariah Standard No. 21 (Financial Papers) thresholds; "
        "spot-asset denominator per engine semantics "
        "(MSCI/FTSE-style, not market-cap averaging)"
    ),
    denominator="spot_total_assets",
    averaging_window="spot",
    debt_to_assets_threshold=Decimal("0.33"),
    interest_income_to_revenue_threshold=Decimal("0.05"),
    cash_and_securities_to_assets_threshold=Decimal("0.33"),
)
