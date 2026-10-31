"""Company data tools: overview, search, prices and indicators, chart patterns, metrics."""

from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.constants import MAX_TOOL_ROWS
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
from app.models.market import CompanyStatus
from app.repositories.company import CompanyRepository

DEFAULT_METRIC_YEARS = 3
_OVERVIEW_FIELDS = (
    "ticker",
    "name",
    "name_ar",
    "sector",
    "industry",
    "currency",
    "trading_currency",
    "status",
    "shares_outstanding",
    "free_float",
    "listing_date",
    "sector_match_basis",
)


async def _company_overview(session: AsyncSession, args: dict[str, Any]) -> dict[str, Any]:
    from app.api.companies import get_company_by_ticker, get_latest_price

    company = await resolve_company(session, args)
    try:
        record = await get_company_by_ticker(company.ticker, session)
        latest = await get_latest_price(company.id, session)
    except HTTPException as exc:
        raise ToolError("NOT_FOUND", str(exc.detail)) from None
    data: dict[str, Any] = {k: record.get(k) for k in _OVERVIEW_FIELDS}
    data["fundamentals"] = record.get("fundamentals")
    data["latest_price"] = {
        k: latest.get(k)
        for k in (
            "status",
            "reason",
            "date",
            "close",
            "previous_close",
            "previous_date",
            "change",
            "change_pct",
            "change_reason",
            "volume",
        )
        if k in latest
    }
    return envelope(
        "company_overview",
        ticker=company.ticker,
        as_of=first_text(latest.get("date")),
        methodology={},
        source="EGX company list, stored daily prices, approved-line fundamentals freshness",
        data=data,
    )


