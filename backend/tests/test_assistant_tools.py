"""Assistant tools: read-only wrappers over the services the routers use."""

import json
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tools import CARD_TOOLS, TOOLS, execute_tool, tool_specs
from app.ai.verify import verify
from app.models.market import Company
from statement_seed import make_company, seed_prices

EXPECTED_TOOLS = {
    "company_overview",
    "investment_score",
    "valuation",
    "stance",
    "shariah_status",
    "price_summary",
    "chart_patterns",
    "financial_metrics",
    "search_companies",
    "screen_companies",
}


@pytest.fixture
async def priced(db_session: AsyncSession) -> Company:
    company = await make_company(db_session, sector="Banks")
    await seed_prices(db_session, company)  # last close 31.9
    return company


@pytest.fixture
async def bare(db_session: AsyncSession) -> Company:
    return await make_company(db_session, sector="Banks")


def test_registry_has_the_contract_tools_and_valid_schemas() -> None:
    assert set(TOOLS) == EXPECTED_TOOLS
    for spec in tool_specs():
        assert spec.description and spec.parameters["type"] == "object"
        assert spec.parameters["additionalProperties"] is False
    assert set(CARD_TOOLS.values()) <= set(TOOLS)


@pytest.mark.parametrize(
    "name",
    [
        "company_overview",
        "investment_score",
        "valuation",
        "stance",
        "shariah_status",
        "price_summary",
        "chart_patterns",
        "financial_metrics",
    ],
)
async def test_company_tools_return_a_sourced_envelope(
    db_session: AsyncSession, priced: Company, name: str
) -> None:
    outcome = await execute_tool(db_session, name, {"ticker": priced.ticker.lower()})
    assert outcome.ok, outcome.output
    out = outcome.output
    assert out["tool"] == name and out["ticker"] == priced.ticker
    assert out["as_of"] and out["source"] and "methodology_versions" in out
    json.dumps(out)  # JSON-serializable as returned
    assert "company_id" not in json.dumps(out["data"])  # identifiers stripped


async def test_overview_and_prices_pass_values_through(
    db_session: AsyncSession, priced: Company
) -> None:
    result = await execute_tool(db_session, "company_overview", {"ticker": priced.ticker})
    overview = result.output
    assert overview["data"]["sector"] == "Banks"
    assert overview["data"]["latest_price"]["status"] == "AVAILABLE"
    assert overview["data"]["latest_price"]["close"].startswith("31.9")
    assert overview["data"]["fundamentals"]["status"] == "INSUFFICIENT_DATA"  # no lines seeded
    summary = (await execute_tool(db_session, "price_summary", {"ticker": priced.ticker})).output
    assert summary["data"]["latest"]["close"].startswith("31.9")
    assert verify("It closed at 31.9.", [summary]).verified
    assert not verify("It closed at 45.2.", [summary]).verified


async def test_missing_data_stays_insufficient_never_zero(
    db_session: AsyncSession, bare: Company
) -> None:
    overview = (await execute_tool(db_session, "company_overview", {"ticker": bare.ticker})).output
    latest = overview["data"]["latest_price"]
    assert latest["status"] == "INSUFFICIENT_DATA" and latest["close"] is None
    fundamentals = overview["data"]["fundamentals"]
    assert fundamentals["status"] == "INSUFFICIENT_DATA" and fundamentals["fiscal_year"] is None
    metrics = (await execute_tool(db_session, "financial_metrics", {"ticker": bare.ticker})).output
    assert metrics["data"]["metrics"] == []
    valuation = (await execute_tool(db_session, "valuation", {"ticker": bare.ticker})).output
    fair = valuation["data"]["fair_value"]
    assert fair["status"] == "INSUFFICIENT_DATA" and fair["value"] is None
    patterns = (await execute_tool(db_session, "chart_patterns", {"ticker": bare.ticker})).output
    assert patterns["data"]["status"] == "INSUFFICIENT_DATA" and patterns["data"]["patterns"] == []


async def test_stance_uses_the_ui_labels_never_buy(
    db_session: AsyncSession, priced: Company
) -> None:
    out = (await execute_tool(db_session, "stance", {"ticker": priced.ticker})).output
    assert out["data"]["stance"] in ("leans buy", "neutral", "leans reduce")
    assert out["methodology_versions"]["stance"]


