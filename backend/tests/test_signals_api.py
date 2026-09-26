"""Tests for the signals API /ranking endpoints."""

import pytest
from httpx import AsyncClient


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
async def test_signals_list_coverage(client: AsyncClient, db_session) -> None:
    from sqlalchemy import text
    from app.signals.engine import SignalEngine
    async with db_session as s:
        r = await SignalEngine(s).run(persist=True)
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
async def test_signals_run_now(client: AsyncClient) -> None:
    response = await client.post("/api/signals/run")
    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "egx_price_momentum@1.1.0"
    assert data["scored_count"] + data["unscorable_count"] == data["universe_total"]