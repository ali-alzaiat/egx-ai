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

from app.valuation.constants import EXPLICIT_STAGE_YEARS


class ValuationModel(Enum):
    """Supported valuation models."""
    PE = "price_to_earnings"
    PB = "price_to_book"
    EV_EBITDA = "ev_to_ebitda"
    DCF = "discounted_cash_flow"
    PS = "price_to_sales"
    FCFE_2STAGE = "fcfe_two_stage"
    DDM = "dividend_discount"
    EXCESS_RETURNS = "excess_returns"
    AFFO_2STAGE = "affo_two_stage"


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


def _two_stage_present_value(
    base_cash_flow: Decimal,
    growth_high: Decimal,
    years_high: int,
    growth_stable: Decimal,
    years_stable: int,
    discount_rate: Decimal,
    terminal_growth_rate: Decimal,
    terminal_discount_rate: Decimal | None = None,
) -> tuple[Decimal, Decimal, Decimal, Decimal] | None:
    """Present value of a 2-stage cash-flow stream plus Gordon terminal value.

    Stage 1 compounds at ``growth_high`` for ``years_high`` years, stage 2 at
    ``growth_stable`` for ``years_stable`` years; the terminal value is a
    Gordon perpetuity on the final projected flow.

    Faded discount rate (valuation 1.2, owner rulings M5 + fade horizon): the
    first ``years_high`` years are discounted at ``discount_rate``; every later
    year (the stable stage) and the Gordon capitalisation of the terminal value
    use ``terminal_discount_rate`` (the long-run cost of equity, on the same
    inflation horizon as ``terminal_growth_rate``). Discount factors compound
    across the switch, so year t > years_high carries
    (1 + discount_rate)^years_high * (1 + terminal_discount_rate)^(t - years_high).
    ``None`` keeps one rate throughout.

    Returns (pv_flows, terminal_value, pv_terminal, enterprise_value),
    or None when the discounting math fails.
    """
    terminal_rate = terminal_discount_rate if terminal_discount_rate is not None else discount_rate
    pv_flows = Decimal("0")
    projected = base_cash_flow
    factor = Decimal("1")
    for _ in range(years_high):
        projected = projected * (1 + growth_high)
        factor = factor * (1 + discount_rate)
        pv = _safe_divide(projected, factor, precision=8)
        if pv is None:
            return None
        pv_flows += pv
    for _ in range(years_stable):
        projected = projected * (1 + growth_stable)
        factor = factor * (1 + terminal_rate)
        pv = _safe_divide(projected, factor, precision=8)
        if pv is None:
            return None
        pv_flows += pv

    terminal_fcf = projected * (1 + terminal_growth_rate)
    terminal_value = _safe_divide(
        terminal_fcf, terminal_rate - terminal_growth_rate, precision=8
    )
    if terminal_value is None:
        return None
    pv_terminal = _safe_divide(terminal_value, factor, precision=8)
    if pv_terminal is None:
        return None
    return (pv_flows, terminal_value, pv_terminal, pv_flows + pv_terminal)


def _faded_growing_stream(
    first_flow: Decimal,
    terminal_first_flow: Decimal,
    growth: Decimal,
    rate: Decimal,
    terminal_rate: Decimal,
    years: int,
) -> Decimal | None:
    """PV of a growing stream whose terminal value is capitalised at a faded rate.

    Flows ``first_flow * (1 + growth) ** (t - 1)`` for ``t = 1..years`` are
    discounted at ``rate``. The year ``years + 1`` flow is ``terminal_first_flow``;
    its Gordon value at ``terminal_rate`` is brought back to today at ``rate`` over
    the explicit years (same fade as ``_two_stage_present_value``, owner ruling M5).
    With ``terminal_rate == rate`` and a consistent terminal flow this equals the
    closed-form perpetuity.
    """
    pv = Decimal("0")
    flow = first_flow
    for year in range(1, years + 1):
        term = _safe_divide(flow, (1 + rate) ** year, precision=8)
        if term is None:
            return None
        pv += term
        flow = flow * (1 + growth)
    terminal_value = _safe_divide(terminal_first_flow, terminal_rate - growth, precision=8)
    if terminal_value is None:
        return None
    pv_terminal = _safe_divide(terminal_value, (1 + rate) ** years, precision=8)
    if pv_terminal is None:
        return None
    return pv + pv_terminal


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


