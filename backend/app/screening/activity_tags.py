"""Shariah business-activity tag snapshot (R44 D-9, R47 S1).

The EGX sector is a peer / valuation classification. It is far too coarse for the Shariah
business-activity rule: "Food, Beverages and Tobacco" contains the substring "tobacco" (31
names, one real tobacco business) and "Banks" holds Islamic and conventional banks alike. So
``screen_industry`` receives only a **tag** from this module, never a raw sector name.

A tag is one of the ``ProhibitedIndustry`` values (FAIL), ``permitted`` or ``islamic_bank``
(PASS), or ``None`` = UNKNOWN (the industry rule stays INSUFFICIENT_DATA, so no COMPLIANT
verdict). Resolution order:

1. A per-company override (``OVERRIDES``), each with a basis and a cited source.
2. A sector default (``SECTOR_DEFAULT_TAGS``) for the sectors where the activity is uniform.
3. Otherwise UNKNOWN. The four review sectors (Food, Beverages and Tobacco; Travel & Leisure;
   IT, Media & Communication; Non-bank financial) have NO sector default: an unreviewed
   company there is UNKNOWN, never a sector-wide fail or pass.

``TAG_SET_VERSION`` is tied to Shariah methodology ``METHODOLOGY_VERSION`` (v2). Adding or
changing a tag or default means bumping ``TAG_SET_VERSION``; results cite it in their source.
"""

from dataclasses import dataclass
from enum import Enum

from app.industry.backfill import normalize_sector_name
from app.screening.methodology import DEFAULT_METHODOLOGY, ProhibitedIndustry

TAG_SET_VERSION = "1.0"
METHODOLOGY_VERSION = DEFAULT_METHODOLOGY.version.value
DECISION_SOURCE = ".workflow/decisions/R44-sectors-and-valuation-assumptions.md section (a) D-9"

PERMITTED = "permitted"
ISLAMIC_BANK = "islamic_bank"

#: Every tag value ``screen_industry`` may receive (None = UNKNOWN is not a value).
ALLOWED_TAGS: frozenset[str] = frozenset(
    {i.value for i in ProhibitedIndustry} | {PERMITTED, ISLAMIC_BANK}
)


class TagBasis(Enum):
    SECTOR_DEFAULT = "sector_default"
    COMPANY_OVERRIDE = "company_override"
    NAME_REVIEW = "name_review"
    UNREVIEWED = "unreviewed"


@dataclass(frozen=True, slots=True)
class ActivityTag:
    """Result of tag resolution: ``tag`` is None when UNKNOWN (``reason`` says why)."""

    tag: str | None
    basis: TagBasis
    source: str
    reason: str
    tag_set_version: str = TAG_SET_VERSION


#: Sector defaults (normalised EGX sector names). Overridable per company.
SECTOR_DEFAULT_TAGS: dict[str, str] = {
    "Banks": ProhibitedIndustry.CONVENTIONAL_BANKING.value,
    "Basic Resources": PERMITTED,
    "Industrial Goods, Services and Automobiles": PERMITTED,
    "Real Estate": PERMITTED,
    "Contracting & Construction Engineering": PERMITTED,
    "Building Materials": PERMITTED,
    "Textile & Durables": PERMITTED,
    "Energy & Support Services": PERMITTED,
    "Trade & Distributors": PERMITTED,
    "Shipping & Transportation Services": PERMITTED,
    "Education Services": PERMITTED,
    "Utilities": PERMITTED,
    "Paper & Packaging": PERMITTED,
    "Health Care & Pharmaceuticals": PERMITTED,
}

#: Sectors with no default: every company is reviewed individually (see ``OVERRIDES``).
REVIEW_SECTORS: frozenset[str] = frozenset(
    {
        "Food, Beverages and Tobacco",
        "Travel & Leisure",
        "IT, Media & Communication Services",
        "Non-bank financial services",
    }
)


@dataclass(frozen=True, slots=True)
class TagOverride:
    ticker: str
    tag: str
    basis: TagBasis
    source: str


