"""Pinned constants for Phase-3 fair value (methodology version 1.3).

1.1 (R45 M5): the discount rate fades. Explicit-stage flows use the cost of equity
(risk-free rate + equity risk premium); the Gordon terminal value is capitalised
at the sourced long-run cost of equity, on the same inflation horizon as the
terminal growth rate. R44 (b): the cost of equity and terminal growth are computed
from sourced rows (see ``app.valuation.assumptions``), not stored by hand.

1.2 (owner rulings F13 + router): stage-1 growth is the company's 3-year revenue CAGR
(four annual revenue points) capped at the sourced Egypt nominal GDP growth, not the
latest single-year growth; the excess-returns and DDM terminal values use the same
long-run cost of equity as the two-stage models.

1.3 (owner rulings R46): the FCFE base is the mean of the last three fiscal years of true
FCFE (operating cash flow - capex + net borrowing, times the parent share of earnings);
stage-1 growth is floored at 0% (the nominal GDP cap is unchanged); banks, identified from
statement lines (net loans + deposits), use justified P/B instead of FCFE; the relative
(P/E) leg stays off until sourced target multiples exist, so fair value is the intrinsic
leg alone.

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

VALUATION_METHODOLOGY_VERSION = "1.3"

#: Fiscal years averaged into the FCFE base (R46 V1; implemented in ``app.statements.bridge``).
FCFE_BASE_YEARS = 3

#: Stage-1 growth floor (R46 V4): a negative revenue CAGR is not extrapolated for five years.
STAGE1_GROWTH_FLOOR = Decimal("0")

#: Explicit stage, in years, valued at the first-stage cost of equity before the terminal
#: value is capitalised at the long-run cost of equity. One value for every model
#: (FCFE/AFFO stage 1, excess returns, DDM); it matches the 2027-2031 horizon of the
#: sourced nominal GDP growth cap (owner ruling, R45). Changing it needs a version bump.
EXPLICIT_STAGE_YEARS = 5

DEFAULT_VALUATION_PROFILE_KEY = "default"

# profile_key -> EGX sector scope (None = default fallback), primary intrinsic
# model, fallback intrinsic model, preferred relative multiple basis.
# Bank→justified P/B (R46 V3; was Excess-Returns), general→FCFE (R25 V2). The relative
# leg is off for every profile until sourced target multiples exist (R46 V5).
# A company uses the "banks" profile when its statement lines include net loans and
# deposits (``bridge.is_bank``), whatever its sector row says.
BANK_PROFILE_KEY = "banks"
VALUATION_PROFILES: dict[str, dict[str, str | None]] = {
    "banks": {
        "egx_sector": "Banks",
        "primary_model": "justified_pb",
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

# Implied-growth reverse calculation (R46 V6): bisection bounds for the stage-1 growth that
# makes the two-stage model value equal the price, and the solver's stopping rule. Display
# only: the implied value never feeds the verdict or the stance.
IMPLIED_GROWTH_MIN = Decimal("-0.5")
IMPLIED_GROWTH_MAX = Decimal("1.0")
IMPLIED_SOLVER_TOLERANCE = Decimal("0.000001")
IMPLIED_SOLVER_MAX_ITERATIONS = 100