def calculate_ps_valuation(
    revenue_per_share: Decimal | None,
    ps_ratio: Decimal | None,
) -> ValuationResult:
    """Calculate implied price using P/S ratio.

    Formula: Price = RPS × P/S Ratio

    Args:
        revenue_per_share: Current revenue per share
        ps_ratio: Target P/S ratio

    Returns:
        ValuationResult with implied price and assumptions
    """
    if revenue_per_share is None or ps_ratio is None:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INSUFFICIENT_DATA,
            model=ValuationModel.PS,
            assumptions={},
            reason="Missing RPS or P/S ratio",
        )

    if revenue_per_share <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.PS,
            assumptions={"rps": str(revenue_per_share), "ps_ratio": str(ps_ratio)},
            reason="Revenue per share must be positive for P/S valuation",
        )

    implied_price = revenue_per_share * ps_ratio

    return ValuationResult(
        value=implied_price,
        status=ValuationStatus.AVAILABLE,
        model=ValuationModel.PS,
        assumptions={
            "rps": str(revenue_per_share),
            "ps_ratio": str(ps_ratio),
            "formula": "Price = RPS × P/S Ratio",
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


def calculate_fcfe_2stage(
    free_cash_flow: Decimal | None,
    growth_high: Decimal | None,
    growth_stable: Decimal | None,
    discount_rate: Decimal | None,
    terminal_growth_rate: Decimal | None,
    years_high: int = EXPLICIT_STAGE_YEARS,
    years_stable: int = 5,
    shares_outstanding: Decimal | None = None,
    terminal_discount_rate: Decimal | None = None,
) -> ValuationResult:
    """Calculate implied share price with a 2-stage FCFE model (general companies).

    Stage 1 compounds FCF at ``growth_high`` for ``years_high`` years, stage 2
    at ``growth_stable`` for ``years_stable`` years; the explicit flows are
    discounted at ``discount_rate`` (cost of equity) and the Gordon terminal
    value is capitalised at ``terminal_discount_rate`` (long-run cost of equity;
    ``None`` = the same rate throughout).

    Args:
        free_cash_flow: Current levered free cash flow (never fabricated)
        growth_high: Near-term growth rate (historical extrapolation, not consensus)
        growth_stable: Stable-phase growth rate
        discount_rate: Cost of equity
        terminal_growth_rate: Perpetual growth rate for the terminal value
        years_high: Stage-1 years (default 5)
        years_stable: Stage-2 years (default 5)
        shares_outstanding: Shares outstanding for per-share value
        terminal_discount_rate: Long-run cost of equity for the terminal value

    Returns:
        ValuationResult with implied price and assumptions
    """
    if any(
        v is None
        for v in [
            free_cash_flow,
            growth_high,
            growth_stable,
            discount_rate,
            terminal_growth_rate,
        ]
    ):
        return ValuationResult(
            value=None,
            status=ValuationStatus.INSUFFICIENT_DATA,
            model=ValuationModel.FCFE_2STAGE,
            assumptions={},
            reason="Missing FCF, growth, discount, or terminal growth rate",
        )

    assert free_cash_flow is not None
    assert growth_high is not None
    assert growth_stable is not None
    assert discount_rate is not None
    assert terminal_growth_rate is not None

    if free_cash_flow <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.FCFE_2STAGE,
            assumptions={"fcf": str(free_cash_flow)},
            reason="Free cash flow must be positive for FCFE valuation",
        )

    if discount_rate <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.FCFE_2STAGE,
            assumptions={"discount_rate": str(discount_rate)},
            reason="Discount rate must be positive for FCFE valuation",
        )

    if discount_rate <= terminal_growth_rate:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.FCFE_2STAGE,
            assumptions={
                "discount_rate": str(discount_rate),
                "terminal_growth_rate": str(terminal_growth_rate),
            },
            reason="Discount rate must be greater than terminal growth rate",
        )

    if terminal_discount_rate is not None and terminal_discount_rate <= terminal_growth_rate:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.FCFE_2STAGE,
            assumptions={
                "terminal_discount_rate": str(terminal_discount_rate),
                "terminal_growth_rate": str(terminal_growth_rate),
            },
            reason="Long-run cost of equity must be greater than terminal growth rate",
        )

    if years_high <= 0 or years_stable <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.FCFE_2STAGE,
            assumptions={
                "years_high": str(years_high),
                "years_stable": str(years_stable),
            },
            reason="Projection horizons must be positive",
        )

    stages = _two_stage_present_value(
        free_cash_flow,
        growth_high,
        years_high,
        growth_stable,
        years_stable,
        discount_rate,
        terminal_growth_rate,
        terminal_discount_rate,
    )
    if stages is None:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.FCFE_2STAGE,
            assumptions={},
            reason="Two-stage discounting math failed",
        )
    pv_flows, terminal_value, pv_terminal, enterprise_value = stages

    if enterprise_value <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.FCFE_2STAGE,
            assumptions={"enterprise_value": str(enterprise_value)},
            reason="Implied enterprise value is not positive",
        )

    if shares_outstanding and shares_outstanding > 0:
        price_per_share = _safe_divide(enterprise_value, shares_outstanding, precision=4)
    else:
        price_per_share = None

    return ValuationResult(
        value=price_per_share,
        status=ValuationStatus.AVAILABLE,
        model=ValuationModel.FCFE_2STAGE,
        assumptions={
            "fcf": str(free_cash_flow),
            "growth_high": str(growth_high),
            "years_high": str(years_high),
            "growth_stable": str(growth_stable),
            "years_stable": str(years_stable),
            "discount_rate": str(discount_rate),
            "terminal_discount_rate": (
                str(terminal_discount_rate) if terminal_discount_rate is not None else None
            ),
            "terminal_growth_rate": str(terminal_growth_rate),
            "pv_flows": str(pv_flows),
            "terminal_value": str(terminal_value),
            "pv_terminal": str(pv_terminal),
            "enterprise_value": str(enterprise_value),
            "shares_outstanding": str(shares_outstanding) if shares_outstanding else None,
            "formula": "2-stage FCFE with Gordon terminal value",
        },
    )


