"""Cross-check thresholds (R50 B11). Changing any value requires a version bump."""

from decimal import Decimal

CROSSCHECK_METHODOLOGY_VERSION = "crosscheck-1.0"

# Check codes, in the order they are shown.
CHECK_PROVENANCE = "provenance"
CHECK_CROSS_SOURCE = "cross_source"
CHECK_ACCOUNTING_IDENTITY = "accounting_identity"
CHECK_PRICE_SANITY = "price_sanity"
CHECK_FRESHNESS = "freshness"
CHECK_ORDER: tuple[str, ...] = (
    CHECK_PROVENANCE,
    CHECK_CROSS_SOURCE,
    CHECK_ACCOUNTING_IDENTITY,
    CHECK_PRICE_SANITY,
    CHECK_FRESHNESS,
)

STATUS_PASS = "pass"
STATUS_WARN = "warn"
STATUS_FAIL = "fail"
STATUS_INSUFFICIENT = "insufficient_data"
#: Worst last: ``overall`` is the check status with the highest severity.
STATUS_SEVERITY: dict[str, int] = {
    STATUS_PASS: 0,
    STATUS_INSUFFICIENT: 1,
    STATUS_WARN: 2,
    STATUS_FAIL: 3,
}

# provenance: warn when less than this share of the latest approved lines is filing-backed;
# fail when none is.
PROVENANCE_WARN_SHARE = Decimal("0.80")

# cross_source: relative difference between our filing-backed value and the vendor value.
CROSS_SOURCE_WARN = Decimal("0.01")
CROSS_SOURCE_FAIL = Decimal("0.05")
#: Bands shown in evidence (the vendor value itself is never shown).
BAND_WITHIN = "within_1_percent"
BAND_WARN = "1_to_5_percent"
BAND_FAIL = "over_5_percent"

# accounting_identity: relative difference between the two sides of an identity.
IDENTITY_WARN = Decimal("0.005")
IDENTITY_FAIL = Decimal("0.02")

# price_sanity. EGX caps a stock's one-day move. The cap is read off the stored history, not from
# a rulebook: regular moves reach exactly +/-20% (R50 real-data check over 234 companies: a 10%
# cap fails 158 of them, a 20% cap fails 33). Confirm it against the EGX trading rules and bump
# the version if it differs. The tolerance absorbs rounding to the tick. A move beyond the cap
# is only excused when the close ratio is close to a whole split ratio (2:1, 3:1, ...), which
# the evidence lists as "possible_splits".
EGX_DAILY_LIMIT = Decimal("0.20")
LIMIT_TOLERANCE = Decimal("0.005")
SPLIT_FACTORS: tuple[int, ...] = (2, 3, 4, 5, 10)
SPLIT_TOLERANCE = Decimal("0.03")
#: More missing trading days than this between two bars is a gap.
GAP_TRADING_DAYS = 5
PRICE_LOOKBACK_DAYS = 365
#: EGX trades Sunday to Thursday (``date.weekday()``: Mon=0 ... Sun=6).
EGX_TRADING_WEEKDAYS: frozenset[int] = frozenset({6, 0, 1, 2, 3})

# freshness: trading days since the last close; whole quarters since the latest period end.
FRESH_PRICE_WARN_DAYS = 3
FRESH_PRICE_FAIL_DAYS = 10
FRESH_PERIOD_WARN_QUARTERS = 2
FRESH_PERIOD_FAIL_QUARTERS = 4

#: Rows of evidence listed per check; the rest are only counted.
MAX_EVIDENCE_ITEMS = 10
