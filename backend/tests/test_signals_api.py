"""Tests for the signals API /ranking endpoints."""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.market import Company, CompanyStatus, DailyPrice, DataSource, DataSourceType

PRICED_SESSIONS = 300


@pytest_asyncio.fixture
async def priced_companies(db_session) -> list[Company]:
    """Three active companies with a year of prices: the engine needs real history
    and the test database starts empty."""
    source = DataSource(
        id=uuid.uuid4(),
        name=f"TEST_SRC_{uuid.uuid4().hex[:6]}",
        source_type=DataSourceType.SYNTHETIC,
    )
    db_session.add(source)
    companies = []
    for drift in (Decimal("0.002"), Decimal("0"), Decimal("-0.002")):
        company = Company(
            id=uuid.uuid4(),
            ticker=f"SIG{uuid.uuid4().hex[:6].upper()}",
            name="Signals probe",
            currency="EGP",
            status=CompanyStatus.ACTIVE,
        )
        db_session.add(company)
        companies.append((company, drift))
    await db_session.flush()
    start = date.today() - timedelta(days=PRICED_SESSIONS)
    for company, drift in companies:
        close = Decimal("10")
        for i in range(PRICED_SESSIONS):
            close = (close * (Decimal("1") + drift + Decimal(i % 3 - 1) / 200)).quantize(
                Decimal("0.0001")
            )
            db_session.add(
                DailyPrice(
                    company_id=company.id,
                    date=start + timedelta(days=i),
                    open=close,
                    high=close * Decimal("1.01"),
                    low=close * Decimal("0.99"),
                    close=close,
                    volume=500_000,
                    source_id=source.id,
                )
            )
    await db_session.flush()
    return [c for c, _ in companies]


@pytest.mark.asyncio
async def test_signals_list_with_filter(client: AsyncClient, test_company) -> None:
    response = await client.get(
        "/api/signals?limit=5&min_score=50&tier=STRONGEST"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 0
    for item in data["results"]:
        assert "ticker" in item
        assert "score" in item
        assert "rank" in item
        assert "model" in item


@pytest.mark.asyncio
async def test_signals_list_coverage(
    client: AsyncClient, db_session, priced_companies
) -> None:
    from app.signals.engine import SignalEngine
    async with db_session as s:
        await SignalEngine(s).run(persist=True)
        await s.commit()
    response = await client.get("/api/signals")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    scored = [i for i in data["results"] if i["status"] == "SCORED"][0]
    assert scored["data_coverage"] is not None


@pytest.mark.asyncio
async def test_signals_model(client: AsyncClient) -> None:
    response = await client.get("/api/signals/model")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "egx_price_momentum"
    assert data["version"] == "1.1.0"
    factors = {f["key"] for f in data["factors"]}
    assert "liquidity" in factors
    assert "volatility" in factors


@pytest.mark.asyncio
async def test_signals_unscorable(client: AsyncClient) -> None:
    response = await client.get("/api/signals/unscorable")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_signals_coverage(client: AsyncClient) -> None:
    response = await client.get("/api/signals/coverage")
    assert response.status_code == 200
    data = response.json()
    assert "universe_total" in data
    assert "active_total" in data
    assert "with_price_data" in data
    assert "priced_of_active" in data
    assert "unscorable" in data
    assert "unpriced_tickers" in data


@pytest.mark.asyncio
async def test_signals_run_now(client: AsyncClient, priced_companies) -> None:
    response = await client.post("/api/signals/run")
    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "egx_price_momentum@1.1.0"
    assert data["scored_count"] + data["unscorable_count"] == data["universe_total"]