def calculate_ddm(
    expected_dps: Decimal | None,
    discount_rate: Decimal | None,
    perpetual_growth_rate: Decimal | None,
    terminal_discount_rate: Decimal | None = None,
    explicit_years: int = EXPLICIT_STAGE_YEARS,
) -> ValuationResult:
    """Calculate implied share price with the Gordon Dividend Discount Model.

    Formula: Value = Expected DPS / (discount rate - perpetual growth).
    Used for consistent dividend payers and as the fallback intrinsic model.

    With ``terminal_discount_rate`` (owner ruling M5) the first ``explicit_years``
    dividends are discounted at ``discount_rate`` and the Gordon terminal value is
    capitalised at the long-run cost of equity, then brought back at ``discount_rate``.

    Args:
        expected_dps: Expected dividend per share next period
        discount_rate: Cost of equity
        perpetual_growth_rate: Perpetual dividend growth rate
        terminal_discount_rate: Long-run cost of equity for the terminal value
        explicit_years: Explicit-stage years when the fade is used

    Returns:
        ValuationResult with implied price and assumptions
    """
    if any(v is None for v in [expected_dps, discount_rate, perpetual_growth_rate]):
        return ValuationResult(
            value=None,
            status=ValuationStatus.INSUFFICIENT_DATA,
            model=ValuationModel.DDM,
            assumptions={},
            reason="Missing expected DPS, discount rate, or perpetual growth rate",
        )

    assert expected_dps is not None
    assert discount_rate is not None
    assert perpetual_growth_rate is not None

    if expected_dps <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.DDM,
            assumptions={"expected_dps": str(expected_dps)},
            reason="Expected DPS must be positive for DDM valuation",
        )

    if discount_rate <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.DDM,
            assumptions={"discount_rate": str(discount_rate)},
            reason="Discount rate must be positive for DDM valuation",
        )

    if discount_rate <= perpetual_growth_rate:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.DDM,
            assumptions={
                "discount_rate": str(discount_rate),
                "perpetual_growth_rate": str(perpetual_growth_rate),
            },
            reason="Discount rate must be greater than perpetual growth rate",
        )

    if terminal_discount_rate is not None:
        if terminal_discount_rate <= perpetual_growth_rate:
            return ValuationResult(
                value=None,
                status=ValuationStatus.INVALID,
                model=ValuationModel.DDM,
                assumptions={
                    "terminal_discount_rate": str(terminal_discount_rate),
                    "perpetual_growth_rate": str(perpetual_growth_rate),
                },
                reason="Long-run cost of equity must be greater than perpetual growth rate",
            )
        faded = _faded_growing_stream(
            expected_dps,
            expected_dps * (1 + perpetual_growth_rate) ** explicit_years,
            perpetual_growth_rate,
            discount_rate,
            terminal_discount_rate,
            explicit_years,
        )
        value = faded.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if faded else None
    else:
        value = _safe_divide(
            expected_dps, discount_rate - perpetual_growth_rate, precision=4
        )
    if value is None or value <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.DDM,
            assumptions={
                "expected_dps": str(expected_dps),
                "discount_rate": str(discount_rate),
            },
            reason="DDM calculation failed",
        )

    return ValuationResult(
        value=value,
        status=ValuationStatus.AVAILABLE,
        model=ValuationModel.DDM,
        assumptions={
            "expected_dps": str(expected_dps),
            "discount_rate": str(discount_rate),
            "perpetual_growth_rate": str(perpetual_growth_rate),
            "terminal_discount_rate": (
                str(terminal_discount_rate) if terminal_discount_rate is not None else None
            ),
            "formula": "Value = Expected DPS / (discount rate - perpetual growth)",
        },
    )


