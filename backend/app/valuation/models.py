"""Deterministic valuation models with explicit assumptions.

All models use Decimal for precision.
No LLM or AI is used for valuation inputs.
Each model documents its assumptions and formula.

References:
- Aswath Damodaran - Investment Valuation
- CFA Institute - Equity Asset Valuation
"""

from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import Enum
from typing import Any, NamedTuple


class ValuationModel(Enum):
    """Supported valuation models."""
    PE = "price_to_earnings"
    PB = "price_to_book"
    EV_EBITDA = "ev_to_ebitda"
    DCF = "discounted_cash_flow"


class ValuationStatus(Enum):
    """Status of a valuation calculation."""
    AVAILABLE = "AVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INVALID = "INVALID"


class ValuationResult(NamedTuple):
    """Result of a valuation calculation."""
    value: Decimal | None
    status: ValuationStatus
    model: ValuationModel
    assumptions: dict[str, str | None]
    reason: str | None = None


def _safe_divide(
    numerator: Decimal,
    denominator: Decimal,
    precision: int = 4,
) -> Decimal | None:
    """Safely divide two Decimals."""
    if denominator == 0:
        return None
    try:
        result = numerator / denominator
        return result.quantize(Decimal(10) ** -precision, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def calculate_pe_valuation(
    earnings_per_share: Decimal | None,
    pe_ratio: Decimal | None,
) -> ValuationResult:
    """Calculate implied price using P/E ratio.

    Formula: Price = EPS × P/E Ratio

    Args:
        earnings_per_share: Current or forward EPS
        pe_ratio: Target P/E ratio (from industry, history, or analyst)

    Returns:
        ValuationResult with implied price and assumptions
    """
    if earnings_per_share is None or pe_ratio is None:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INSUFFICIENT_DATA,
            model=ValuationModel.PE,
            assumptions={},
            reason="Missing EPS or P/E ratio",
        )

    if earnings_per_share <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.PE,
            assumptions={"eps": str(earnings_per_share), "pe_ratio": str(pe_ratio)},
            reason="EPS must be positive for P/E valuation",
        )

    implied_price = earnings_per_share * pe_ratio

    return ValuationResult(
        value=implied_price,
        status=ValuationStatus.AVAILABLE,
        model=ValuationModel.PE,
        assumptions={
            "eps": str(earnings_per_share),
            "pe_ratio": str(pe_ratio),
            "formula": "Price = EPS × P/E Ratio",
        },
    )


def calculate_pb_valuation(
    book_value_per_share: Decimal | None,
    pb_ratio: Decimal | None,
) -> ValuationResult:
    """Calculate implied price using P/B ratio.

    Formula: Price = BVPS × P/B Ratio

    Args:
        book_value_per_share: Current book value per share
        pb_ratio: Target P/B ratio

    Returns:
        ValuationResult with implied price and assumptions
    """
    if book_value_per_share is None or pb_ratio is None:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INSUFFICIENT_DATA,
            model=ValuationModel.PB,
            assumptions={},
            reason="Missing BVPS or P/B ratio",
        )

    if book_value_per_share <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.PB,
            assumptions={"bvps": str(book_value_per_share), "pb_ratio": str(pb_ratio)},
            reason="Book value per share must be positive",
        )

    implied_price = book_value_per_share * pb_ratio

    return ValuationResult(
        value=implied_price,
        status=ValuationStatus.AVAILABLE,
        model=ValuationModel.PB,
        assumptions={
            "bvps": str(book_value_per_share),
            "pb_ratio": str(pb_ratio),
            "formula": "Price = BVPS × P/B Ratio",
        },
    )


def calculate_ev_ebitda_valuation(
    ebitda: Decimal | None,
    ev_ebitda_ratio: Decimal | None,
    net_debt: Decimal | None,
    shares_outstanding: Decimal | None,
) -> ValuationResult:
    """Calculate implied share price using EV/EBITDA.

    Formula:
    Enterprise Value = EBITDA × EV/EBITDA Ratio
    Equity Value = Enterprise Value - Net Debt
    Price per Share = Equity Value / Shares Outstanding

    Args:
        ebitda: Earnings before interest, tax, depreciation, amortization
        ev_ebitda_ratio: Target EV/EBITDA ratio
        net_debt: Total debt minus cash
        shares_outstanding: Number of shares outstanding

    Returns:
        ValuationResult with implied price and assumptions
    """
    if any(v is None for v in [ebitda, ev_ebitda_ratio, net_debt, shares_outstanding]):
        return ValuationResult(
            value=None,
            status=ValuationStatus.INSUFFICIENT_DATA,
            model=ValuationModel.EV_EBITDA,
            assumptions={},
            reason="Missing EBITDA, EV/EBITDA ratio, net debt, or shares outstanding",
        )

    assert ebitda is not None
    assert ev_ebitda_ratio is not None
    assert net_debt is not None
    assert shares_outstanding is not None

    if ebitda <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.EV_EBITDA,
            assumptions={
                "ebitda": str(ebitda),
                "ev_ebitda_ratio": str(ev_ebitda_ratio),
            },
            reason="EBITDA must be positive for EV/EBITDA valuation",
        )

    if shares_outstanding <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.EV_EBITDA,
            assumptions={"shares_outstanding": str(shares_outstanding)},
            reason="Shares outstanding must be positive",
        )

    enterprise_value = ebitda * ev_ebitda_ratio
    equity_value = enterprise_value - net_debt
    price_per_share = _safe_divide(equity_value, shares_outstanding, precision=4)

    if price_per_share is None:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.EV_EBITDA,
            assumptions={},
            reason="Division by zero in price calculation",
        )

    return ValuationResult(
        value=price_per_share,
        status=ValuationStatus.AVAILABLE,
        model=ValuationModel.EV_EBITDA,
        assumptions={
            "ebitda": str(ebitda),
            "ev_ebitda_ratio": str(ev_ebitda_ratio),
            "net_debt": str(net_debt),
            "shares_outstanding": str(shares_outstanding),
            "enterprise_value": str(enterprise_value),
            "equity_value": str(equity_value),
            "formula": "Price = (EBITDA × EV/EBITDA - Net Debt) / Shares",
        },
    )