_ISLAMIC_BANK_SOURCE = (
    f"{DECISION_SOURCE}: Islamic-bank carve-out; EGX33 Shariah constituents "
    "(app/screening/egx33.py) list this bank"
)
_NAME_SOURCE = (
    "data/egx_universe.csv (stockanalysis.com EGX listing, fetched 2026-10-23): company "
    "name states insurance and is not takaful"
)

#: Per-company reviews. ``permitted`` in a review sector needs a cited activity source
#: (EGX CompanyDetails or a filing); a name alone is UNKNOWN. A FAIL from a name alone is
#: limited to the insurer case.
OVERRIDES: tuple[TagOverride, ...] = (
    TagOverride("FAIT", ISLAMIC_BANK, TagBasis.COMPANY_OVERRIDE, _ISLAMIC_BANK_SOURCE),
    TagOverride("FAITA", ISLAMIC_BANK, TagBasis.COMPANY_OVERRIDE, _ISLAMIC_BANK_SOURCE),
    TagOverride("ADIB", ISLAMIC_BANK, TagBasis.COMPANY_OVERRIDE, _ISLAMIC_BANK_SOURCE),
    TagOverride("SAUD", ISLAMIC_BANK, TagBasis.COMPANY_OVERRIDE, _ISLAMIC_BANK_SOURCE),
    TagOverride(
        "EAST",
        ProhibitedIndustry.TOBACCO.value,
        TagBasis.COMPANY_OVERRIDE,
        f"{DECISION_SOURCE}: Eastern Company is the tobacco business in its sector "
        "(research r43-sector-and-valuation-sources.md section A4)",
    ),
    TagOverride(
        "DEIN",
        ProhibitedIndustry.CONVENTIONAL_INSURANCE.value,
        TagBasis.NAME_REVIEW,
        _NAME_SOURCE,
    ),
    TagOverride(
        "MOIN",
        ProhibitedIndustry.CONVENTIONAL_INSURANCE.value,
        TagBasis.NAME_REVIEW,
        _NAME_SOURCE,
    ),
)

_OVERRIDES_BY_TICKER: dict[str, TagOverride] = {o.ticker: o for o in OVERRIDES}

#: Tickers that carry the Islamic-bank tag (feeds the purification carve-out check).
ISLAMIC_BANK_TAGGED: frozenset[str] = frozenset(
    o.ticker for o in OVERRIDES if o.tag == ISLAMIC_BANK
)


def resolve_activity_tag(ticker: str, egx_sector: str | None) -> ActivityTag:
    """Resolve the Shariah activity tag for one company. Pure; no I/O.

    ``egx_sector`` is only used to look up a sector default; it is never returned as a tag.
    """
    override = _OVERRIDES_BY_TICKER.get(ticker.strip().upper())
    if override is not None:
        return ActivityTag(
            tag=override.tag,
            basis=override.basis,
            source=override.source,
            reason=f"Per-company activity review: {override.tag}",
        )
    if egx_sector is None or not egx_sector.strip():
        return ActivityTag(
            tag=None,
            basis=TagBasis.UNREVIEWED,
            source=DECISION_SOURCE,
            reason="No EGX sector assigned and no company review: business activity unknown",
        )
    sector = normalize_sector_name(egx_sector)
    default = SECTOR_DEFAULT_TAGS.get(sector)
    if default is not None:
        return ActivityTag(
            tag=default,
            basis=TagBasis.SECTOR_DEFAULT,
            source=f"{DECISION_SOURCE}: sector default for '{sector}'",
            reason=f"Sector default for '{sector}': {default}",
        )
    if sector in REVIEW_SECTORS:
        reason = (
            f"'{sector}' has no sector default and this company has no activity review: "
            "business activity unknown"
        )
    else:
        reason = f"Sector '{sector}' is not in the activity-tag set: business activity unknown"
    return ActivityTag(
        tag=None, basis=TagBasis.UNREVIEWED, source=DECISION_SOURCE, reason=reason
    )