def calculate_excess_returns(
    stable_book_value_per_share: Decimal | None,
    stable_roe: Decimal | None,
    cost_of_equity: Decimal | None,
    perpetual_growth_rate: Decimal | None,
    terminal_discount_rate: Decimal | None = None,
    explicit_years: int = EXPLICIT_STAGE_YEARS,
) -> ValuationResult:
    """Calculate implied share price with the Excess Returns model (banks/insurers).

    Formula: Excess = (Stable ROE - Cost of Equity) × Stable BV/share;
    Fair Value/share = Stable BV/share + Excess / (CoE - g).
    Terminal excess is already a present value (perpetuity from today), so no
    further discounting is applied.

    With ``terminal_discount_rate`` (owner ruling M5) the first ``explicit_years``
    excess returns ``(ROE - CoE) x BV x (1+g)^(t-1)`` are discounted at ``CoE`` and the
    terminal excess ``(ROE - long-run CoE) x BV x (1+g)^years`` is capitalised at the
    long-run cost of equity, then brought back to today at ``CoE``. Equal rates give
    the closed form above.

    Args:
        stable_book_value_per_share: Stable book value per share
        stable_roe: Stable return on equity (fraction, e.g. 0.12)
        cost_of_equity: Cost of equity (fraction)
        perpetual_growth_rate: Perpetual growth rate of excess returns
        terminal_discount_rate: Long-run cost of equity for the terminal excess
        explicit_years: Explicit-stage years when the fade is used

    Returns:
        ValuationResult with implied price and assumptions
    """
    if any(
        v is None
        for v in [
            stable_book_value_per_share,
            stable_roe,
            cost_of_equity,
            perpetual_growth_rate,
        ]
    ):
        return ValuationResult(
            value=None,
            status=ValuationStatus.INSUFFICIENT_DATA,
            model=ValuationModel.EXCESS_RETURNS,
            assumptions={},
            reason="Missing stable BVPS, stable ROE, cost of equity, or perpetual growth",
        )

    assert stable_book_value_per_share is not None
    assert stable_roe is not None
    assert cost_of_equity is not None
    assert perpetual_growth_rate is not None

    if stable_book_value_per_share <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.EXCESS_RETURNS,
            assumptions={"stable_bvps": str(stable_book_value_per_share)},
            reason="Stable book value per share must be positive",
        )

    if cost_of_equity <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.EXCESS_RETURNS,
            assumptions={"cost_of_equity": str(cost_of_equity)},
            reason="Cost of equity must be positive",
        )

    if cost_of_equity <= perpetual_growth_rate:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.EXCESS_RETURNS,
            assumptions={
                "cost_of_equity": str(cost_of_equity),
                "perpetual_growth_rate": str(perpetual_growth_rate),
            },
            reason="Cost of equity must be greater than perpetual growth rate",
        )

    excess = (stable_roe - cost_of_equity) * stable_book_value_per_share
    if terminal_discount_rate is not None:
        if terminal_discount_rate <= perpetual_growth_rate:
            return ValuationResult(
                value=None,
                status=ValuationStatus.INVALID,
                model=ValuationModel.EXCESS_RETURNS,
                assumptions={
                    "terminal_discount_rate": str(terminal_discount_rate),
                    "perpetual_growth_rate": str(perpetual_growth_rate),
                },
                reason="Long-run cost of equity must be greater than perpetual growth rate",
            )
        terminal_excess = _faded_growing_stream(
            excess,
            (stable_roe - terminal_discount_rate)
            * stable_book_value_per_share
            * (1 + perpetual_growth_rate) ** explicit_years,
            perpetual_growth_rate,
            cost_of_equity,
            terminal_discount_rate,
            explicit_years,
        )
    else:
        terminal_excess = _safe_divide(
            excess, cost_of_equity - perpetual_growth_rate, precision=8
        )
    if terminal_excess is None:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.EXCESS_RETURNS,
            assumptions={},
            reason="Terminal excess-returns calculation failed",
        )
    fair_value = stable_book_value_per_share + terminal_excess

    if fair_value <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.EXCESS_RETURNS,
            assumptions={
                "stable_bvps": str(stable_book_value_per_share),
                "stable_roe": str(stable_roe),
                "cost_of_equity": str(cost_of_equity),
                "excess": str(excess),
            },
            reason="Implied fair value is not positive",
        )

    return ValuationResult(
        value=fair_value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP),
        status=ValuationStatus.AVAILABLE,
        model=ValuationModel.EXCESS_RETURNS,
        assumptions={
            "stable_bvps": str(stable_book_value_per_share),
            "stable_roe": str(stable_roe),
            "cost_of_equity": str(cost_of_equity),
            "perpetual_growth_rate": str(perpetual_growth_rate),
            "excess": str(excess),
            "terminal_excess": str(terminal_excess),
            "terminal_discount_rate": (
                str(terminal_discount_rate) if terminal_discount_rate is not None else None
            ),
            "formula": "FV = Stable BV + (Stable ROE - CoE) × Stable BV / (CoE - g)",
        },
    )


