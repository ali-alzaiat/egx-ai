"""Pinned constants for Phase-3 fair value (methodology version 1.0).

Sources:
- 4-model split + P/E→P/S→P/B router: Simply Wall St valuation methodology,
  https://support.simplywall.st/hc/en-us/articles/4751563581071
  (via `.workflow/research/phase-3-valuation.md` §1).
- Widening margin-of-safety ladder: Morningstar Uncertainty Rating thresholds,
  https://www.morningstar.com/stocks/how-measure-stocks-uncertainty
  (via research §2; fed here by our own data-quality score instead of
  analyst judgment).
- TIKR-3-input adjustability (revenue growth, operating margin, exit
  multiple) + bull/base/bear side-by-side: TIKR Valuation Model Builder,
  https://support.tikr.com/hc/en-us/articles/41118126176667 (via §6).
- Fixed weights are disclosed in every response; nothing is fitted per
  company (no black-box fitting). Changing any value below requires bumping
  VALUATION_METHODOLOGY_VERSION.
"""

from decimal import Decimal

VALUATION_METHODOLOGY_VERSION = "1.0"

DEFAULT_VALUATION_PROFILE_KEY = "default"

# profile_key -> EGX sector scope (None = default fallback), primary intrinsic
# model, fallback intrinsic model, preferred relative multiple basis.
# Bank→Excess-Returns+P/B, general→FCFE+P/E-or-P/S (R25 V2).
VALUATION_PROFILES: dict[str, dict[str, str | None]] = {
    "banks": {
        "egx_sector": "Banks",
        "primary_model": "excess_returns",
        "fallback_model": "dividend_discount",
        "preferred_multiple": "pb",
    },
    "real_estate": {
        "egx_sector": "Real Estate",
        "primary_model": "affo_two_stage",
        "fallback_model": "dividend_discount",
        "preferred_multiple": "pb",
    },
    "industrials": {
        "egx_sector": "Industrial Goods, Services and Automobiles",
        "primary_model": "fcfe_two_stage",
        "fallback_model": "dividend_discount",
        "preferred_multiple": "pe",
    },
    "default": {
        "egx_sector": None,
        "primary_model": "fcfe_two_stage",
        "fallback_model": "dividend_discount",
        "preferred_multiple": "pe",
    },
}

# Fixed per-profile weights over (primary intrinsic, relative leg).
# Exposed verbatim in every fair-value response.
PROFILE_WEIGHTS: dict[str, dict[str, Decimal]] = {
    "banks": {"intrinsic": Decimal("0.6"), "relative": Decimal("0.4")},
    "real_estate": {"intrinsic": Decimal("0.6"), "relative": Decimal("0.4")},
    "industrials": {"intrinsic": Decimal("0.6"), "relative": Decimal("0.4")},
    "default": {"intrinsic": Decimal("0.6"), "relative": Decimal("0.4")},
}

# Data-quality score (0-100) -> confidence level. Mirrors the Morningstar
# Low/Medium/High/VeryHigh ladder; required_discount widens as confidence
# falls — a verdict of "potentially undervalued" needs a bigger discount
# when the inputs are weaker.
CONFIDENCE_LADDER: tuple[tuple[str, float, Decimal], ...] = (
    ("VeryHigh", 80.0, Decimal("0.10")),
    ("High", 60.0, Decimal("0.15")),
    ("Medium", 40.0, Decimal("0.20")),
    ("Low", 0.01, Decimal("0.30")),
)

# Bull/bear deltas applied to the base TIKR-3-inputs (fixed, disclosed).
SCENARIO_GROWTH_DELTA = Decimal("0.02")
SCENARIO_MARGIN_DELTA = Decimal("0.01")
SCENARIO_EXIT_DELTA = Decimal("1.0")

# 1-D sensitivity steps around the base case (2-D grid deferred to Phase 10).
SENSITIVITY_DISCOUNT_STEPS: tuple[Decimal, ...] = (
    Decimal("-0.02"),
    Decimal("-0.01"),
    Decimal("0.01"),
    Decimal("0.02"),
)
SENSITIVITY_GROWTH_STEPS: tuple[Decimal, ...] = (
    Decimal("-0.02"),
    Decimal("-0.01"),
    Decimal("0.01"),
    Decimal("0.02"),
)

RANGE_NOTE = (
    "Bull/base/bear values are a range under stated assumptions, not a target. "
    "Read them as what each scenario implies, not as what the price will do."
)

DISCOUNT_FIXED_NOTE = (
    "Discount rate is shown but fixed in v1; only revenue growth, operating "
    "margin, and exit multiple are adjustable."
)
