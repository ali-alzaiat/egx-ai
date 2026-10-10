"""Tests for the in-process market refresh job, its router and assessment phase."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.ingestion import jobs
from app.ingestion.egx.universe import UniverseEntry, UniverseSnapshot
from app.ingestion.fake_provider import FakeMarketDataProvider
from app.ingestion.provider import DailyPriceData
from app.models.data_quality import DataQualityAssessment
from app.models.market import Company


class _StubProvider:
    """Fake price provider: deterministic bars, optional per-ticker failure/delay."""

    def __init__(
        self,
        fail: set[str] | None = None,
        delay: float = 0.0,
        empty: set[str] | None = None,
    ) -> None:
        self.fail = fail or set()
        self.delay = delay
        self.empty = empty or set()
        self._inner = FakeMarketDataProvider()

    async def get_companies(self) -> list[object]:
        return list(await self._inner.get_companies())

    async def get_daily_prices(
        self,
        ticker: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[DailyPriceData]:
        if self.delay:
            await asyncio.sleep(self.delay)
        if ticker in self.fail:
            raise RuntimeError(f"no history for {ticker}")
        if ticker in self.empty:
            return []
        return await self._inner.get_daily_prices(ticker, start_date, end_date)


class _StubUniverseSource:
    name = "TEST_UNIVERSE"

    def __init__(self, tickers: list[str]) -> None:
        self._tickers = tickers

    async def fetch(self) -> UniverseSnapshot:
        return UniverseSnapshot(
            entries=tuple(UniverseEntry(ticker=t, name=t) for t in self._tickers),
            source_name=self.name,
            source_url="https://example.test/universe",
            fetched_at=datetime.now(UTC),
        )


class _FailingUniverseSource:
    name = "FAILING_UNIVERSE"

    async def fetch(self) -> UniverseSnapshot:
        raise RuntimeError("universe source down")


@pytest.fixture
def refresh_env(monkeypatch, db_session):
    """Point the job at the test transaction and a stub universe."""
    jobs.reset_job()

    @asynccontextmanager
    async def session_factory():
        yield db_session

    monkeypatch.setattr(jobs, "_session_factory", session_factory)
    monkeypatch.setattr(
        jobs, "create_universe_source", lambda: _StubUniverseSource(["COMI", "HRHO"])
    )
    yield
    jobs.reset_job()


async def _await_job() -> None:
    task = jobs.current_job().task
    assert task is not None
    await task


_TICKERS = {"tickers": "COMI,HRHO"}


async def test_full_refresh_happy_path(client, refresh_env, monkeypatch, db_session):
    monkeypatch.setattr(jobs, "create_price_provider", lambda: _StubProvider())

    response = await client.post("/api/ingestion/sync", params=_TICKERS)
    assert response.status_code == 202
    accepted = response.json()
    assert accepted["status"] == "accepted"
    assert accepted["started_at"] is not None
    assert accepted["finished_at"] is None

    await _await_job()
    done = jobs.current_job().to_dict()
    assert done["status"] == "done"
    assert done["finished_at"] is not None
    assert done["phase"] is None
    assert done["universe"] == {"discovered": 2}
    assert done["prices"]["companies_total"] == 2
    assert done["prices"]["companies_fetched"] == 2
    assert done["prices"]["failed_count"] == 0
    assert done["prices"]["records_written"] > 0
    assert done["assessment"]["companies_assessed"] >= 2
    assert (
        done["assessment"]["scores_written"]
        == done["assessment"]["companies_assessed"] * 3
    )

    company_count = (await db_session.execute(select(func.count(Company.id)))).scalar_one()
    rows = (
        await db_session.execute(select(func.count(DataQualityAssessment.id)))
    ).scalar_one()
    assert rows == company_count * 3


async def test_single_flight_returns_409(client, refresh_env, monkeypatch):
    monkeypatch.setattr(jobs, "create_price_provider", lambda: _StubProvider(delay=0.2))

    first = await client.post("/api/ingestion/sync", params=_TICKERS)
    assert first.status_code == 202

    second = await client.post("/api/ingestion/sync", params=_TICKERS)
    assert second.status_code == 409
    body = second.json()
    assert body["status"] in ("accepted", "running")
    assert "detail" not in body  # 409 body is the job object itself

    await _await_job()
    assert jobs.current_job().status == "done"


async def test_terminal_state_starts_new_job(client, refresh_env, monkeypatch):
    monkeypatch.setattr(jobs, "create_price_provider", lambda: _StubProvider())
    params = {"universe_only": True}

    assert (await client.post("/api/ingestion/sync", params=params)).status_code == 202
    await _await_job()
    first_started = jobs.current_job().started_at

    second = await client.post("/api/ingestion/sync", params=params)
    assert second.status_code == 202
    assert jobs.current_job().started_at != first_started
    await _await_job()


async def test_partial_on_ticker_failure(client, refresh_env, monkeypatch):
    monkeypatch.setattr(
        jobs, "create_price_provider", lambda: _StubProvider(fail={"COMI"})
    )

    assert (await client.post("/api/ingestion/sync", params=_TICKERS)).status_code == 202
    await _await_job()

    job = jobs.current_job().to_dict()
    assert job["status"] == "partial"
    assert job["prices"]["companies_total"] == 2
    assert job["prices"]["companies_fetched"] == 1
    assert job["prices"]["failed_count"] == 1
    assert job["prices"]["failed_tickers"] == [
        {"ticker": "COMI", "error": "no history for COMI"}
    ]
    assert job["assessment"]["scores_written"] > 0
    assert job["error"] is None


async def test_partial_on_empty_history(client, refresh_env, monkeypatch):
    monkeypatch.setattr(
        jobs, "create_price_provider", lambda: _StubProvider(empty={"COMI"})
    )

    assert (await client.post("/api/ingestion/sync", params=_TICKERS)).status_code == 202
    await _await_job()

    job = jobs.current_job().to_dict()
    assert job["status"] == "partial"
    assert job["prices"]["companies_total"] == 2
    assert job["prices"]["companies_fetched"] == 1
    assert job["prices"]["failed_count"] == 1
    assert job["prices"]["failed_tickers"] == [
        {"ticker": "COMI", "error": "Yahoo returned no history"}
    ]
    assert job["assessment"]["scores_written"] > 0
    assert job["error"] is None


async def test_failed_on_uncaught_exception(client, refresh_env, monkeypatch):
    monkeypatch.setattr(jobs, "create_universe_source", lambda: _FailingUniverseSource())

    assert (await client.post("/api/ingestion/sync")).status_code == 202
    await _await_job()

    job = jobs.current_job().to_dict()
    assert job["status"] == "failed"
    assert job["error"] is not None
    assert "universe source down" in job["error"]
    assert job["phase"] == "universe"
    assert job["finished_at"] is not None


async def test_timeout_fails_job(client, refresh_env, monkeypatch):
    monkeypatch.setattr(settings, "SYNC_JOB_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(jobs, "create_price_provider", lambda: _StubProvider(delay=1.0))

    assert (await client.post("/api/ingestion/sync", params=_TICKERS)).status_code == 202
    await _await_job()

    job = jobs.current_job().to_dict()
    assert job["status"] == "failed"
    assert job["error"] is not None
    assert "TimeoutError" in job["error"]


async def test_status_endpoint_always_200(client, refresh_env, monkeypatch):
    idle = await client.get("/api/ingestion/sync/status")
    assert idle.status_code == 200
    assert idle.json()["status"] == "idle"
    assert idle.json()["started_at"] is None

    monkeypatch.setattr(jobs, "create_price_provider", lambda: _StubProvider(delay=0.1))
    assert (await client.post("/api/ingestion/sync", params=_TICKERS)).status_code == 202
    running = await client.get("/api/ingestion/sync/status")
    assert running.status_code == 200

    await _await_job()
    done = await client.get("/api/ingestion/sync/status")
    assert done.status_code == 200
    assert done.json()["status"] == "done"


async def test_active_tickers_reads_active_universe(db_session, test_company):
    tickers = await jobs._active_tickers(db_session)
    assert test_company.ticker in tickers


async def test_get_data_quality_stays_read_only(client, refresh_env, db_session, test_company):
    before = (
        await db_session.execute(select(func.count(DataQualityAssessment.id)))
    ).scalar_one()

    response = await client.get(f"/api/data-quality/companies/{test_company.id}")
    assert response.status_code == 200

    after = (
        await db_session.execute(select(func.count(DataQualityAssessment.id)))
    ).scalar_one()
    assert after == before


async def test_data_sources_exposes_last_synced_at(client):
    response = await client.get("/api/data-sources")
    assert response.status_code == 200
    items = response.json()
    assert items  # the dev/test database always has at least one source
    assert all("last_synced_at" in item for item in items)