def calculate_affo_2stage(
    cash_flow: Decimal | None,
    growth_high: Decimal | None,
    growth_stable: Decimal | None,
    discount_rate: Decimal | None,
    terminal_growth_rate: Decimal | None,
    years_high: int = EXPLICIT_STAGE_YEARS,
    years_stable: int = 5,
    shares_outstanding: Decimal | None = None,
    cash_flow_source: str = "affo",
    terminal_discount_rate: Decimal | None = None,
) -> ValuationResult:
    """Calculate implied share price with a 2-stage AFFO model (REITs/developers).

    Identical mechanics to the 2-stage FCFE model but discounts adjusted funds
    from operations. The caller resolves the AFFO → FFO → FCF fallback chain
    and records which series was used in ``cash_flow_source``.

    Args:
        cash_flow: Current AFFO (or FFO/FCF fallback — see cash_flow_source)
        growth_high: Near-term growth rate
        growth_stable: Stable-phase growth rate
        discount_rate: Cost of equity
        terminal_growth_rate: Perpetual growth rate for the terminal value
        years_high: Stage-1 years (default 5)
        years_stable: Stage-2 years (default 5)
        shares_outstanding: Shares outstanding for per-share value
        cash_flow_source: One of "affo", "ffo", "fcf"
        terminal_discount_rate: Long-run cost of equity for the terminal value
            (``None`` = the same rate throughout)

    Returns:
        ValuationResult with implied price and assumptions
    """
    if cash_flow_source not in ("affo", "ffo", "fcf"):
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.AFFO_2STAGE,
            assumptions={"cash_flow_source": cash_flow_source},
            reason="cash_flow_source must be one of affo, ffo, fcf",
        )

    if any(
        v is None
        for v in [
            cash_flow,
            growth_high,
            growth_stable,
            discount_rate,
            terminal_growth_rate,
        ]
    ):
        return ValuationResult(
            value=None,
            status=ValuationStatus.INSUFFICIENT_DATA,
            model=ValuationModel.AFFO_2STAGE,
            assumptions={},
            reason="Missing AFFO, growth, discount, or terminal growth rate",
        )

    assert cash_flow is not None
    assert growth_high is not None
    assert growth_stable is not None
    assert discount_rate is not None
    assert terminal_growth_rate is not None

    if cash_flow <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.AFFO_2STAGE,
            assumptions={"cash_flow": str(cash_flow)},
            reason="Cash flow must be positive for AFFO valuation",
        )

    if discount_rate <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.AFFO_2STAGE,
            assumptions={"discount_rate": str(discount_rate)},
            reason="Discount rate must be positive for AFFO valuation",
        )

    if discount_rate <= terminal_growth_rate:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.AFFO_2STAGE,
            assumptions={
                "discount_rate": str(discount_rate),
                "terminal_growth_rate": str(terminal_growth_rate),
            },
            reason="Discount rate must be greater than terminal growth rate",
        )

    if terminal_discount_rate is not None and terminal_discount_rate <= terminal_growth_rate:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.AFFO_2STAGE,
            assumptions={
                "terminal_discount_rate": str(terminal_discount_rate),
                "terminal_growth_rate": str(terminal_growth_rate),
            },
            reason="Long-run cost of equity must be greater than terminal growth rate",
        )

    if years_high <= 0 or years_stable <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.AFFO_2STAGE,
            assumptions={
                "years_high": str(years_high),
                "years_stable": str(years_stable),
            },
            reason="Projection horizons must be positive",
        )

    stages = _two_stage_present_value(
        cash_flow,
        growth_high,
        years_high,
        growth_stable,
        years_stable,
        discount_rate,
        terminal_growth_rate,
        terminal_discount_rate,
    )
    if stages is None:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.AFFO_2STAGE,
            assumptions={},
            reason="Two-stage discounting math failed",
        )
    pv_flows, terminal_value, pv_terminal, enterprise_value = stages

    if enterprise_value <= 0:
        return ValuationResult(
            value=None,
            status=ValuationStatus.INVALID,
            model=ValuationModel.AFFO_2STAGE,
            assumptions={"enterprise_value": str(enterprise_value)},
            reason="Implied enterprise value is not positive",
        )

    if shares_outstanding and shares_outstanding > 0:
        price_per_share = _safe_divide(enterprise_value, shares_outstanding, precision=4)
    else:
        price_per_share = None

    return ValuationResult(
        value=price_per_share,
        status=ValuationStatus.AVAILABLE,
        model=ValuationModel.AFFO_2STAGE,
        assumptions={
            "cash_flow": str(cash_flow),
            "cash_flow_source": cash_flow_source,
            "growth_high": str(growth_high),
            "years_high": str(years_high),
            "growth_stable": str(growth_stable),
            "years_stable": str(years_stable),
            "discount_rate": str(discount_rate),
            "terminal_discount_rate": (
                str(terminal_discount_rate) if terminal_discount_rate is not None else None
            ),
            "terminal_growth_rate": str(terminal_growth_rate),
            "pv_flows": str(pv_flows),
            "terminal_value": str(terminal_value),
            "pv_terminal": str(pv_terminal),
            "enterprise_value": str(enterprise_value),
            "shares_outstanding": str(shares_outstanding) if shares_outstanding else None,
            "formula": "2-stage AFFO with Gordon terminal value",
        },
    )


