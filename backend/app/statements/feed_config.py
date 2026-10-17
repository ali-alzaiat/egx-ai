"""Feed configuration for automated statement fetching.

Only the official EGX disclosure channel ships by default: per AGENTS.md the
fetch layer must use official/primary sources and must never bypass
CAPTCHAs/auth/robots. Company IR URLs are NOT invented here — they are filled
only with user-verified URLs (keep ``ir_urls`` empty until then).
"""

from dataclasses import dataclass, field

# EGX30 top-10 is NOT hardcoded here: the first batch list is recorded from the
# running system's EGX universe (UniverseService / sync output) at execution
# time and must be verifiable — see .workflow/decisions/R41 record. Until then
# fetch callers pass explicit tickers.
BATCH_1_TICKERS: tuple[str, ...] = ()

EGX_DISCLOSURE_PATTERN = "https://www.egx.com.eg/en/CompanyDetails.aspx?ISIN={isin}"


@dataclass
class CompanyFeed:
    """Ordered official feeds for one company."""

    ticker: str
    ir_urls: list[str] = field(default_factory=list)
    egx_disclosure: bool = True


def feed_for(ticker: str) -> CompanyFeed:
    """Build the feed plan for ``ticker`` (EGX disclosures only by default)."""
    return CompanyFeed(ticker=ticker, ir_urls=[], egx_disclosure=True)
