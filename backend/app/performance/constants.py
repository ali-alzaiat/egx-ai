"""Performance constants (R50 B9). Changing any window or rule requires a version bump."""

from decimal import Decimal

PERFORMANCE_METHODOLOGY_VERSION = "performance-1.1"

#: Trading-day windows: the return runs from the close N trading days before the latest close.
WINDOW_TRADING_DAYS: dict[str, int] = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252}
#: Year to date: from the last close of the previous calendar year.
YTD_WINDOW = "YTD"
WINDOW_ORDER: tuple[str, ...] = ("1M", "3M", "6M", YTD_WINDOW, "1Y")

#: Returns are fractions (0.1234 = 12.34%) rounded to this many places.
RETURN_QUANT = Decimal("0.0001")

BENCHMARK_INDEX = "EGX30"

#: Sector peer benchmark (R50 B14): the median return of the company's sector peers.
MIN_SECTOR_PEERS = 5
#: A peer whose latest close is older than this (calendar days before as-of) is left out.
PEER_MAX_STALE_DAYS = 10

#: A reported quarter covers about 90 days; a longer span is a cumulative (year-to-date)
#: figure, which cannot be summed into a trailing-twelve-month total.
QUARTER_MAX_SPAN_DAYS = 100
QUARTER_TYPES: tuple[str, ...] = ("Q1", "Q2", "Q3", "Q4")
ANNUAL_TYPE = "ANNUAL"

#: Statement-ontology codes read for fundamentals growth.
REVENUE_CODE = "revenue"
NET_INCOME_CODE = "net_income"

PERFORMANCE_SOURCE = (
    "EGX AI performance engine over stored prices, EGX30 and approved statement lines"
)
