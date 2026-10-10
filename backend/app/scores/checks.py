"""Pure, deterministic investment-score check engine (no I/O, no clock, no DB).

Every check returns PASS / FAIL / NOT_RUN with its threshold and cited
inputs. Missing inputs report NOT_RUN — never FAIL, never zero-filled.
Zero and negative values rank naturally inside each formula; ratios with a
non-positive denominator report NOT_RUN (undefined, not failed).

Check inventory (SWS MODEL.markdown via research §1; R28 cuts applied):
- value (5, degraded): two FV discount tiers + PE/PB vs market/industry.
  CUT: PEG, analyst-target legs (thin consensus).
- past (6, full): EPS growth/level/momentum, ROE level, ROCE trend,
  ROA vs industry.
- health-standard (6) / health-banks (6, individually gated dual track).
- dividend (3, narrowed): stability + earnings coverage + growing.
  CUT: cash-payout-%/yield thresholds (`no data`).
- growth (3, honest-degrade): historical-extrapolation fallback plus a
  disclosed current-ROE proxy for forecast ROE, else NOT_RUN.
  No synthetic consensus is ever constructed.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from app.scores.constants import (
    BANK_CHARGE_OFF_MAX,
    BANK_DEPOSITS_SHARE_MIN,
    BANK_EQUITY_MULTIPLIER_MAX,
    BANK_LOANS_TO_ASSETS_MAX,
    BANK_LOANS_TO_DEPOSITS_MAX,
    CONFIDENCE_BANDS,
    DIVIDEND_GROWING_MIN_HISTORY_YEARS,
    DIVIDEND_PAYOUT_MAX,
    DIVIDEND_PAYOUT_MIN,
    DIVIDEND_STABILITY_MAX_DROP,
    FUTURE_ROE_THRESHOLD,
    GROWTH_HIGH_THRESHOLD,
    HEALTH_DE_RATIO_MAX,
    HEALTH_EBIT_INTEREST_COVER_MIN,
    HEALTH_OCF_TO_DEBT_MIN,
    MIN_CHECKS_RUN_PER_COMPONENT,
    MIN_VALID_COMPONENTS_FOR_HEADLINE,
    PAST_ROE_THRESHOLD,
    SCORE_METHODOLOGY_VERSION,
    VALUE_FV_DISCOUNT_THRESHOLD,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class CheckStatus(enum.StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"


class ComponentStatus(enum.StrEnum):
    AVAILABLE = "AVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True, slots=True)
class ScoreInputs:
    """Every check input; None means unknown (check reports NOT_RUN)."""

    # Value
    current_price: Decimal | None = None
    fair_value: Decimal | None = None
    pe_ratio: Decimal | None = None
    market_pe_avg: Decimal | None = None
    industry_pe_avg: Decimal | None = None
    pb_ratio: Decimal | None = None
    industry_pb_avg: Decimal | None = None
    # Past performance
    eps_growth_1y: Decimal | None = None
    industry_eps_growth_avg: Decimal | None = None
    eps_now: Decimal | None = None
    eps_5y_ago: Decimal | None = None
    eps_growth_now: Decimal | None = None
    eps_growth_5y_avg: Decimal | None = None
    roe_now: Decimal | None = None
    roce_now: Decimal | None = None
    roce_3y_ago: Decimal | None = None
    roa_now: Decimal | None = None
    industry_roa_avg: Decimal | None = None
    # Health, standard track
    st_assets: Decimal | None = None
    st_liabilities: Decimal | None = None
    lt_liabilities: Decimal | None = None
    de_ratio_now: Decimal | None = None
    de_ratio_5y_ago: Decimal | None = None
    operating_cash_flow: Decimal | None = None
    total_debt: Decimal | None = None
    ebit: Decimal | None = None
    net_interest_expense: Decimal | None = None
    total_assets: Decimal | None = None
    total_equity: Decimal | None = None
    # Health, bank track (each check individually gated)
    bank_allowance: Decimal | None = None
    bank_npl: Decimal | None = None
    bank_deposits: Decimal | None = None
    bank_total_liabilities: Decimal | None = None
    bank_net_loans: Decimal | None = None
    bank_net_charge_offs: Decimal | None = None
    bank_avg_loans: Decimal | None = None
    # Dividend (DPS history ordered oldest -> newest)
    dps_history: tuple[Decimal, ...] = ()
    dividend_years: int | None = None
    earnings_payout: Decimal | None = None
    # Growth (historical-extrapolation fallback; forecasts never invented)
    hist_earnings_growth: Decimal | None = None
    hist_revenue_growth: Decimal | None = None


@dataclass(frozen=True, slots=True)
class CheckResult:
    check_key: str
    component: str
    status: CheckStatus
    threshold: str
    inputs: dict[str, str | None]
    reason: str

    def as_dict(self) -> dict[str, object]:
        return {
            "check_key": self.check_key,
            "component": self.component,
            "status": self.status.value,
            "threshold": self.threshold,
            "inputs": dict(self.inputs),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ComponentResult:
    key: str
    status: ComponentStatus
    score: float | None
    passes: int
    ran: int
    total: int
    checks: tuple[CheckResult, ...] = field(default_factory=tuple)
    reason: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "status": self.status.value,
            "score": self.score,
            "passes": self.passes,
            "ran": self.ran,
            "total": self.total,
            "reason": self.reason,
            "checks": [c.as_dict() for c in self.checks],
        }


@dataclass(frozen=True, slots=True)
class Confidence:
    level: str
    dq_score: float | None
    n_checks_run: int
    bands: tuple[tuple[str, float, int], ...] = CONFIDENCE_BANDS
    reason: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "level": self.level,
            "dq_score": self.dq_score,
            "n_checks_run": self.n_checks_run,
            "bands": [
                {"level": level, "min_dq_score": min_dq, "min_checks_run": min_n}
                for level, min_dq, min_n in self.bands
            ],
            "reason": self.reason,
        }


def _opt(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _not_run(
    check_key: str, component: str, threshold: str, inputs: dict[str, str | None], reason: str
) -> CheckResult:
    return CheckResult(
        check_key=check_key,
        component=component,
        status=CheckStatus.NOT_RUN,
        threshold=threshold,
        inputs=inputs,
        reason=reason,
    )


def _verdict(
    check_key: str,
    component: str,
    passed: bool,
    threshold: str,
    inputs: dict[str, str | None],
    pass_reason: str,
    fail_reason: str,
) -> CheckResult:
    return CheckResult(
        check_key=check_key,
        component=component,
        status=CheckStatus.PASS if passed else CheckStatus.FAIL,
        threshold=threshold,
        inputs=inputs,
        reason=pass_reason if passed else fail_reason,
    )


# ---------------------------------------------------------------------------
# Value (degraded: FV + PE/PB vs market/industry; no PEG/analyst-target)
# ---------------------------------------------------------------------------


def check_value_fv_discount(i: ScoreInputs) -> CheckResult:
    key, comp = "value_fv_discount", "value"
    threshold = f"current price >= {VALUE_FV_DISCOUNT_THRESHOLD * 100:.0f}% below fair value"
    cited = {"current_price": _opt(i.current_price), "fair_value": _opt(i.fair_value)}
    if i.current_price is None or i.fair_value is None:
        return _not_run(key, comp, threshold, cited, "No fair value or price; check not run.")
    if i.fair_value <= 0 or i.current_price <= 0:
        return _not_run(
            key, comp, threshold, cited, "Non-positive fair value or price; discount undefined."
        )
    discount = (i.fair_value - i.current_price) / i.fair_value
    return _verdict(
        key, comp, discount >= VALUE_FV_DISCOUNT_THRESHOLD, threshold, cited,
        f"Price is {discount * 100:.1f}% below fair value; meets the discount threshold.",
        f"Price is {discount * 100:.1f}% vs fair value; below the discount threshold.",
    )


def check_value_fv_deep_discount(i: ScoreInputs) -> CheckResult:
    """Second intrinsic point at a 40%+ discount (SWS 'substantially undervalued')."""
    key, comp = "value_fv_deep_discount", "value"
    threshold = "current price >= 40% below fair value"
    cited = {"current_price": _opt(i.current_price), "fair_value": _opt(i.fair_value)}
    if i.current_price is None or i.fair_value is None:
        return _not_run(key, comp, threshold, cited, "No fair value or price; check not run.")
    if i.fair_value <= 0 or i.current_price <= 0:
        return _not_run(
            key, comp, threshold, cited, "Non-positive fair value or price; discount undefined."
        )
    discount = (i.fair_value - i.current_price) / i.fair_value
    return _verdict(
        key, comp, discount >= Decimal("0.40"), threshold, cited,
        f"Price is {discount * 100:.1f}% below fair value; deeply discounted.",
        f"Price is {discount * 100:.1f}% vs fair value; not deeply discounted.",
    )


def _pe_check(
    key: str, pe: Decimal | None, avg: Decimal | None, avg_label: str
) -> CheckResult:
    comp = "value"
    threshold = f"0 < PE < {avg_label} average ({_opt(avg)})"
    cited = {"pe_ratio": _opt(pe), "average": _opt(avg)}
    if pe is None or avg is None:
        return _not_run(key, comp, threshold, cited, "No PE or comparison average; check not run.")
    if pe <= 0:
        return _verdict(
            key, comp, False, threshold, cited,
            "", f"PE {pe} is not positive; fails the 0 < PE leg.",
        )
    return _verdict(
        key, comp, pe < avg, threshold, cited,
        f"PE {pe} is below the {avg_label} average {avg}.",
        f"PE {pe} is at or above the {avg_label} average {avg}.",
    )


def check_value_pe_vs_market(i: ScoreInputs) -> CheckResult:
    return _pe_check("value_pe_vs_market", i.pe_ratio, i.market_pe_avg, "market")


def check_value_pe_vs_industry(i: ScoreInputs) -> CheckResult:
    return _pe_check("value_pe_vs_industry", i.pe_ratio, i.industry_pe_avg, "industry")


def check_value_pb_vs_industry(i: ScoreInputs) -> CheckResult:
    key, comp = "value_pb_vs_industry", "value"
    threshold = f"0 < PB < industry average ({_opt(i.industry_pb_avg)})"
    cited = {"pb_ratio": _opt(i.pb_ratio), "industry_pb_avg": _opt(i.industry_pb_avg)}
    if i.pb_ratio is None or i.industry_pb_avg is None:
        return _not_run(key, comp, threshold, cited, "No PB or industry average; check not run.")
    if i.pb_ratio <= 0:
        return _verdict(key, comp, False, threshold, cited, "",
                        f"PB {i.pb_ratio} is not positive; fails the 0 < PB leg.")
    return _verdict(
        key, comp, i.pb_ratio < i.industry_pb_avg, threshold, cited,
        f"PB {i.pb_ratio} is below the industry average {i.industry_pb_avg}.",
        f"PB {i.pb_ratio} is at or above the industry average {i.industry_pb_avg}.",
    )


# ---------------------------------------------------------------------------
# Past performance (full 6)
# ---------------------------------------------------------------------------


def check_past_eps_growth_vs_industry(i: ScoreInputs) -> CheckResult:
    key, comp = "past_eps_growth_vs_industry", "past"
    threshold = f"1-yr EPS growth > industry average ({_opt(i.industry_eps_growth_avg)})"
    cited = {"eps_growth_1y": _opt(i.eps_growth_1y),
             "industry_eps_growth_avg": _opt(i.industry_eps_growth_avg)}
    if i.eps_growth_1y is None or i.industry_eps_growth_avg is None:
        return _not_run(key, comp, threshold, cited, "No EPS growth/industry avg; check not run.")
    return _verdict(
        key, comp, i.eps_growth_1y > i.industry_eps_growth_avg, threshold, cited,
        f"1-yr EPS growth {i.eps_growth_1y} is above the industry average.",
        f"1-yr EPS growth {i.eps_growth_1y} is at or below the industry average.",
    )


def check_past_eps_vs_5y(i: ScoreInputs) -> CheckResult:
    key, comp = "past_eps_vs_5y", "past"
    threshold = "EPS now > EPS 5 years ago"
    cited = {"eps_now": _opt(i.eps_now), "eps_5y_ago": _opt(i.eps_5y_ago)}
    if i.eps_now is None or i.eps_5y_ago is None:
        return _not_run(key, comp, threshold, cited, "No current or 5-yr-ago EPS; check not run.")
    return _verdict(
        key, comp, i.eps_now > i.eps_5y_ago, threshold, cited,
        f"EPS now {i.eps_now} exceeds EPS 5 years ago {i.eps_5y_ago}.",
        f"EPS now {i.eps_now} does not exceed EPS 5 years ago {i.eps_5y_ago}.",
    )


def check_past_eps_momentum(i: ScoreInputs) -> CheckResult:
    key, comp = "past_eps_momentum", "past"
    threshold = "current-yr EPS growth > 5-yr average EPS growth"
    cited = {"eps_growth_now": _opt(i.eps_growth_now),
             "eps_growth_5y_avg": _opt(i.eps_growth_5y_avg)}
    if i.eps_growth_now is None or i.eps_growth_5y_avg is None:
        return _not_run(key, comp, threshold, cited, "No current/5-yr EPS growth; check not run.")
    return _verdict(
        key, comp, i.eps_growth_now > i.eps_growth_5y_avg, threshold, cited,
        "Current EPS growth exceeds its 5-yr average.",
        "Current EPS growth is at or below its 5-yr average.",
    )


def check_past_roe_level(i: ScoreInputs) -> CheckResult:
    key, comp = "past_roe_level", "past"
    threshold = f"current ROE > {PAST_ROE_THRESHOLD * 100:.0f}%"
    cited = {"roe_now": _opt(i.roe_now)}
    if i.roe_now is None:
        return _not_run(key, comp, threshold, cited, "No current ROE; check not run.")
    return _verdict(
        key, comp, i.roe_now > PAST_ROE_THRESHOLD, threshold, cited,
        f"Current ROE {i.roe_now} exceeds {PAST_ROE_THRESHOLD}.",
        f"Current ROE {i.roe_now} is at or below {PAST_ROE_THRESHOLD}.",
    )


def check_past_roce_trend(i: ScoreInputs) -> CheckResult:
    key, comp = "past_roce_trend", "past"
    threshold = "current ROCE > ROCE 3 years ago"
    cited = {"roce_now": _opt(i.roce_now), "roce_3y_ago": _opt(i.roce_3y_ago)}
    if i.roce_now is None or i.roce_3y_ago is None:
        return _not_run(key, comp, threshold, cited, "No current or 3-yr-ago ROCE; check not run.")
    return _verdict(
        key, comp, i.roce_now > i.roce_3y_ago, threshold, cited,
        f"Current ROCE {i.roce_now} exceeds ROCE 3 years ago {i.roce_3y_ago}.",
        f"Current ROCE {i.roce_now} is at or below ROCE 3 years ago {i.roce_3y_ago}.",
    )


def check_past_roa_vs_industry(i: ScoreInputs) -> CheckResult:
    key, comp = "past_roa_vs_industry", "past"
    threshold = f"current ROA > industry average ({_opt(i.industry_roa_avg)})"
    cited = {"roa_now": _opt(i.roa_now), "industry_roa_avg": _opt(i.industry_roa_avg)}
    if i.roa_now is None or i.industry_roa_avg is None:
        return _not_run(key, comp, threshold, cited, "No ROA or industry average; check not run.")
    return _verdict(
        key, comp, i.roa_now > i.industry_roa_avg, threshold, cited,
        f"Current ROA {i.roa_now} is above the industry average.",
        f"Current ROA {i.roa_now} is at or below the industry average.",
    )


# ---------------------------------------------------------------------------
# Health, standard track (6)
# ---------------------------------------------------------------------------


def check_health_liquidity_st(i: ScoreInputs) -> CheckResult:
    key, comp = "health_liquidity_st", "health"
    threshold = "short-term assets > short-term liabilities"
    cited = {"st_assets": _opt(i.st_assets), "st_liabilities": _opt(i.st_liabilities)}
    if i.st_assets is None or i.st_liabilities is None:
        return _not_run(key, comp, threshold, cited, "No short-term items; check not run.")
    return _verdict(
        key, comp, i.st_assets > i.st_liabilities, threshold, cited,
        "Short-term assets cover short-term liabilities.",
        "Short-term assets do not cover short-term liabilities.",
    )


def check_health_liquidity_lt(i: ScoreInputs) -> CheckResult:
    key, comp = "health_liquidity_lt", "health"
    threshold = "short-term assets > long-term liabilities"
    cited = {"st_assets": _opt(i.st_assets), "lt_liabilities": _opt(i.lt_liabilities)}
    if i.st_assets is None or i.lt_liabilities is None:
        return _not_run(
            key, comp, threshold, cited, "No ST assets or LT liabilities; check not run."
        )
    return _verdict(
        key, comp, i.st_assets > i.lt_liabilities, threshold, cited,
        "Short-term assets cover long-term liabilities.",
        "Short-term assets do not cover long-term liabilities.",
    )


def check_health_leverage_trend(i: ScoreInputs) -> CheckResult:
    key, comp = "health_leverage_trend", "health"
    threshold = "D/E ratio has not increased vs 5 years ago"
    cited = {"de_ratio_now": _opt(i.de_ratio_now), "de_ratio_5y_ago": _opt(i.de_ratio_5y_ago)}
    if i.de_ratio_now is None or i.de_ratio_5y_ago is None:
        return _not_run(key, comp, threshold, cited, "No current or 5-yr-ago D/E; check not run.")
    return _verdict(
        key, comp, i.de_ratio_now <= i.de_ratio_5y_ago, threshold, cited,
        "D/E has not increased vs 5 years ago.",
        "D/E has increased vs 5 years ago.",
    )


def check_health_leverage_level(i: ScoreInputs) -> CheckResult:
    key, comp = "health_leverage_level", "health"
    threshold = f"D/E < {HEALTH_DE_RATIO_MAX * 100:.0f}%"
    cited = {"de_ratio_now": _opt(i.de_ratio_now)}
    if i.de_ratio_now is None:
        return _not_run(key, comp, threshold, cited, "No D/E ratio; check not run.")
    return _verdict(
        key, comp, i.de_ratio_now < HEALTH_DE_RATIO_MAX, threshold, cited,
        f"D/E {i.de_ratio_now} is below {HEALTH_DE_RATIO_MAX}.",
        f"D/E {i.de_ratio_now} is at or above {HEALTH_DE_RATIO_MAX}.",
    )


def check_health_cash_coverage(i: ScoreInputs) -> CheckResult:
    key, comp = "health_cash_coverage", "health"
    threshold = f"operating cash flow > {HEALTH_OCF_TO_DEBT_MIN * 100:.0f}% of total debt"
    cited = {"operating_cash_flow": _opt(i.operating_cash_flow),
             "total_debt": _opt(i.total_debt)}
    if i.operating_cash_flow is None or i.total_debt is None:
        return _not_run(key, comp, threshold, cited, "No cash flow or debt figure; check not run.")
    if i.total_debt <= 0:
        return _not_run(
            key, comp, threshold, cited, "Total debt is not positive; coverage ratio undefined.")
    return _verdict(
        key, comp, i.operating_cash_flow > HEALTH_OCF_TO_DEBT_MIN * i.total_debt,
        threshold, cited,
        "Operating cash flow covers more than 20% of total debt.",
        "Operating cash flow covers 20% or less of total debt.",
    )


def check_health_interest_cover(i: ScoreInputs) -> CheckResult:
    key, comp = "health_interest_cover", "health"
    threshold = f"EBIT >= {HEALTH_EBIT_INTEREST_COVER_MIN}x net interest expense"
    cited = {"ebit": _opt(i.ebit), "net_interest_expense": _opt(i.net_interest_expense)}
    if i.ebit is None or i.net_interest_expense is None:
        return _not_run(key, comp, threshold, cited, "No EBIT or interest expense; check not run.")
    if i.net_interest_expense <= 0:
        return _not_run(
            key, comp, threshold, cited, "Interest expense is not positive; cover ratio undefined.")
    return _verdict(
        key, comp, i.ebit >= HEALTH_EBIT_INTEREST_COVER_MIN * i.net_interest_expense,
        threshold, cited,
        "EBIT covers at least 5x net interest expense.",
        "EBIT covers less than 5x net interest expense.",
    )


# ---------------------------------------------------------------------------
# Health, bank track (6, each individually gated per-ticker)
# ---------------------------------------------------------------------------


def check_bank_capital(i: ScoreInputs) -> CheckResult:
    key, comp = "bank_capital", "health"
    threshold = f"total assets <= {BANK_EQUITY_MULTIPLIER_MAX:.0f}x total equity"
    cited = {"total_assets": _opt(i.total_assets), "total_equity": _opt(i.total_equity)}
    if i.total_assets is None or i.total_equity is None:
        return _not_run(key, comp, threshold, cited, "No bank assets or equity; check not run.")
    if i.total_equity <= 0:
        return _not_run(
            key, comp, threshold, cited, "Non-positive bank equity; multiplier undefined."
        )
    return _verdict(
        key, comp, i.total_assets <= BANK_EQUITY_MULTIPLIER_MAX * i.total_equity,
        threshold, cited,
        "Assets are within 20x equity.",
        "Assets exceed 20x equity.",
    )


def check_bank_allowance(i: ScoreInputs) -> CheckResult:
    key, comp = "bank_allowance", "health"
    threshold = "loan-loss allowance > non-performing loans"
    cited = {"bank_allowance": _opt(i.bank_allowance), "bank_npl": _opt(i.bank_npl)}
    if i.bank_allowance is None or i.bank_npl is None:
        return _not_run(key, comp, threshold, cited, "No allowance or NPL figure; check not run.")
    return _verdict(
        key, comp, i.bank_allowance > i.bank_npl, threshold, cited,
        "Allowance fully covers non-performing loans.",
        "Allowance does not cover non-performing loans.",
    )


def check_bank_funding(i: ScoreInputs) -> CheckResult:
    key, comp = "bank_funding", "health"
    threshold = f"deposits > {BANK_DEPOSITS_SHARE_MIN * 100:.0f}% of liabilities"
    cited = {"bank_deposits": _opt(i.bank_deposits),
             "bank_total_liabilities": _opt(i.bank_total_liabilities)}
    if i.bank_deposits is None or i.bank_total_liabilities is None:
        return _not_run(key, comp, threshold, cited, "No deposit/liability figure; check not run.")
    if i.bank_total_liabilities <= 0:
        return _not_run(key, comp, threshold, cited, "Non-positive liabilities; share undefined.")
    return _verdict(
        key, comp, i.bank_deposits > BANK_DEPOSITS_SHARE_MIN * i.bank_total_liabilities,
        threshold, cited,
        "Deposits fund more than half of liabilities.",
        "Deposits fund half or less of liabilities.",
    )


def check_bank_loans_to_assets(i: ScoreInputs) -> CheckResult:
    key, comp = "bank_loans_to_assets", "health"
    threshold = f"net loans < {BANK_LOANS_TO_ASSETS_MAX * 100:.0f}% of assets"
    cited = {"bank_net_loans": _opt(i.bank_net_loans), "total_assets": _opt(i.total_assets)}
    if i.bank_net_loans is None or i.total_assets is None:
        return _not_run(key, comp, threshold, cited, "No net-loan or asset figure; check not run.")
    if i.total_assets <= 0:
        return _not_run(key, comp, threshold, cited, "Assets are not positive; ratio undefined.")
    return _verdict(
        key, comp, i.bank_net_loans < BANK_LOANS_TO_ASSETS_MAX * i.total_assets,
        threshold, cited,
        "Net loans are below 110% of assets.",
        "Net loans are at or above 110% of assets.",
    )


def check_bank_loans_to_deposits(i: ScoreInputs) -> CheckResult:
    key, comp = "bank_loans_to_deposits", "health"
    threshold = f"loans < {BANK_LOANS_TO_DEPOSITS_MAX * 100:.0f}% of deposits"
    cited = {"bank_net_loans": _opt(i.bank_net_loans), "bank_deposits": _opt(i.bank_deposits)}
    if i.bank_net_loans is None or i.bank_deposits is None:
        return _not_run(key, comp, threshold, cited, "No loan or deposit figure; check not run.")
    if i.bank_deposits <= 0:
        return _not_run(key, comp, threshold, cited, "Deposits are not positive; ratio undefined.")
    return _verdict(
        key, comp, i.bank_net_loans < BANK_LOANS_TO_DEPOSITS_MAX * i.bank_deposits,
        threshold, cited,
        "Loans are below 125% of deposits.",
        "Loans are at or above 125% of deposits.",
    )


def check_bank_charge_off(i: ScoreInputs) -> CheckResult:
    key, comp = "bank_charge_off", "health"
    threshold = f"net charge-off ratio < {BANK_CHARGE_OFF_MAX * 100:.0f}%"
    cited = {"bank_net_charge_offs": _opt(i.bank_net_charge_offs),
             "bank_avg_loans": _opt(i.bank_avg_loans)}
    if i.bank_net_charge_offs is None or i.bank_avg_loans is None:
        return _not_run(key, comp, threshold, cited, "No charge-off or loan figure; check not run.")
    if i.bank_avg_loans <= 0:
        return _not_run(key, comp, threshold, cited, "Non-positive avg loans; ratio undefined.")
    ratio = i.bank_net_charge_offs / i.bank_avg_loans
    return _verdict(
        key, comp, ratio < BANK_CHARGE_OFF_MAX, threshold, cited,
        f"Net charge-off ratio {ratio:.4f} is below 3%.",
        f"Net charge-off ratio {ratio:.4f} is at or above 3%.",
    )


# ---------------------------------------------------------------------------
# Dividend (narrowed: stability + earnings coverage + history)
# ---------------------------------------------------------------------------


def check_dividend_stability(i: ScoreInputs) -> CheckResult:
    key, comp = "dividend_stability", "dividend"
    threshold = f"no year-on-year DPS drop over {DIVIDEND_STABILITY_MAX_DROP * 100:.0f}%"
    cited = {"dps_history": "[" + ",".join(str(d) for d in i.dps_history) + "]"
             if i.dps_history else None}
    if len(i.dps_history) < 2:
        return _not_run(key, comp, threshold, cited, "Fewer than 2 DPS; check not run.")
    pairs = zip(i.dps_history, i.dps_history[1:], strict=False)
    for prev, now in pairs:
        if prev <= 0:
            return _not_run(
                key, comp, threshold, cited, "Non-positive base DPS; drop ratio undefined.")
        if (prev - now) / prev > DIVIDEND_STABILITY_MAX_DROP:
            return _verdict(key, comp, False, threshold, cited, "",
                            f"DPS fell from {prev} to {now}, more than 20%.")
    return _verdict(key, comp, True, threshold, cited,
                    "No year-on-year DPS drop exceeded 20%.", "")


def check_dividend_earnings_coverage(i: ScoreInputs) -> CheckResult:
    key, comp = "dividend_earnings_coverage", "dividend"
    threshold = f"earnings payout in {DIVIDEND_PAYOUT_MIN:.0f}-{DIVIDEND_PAYOUT_MAX * 100:.0f}%"
    cited = {"earnings_payout": _opt(i.earnings_payout)}
    if i.earnings_payout is None:
        return _not_run(key, comp, threshold, cited, "No earnings payout ratio; check not run.")
    covered = DIVIDEND_PAYOUT_MIN <= i.earnings_payout <= DIVIDEND_PAYOUT_MAX
    return _verdict(
        key, comp, covered, threshold, cited,
        f"Earnings payout {i.earnings_payout} is within 0-90%.",
        f"Earnings payout {i.earnings_payout} is outside 0-90% (uncovered or over-distributed).",
    )


def check_dividend_growing(i: ScoreInputs) -> CheckResult:
    key, comp = "dividend_growing", "dividend"
    threshold = f"DPS now > DPS {DIVIDEND_GROWING_MIN_HISTORY_YEARS}y ago"
    years = i.dividend_years if i.dividend_years is not None else len(i.dps_history)
    cited = {"dps_first": _opt(i.dps_history[0]) if i.dps_history else None,
             "dps_last": _opt(i.dps_history[-1]) if i.dps_history else None,
             "dividend_years": str(years)}
    if len(i.dps_history) < 2:
        return _not_run(key, comp, threshold, cited, "No DPS history; check not run.")
    if years < DIVIDEND_GROWING_MIN_HISTORY_YEARS:
        # Fails open: short pay-history is not evidence against growth.
        return _not_run(
            key, comp, threshold, cited,
            f"Only {years}y of pay history (<{DIVIDEND_GROWING_MIN_HISTORY_YEARS}y); "
            "growing-dividend fails open to not-run.",
        )
    return _verdict(
        key, comp, i.dps_history[-1] > i.dps_history[0], threshold, cited,
        "DPS now exceeds DPS 10 years ago.",
        "DPS now does not exceed DPS 10 years ago.",
    )


# ---------------------------------------------------------------------------
# Future growth (honest-degrade: historical extrapolation, else NOT_RUN)
# ---------------------------------------------------------------------------


def check_growth_earnings_hist(i: ScoreInputs) -> CheckResult:
    key, comp = "growth", "growth"
    threshold = (
        f"historical earnings growth > {GROWTH_HIGH_THRESHOLD * 100:.0f}% "
        "(extrapolation fallback; no consensus available)"
    )
    cited = {"hist_earnings_growth": _opt(i.hist_earnings_growth)}
    if i.hist_earnings_growth is None:
        return _not_run(
            key, comp, threshold, cited,
            "No forecast and no historical earnings growth; check not run.")
    return _verdict(
        key, comp, i.hist_earnings_growth > GROWTH_HIGH_THRESHOLD, threshold, cited,
        "Historical earnings growth exceeds 20%.",
        "Historical earnings growth is at or below 20%.",
    )


def check_growth_revenue_hist(i: ScoreInputs) -> CheckResult:
    key, comp = "growth", "growth"
    threshold = (
        f"historical revenue growth > {GROWTH_HIGH_THRESHOLD * 100:.0f}% "
        "(extrapolation fallback; no consensus available)"
    )
    cited = {"hist_revenue_growth": _opt(i.hist_revenue_growth)}
    if i.hist_revenue_growth is None:
        return _not_run(
            key, comp, threshold, cited,
            "No forecast and no historical revenue growth; check not run.")
    return _verdict(
        key, comp, i.hist_revenue_growth > GROWTH_HIGH_THRESHOLD, threshold, cited,
        "Historical revenue growth exceeds 20%.",
        "Historical revenue growth is at or below 20%.",
    )


# ---------------------------------------------------------------------------
# Engine: run, components, headline, confidence
# ---------------------------------------------------------------------------

def check_growth_roe_proxy(i: ScoreInputs) -> CheckResult:
    """Degraded proxy for SWS 'forecast ROE in 3y > 20%': current ROE stands in.

    Disclosed as a historical proxy — no forecast is constructed. It shares
    its input with past_roe_level (as SWS shares ROE across past and future),
    but the semantic differs: here current profitability proxies for the
    forward return the consensus check would use.
    """
    key, comp = "growth_roe_proxy", "growth"
    threshold = (
        f"current ROE > {FUTURE_ROE_THRESHOLD * 100:.0f}% "
        "(historical proxy; no forecast available)"
    )
    cited = {"roe_now": _opt(i.roe_now)}
    if i.roe_now is None:
        return _not_run(
            key, comp, threshold, cited,
            "No forecast and no current ROE; check not run.")
    return _verdict(
        key, comp, i.roe_now > FUTURE_ROE_THRESHOLD, threshold, cited,
        "Current ROE exceeds 20%, proxying forward returns.",
        "Current ROE is at or below 20%.",
    )


VALUE_CHECKS = (
    check_value_fv_discount,
    check_value_fv_deep_discount,
    check_value_pe_vs_market,
    check_value_pe_vs_industry,
    check_value_pb_vs_industry,
)
PAST_CHECKS = (
    check_past_eps_growth_vs_industry,
    check_past_eps_vs_5y,
    check_past_eps_momentum,
    check_past_roe_level,
    check_past_roce_trend,
    check_past_roa_vs_industry,
)
HEALTH_STANDARD_CHECKS = (
    check_health_liquidity_st,
    check_health_liquidity_lt,
    check_health_leverage_trend,
    check_health_leverage_level,
    check_health_cash_coverage,
    check_health_interest_cover,
)
HEALTH_BANK_CHECKS = (
    check_bank_capital,
    check_bank_allowance,
    check_bank_funding,
    check_bank_loans_to_assets,
    check_bank_loans_to_deposits,
    check_bank_charge_off,
)
DIVIDEND_CHECKS = (
    check_dividend_stability,
    check_dividend_earnings_coverage,
    check_dividend_growing,
)
GROWTH_CHECKS = (
    check_growth_earnings_hist,
    check_growth_revenue_hist,
    check_growth_roe_proxy,
)

COMPONENT_ORDER = ("value", "past", "health", "dividend", "growth")


def run_checks(
    inputs: ScoreInputs, *, health_track: str = "standard"
) -> tuple[CheckResult, ...]:
    """Run every check for the routed health track, deterministically."""
    checks = [*VALUE_CHECKS, *PAST_CHECKS]
    checks += list(HEALTH_BANK_CHECKS if health_track == "banks" else HEALTH_STANDARD_CHECKS)
    checks += [*DIVIDEND_CHECKS, *GROWTH_CHECKS]
    return tuple(fn(inputs) for fn in checks)


def score_component(key: str, checks: Sequence[CheckResult]) -> ComponentResult:
    """Component score = passes / ran x 100; valid only with >=3 checks run."""
    ran = sum(1 for c in checks if c.status is not CheckStatus.NOT_RUN)
    passes = sum(1 for c in checks if c.status is CheckStatus.PASS)
    total = len(checks)
    if ran < MIN_CHECKS_RUN_PER_COMPONENT:
        return ComponentResult(
            key=key,
            status=ComponentStatus.INSUFFICIENT_DATA,
            score=None,
            passes=passes,
            ran=ran,
            total=total,
            checks=tuple(checks),
            reason=(
                f"Only {ran} of {total} {key} checks ran "
                f"(need {MIN_CHECKS_RUN_PER_COMPONENT}); component INSUFFICIENT_DATA."
            ),
        )
    return ComponentResult(
        key=key,
        status=ComponentStatus.AVAILABLE,
        score=round(passes / ran * 100, 1),
        passes=passes,
        ran=ran,
        total=total,
        checks=tuple(checks),
        reason=f"{passes} of {ran} {key} checks passed.",
    )


def score_all_components(
    results: Sequence[CheckResult],
) -> dict[str, ComponentResult]:
    """Group check results by component (in COMPONENT_ORDER) and score each."""
    by_key: dict[str, list[CheckResult]] = {k: [] for k in COMPONENT_ORDER}
    for r in results:
        by_key.setdefault(r.component, []).append(r)
    return {k: score_component(k, by_key[k]) for k in COMPONENT_ORDER}


def headline_score(
    components: dict[str, ComponentResult],
) -> tuple[float | None, str]:
    """Equal-weight mean of valid components; null + reason below the floor."""
    valid = [c.score for c in components.values()
             if c.status is ComponentStatus.AVAILABLE and c.score is not None]
    if len(valid) < MIN_VALID_COMPONENTS_FOR_HEADLINE:
        return (
            None,
            f"Only {len(valid)} of {len(components)} components valid "
            f"(need {MIN_VALID_COMPONENTS_FOR_HEADLINE}); headline INSUFFICIENT_DATA.",
        )
    return (
        round(sum(valid) / len(valid), 1),
        f"Mean of {len(valid)} valid components (equal-weighted).",
    )


def confidence_for(
    dq_score: float | None,
    dq_capped: bool,
    n_checks_run: int,
    total_checks: int,
) -> Confidence:
    """DQ-fed confidence ladder (display-only; never moves the score).

    ``dq_score`` is the minimum across the investing scopes; ``dq_capped``
    is True when a scope is MISSING or unassessed (caps at Low).
    """
    if dq_capped or dq_score is None:
        return Confidence(
            level="Low",
            dq_score=dq_score,
            n_checks_run=n_checks_run,
            reason=(
                "Data-quality assessment MISSING or absent for an investing scope; "
                "confidence capped at Low."
            ),
        )
    for level, min_dq, min_n in CONFIDENCE_BANDS:
        if dq_score >= min_dq and n_checks_run >= min_n:
            return Confidence(
                level=level,
                dq_score=dq_score,
                n_checks_run=n_checks_run,
                reason=(
                    f"Min investing-scope quality {dq_score:.1f}/100 with "
                    f"{n_checks_run}/{total_checks} checks run."
                ),
            )
    return Confidence(
        level="Low",
        dq_score=dq_score,
        n_checks_run=n_checks_run,
        reason=(
            f"Min investing-scope quality {dq_score:.1f}/100 with "
            f"{n_checks_run}/{total_checks} checks run."
        ),
    )


def headline_label(headline: float | None) -> dict[str, str]:
    """Hedged headline copy per rule 10 — never a BUY/SELL instruction."""
    if headline is None:
        return {
            "label": "INSUFFICIENT_DATA",
            "detail": (
                "No headline: too few components have data, so no score is computed."
            ),
        }
    if headline >= 75:
        detail = "A high share of checks passed; potentially stronger under these assumptions."
    elif headline >= 50:
        detail = "A mixed share of checks passed; potentially mixed under these assumptions."
    elif headline >= 25:
        detail = "A low share of checks passed; potentially weaker under these assumptions."
    else:
        detail = "Very few checks passed; potentially weakest under these assumptions."
    return {"label": "SCORED", "detail": detail}


def buy_zone(
    fair_value: Decimal | None,
    current_price: Decimal | None,
    margin_of_safety: Decimal,
) -> dict[str, object]:
    """Display-only Buy Zone from the margin-of-safety selector; never scores."""
    if fair_value is None or fair_value <= 0 or current_price is None:
        return {
            "status": "INSUFFICIENT_DATA",
            "buy_zone_price": None,
            "in_buy_zone": None,
            "margin_of_safety": str(margin_of_safety),
            "reason": "No fair value or current price; Buy Zone not computed.",
        }
    zone = fair_value * (Decimal("1") - margin_of_safety)
    in_zone = current_price <= zone
    return {
        "status": "AVAILABLE",
        "buy_zone_price": str(zone),
        "in_buy_zone": in_zone,
        "margin_of_safety": str(margin_of_safety),
        "reason": (
            "Price is within the selected margin-of-safety Buy Zone; "
            "potentially of interest under these assumptions."
            if in_zone else
            "Price is above the selected margin-of-safety Buy Zone under these assumptions."
        ),
    }


def methodology() -> str:
    return SCORE_METHODOLOGY_VERSION
