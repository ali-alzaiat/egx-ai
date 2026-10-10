"""Pinned constants for industry intelligence (methodology version 1.0).

Sources:
- GICS 11 sector names + 4-level counts (11/25/74/163): MSCI/S&P GICS
  methodology, https://www.spglobal.com/spdji/en/documents/methodologies/methodology-gics.pdf
  (via `.workflow/research/phase-2-industry-competitive-landscape.md` Track A1).
- GICS branch codes below: MSCI GICS methodology August 2024 /
  February 2025 (Banks 4010/401010/40101010/40101015; Real Estate
  6020/602010/60201010-60201040; Industrials 2010/201030/20103010).
- EGX 18-sector names: https://www.egx.com.eg/en/listedstocks.aspx
  (via research Track A2).
"""

INDUSTRY_METHODOLOGY_VERSION = "1.0"

# Percentiles need at least this many values with data (target included).
# Below it the metric reports INSUFFICIENT_DATA — never a 1-of-1 "top decile".
MIN_VALUES_WITH_DATA = 3

# Editable peer-list safety bound (Simply Wall St "Edit Peers" pattern).
MAX_OVERRIDE_PEERS = 50

EGX_LISTED_STOCKS_URL = "https://www.egx.com.eg/en/listedstocks.aspx"
EGX_SECTOR_SOURCE_NAME = "EGX listed stocks"

EGX_SECTOR_NAMES: tuple[str, ...] = (
    "Banks",
    "Basic Resources",
    "Health Care & Pharmaceuticals",
    "Industrial Goods, Services and Automobiles",
    "Real Estate",
    "Travel & Leisure",
    "Utilities",
    "IT, Media & Communication Services",
    "Food, Beverages and Tobacco",
    "Energy & Support Services",
    "Trade & Distributors",
    "Shipping & Transportation Services",
    "Education Services",
    "Non-bank financial services",
    "Contracting & Construction Engineering",
    "Textile & Durables",
    "Building Materials",
    "Paper & Packaging",
)

# (code, name) for the 11 canonical GICS sectors.
GICS_SECTORS: tuple[tuple[str, str], ...] = (
    ("10", "Energy"),
    ("15", "Materials"),
    ("20", "Industrials"),
    ("25", "Consumer Discretionary"),
    ("30", "Consumer Staples"),
    ("35", "Health Care"),
    ("40", "Financials"),
    ("45", "Information Technology"),
    ("50", "Communication Services"),
    ("55", "Utilities"),
    ("60", "Real Estate"),
)

# (group_code, group_name, industry_code, industry_name,
#  sub_code, sub_name) — only the three branches Phase 2 profiles need.
# Remaining GICS branches are added when a later phase needs them (R22 cut).
GICS_BRANCHES: tuple[tuple[str, str, str, str, str, str], ...] = (
    ("4010", "Banks", "401010", "Banks", "40101010", "Diversified Banks"),
    ("4010", "Banks", "401010", "Banks", "40101015", "Regional Banks"),
    (
        "6020",
        "Real Estate Management & Development",
        "602010",
        "Real Estate Management & Development",
        "60201030",
        "Real Estate Development",
    ),
    (
        "2010",
        "Capital Goods",
        "201030",
        "Construction & Engineering",
        "20103010",
        "Construction & Engineering",
    ),
)

# (GICS sector code for the branch's top level, group/industry/sub rows above).
GICS_BRANCH_SECTORS: dict[str, str] = {
    "4010": "40",
    "6020": "60",
    "2010": "20",
}

# EGX sector name -> GICS sub-industry code (only where verified, never guessed).
EGX_TO_GICS_SUB: tuple[tuple[str, str], ...] = (
    ("Banks", "40101010"),
    ("Real Estate", "60201030"),
    ("Industrial Goods, Services and Automobiles", "20103010"),
    ("Contracting & Construction Engineering", "20103010"),
)

DEFAULT_PROFILE_KEY = "default"

# profile_key -> (EGX sector name scope or None for default, metric keys in order).
# Every metric_key is a real code from app.metrics.definitions (no invented metrics).
METRIC_PROFILES: tuple[tuple[str, str | None, tuple[str, ...]], ...] = (
    (
        "banks",
        "Banks",
        ("roe", "roa", "net_margin", "debt_to_equity", "net_income_growth_yoy"),
    ),
    (
        "real_estate",
        "Real Estate",
        ("roe", "roa", "net_margin", "debt_to_assets", "revenue_growth_yoy"),
    ),
    (
        "industrials",
        "Industrial Goods, Services and Automobiles",
        ("roe", "roa", "gross_margin", "operating_margin", "debt_to_equity"),
    ),
    (
        "default",
        None,
        ("roe", "roa", "net_margin", "debt_to_equity", "current_ratio"),
    ),
)
