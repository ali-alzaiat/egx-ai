"""Per-company analysis tools: score, valuation, stance, Shariah. Each calls the router's code."""

from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tools.base import (
    TICKER_PROPERTY,
    ToolDef,
    ToolError,
    envelope,
    first_text,
    object_schema,
    resolve_company,
    strip_noise,
)

#: What the UI shows for each stance code (frontend dict `stance`): never an instruction.
STANCE_LABELS = {"buy": "leans buy", "hold": "neutral", "reduce": "leans reduce"}
STANCE_CODES = {label: code for code, label in STANCE_LABELS.items()}


async def _investment_score(session: AsyncSession, args: dict[str, Any]) -> dict[str, Any]:
    from app.api.scores import get_score

    company = await resolve_company(session, args)
    try:
        payload = await get_score(company.id, session)
    except HTTPException as exc:
        raise ToolError("NOT_FOUND", str(exc.detail)) from None
    data = strip_noise(payload)
    return envelope(
        "investment_score",
        ticker=company.ticker,
        as_of=first_text(
            data.get("price_as_of"), (data.get("assessment") or {}).get("as_of")
        ),
        methodology={"score": data.get("methodology_version")},
        source="EGX AI investment-score engine over approved statement lines and stored prices",
        data=data,
    )


def _score_insufficient(output: dict[str, Any]) -> str | None:
    assessment = output.get("data", {}).get("assessment")
    if assessment is None:
        return "No investment score could be computed for this company yet."
    headline = assessment.get("headline") or {}
    if headline.get("status") == "INSUFFICIENT_DATA":
        return str(headline.get("reason") or "The score has too little data.")
    return None


async def _valuation(session: AsyncSession, args: dict[str, Any]) -> dict[str, Any]:
    from app.api.valuation import get_fair_value

    company = await resolve_company(session, args)
    try:
        payload = await get_fair_value(company.id, session)
    except HTTPException as exc:
        raise ToolError("NOT_FOUND", str(exc.detail)) from None
    data = strip_noise(payload)
    return envelope(
        "valuation",
        ticker=company.ticker,
        as_of=first_text(data.get("as_of"), data.get("price_as_of")),
        methodology={"valuation": data.get("methodology_version")},
        source="EGX AI fair-value engine over approved statement lines and sourced assumptions",
        data=data,
    )


def _valuation_insufficient(output: dict[str, Any]) -> str | None:
    fair_value = output.get("data", {}).get("fair_value")
    if isinstance(fair_value, dict) and fair_value.get("status") == "INSUFFICIENT_DATA":
        return str(fair_value.get("reason") or "No fair value could be computed.")
    return None


def label_stance(payload: dict[str, Any]) -> dict[str, Any]:
    """Swap the stance code for the label the UI shows ("leans buy", never "BUY")."""
    out = dict(payload)
    code = out.get("stance")
    if isinstance(code, str):
        out["stance"] = STANCE_LABELS.get(code, code)
    return out


async def _stance(session: AsyncSession, args: dict[str, Any]) -> dict[str, Any]:
    from app.api.stance import DEFAULT_STOP_PCT, get_stance

    company = await resolve_company(session, args)
    try:
        payload = await get_stance(company.ticker, None, float(DEFAULT_STOP_PCT), session)
    except HTTPException as exc:
        raise ToolError("NOT_FOUND", str(exc.detail)) from None
    data = label_stance(strip_noise(payload))
    return envelope(
        "stance",
        ticker=company.ticker,
        as_of=first_text(data.get("as_of")),
        methodology={"stance": data.get("rules_version")},
        source="EGX AI stance engine (score, valuation, technicals; Shariah shown separately)",
        data=data,
    )


async def _shariah_status(session: AsyncSession, args: dict[str, Any]) -> dict[str, Any]:
    from app.api.screening import get_screening_result
    from app.screening.status import shariah_statuses

    company = await resolve_company(session, args)
    try:
        payload = await get_screening_result(company.id, session)
    except HTTPException as exc:
        raise ToolError("NOT_FOUND", str(exc.detail)) from None
    block = (await shariah_statuses(session, [company.id])).get(company.id)
    data = strip_noise(payload)
    data["verdict_and_egx33"] = block
    return envelope(
        "shariah_status",
        ticker=company.ticker,
        as_of=first_text(data.get("report_date"), data.get("screened_at")),
        methodology={"shariah": data.get("methodology_version")},
        source="EGX AI Shariah screen over approved statement lines; EGX33 membership records",
        data=data,
    )