async def _search_companies(session: AsyncSession, args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query")
    if not isinstance(query, str) or not query.strip() or len(query) > 100:
        raise ToolError("INVALID_ARGUMENT", "query must be 1-100 characters")
    limit = _limit(args.get("limit"))
    companies, total = await CompanyRepository(session).list_companies(
        page=1, page_size=limit, search=query.strip(), status=CompanyStatus.ACTIVE
    )
    rows = [
        {
            "ticker": c.ticker,
            "name": c.name,
            "name_ar": c.name_ar,
            "sector": c.sector,
            "industry": c.industry,
        }
        for c in companies
    ]
    return envelope(
        "search_companies",
        ticker=None,
        as_of=None,
        methodology={},
        source="EGX company list",
        data={"query": query.strip(), "total_matches": total, "returned": len(rows), "items": rows},
    )


def _limit(raw: Any) -> int:
    if raw is None:
        return 10
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 1:
        raise ToolError("INVALID_ARGUMENT", "limit must be a positive integer")
    return int(min(raw, MAX_TOOL_ROWS))


async def _price_summary(session: AsyncSession, args: dict[str, Any]) -> dict[str, Any]:
    from app.api.companies import get_latest_price
    from app.api.technical import get_indicators
    from app.technical.service import TECHNICAL_METHODOLOGY_VERSION

    company = await resolve_company(session, args)
    try:
        latest = await get_latest_price(company.id, session)
        indicators = await get_indicators(company.id, None, session)
    except HTTPException as exc:
        raise ToolError("NOT_FOUND", str(exc.detail)) from None
    price = {
        k: latest.get(k)
        for k in (
            "status",
            "reason",
            "date",
            "open",
            "high",
            "low",
            "close",
            "previous_close",
            "previous_date",
            "change",
            "change_pct",
            "change_reason",
            "volume",
            "value_traded",
        )
        if k in latest
    }
    rows = [
        {
            "indicator": r.get("indicator_type"),
            "value": r.get("value"),
            "status": r.get("status"),
            "reason": r.get("reason"),
            "parameters": r.get("parameters"),
        }
        for r in indicators
    ]
    return envelope(
        "price_summary",
        ticker=company.ticker,
        as_of=first_text(latest.get("date")),
        methodology={"technical": TECHNICAL_METHODOLOGY_VERSION},
        source="Stored daily prices (Yahoo Finance) and the EGX AI technical-indicator engine",
        data={"latest": price, "indicators": rows},
    )


def _drop_geometry(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{k: v for k, v in item.items() if k not in ("points", "lines")} for item in items]


async def _chart_patterns(session: AsyncSession, args: dict[str, Any]) -> dict[str, Any]:
    from app.technical.pattern_backtest import patterns_for_company

    company = await resolve_company(session, args)
    payload = await patterns_for_company(session, company.id)
    if payload is None:
        raise ToolError("NOT_FOUND", "Company not found")
    patterns = _drop_geometry(payload.get("patterns", []))
    forming = _drop_geometry(payload.get("forming", []))
    stats = payload.get("stats", {})
    forming_stats = payload.get("forming_stats", {})
    odds = {p["stats_key"]: stats.get(p["stats_key"]) for p in patterns if "stats_key" in p}
    forming_odds = {f["pattern"]: forming_stats.get(f["pattern"]) for f in forming}
    data = {
        "status": payload.get("status"),
        "reason": payload.get("reason"),
        "patterns": patterns,
        "forming": forming,
        "measured_odds": odds,
        "forming_odds": forming_odds,
        "note": payload.get("note"),
        "forming_note": payload.get("forming_note"),
    }
    return envelope(
        "chart_patterns",
        ticker=company.ticker,
        as_of=first_text(payload.get("as_of")),
        methodology={"patterns": payload.get("version")},
        source="EGX AI chart-pattern detector over stored daily prices, with measured EGX odds",
        data=data,
    )


async def _financial_metrics(session: AsyncSession, args: dict[str, Any]) -> dict[str, Any]:
    from app.api.metrics import list_company_metrics
    from app.metrics.service import METRICS_INPUT_VERSION

    company = await resolve_company(session, args)
    fiscal_year = args.get("fiscal_year")
    if fiscal_year is not None and (
        isinstance(fiscal_year, bool) or not isinstance(fiscal_year, int)
    ):
        raise ToolError("INVALID_ARGUMENT", "fiscal_year must be an integer")
    metric_code = args.get("metric_code")
    if metric_code is not None and not isinstance(metric_code, str):
        raise ToolError("INVALID_ARGUMENT", "metric_code must be a string")
    try:
        rows = await list_company_metrics(company.id, fiscal_year, metric_code, session)
    except HTTPException as exc:
        raise ToolError("NOT_FOUND", str(exc.detail)) from None
    if fiscal_year is None:
        years = sorted({r["fiscal_year"] for r in rows if r.get("fiscal_year")}, reverse=True)
        keep = set(years[:DEFAULT_METRIC_YEARS])
        rows = [r for r in rows if r.get("fiscal_year") in keep or not r.get("fiscal_year")]
    compact = [
        {
            k: r.get(k)
            for k in (
                "metric_code",
                "display_name",
                "fiscal_year",
                "period_end",
                "value",
                "unit",
                "status",
                "reason",
                "source_tier",
                "provisional",
            )
        }
        for r in rows
    ]
    meta = rows[0] if rows else {}
    return envelope(
        "financial_metrics",
        ticker=company.ticker,
        as_of=first_text(meta.get("calculated_at")),
        methodology={"metrics": METRICS_INPUT_VERSION},
        source="EGX AI metric engine over approved statement lines (filing-backed or vendor)",
        data={
            "metrics": strip_noise(compact),
            "note": (
                f"Newest {DEFAULT_METRIC_YEARS} fiscal years unless fiscal_year is given."
                if fiscal_year is None
                else None
            ),
        },
    )


COMPANY_TOOLS: tuple[ToolDef, ...] = (
    ToolDef(
        name="company_overview",
        description=(
            "Basic profile of one company: name, sector, industry, currency, share data, how "
            "fresh its fundamentals are, and its latest stored price with the session change."
        ),
        parameters=object_schema({"ticker": TICKER_PROPERTY}, ["ticker"]),
        run=_company_overview,
    ),
    ToolDef(
        name="search_companies",
        description="Find companies by part of a ticker or name (English). Returns tickers.",
        parameters=object_schema(
            {
                "query": {"type": "string", "description": "Part of a ticker or company name."},
                "limit": {
                    "type": "integer",
                    "description": f"Rows to return, at most {MAX_TOOL_ROWS}.",
                },
            },
            ["query"],
        ),
        run=_search_companies,
    ),
    ToolDef(
        name="price_summary",
        description=(
            "Latest stored price of one company with the change against the previous session, "
            "and its technical indicators (moving averages, RSI and similar) with their status."
        ),
        parameters=object_schema({"ticker": TICKER_PROPERTY}, ["ticker"]),
        run=_price_summary,
    ),
    ToolDef(
        name="chart_patterns",
        description=(
            "Chart shapes confirmed in the last year and shapes forming now for one company, "
            "with the measured EGX odds for each shape. Display only, not a prediction."
        ),
        parameters=object_schema({"ticker": TICKER_PROPERTY}, ["ticker"]),
        run=_chart_patterns,
    ),
    ToolDef(
        name="financial_metrics",
        description=(
            "Computed financial ratios of one company per fiscal year (margins, returns, "
            "leverage, growth, cash-flow metrics) with value, unit, status and source tier."
        ),
        parameters=object_schema(
            {
                "ticker": TICKER_PROPERTY,
                "fiscal_year": {"type": "integer", "description": "Only this fiscal year."},
                "metric_code": {"type": "string", "description": "Only this metric, e.g. roe."},
            },
            ["ticker"],
        ),
        run=_financial_metrics,
    ),
)
