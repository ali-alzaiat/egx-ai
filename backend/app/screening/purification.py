"""Dividend-method purification estimates in EGP (R32 B3/B4).

Formula (Zoya dividend method = Islamicly ratio = MSCI complement):
``purify_EGP = dividend_EGP_received x (non_permissible_revenue / total_revenue)``.

Every estimate labels its doctrine ("dividend-method") and carries ratio
provenance + DPS source. The ratio is never invented: without parsed filing
inputs the estimate degrades to INSUFFICIENT_DATA citing the Islamicly
14-line impure-income checklist vocabulary. Purification is not zakat and
earns no reward (Zoya purification guide).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum


class PurificationStatus(Enum):
    """Estimate outcome: a number or an honest gap."""
    OK = "OK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class PurificationBranch(Enum):
    """Which doctrine branch produced the estimate."""
    RATIO = "ratio"
    FAIL_HOLDING = "fail-holding"
    ISLAMIC_BANK_CARVE_OUT = "islamic-bank-carve-out"
    INSUFFICIENT_DATA = "insufficient-data"


PURIFICATION_DOCTRINE = "dividend-method"

NOT_ZAKAT_COPY = (
    "Purification is not zakat and earns no reward: donate the amount and "
    "do not count it toward annual zakat obligations."
)

# EGX Islamic banks that pass screening by core-business carve-out, not by
# ratio (research §3/§6). Their dividends take the carve-out branch — never a
# silent zero multiplication.
ISLAMIC_BANK_TICKERS: frozenset[str] = frozenset({"FAIT", "ADIB", "SAUD"})

# The 14-line impure-income filing-extraction checklist (Islamicly) cited
# verbatim in vocabulary whenever the ratio is unknown (R32 B4).
MISSING_RATIO_REASON = (
    "Purification ratio unavailable: non-permissible revenue not parsed from "
    "cited filings (interest on bank deposits, term deposits, bonds/debentures, "
    "money-market instruments, other interest; non-permissible investment income "
    "from equity, derivatives, mutual funds; alcohol, conventional financial "
    "services, financial lease, pork, gambling, pornography, tobacco sales, or "
    "other identified non-permissible income, over total revenue)."
)


@dataclass(frozen=True)
class PurificationEstimate:
    """Result of a dividend-method purification estimate."""
    status: PurificationStatus
    branch: PurificationBranch
    doctrine: str
    amount_egp: Decimal | None
    dividend_egp: Decimal | None
    ratio: Decimal | None
    ratio_provenance: str | None
    dps: Decimal | None
    dps_source: str | None
    dps_date: date | None
    reason: str | None = None
    missing_input: str | None = None
    note: str = NOT_ZAKAT_COPY


def _insufficient(
    *,
    branch: PurificationBranch,
    dividend_egp: Decimal | None,
    dps: Decimal | None,
    dps_source: str | None,
    dps_date: date | None,
    ratio_provenance: str | None,
    reason: str,
    missing_input: str | None,
) -> PurificationEstimate:
    """Build an INSUFFICIENT_DATA estimate; the amount stays None, never zero."""
    return PurificationEstimate(
        status=PurificationStatus.INSUFFICIENT_DATA,
        branch=branch,
        doctrine=PURIFICATION_DOCTRINE,
        amount_egp=None,
        dividend_egp=dividend_egp,
        ratio=None,
        ratio_provenance=ratio_provenance,
        dps=dps,
        dps_source=dps_source,
        dps_date=dps_date,
        reason=reason,
        missing_input=missing_input,
    )


def normalize_ticker(ticker: str) -> str:
    """Normalize a ticker for carve-out matching (strips a `.CA` suffix)."""
    return ticker.split(".")[0].strip().upper()


def estimate_dividend_purification(
    *,
    ticker: str,
    is_compliant: bool | None,
    dividend_egp: Decimal | None = None,
    dps: Decimal | None = None,
    shares_held: Decimal | None = None,
    non_permissible_revenue: Decimal | None = None,
    total_revenue: Decimal | None = None,
    ratio_provenance: str | None = None,
    dps_source: str | None = None,
    dps_date: date | None = None,
) -> PurificationEstimate:
    """Estimate dividend purification in EGP (deterministic, no AI).

    Branches, in order: Islamic-bank carve-out, FAIL holding (whole dividend),
    dividend resolution (explicit amount, else DPS x shares), ratio gating.

    Args:
        ticker: Company ticker (carve-out matching is case-insensitive).
        is_compliant: Latest screening verdict; None means unknown.
        dividend_egp: Dividend received in EGP (wins over DPS x shares).
        dps: Dividend per share in EGP, stored with source + date.
        shares_held: Shares held, for DPS x shares derivation.
        non_permissible_revenue: Filing-parsed impure revenue; never proxied.
        total_revenue: Filing-parsed total revenue.
        ratio_provenance: Filing citation behind the ratio inputs.
        dps_source: Source behind the DPS figure.
        dps_date: Date of the DPS figure.

    Returns:
        PurificationEstimate with status OK or INSUFFICIENT_DATA.
    """
    if normalize_ticker(ticker) in ISLAMIC_BANK_TICKERS:
        return _insufficient(
            branch=PurificationBranch.ISLAMIC_BANK_CARVE_OUT,
            dividend_egp=dividend_egp,
            dps=dps,
            dps_source=dps_source,
            dps_date=dps_date,
            ratio_provenance=ratio_provenance,
            reason=(
                f"{normalize_ticker(ticker)} passes screening by Islamic-bank "
                "core-business carve-out, not by ratio: dividend-method "
                "purification does not apply; no amount estimated."
            ),
            missing_input=None,
        )

    if dividend_egp is None and dps is not None and shares_held is not None:
        if dps < 0 or shares_held < 0:
            return _insufficient(
                branch=PurificationBranch.INSUFFICIENT_DATA,
                dividend_egp=None,
                dps=dps,
                dps_source=dps_source,
                dps_date=dps_date,
                ratio_provenance=ratio_provenance,
                reason="DPS and shares held must be >= 0 to derive dividend_egp.",
                missing_input="dividend_egp",
            )
        dividend_egp = dps * shares_held

    if dividend_egp is None:
        return _insufficient(
            branch=PurificationBranch.INSUFFICIENT_DATA,
            dividend_egp=None,
            dps=dps,
            dps_source=dps_source,
            dps_date=dps_date,
            ratio_provenance=ratio_provenance,
            reason="Dividend received unknown: supply dividend_egp or dps + shares_held.",
            missing_input="dividend_egp",
        )
    if dividend_egp < 0:
        return _insufficient(
            branch=PurificationBranch.INSUFFICIENT_DATA,
            dividend_egp=dividend_egp,
            dps=dps,
            dps_source=dps_source,
            dps_date=dps_date,
            ratio_provenance=ratio_provenance,
            reason="Dividend received must be >= 0.",
            missing_input="dividend_egp",
        )

    if is_compliant is False:
        # Failed-company dividend rule (IdealRatings/Boursa FAQ): holding a
        # FAIL name means purifying the entire dividend amount.
        return PurificationEstimate(
            status=PurificationStatus.OK,
            branch=PurificationBranch.FAIL_HOLDING,
            doctrine=PURIFICATION_DOCTRINE,
            amount_egp=dividend_egp,
            dividend_egp=dividend_egp,
            ratio=None,
            ratio_provenance=ratio_provenance,
            dps=dps,
            dps_source=dps_source,
            dps_date=dps_date,
            reason="Holding failed screening: purify the entire dividend amount.",
        )

    if non_permissible_revenue is None or total_revenue is None:
        missing = ", ".join(
            label
            for label, present in (
                ("non_permissible_revenue", non_permissible_revenue),
                ("total_revenue", total_revenue),
            )
            if present is None
        )
        return _insufficient(
            branch=PurificationBranch.INSUFFICIENT_DATA,
            dividend_egp=dividend_egp,
            dps=dps,
            dps_source=dps_source,
            dps_date=dps_date,
            ratio_provenance=ratio_provenance,
            reason=MISSING_RATIO_REASON,
            missing_input=missing,
        )
    if total_revenue == 0:
        return _insufficient(
            branch=PurificationBranch.INSUFFICIENT_DATA,
            dividend_egp=dividend_egp,
            dps=dps,
            dps_source=dps_source,
            dps_date=dps_date,
            ratio_provenance=ratio_provenance,
            reason="Total revenue is zero: purification ratio undefined.",
            missing_input="total_revenue",
        )
    if non_permissible_revenue < 0 or total_revenue < 0:
        return _insufficient(
            branch=PurificationBranch.INSUFFICIENT_DATA,
            dividend_egp=dividend_egp,
            dps=dps,
            dps_source=dps_source,
            dps_date=dps_date,
            ratio_provenance=ratio_provenance,
            reason="Revenue inputs must be >= 0.",
            missing_input="non_permissible_revenue, total_revenue",
        )

    ratio = non_permissible_revenue / total_revenue
    return PurificationEstimate(
        status=PurificationStatus.OK,
        branch=PurificationBranch.RATIO,
        doctrine=PURIFICATION_DOCTRINE,
        amount_egp=dividend_egp * ratio,
        dividend_egp=dividend_egp,
        ratio=ratio,
        ratio_provenance=ratio_provenance,
        dps=dps,
        dps_source=dps_source,
        dps_date=dps_date,
    )
