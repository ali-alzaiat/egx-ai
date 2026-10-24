"""Pinned constants for Phase-4 investment scores (methodology version 1.0).

Sources:
- 5-component × pass/fail checks, equal weighting, dual health tracks, and
  per-check thresholds: Simply Wall St Company Analysis Model,
  https://github.com/SimplyWallSt/Company-Analysis-Model/blob/master/MODEL.markdown
  (via `.workflow/research/phase-4-investment-score.md` §1).
- Confidence separated from the score (uncertainty widens bands, never moves
  the value) + margin-of-safety selector driving a display-only Buy Zone:
  Morningstar Uncertainty Rating + Alpha Spread Buy Zone (via research §2-§3).
- EGX degradation choices (no PEG/analyst-target, narrowed dividend,
  historical-extrapolation growth, per-ticker bank gating): R28 scope verdict.
Changing any value below requires bumping SCORE_METHODOLOGY_VERSION.
"""

from decimal import Decimal

# 1.1 (R45 M4): dividend_stability / dividend_growing are NOT_RUN until a declared-DPS
# source exists; dividend_earnings_coverage is cash paid / EPS.
SCORE_METHODOLOGY_VERSION = "1.1"

DEFAULT_SCORE_PROFILE_KEY = "default"

# A component is valid only when at least this many of its checks ran.
# Missing checks report NOT_RUN — never fail, never zero-filled.
MIN_CHECKS_RUN_PER_COMPONENT = 3

# The headline is valid only when at least this many of the 5 components
# are valid; otherwise it is null with a reason (never a default score).
MIN_VALID_COMPONENTS_FOR_HEADLINE = 3

# Dividend-growing check needs this many years of DPS history; shorter
# histories fail open to NOT_RUN instead of FAIL.
DIVIDEND_GROWING_MIN_HISTORY_YEARS = 10

# Default margin of safety for the display-only Buy Zone (Alpha Spread
# precedent: 20%). It never moves the score — only the buy-zone band.
DEFAULT_MARGIN_OF_SAFETY = Decimal("0.20")

# Value thresholds (SWS MODEL.markdown: 20% discount, PE/PB comparisons).
VALUE_FV_DISCOUNT_THRESHOLD = Decimal("0.20")
DIVIDEND_STABILITY_MAX_DROP = Decimal("0.20")
DIVIDEND_PAYOUT_MIN = Decimal("0")
DIVIDEND_PAYOUT_MAX = Decimal("0.90")
PAST_ROE_THRESHOLD = Decimal("0.20")
FUTURE_ROE_THRESHOLD = Decimal("0.20")
GROWTH_HIGH_THRESHOLD = Decimal("0.20")

# Standard-track health thresholds (SWS non-financials 6 checks).
HEALTH_DE_RATIO_MAX = Decimal("0.40")
HEALTH_OCF_TO_DEBT_MIN = Decimal("0.20")
HEALTH_EBIT_INTEREST_COVER_MIN = Decimal("5")

# Bank-track health thresholds (SWS financials 6 checks).
BANK_EQUITY_MULTIPLIER_MAX = Decimal("20")
BANK_DEPOSITS_SHARE_MIN = Decimal("0.50")
BANK_LOANS_TO_ASSETS_MAX = Decimal("1.10")
BANK_LOANS_TO_DEPOSITS_MAX = Decimal("1.25")
BANK_CHARGE_OFF_MAX = Decimal("0.03")

# Confidence ladder bands, fed by data quality + checks run (display-only:
# confidence never moves the score, only the buy-zone requirement).
# (level, min_dq_score, min_checks_run)
CONFIDENCE_BANDS: tuple[tuple[str, float, int], ...] = (
    ("VeryHigh", 80.0, 18),
    ("High", 60.0, 14),
    ("Medium", 40.0, 10),
    ("Low", 0.0, 0),
)

# score_profile_key -> (EGX sector scope or None for default, health track).
# Banks take the 6-check financial track; everyone else the standard track.
SCORE_PROFILES: tuple[tuple[str, str | None, str], ...] = (
    ("banks", "Banks", "banks"),
    ("default", None, "standard"),
)

SCORE_SCALE = "0-100 per component and headline; higher passed more checks"
SCORE_DISCLAIMER = (
    "An investment score summarizes the checks above under these assumptions; "
    "it is potentially informative, not a recommendation to buy or sell."
)
