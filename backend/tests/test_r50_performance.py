"""R50: EGX30 sync in the price phase, the index repository and the company_performance tool."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tools import TOOLS, execute_tool
from app.ingestion import jobs
from app.repositories.index_prices import IndexPriceRepository
from statement_seed import make_company, seed_prices, seed_year
from test_ingestion_jobs import _await_job, _StubProvider, refresh_env  # noqa: F401


async def test_index_series_upsert_and_range(db_session: AsyncSession) -> None:
    repo = IndexPriceRepository(db_session)
    rows = [(date(2026, 10, d), Decimal("30000") + d) for d in (1, 2, 5)]
    assert await repo.upsert_many("EGX30", rows, "yahoo_finance") == 3
    assert await repo.upsert_many("EGX30", [(date(2026, 10, 2), Decimal("1"))], "yahoo_finance")
    series = await repo.series("EGX30", date(2026, 10, 2), date(2026, 10, 5))
    assert series == [(date(2026, 10, 2), Decimal("1.0000")), (date(2026, 10, 5), Decimal("30005"))]
    assert await repo.series("OTHER") == []


async def test_company_performance_tool_end_to_end(db_session: AsyncSession) -> None:
    company = await make_company(db_session, sector="Banks")
    last = await seed_prices(db_session, company, bars=300)  # +0.1 a day, ends today
    repo = IndexPriceRepository(db_session)
    await repo.upsert_many(
        "EGX30",
        [(last - timedelta(days=299 - i), Decimal("30000") + 10 * i) for i in range(300)],
        "yahoo_finance",
    )
    await seed_year(db_session, company, 2024, {"revenue": Decimal("1000")}, tier="filing")
    await seed_year(
        db_session, company, 2025, {"revenue": Decimal("1200"), "net_income": Decimal("100")},
        tier="filing",
    )

    outcome = await execute_tool(db_session, "company_performance", {"ticker": company.ticker})
    assert outcome.ok, outcome.output
    out = outcome.output
    assert out["tool"] == "company_performance" and out["ticker"] == company.ticker
    assert out["methodology_versions"] == {"performance": "performance-1.1"}
    assert out["as_of"] == last.isoformat()
    assert "stored prices, EGX30" in out["source"]
    window = out["data"]["returns"]["1M"]
    stock_1m, index_1m = Decimal(window["stock"]["return"]), Decimal(window["index"]["return"])
    assert stock_1m > 0 and index_1m > 0
    assert Decimal(window["relative"]["relative"]) == stock_1m - index_1m
    revenue = out["data"]["fundamentals"]["revenue"]
    assert revenue["annual"]["value"] == "1200.0000"
    assert revenue["annual"]["yoy"]["delta_pct"] == "0.2000"
    assert revenue["ttm"]["status"] == "INSUFFICIENT_DATA"  # annual filings only, no quarters


async def test_company_performance_without_index_or_prices(db_session: AsyncSession) -> None:
    company = await make_company(db_session)
    outcome = await execute_tool(db_session, "company_performance", {"ticker": company.ticker})
    assert outcome.ok
    data = outcome.output["data"]
    assert data["price_as_of"] is None and data["index_as_of"] is None
    assert data["returns"]["1Y"]["stock"]["status"] == "INSUFFICIENT_DATA"
    assert data["returns"]["1Y"]["relative"]["status"] == "INSUFFICIENT_DATA"
    assert data["fundamentals"]["ttm_net_margin"]["status"] == "INSUFFICIENT_DATA"


async def test_unknown_ticker_is_a_tool_error(db_session: AsyncSession) -> None:
    outcome = await execute_tool(db_session, "company_performance", {"ticker": "NOPE9"})
    assert not outcome.ok and outcome.output["error"] == "UNKNOWN_TICKER"
    assert "company_performance" in TOOLS


# --- job: EGX30 fetch is best effort -----------------------------------------------------------


class _Index:
    def __init__(self, closes: list[tuple[date, Decimal]] | Exception) -> None:
        self.closes = closes

    async def get_index_closes(
        self, index_code: str, start_date: date, end_date: date
    ) -> list[tuple[date, Decimal]]:
        if isinstance(self.closes, Exception):
            raise self.closes
        assert index_code == "EGX30"
        return self.closes


@pytest.mark.usefixtures("refresh_env")
async def test_sync_stores_egx30(client, monkeypatch, db_session) -> None:  # type: ignore[no-untyped-def]
    closes = [(date(2026, 10, 1), Decimal("31000.5")), (date(2026, 10, 2), Decimal("31100"))]
    monkeypatch.setattr(jobs, "create_price_provider", lambda: _StubProvider())
    monkeypatch.setattr(jobs, "create_index_provider", lambda: _Index(closes))
    response = await client.post("/api/ingestion/sync", params={"tickers": "COMI,HRHO"})
    assert response.status_code == 202
    await _await_job()
    done = jobs.current_job().to_dict()
    assert done["status"] == "done" and done["index_prices"] == {"EGX30": 2}
    assert await IndexPriceRepository(db_session).series("EGX30") == [
        (date(2026, 10, 1), Decimal("31000.5000")),
        (date(2026, 10, 2), Decimal("31100.0000")),
    ]


@pytest.mark.usefixtures("refresh_env")
async def test_egx30_failure_is_logged_and_never_fails_the_job(
    client, monkeypatch, db_session, caplog  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setattr(jobs, "create_price_provider", lambda: _StubProvider())
    monkeypatch.setattr(jobs, "create_index_provider", lambda: _Index(RuntimeError("yahoo down")))
    # alembic's fileConfig (run when the test database is migrated) disables existing loggers.
    monkeypatch.setattr(jobs.logger, "disabled", False)
    with caplog.at_level("WARNING", logger="app.ingestion.jobs"):
        response = await client.post("/api/ingestion/sync", params={"tickers": "COMI,HRHO"})
        assert response.status_code == 202
        await _await_job()
    done = jobs.current_job().to_dict()
    assert done["status"] == "done" and done["index_prices"] == {"EGX30": 0}
    assert "Index EGX30 fetch failed" in caplog.text
    assert await IndexPriceRepository(db_session).series("EGX30") == []


@pytest.mark.usefixtures("refresh_env")
async def test_sync_runs_crosschecks_for_synced_tickers_only(
    client, monkeypatch, db_session  # type: ignore[no-untyped-def]
) -> None:
    from sqlalchemy import select

    from app.dataquality.crosscheck_service import CrosscheckService
    from app.models.market import Company

    monkeypatch.setattr(jobs, "create_price_provider", lambda: _StubProvider())
    response = await client.post("/api/ingestion/sync", params={"tickers": "COMI,HRHO"})
    assert response.status_code == 202
    await _await_job()
    done = jobs.current_job().to_dict()
    assert done["status"] == "done"
    assert done["crosschecks"] == {"companies_checked": 2, "companies_failed": 0}
    rows = await db_session.execute(select(Company).where(Company.ticker.in_(["COMI", "HRHO"])))
    for company in rows.scalars():
        assert len((await CrosscheckService(db_session).latest(company.id))["checks"]) == 5


# --- sector peer benchmark through the tool (R50 B14) -------------------------------------------


async def _sector_company(
    session: AsyncSession, sector: str, bars: int, last_close: str, status: object = None
) -> tuple[str, str]:
    """A company with flat closes of 100 and a final close of ``last_close``."""
    from app.models.market import DailyPrice, DataSource, DataSourceType

    company = await make_company(session, sector=sector)
    if status is not None:
        company.status = status  # type: ignore[assignment]
    source = DataSource(
        id=uuid.uuid4(), name=f"peer {uuid.uuid4().hex[:8]}", source_type=DataSourceType.MANUAL
    )
    session.add(source)
    await session.flush()
    last = date.today()
    for i in range(bars):
        close = Decimal(last_close) if i == bars - 1 else Decimal("100")
        session.add(
            DailyPrice(
                id=uuid.uuid4(), company_id=company.id, date=last - timedelta(days=bars - 1 - i),
                open=close, high=close, low=close, close=close, volume=1000, source_id=source.id,
            )
        )
    await session.flush()
    return str(company.id), company.ticker


async def test_tool_reports_the_sector_median_without_the_company_itself(
    db_session: AsyncSession,
) -> None:
    sector = "R50 Test Sector"
    for r in ("1.10", "1.20", "1.30", "1.40", "1.50"):  # five peers: +10%..+50% in the window
        await _sector_company(db_session, sector, 400, str(Decimal(r) * 100))
    # Another sector must not leak in, and the company's own huge move must not count.
    await _sector_company(db_session, "Other Sector", 400, "900")
    _, ticker = await _sector_company(db_session, sector, 400, "200")  # +100% itself

    outcome = await execute_tool(db_session, "company_performance", {"ticker": ticker})
    assert outcome.ok, outcome.output
    data = outcome.output["data"]
    assert data["sector"] == sector
    block = data["returns"]["1M"]["sector"]
    assert block["peer_count"] == 5  # not 6: the company is excluded
    assert block["median"] == "0.3000"  # median of +10..+50% without the company
    assert block["relative_to_sector"] == "0.7000"  # +100% - 30%
    assert data["returns"]["1Y"]["sector"]["peer_count"] == 5
    assert outcome.output["methodology_versions"] == {"performance": "performance-1.1"}


async def test_tool_sector_benchmark_needs_five_active_peers(db_session: AsyncSession) -> None:
    from app.models.market import CompanyStatus

    sector = "R50 Thin Sector"
    for _ in range(4):
        await _sector_company(db_session, sector, 400, "110")
    await _sector_company(db_session, sector, 400, "110", status=CompanyStatus.DELISTED)
    _, ticker = await _sector_company(db_session, sector, 400, "120")
    outcome = await execute_tool(db_session, "company_performance", {"ticker": ticker})
    block = outcome.output["data"]["returns"]["1M"]["sector"]
    assert block["status"] == "INSUFFICIENT_DATA" and block["peer_count"] == 4  # delisted: out
    assert "at least 5" in block["reason"]


async def test_company_without_a_sector_has_no_peer_benchmark(db_session: AsyncSession) -> None:
    company = await make_company(db_session)  # no sector
    outcome = await execute_tool(db_session, "company_performance", {"ticker": company.ticker})
    data = outcome.output["data"]
    assert data["sector"] is None
    block = data["returns"]["1M"]["sector"]
    assert block["status"] == "INSUFFICIENT_DATA" and block["peer_count"] == 0
    assert "no sector" in block["reason"]


async def test_peer_closes_are_read_in_one_query(db_session: AsyncSession) -> None:
    from sqlalchemy import event

    sector = "R50 Query Sector"
    for _ in range(6):
        await _sector_company(db_session, sector, 60, "110")
    _, ticker = await _sector_company(db_session, sector, 60, "120")
    statements: list[str] = []
    sync_engine = db_session.bind.sync_engine  # type: ignore[union-attr]

    def capture(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        statements.append(statement)

    event.listen(sync_engine, "before_cursor_execute", capture)
    try:
        await execute_tool(db_session, "company_performance", {"ticker": ticker})
    finally:
        event.remove(sync_engine, "before_cursor_execute", capture)
    peer_reads = [s for s in statements if "FROM daily_prices JOIN companies" in s]
    assert len(peer_reads) == 1
