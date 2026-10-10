"""Pinned constants for Phase-5 investment theses (methodology version 1.0).

Sources:
- Thesis skeleton (5 pillars + labelled assumptions + own fair value +
  update timeline + shareholder toggle): Simply Wall St Community Narratives,
  https://support.simplywall.st/hc/en-us/articles/13416018054415-Getting-Started-with-Narratives
  (via `.workflow/research/phase-5-investment-thesis.md` §1).
- Section authority (Bulls/Bears x3 as assumption-shifters, FV drivers,
  Risk, Capital Allocation): Morningstar company reports (via research §2).
- Scenario display (Bear/Base/Bull assumption table + range-not-guess +
  sensitivity): Alpha Spread valuation scenarios (via research §3).
- Stored invalidation (2-4 per thesis, threshold + period + evidence source,
  versioned, append-only ledger, trigger forces reassessment never auto-sell):
  ThesisCheck / Synoptiv kill-criteria pattern (via research §4).
- Catalyst records (event + date/window + variable + expectation + outcome +
  Confirmed-vs-Tentative label): EarningsTracker labelling + EGX continuing
  obligations cadence (via research §4-§5).
Changing any value below requires bumping THESIS_METHODOLOGY_VERSION.
"""

THESIS_METHODOLOGY_VERSION = "1.0"

DEFAULT_HORIZON_YEARS = 5
MIN_HORIZON_YEARS = 1
MAX_HORIZON_YEARS = 30

MIN_INVALIDATIONS = 2
MAX_INVALIDATIONS = 4
MAX_BULL_BEAR_CASES = 3

# The six mandated EGX continuing-obligation disclosures every invalidation
# evidence source must be one of (research §5; Baker McKenzie continuing
# obligations summary). Free-text sources are rejected: a trigger must cite
# a disclosure that actually exists.
MANDATED_EVIDENCE_SOURCES: tuple[str, ...] = (
    "material_news_disclosure",
    "quarterly_shareholder_report",
    "annual_financial_statements",
    "quarterly_financial_statements",
    "board_resolution_summary",
    "distribution_disclosure",
)

INVALIDATION_DIRECTIONS: tuple[str, ...] = ("below", "above")
INVALIDATION_STATUSES: tuple[str, ...] = ("Active", "Triggered", "Reassessed")
LEDGER_CLASSIFICATIONS: tuple[str, ...] = (
    "Confirmed",
    "Pending",
    "Challenged",
    "Invalidated",
    "New",
)
CATALYST_OUTCOMES: tuple[str, ...] = ("Pending", "Hit", "Miss", "Pushed")
CATALYST_LABELS: tuple[str, ...] = ("Confirmed", "Tentative")

# The only pre-committed action a trigger may carry (rules 9/10): a firing
# threshold forces documented reassessment. Auto-sell and stop-loss-as-
# invalidation are never stored.
PRECOMMITTED_ACTION = "documented_reassessment"

# Skeleton catalysts seeded on every assess from the mandated EGX disclosure
# cadence (research §5). All Tentative until a dated filing confirms them;
# provenance is the obligations reference, never a guessed event row.
# (event, window_text, variable_tested, base_expectation)
CATALYST_SKELETON: tuple[tuple[str, str, str, str], ...] = (
    (
        "Annual financial statements",
        "annual",
        "earnings_power",
        "Results published on the EGX screens and company site ahead of the AGM",
    ),
    (
        "Quarterly financial statements",
        "quarterly",
        "earnings_power",
        "Quarterly statements published on the EGX screens",
    ),
    (
        "AGM resolutions",
        "annual",
        "capital_allocation",
        "AGM resolution summary disclosed before the next session",
    ),
    (
        "Dividend distribution disclosure",
        "as declared",
        "capital_allocation",
        "Cash/bonus distribution disclosed when declared",
    ),
    (
        "Board and shareholder structure report",
        "quarterly",
        "ownership",
        "Quarterly board/shareholder/treasury-structure report within 10 days",
    ),
)

SKELETON_PROVENANCE = (
    "https://resourcehub.bakermckenzie.com/en/resources/"
    "cross-border-listings-guide/europe-middle-east--africa/"
    "egyptian-exchange/topics/continuing-obligationsperiodic-reporting"
)

# Default invalidation templates used to pad a thesis up to the 2-condition
# minimum. These are methodology templates (metric + threshold + period),
# not facts about any company: they only fire against that company's own
# stored metric rows, and stay Active on missing data.
# (metric, threshold in the metric's stored unit, direction, period,
#  evidence_source)
DEFAULT_INVALIDATIONS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "revenue_growth_yoy",
        "0",
        "below",
        "two consecutive quarters",
        "quarterly_financial_statements",
    ),
    (
        "operating_margin",
        "0",
        "below",
        "annual",
        "annual_financial_statements",
    ),
)

THESIS_DISCLAIMER = (
    "This thesis summarizes the stored assumptions above under these "
    "assumptions; it is potentially informative, not a recommendation to buy "
    "or sell. A triggered condition forces documented reassessment, never an "
    "automatic sale."
)
