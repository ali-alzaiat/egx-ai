"""Deterministic period comparison: TTM + YoY deltas + TTM margin (R34 P0-5).

1-yr + TTM only (5/3-yr best-fit deferred per R34). Every function is pure
Decimal arithmetic over caller-supplied series: a TTM needs exactly four
reported quarters — anything less is INSUFFICIENT_DATA, never a partial sum.
Division by zero (YoY off a zero base, margin off zero revenue) yields an
explicit reason, never an exception and never a zero-filled rate.
"""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

_FOUR_DP = Decimal("0.0001")


def quantize4(value: Decimal) -> Decimal:
    """Deterministic 4dp rounding for stored amounts and rates (explicit HALF_UP).

    Amounts are quantized at the record boundary so in-memory and DB-read rows
    serialize identically under the ``Numeric(20, 4)`` column semantics.
    """
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP
        return value.quantize(_FOUR_DP)


def compute_ttm(quarters: Sequence[Decimal | None], *, metric: str) -> dict[str, Any]:
    """Trailing-4-quarter sum; fewer than four or any missing leg refuses."""
    values = list(quarters)
    if len(values) != 4:
        return {
            "value": None,
            "status": "INSUFFICIENT_DATA",
            "reason": f"TTM needs four reported quarters for {metric}; got {len(values)}",
        }
    clean: list[Decimal] = []
    for value in values:
        if value is None:
            return {
                "value": None,
                "status": "INSUFFICIENT_DATA",
                "reason": f"TTM needs four reported quarters for {metric}; one is missing",
            }
        clean.append(value)
    total = Decimal("0")
    for value in clean:
        total += value
    return {"value": str(total), "status": "OK"}


def yoy_delta(
    *,
    current: Decimal | None,
    prior: Decimal | None,
    metric: str,
    current_label: str,
    prior_label: str,
) -> dict[str, Any]:
    """``current_label vs prior_label`` framing (e.g. Q2-2026 vs Q2-2025)."""
    base: dict[str, Any] = {
        "metric": metric,
        "current_label": current_label,
        "prior_label": prior_label,
        "current": str(current) if current is not None else None,
        "prior": str(prior) if prior is not None else None,
    }
    if current is None or prior is None:
        missing = "current" if current is None else "prior"
        return {
            **base,
            "delta": None,
            "delta_pct": None,
            "status": "INSUFFICIENT_DATA",
            "reason": f"YoY needs both legs for {metric}; {missing} is missing",
        }
    delta = current - prior
    if prior == 0:
        return {
            **base,
            "delta": str(delta),
            "delta_pct": None,
            "status": "OK",
            "reason": "prior-year value is zero; percent change undefined",
        }
    return {
        **base,
        "delta": str(delta),
        "delta_pct": str(quantize4(delta / prior)),
        "status": "OK",
    }


def ttm_margin(
    *, ttm_net_income: Decimal | None, ttm_revenue: Decimal | None
) -> dict[str, Any]:
    """Net-income TTM over revenue TTM; missing or zero revenue refuses."""
    if ttm_net_income is None or ttm_revenue is None:
        missing = "net income" if ttm_net_income is None else "revenue"
        return {
            "value": None,
            "status": "INSUFFICIENT_DATA",
            "reason": f"TTM margin needs both legs; {missing} TTM is missing",
        }
    if ttm_revenue == 0:
        return {
            "value": None,
            "status": "INSUFFICIENT_DATA",
            "reason": "TTM revenue is zero; margin undefined",
        }
    return {"value": str(quantize4(ttm_net_income / ttm_revenue)), "status": "OK"}


def margin_vs_prior_year(
    *,
    current_margin: dict[str, Any],
    prior_margin: dict[str, Any],
) -> dict[str, Any]:
    """TTM-margin-vs-prior-year block; either leg missing refuses the block."""
    if current_margin.get("status") != "OK" or prior_margin.get("status") != "OK":
        return {
            "current": current_margin,
            "prior": prior_margin,
            "delta": None,
            "status": "INSUFFICIENT_DATA",
            "reason": "need current and prior-year TTM margins",
        }
    current = Decimal(str(current_margin["value"]))
    prior = Decimal(str(prior_margin["value"]))
    return {
        "current": current_margin,
        "prior": prior_margin,
        "delta": str(quantize4(current - prior)),
        "status": "OK",
    }
