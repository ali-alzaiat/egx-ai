"""Piotroski F-Score (R47 Q1): nine yes/no checks on the latest fiscal year vs the prior one.

Pure and deterministic: no database, clock or I/O. It is shown beside the investment score and
is NOT part of it (no change to the score or its methodology version).

Source: Piotroski, J. D. (2000), "Value Investing: The Use of Historical Financial Statement
Information to Separate Winners from Losers", Journal of Accounting Research 38 (Supplement).

Our deviations from the paper, each stated in ``DEVIATIONS`` and returned with every result:

* ROA, asset turnover and leverage use **year-end** total assets of the same fiscal year (the
  paper uses beginning-of-year assets, which would need a third year of statements).
* Leverage is **interest-bearing debt / total assets**: the statement ontology has no separate
  long-term-debt line.
* "No new shares" compares period-end ``shares_outstanding``; a bonus issue or split also
  raises the count and is not distinguished (it shows as FAIL with this caveat).
* ROA uses ``net_income`` (to common holders), not income before extraordinary items.

A check with a missing or unusable input is INSUFFICIENT_DATA, never a pass or a fail. The
total is "passes out of the checks that ran", plus how many ran. Banks are NOT_RUN: working
capital, gross margin and debt/asset ratios do not describe a bank.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

PIOTROSKI_METHODOLOGY_VERSION = "piotroski-1.0"
CHECKS_TOTAL = 9

CheckStatus = Literal["PASS", "FAIL", "INSUFFICIENT_DATA"]
ResultStatus = Literal["AVAILABLE", "INSUFFICIENT_DATA", "NOT_RUN"]

#: Statement-line codes the F-Score reads (per fiscal year).
PIOTROSKI_LINE_CODES: tuple[str, ...] = (
    "net_income",
    "total_assets",
    "cfo",
    "interest_bearing_debt",
    "current_assets",
    "current_liabilities",
    "shares_outstanding",
    "gross_profit",
    "revenue",
)

DEVIATIONS: tuple[str, ...] = (
    "ROA, asset turnover and leverage use year-end total assets of the same fiscal year, "
    "not beginning-of-year assets.",
    "Leverage is interest-bearing debt / total assets (no separate long-term-debt line).",
    "No new shares compares period-end shares outstanding; bonus issues and splits also raise "
    "the count and are not distinguished.",
    "ROA uses net income to common holders, not income before extraordinary items.",
)

Values = Mapping[str, Decimal]


@dataclass(frozen=True, slots=True)
class PiotroskiCheck:
    key: str
    label: str
    group: Literal["profitability", "leverage_liquidity", "operating_efficiency"]
    status: CheckStatus
    reason: str | None
    #: Named inputs as plain strings (None = the input was missing); never a substituted 0.
    inputs: dict[str, str | None]


@dataclass(frozen=True, slots=True)
class PiotroskiResult:
    version: str
    status: ResultStatus
    reason: str | None
    fiscal_year: int | None
    prior_fiscal_year: int | None
    #: Passes out of the checks that ran; None when none ran (never 0 for "no data").
    passes: int | None
    checks_run: int
    checks_total: int = CHECKS_TOTAL
    checks: tuple[PiotroskiCheck, ...] = ()
    deviations: tuple[str, ...] = field(default=DEVIATIONS)


@dataclass(frozen=True, slots=True)
class _Ratio:
    value: Decimal | None
    reason: str | None
    inputs: dict[str, str | None]


def _s(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def _ratio(
    num_code: str,
    den_code: str,
    vals: Values | None,
    year: int | None,
    *,
    den_positive: bool = True,
    den_label: str | None = None,
) -> _Ratio:
    num = vals.get(num_code) if vals is not None else None
    den = vals.get(den_code) if vals is not None else None
    tag = f"FY{year}" if year is not None else "period"
    inputs = {f"{num_code}_{tag}": _s(num), f"{den_code}_{tag}": _s(den)}
    if vals is None:
        return _Ratio(None, f"no approved annual statements for {tag}", inputs)
    if num is None:
        return _Ratio(None, f"missing statement line: {num_code} ({tag})", inputs)
    if den is None:
        return _Ratio(None, f"missing statement line: {den_code} ({tag})", inputs)
    if den_positive and den <= 0:
        name = den_label or den_code
        return _Ratio(None, f"{name} is not positive ({tag}): ratio undefined", inputs)
    return _Ratio(num / den, None, inputs)


def _insufficient(
    key: str, label: str, group: str, reason: str, inputs: dict[str, str | None]
) -> PiotroskiCheck:
    return PiotroskiCheck(key, label, group, "INSUFFICIENT_DATA", reason, inputs)  # type: ignore[arg-type]


def _verdict(
    key: str, label: str, group: str, passed: bool, inputs: dict[str, str | None],
    reason: str | None = None,
) -> PiotroskiCheck:
    status: CheckStatus = "PASS" if passed else "FAIL"
    return PiotroskiCheck(key, label, group, status, reason, inputs)  # type: ignore[arg-type]


def _level_check(
    key: str, label: str, group: str, r: _Ratio, test: Callable[[Decimal], bool]
) -> PiotroskiCheck:
    if r.value is None:
        return _insufficient(key, label, group, r.reason or "input unavailable", r.inputs)
    inputs = dict(r.inputs)
    inputs["ratio"] = str(r.value)
    return _verdict(key, label, group, test(r.value), inputs)


def _delta_check(
    key: str,
    label: str,
    group: str,
    now: _Ratio,
    before: _Ratio,
    *,
    improves_when: Literal["up", "down"],
) -> PiotroskiCheck:
    inputs = {**now.inputs, **before.inputs}
    if now.value is None or before.value is None:
        reason = now.reason if now.value is None else before.reason
        return _insufficient(key, label, group, reason or "input unavailable", inputs)
    inputs["ratio_now"] = str(now.value)
    inputs["ratio_prior"] = str(before.value)
    better = now.value > before.value if improves_when == "up" else now.value < before.value
    return _verdict(key, label, group, better, inputs)


def evaluate_piotroski(
    latest: Values | None,
    prior: Values | None,
    *,
    fiscal_year: int | None,
    prior_fiscal_year: int | None,
    is_bank: bool = False,
    bank_reason: str | None = None,
) -> PiotroskiResult:
    """Run the nine checks. ``latest``/``prior`` map statement-line code to value."""
    if is_bank:
        return PiotroskiResult(
            version=PIOTROSKI_METHODOLOGY_VERSION,
            status="NOT_RUN",
            reason=bank_reason
            or "Banks are not scored: working capital, gross margin and debt/asset ratios do "
            "not describe a bank.",
            fiscal_year=fiscal_year,
            prior_fiscal_year=prior_fiscal_year,
            passes=None,
            checks_run=0,
        )
    if latest is None:
        return PiotroskiResult(
            version=PIOTROSKI_METHODOLOGY_VERSION,
            status="INSUFFICIENT_DATA",
            reason="no approved annual statement lines",
            fiscal_year=None,
            prior_fiscal_year=None,
            passes=None,
            checks_run=0,
        )

    p, q = "profitability", "leverage_liquidity"
    e = "operating_efficiency"
    fy, pfy = fiscal_year, prior_fiscal_year

    roa_now = _ratio("net_income", "total_assets", latest, fy, den_label="total assets")
    roa_prior = _ratio("net_income", "total_assets", prior, pfy, den_label="total assets")
    lev_now = _ratio(
        "interest_bearing_debt", "total_assets", latest, fy, den_label="total assets"
    )
    lev_prior = _ratio(
        "interest_bearing_debt", "total_assets", prior, pfy, den_label="total assets"
    )
    cr_now = _ratio(
        "current_assets", "current_liabilities", latest, fy, den_label="current liabilities"
    )
    cr_prior = _ratio(
        "current_assets", "current_liabilities", prior, pfy, den_label="current liabilities"
    )
    gm_now = _ratio("gross_profit", "revenue", latest, fy, den_label="revenue")
    gm_prior = _ratio("gross_profit", "revenue", prior, pfy, den_label="revenue")
    at_now = _ratio("revenue", "total_assets", latest, fy, den_label="total assets")
    at_prior = _ratio("revenue", "total_assets", prior, pfy, den_label="total assets")

    checks: list[PiotroskiCheck] = [
        _level_check("roa_positive", "Return on assets is positive", p, roa_now, lambda v: v > 0),
        _cfo_positive(latest, fy),
        _delta_check(
            "roa_improving", "Return on assets is higher than last year", p, roa_now, roa_prior,
            improves_when="up",
        ),
        _accruals(latest, fy),
        _delta_check(
            "leverage_falling", "Interest-bearing debt / assets is lower than last year", q,
            lev_now, lev_prior, improves_when="down",
        ),
        _delta_check(
            "current_ratio_improving", "Current ratio is higher than last year", q,
            cr_now, cr_prior, improves_when="up",
        ),
        _no_new_shares(latest, prior, fy, pfy),
        _delta_check(
            "gross_margin_improving", "Gross margin is higher than last year", e,
            gm_now, gm_prior, improves_when="up",
        ),
        _delta_check(
            "asset_turnover_improving", "Asset turnover is higher than last year", e,
            at_now, at_prior, improves_when="up",
        ),
    ]
    ran = [c for c in checks if c.status != "INSUFFICIENT_DATA"]
    passes = sum(1 for c in ran if c.status == "PASS")
    if not ran:
        return PiotroskiResult(
            version=PIOTROSKI_METHODOLOGY_VERSION,
            status="INSUFFICIENT_DATA",
            reason="none of the nine checks had the statement lines it needs",
            fiscal_year=fy,
            prior_fiscal_year=pfy,
            passes=None,
            checks_run=0,
            checks=tuple(checks),
        )
    return PiotroskiResult(
        version=PIOTROSKI_METHODOLOGY_VERSION,
        status="AVAILABLE",
        reason=None,
        fiscal_year=fy,
        prior_fiscal_year=pfy,
        passes=passes,
        checks_run=len(ran),
        checks=tuple(checks),
    )


def _cfo_positive(latest: Values, fy: int | None) -> PiotroskiCheck:
    key, label, group = "cfo_positive", "Operating cash flow is positive", "profitability"
    cfo = latest.get("cfo")
    inputs = {f"cfo_FY{fy}": _s(cfo)}
    if cfo is None:
        return _insufficient(key, label, group, f"missing statement line: cfo (FY{fy})", inputs)
    return _verdict(key, label, group, cfo > 0, inputs)


def _accruals(latest: Values, fy: int | None) -> PiotroskiCheck:
    key = "accruals_cash_backed"
    label = "Operating cash flow exceeds net income"
    group = "profitability"
    cfo, ni = latest.get("cfo"), latest.get("net_income")
    inputs = {f"cfo_FY{fy}": _s(cfo), f"net_income_FY{fy}": _s(ni)}
    for code, val in (("cfo", cfo), ("net_income", ni)):
        if val is None:
            reason = f"missing statement line: {code} (FY{fy})"
            return _insufficient(key, label, group, reason, inputs)
    assert cfo is not None and ni is not None
    return _verdict(key, label, group, cfo > ni, inputs)


def _no_new_shares(
    latest: Values, prior: Values | None, fy: int | None, pfy: int | None
) -> PiotroskiCheck:
    key, label, group = "no_new_shares", "No new shares issued", "leverage_liquidity"
    now = latest.get("shares_outstanding")
    before = prior.get("shares_outstanding") if prior is not None else None
    inputs = {f"shares_outstanding_FY{fy}": _s(now), f"shares_outstanding_FY{pfy}": _s(before)}
    if prior is None:
        reason = f"no approved annual statements for FY{pfy}"
        return _insufficient(key, label, group, reason, inputs)
    if now is None:
        return _insufficient(
            key, label, group, f"missing statement line: shares_outstanding (FY{fy})", inputs
        )
    if before is None:
        return _insufficient(
            key, label, group, f"missing statement line: shares_outstanding (FY{pfy})", inputs
        )
    if now <= before:
        return _verdict(key, label, group, True, inputs)
    return _verdict(
        key, label, group, False, inputs,
        reason="share count rose; a bonus issue or split is not distinguished from new equity",
    )