async def _company_performance(session: AsyncSession, args: dict[str, Any]) -> dict[str, Any]:
    from app.performance.constants import PERFORMANCE_SOURCE
    from app.performance.service import PerformanceService

    company = await resolve_company(session, args)
    today = datetime.now(UTC).date()
    data = await PerformanceService(session).company_performance(company.id, today)
    return envelope(
        "company_performance",
        ticker=company.ticker,
        as_of=first_text(data.get("price_as_of")),
        methodology={"performance": data.pop("methodology_version")},
        source=PERFORMANCE_SOURCE,
        data=data,
    )


DATA_CHECK_SOURCE = "EGX AI data cross-checks over stored prices and approved statement lines"


async def _data_check(session: AsyncSession, args: dict[str, Any]) -> dict[str, Any]:
    from app.dataquality.crosscheck_service import CrosscheckService

    company = await resolve_company(session, args)
    service = CrosscheckService(session)
    data = await service.latest(company.id)
    if data["computed_at"] is None:
        data = await service.run(company.id)  # never run yet: run once so there is an answer
    data = strip_noise(data)
    version = data.pop("methodology_version")
    computed_at = data.get("computed_at")
    return envelope(
        "data_check",
        ticker=company.ticker,
        as_of=computed_at[:10] if isinstance(computed_at, str) else None,
        methodology={"crosscheck": version},
        source=DATA_CHECK_SOURCE,
        data=data,
    )


def _data_check_insufficient(output: dict[str, Any]) -> str | None:
    if not output.get("data", {}).get("checks"):
        return "No data cross-checks could be computed for this company yet."
    return None


TICKER_ONLY = object_schema({"ticker": TICKER_PROPERTY}, ["ticker"])

ANALYSIS_TOOLS: tuple[ToolDef, ...] = (
    ToolDef(
        name="investment_score",
        description=(
            "Investment score of one company: headline, components, checks, Piotroski and "
            "dividend-safety extras, confidence and the data behind them."
        ),
        parameters=TICKER_ONLY,
        run=_investment_score,
        insufficient=_score_insufficient,
    ),
    ToolDef(
        name="valuation",
        description=(
            "Fair-value estimate of one company under the stated methodology: weighted fair "
            "value, models used, scenarios, verdict versus the market price and assumptions."
        ),
        parameters=TICKER_ONLY,
        run=_valuation,
        insufficient=_valuation_insufficient,
    ),
    ToolDef(
        name="stance",
        description=(
            "Research stance of one company (leans buy / neutral / leans reduce) with "
            "confidence, reasons per engine, reference levels, liquidity and limitations. "
            "A research lean, not an instruction."
        ),
        parameters=TICKER_ONLY,
        run=_stance,
    ),
    ToolDef(
        name="company_performance",
        description=(
            "Performance of one company: price returns over 1M / 3M / 6M / YTD / 1Y next to "
            "the EGX30 index and the difference, plus revenue and net income TTM and "
            "year-over-year change and the TTM net margin, all computed in code. Fractions: "
            "0.12 means 12%. Windows the data does not reach are INSUFFICIENT_DATA."
        ),
        parameters=TICKER_ONLY,
        run=_company_performance,
    ),
    ToolDef(
        name="data_check",
        description=(
            "Data cross-checks of one company: whether our figures are backed by filings, agree "
            "with a second source, satisfy accounting identities, have sane prices and are "
            "fresh. Each check is pass / warn / fail / insufficient_data with its evidence; "
            "`overall` is the worst. It never contains vendor figures."
        ),
        parameters=TICKER_ONLY,
        run=_data_check,
        insufficient=_data_check_insufficient,
    ),
    ToolDef(
        name="shariah_status",
        description=(
            "Shariah screening of one company: our rule-by-rule verdict (with INSUFFICIENT_DATA "
            "where inputs are missing) next to official EGX33 membership."
        ),
        parameters=TICKER_ONLY,
        run=_shariah_status,
    ),
)