async def test_ticker_arguments_are_validated_against_the_company_table(
    db_session: AsyncSession,
) -> None:
    unknown = await execute_tool(db_session, "valuation", {"ticker": "NOPE"})
    assert not unknown.ok and unknown.output["error"] == "UNKNOWN_TICKER"
    for bad in (None, "", "A B", "x" * 30, "COMI'; DROP TABLE companies;--", 5):
        outcome = await execute_tool(db_session, "stance", {"ticker": bad})
        assert not outcome.ok and outcome.output["error"] == "INVALID_ARGUMENT"
    assert (await execute_tool(db_session, "stance", {})).output["error"] == "INVALID_ARGUMENT"
    no_tool = await execute_tool(db_session, "delete_everything", {})
    assert no_tool.output["error"] == "UNKNOWN_TOOL"
    broken = await execute_tool(db_session, "stance", {"__invalid_arguments__": "{{"})
    assert broken.output["error"] == "INVALID_ARGUMENT"


async def test_search_companies(db_session: AsyncSession, priced: Company) -> None:
    out = (await execute_tool(db_session, "search_companies", {"query": priced.ticker[:7]})).output
    assert [r["ticker"] for r in out["data"]["items"]] == [priced.ticker]
    empty = (await execute_tool(db_session, "search_companies", {"query": "zzzzqqqq"})).output
    assert empty["data"]["items"] == [] and empty["data"]["total_matches"] == 0
    assert not (await execute_tool(db_session, "search_companies", {"query": ""})).ok
    assert not (await execute_tool(db_session, "search_companies", {"query": "a", "limit": 0})).ok


async def test_screen_companies_filters_and_rejects_free_form(
    db_session: AsyncSession, priced: Company, bare: Company
) -> None:
    banks = (
        await execute_tool(db_session, "screen_companies", {"sector": "banks", "limit": 25})
    ).output["data"]
    tickers = {r["ticker"] for r in banks["items"]}
    assert {priced.ticker, bare.ticker} <= tickers or banks["total_matches"] > 25

    unscreened = (
        await execute_tool(
            db_session,
            "screen_companies",
            {"sector": "Banks", "shariah_verdict": "NOT_SCREENED", "limit": 25},
        )
    ).output["data"]
    assert unscreened["filters"]["shariah_verdict"] == "NOT_SCREENED"
    assert all(r["shariah_verdict"] == "NOT_SCREENED" for r in unscreened["items"])

    nothing = (
        await execute_tool(
            db_session,
            "screen_companies",
            {"sector": "Banks", "metrics": [{"code": "roe", "op": "gte", "value": 0.15}]},
        )
    ).output["data"]
    # No metric is computed for these companies: they are left out, not treated as zero.
    assert nothing["items"] == [] and nothing["notes"]

    no_sector = (await execute_tool(db_session, "screen_companies", {"sector": "Moon"})).output
    assert no_sector["data"]["items"] == [] and "Sectors" in no_sector["data"]["notes"][0]

    for bad in (
        {"shariah_verdict": "MAYBE"},
        {"stance": "buy"},
        {"forming": "sideways"},
        {"metrics": [{"code": "drop table", "op": "gte", "value": 1}]},
        {"metrics": [{"code": "roe", "op": "gt", "value": 1}]},
        {"metrics": [{"code": "roe", "op": "gte", "value": "abc"}]},
        {"metrics": [{"code": "roe", "op": "gte", "value": 1}] * 4},
        {"limit": -1},
    ):
        outcome = await execute_tool(db_session, "screen_companies", bad)
        assert not outcome.ok and outcome.output["error"] == "INVALID_ARGUMENT", bad


async def test_screen_by_stance_and_forming_run_on_stored_results(
    db_session: AsyncSession, priced: Company
) -> None:
    out: dict[str, Any] = (
        await execute_tool(
            db_session,
            "screen_companies",
            {"sector": "Banks", "stance": "neutral", "limit": 25},
        )
    ).output["data"]
    assert out["filters"]["stance"] == "neutral"
    assert all(r["stance"] == "neutral" for r in out["items"])
    forming = (
        await execute_tool(db_session, "screen_companies", {"sector": "Banks", "forming": "any"})
    ).output["data"]
    assert all("forming" in r for r in forming["items"])


async def test_tools_never_write_rows_we_did_not_already_write_on_view(
    db_session: AsyncSession, priced: Company
) -> None:
    from app.models.assistant import AiMessage, AiProviderKey

    for name in ("search_companies", "screen_companies"):
        await execute_tool(db_session, name, {"query": "a", "sector": "Banks"})
    for model in (AiMessage, AiProviderKey):
        assert (await db_session.execute(select(func.count()).select_from(model))).scalar() == 0