def calculate_dcf_valuation(
    free_cash_flow: Decimal | None,
    growth_rate: Decimal | None,
    discount_rate: Decimal | None,
    terminal_growth_rate: Decimal | None,
    projection_years: int = 5,
    shares_outstanding: Decimal | None = None,
) -> ValuationResult:
    """Calculate implied share price using DCF model.

    Formula:
    PV of projected FCFs = Σ FCF × (1 + g)^t / (1 + r)^t
    Terminal Value = FCF × (1 + g_n) / (r - g_n)
    PV of Terminal Value = Terminal Value / (1 + r)^n
    Enterprise Value = PV of FCFs + PV of Terminal Value
    Price per Share = Enterprise Value / Shares Outstanding

    Args:
        free_cash_flow: Current free cash flow
        growth_rate: Expected growth rate for projections
        discount_rate: WACC or required rate of return
        terminal_growth_rate: Long-term growth rate for terminal value
        projection_years: Number of years to project (default 5)
        shares_outstanding: Number of shares outstanding

    Returns:
        ValuationResult with implied price and assumptions
    """
    if any(v is None for v in [free_cash_flow, growth_rate, discount_rate, terminal_growth_rate]):
        return ValuationResult(
            value=None,
            status=ValuationStatus.INSUFFICIENT_DATA,
            model=ValuationModel.DCF,
            assumptions={},
            reason="Missing FCF, growth rate, discount rate, or terminal growth rate",
        )

    assert free_cash_flow is not None
    assert growth_rate is not None
    assert discount_rate is not None
    assert terminal_growth_rate is not None

    if free_cash_flow <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.DCF,
            assumptions={"fcf": str(free_cash_flow)},
            reason="Free cash flow must be positive for DCF valuation",
        )

    if discount_rate <= terminal_growth_rate:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.DCF,
            assumptions={
                "discount_rate": str(discount_rate),
                "terminal_growth_rate": str(terminal_growth_rate),
            },
            reason="Discount rate must be greater than terminal growth rate",
        )

    # Calculate present value of projected FCFs
    pv_fcfs = Decimal("0")
    projected_fcf = free_cash_flow

    for year in range(1, projection_years + 1):
        projected_fcf = projected_fcf * (1 + growth_rate)
        discount_factor = (1 + discount_rate) ** year
        pv = _safe_divide(projected_fcf, discount_factor, precision=8)
        if pv is not None:
            pv_fcfs += pv

    # Calculate terminal value
    terminal_fcf = projected_fcf * (1 + terminal_growth_rate)
    terminal_value = _safe_divide(
        terminal_fcf,
        discount_rate - terminal_growth_rate,
        precision=8,
    )

    if terminal_value is None:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.DCF,
            assumptions={},
            reason="Terminal value calculation failed",
        )

    # Discount terminal value
    pv_terminal = _safe_divide(
        terminal_value,
        (1 + discount_rate) ** projection_years,
        precision=8,
    )

    if pv_terminal is None:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.DCF,
            assumptions={},
            reason="Terminal value discounting failed",
        )

    enterprise_value = pv_fcfs + pv_terminal

    # Calculate price per share if shares outstanding provided
    if shares_outstanding and shares_outstanding > 0:
        price_per_share = _safe_divide(enterprise_value, shares_outstanding, precision=4)
    else:
        price_per_share = None

    return ValuationResult(
        value=price_per_share,
        status=ValuationStatus.AVAILABLE,
        model=ValuationModel.DCF,
        assumptions={
            "fcf": str(free_cash_flow),
            "growth_rate": str(growth_rate),
            "discount_rate": str(discount_rate),
            "terminal_growth_rate": str(terminal_growth_rate),
            "projection_years": str(projection_years),
            "pv_fcfs": str(pv_fcfs),
            "terminal_value": str(terminal_value),
            "pv_terminal": str(pv_terminal),
            "enterprise_value": str(enterprise_value),
            "shares_outstanding": str(shares_outstanding) if shares_outstanding else None,
            "formula": "DCF with terminal value",
        },
    )


def calculate_sensitivity(
    base_value: Decimal,
    base_assumptions: dict[str, Decimal],
    param_name: str,
    param_range: list[Decimal],
    calculator: Callable[..., Any],
) -> list[dict[str, Any]]:
    """Perform sensitivity analysis on a valuation parameter.

    Args:
        base_value: Base case valuation result
        base_assumptions: Base case assumptions
        param_name: Parameter to vary
        param_range: List of parameter values to test
        calculator: Function to calculate valuation with modified parameter

    Returns:
        List of sensitivity results
    """
    results = []

    for param_value in param_range:
        modified_assumptions = base_assumptions.copy()
        modified_assumptions[param_name] = param_value

        try:
            result = calculator(**modified_assumptions)
            change_pct = _safe_divide(
                result.value - base_value,
                abs(base_value),
                precision=2,
            )
            results.append({
                "parameter": param_name,
                "value": str(param_value),
                "valuation": str(result.value) if result.value else None,
                "change_from_base": f"{change_pct * 100}%" if change_pct else None,
            })
        except Exception:
            results.append({
                "parameter": param_name,
                "value": str(param_value),
                "valuation": None,
                "change_from_base": None,
            })

    return results
