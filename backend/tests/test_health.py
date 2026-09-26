import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


@pytest.mark.asyncio
async def test_root(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "EGX AI"
    assert "version" in data
