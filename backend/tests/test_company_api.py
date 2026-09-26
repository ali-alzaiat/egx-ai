"""Tests for company API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_companies_empty(client: AsyncClient) -> None:
    response = await client.get("/api/companies")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_get_company_not_found(client: AsyncClient) -> None:
    import uuid

    fake_id = uuid.uuid4()
    response = await client.get(f"/api/companies/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_company_by_ticker_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/companies/ticker/INVALID")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_companies_pagination(client: AsyncClient) -> None:
    response = await client.get("/api/companies?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 10


@pytest.mark.asyncio
async def test_list_companies_search(client: AsyncClient) -> None:
    response = await client.get("/api/companies?search=COMI")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_companies_filter_status(client: AsyncClient) -> None:
    response = await client.get("/api/companies?status=ACTIVE")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_company_prices_not_found(client: AsyncClient) -> None:
    import uuid

    fake_id = uuid.uuid4()
    response = await client.get(f"/api/companies/{fake_id}/prices")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_latest_price_not_found(client: AsyncClient) -> None:
    import uuid

    fake_id = uuid.uuid4()
    response = await client.get(f"/api/companies/{fake_id}/prices/latest")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_company_prices_invalid_date_range(client: AsyncClient) -> None:
    import uuid

    fake_id = uuid.uuid4()
    response = await client.get(
        f"/api/companies/{fake_id}/prices?start_date=2026-09-01&end_date=2026-01-01"
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_health_still_works(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