def select_preferred_multiple(
    earnings_per_share: Decimal | None,
    pe_ratio: Decimal | None,
    revenue_per_share: Decimal | None,
    ps_ratio: Decimal | None,
    book_value_per_share: Decimal | None,
    pb_ratio: Decimal | None,
) -> ValuationResult:
    """Select the preferred relative multiple: P/E → P/S → P/B.

    P/E wins for profitable companies with a sane target (P/E < 150);
    P/S covers growth/early-stage names; P/B covers banks/financials where the
    asset base drives income. Anything else reports INSUFFICIENT_DATA — never
    a zero or a guessed multiple.

    Returns:
        ValuationResult from the winning multiple, tagged with
        ``selected_multiple`` in assumptions.
    """
    if (
        earnings_per_share is not None
        and earnings_per_share > 0
        and pe_ratio is not None
        and pe_ratio > 0
        and pe_ratio < 150
    ):
        result = calculate_pe_valuation(earnings_per_share, pe_ratio)
        return result._replace(
            assumptions={**result.assumptions, "selected_multiple": "pe"}
        )

    if (
        revenue_per_share is not None
        and revenue_per_share > 0
        and ps_ratio is not None
        and ps_ratio > 0
    ):
        result = calculate_ps_valuation(revenue_per_share, ps_ratio)
        return result._replace(
            assumptions={**result.assumptions, "selected_multiple": "ps"}
        )

    if (
        book_value_per_share is not None
        and book_value_per_share > 0
        and pb_ratio is not None
        and pb_ratio > 0
    ):
        result = calculate_pb_valuation(book_value_per_share, pb_ratio)
        return result._replace(
            assumptions={**result.assumptions, "selected_multiple": "pb"}
        )

    return ValuationResult(
        value=None,
        status=ValuationStatus.INSUFFICIENT_DATA,
        model=ValuationModel.PE,
        assumptions={"selected_multiple": None},
        reason=(
            "No usable multiple: need profitable EPS with P/E<150, "
            "or RPS with P/S, or BVPS with P/B"
        ),
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
