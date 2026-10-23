"""API token authentication: every router except health is protected."""

from httpx import AsyncClient

from app.core.config import settings


async def test_health_is_public(anon_client: AsyncClient) -> None:
    response = await anon_client.get("/api/health")
    assert response.status_code == 200


async def test_missing_token_is_rejected(anon_client: AsyncClient) -> None:
    response = await anon_client.get("/api/companies")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_wrong_token_is_rejected(anon_client: AsyncClient) -> None:
    response = await anon_client.get(
        "/api/companies", headers={"Authorization": "Bearer " + "y" * 43}
    )
    assert response.status_code == 401


async def test_mutating_route_requires_token(anon_client: AsyncClient) -> None:
    response = await anon_client.post("/api/ingestion/sync")
    assert response.status_code == 401


async def test_valid_token_is_accepted(client: AsyncClient) -> None:
    response = await client.get("/api/companies")
    assert response.status_code == 200


async def test_unconfigured_token_fails_closed(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "API_TOKEN", "")
    response = await client.get("/api/companies", headers={"Authorization": "Bearer "})
    assert response.status_code == 503


async def test_short_token_fails_closed(client: AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "API_TOKEN", "short")
    response = await client.get("/api/companies", headers={"Authorization": "Bearer short"})
    assert response.status_code == 503


async def test_api_docs_disabled_by_default(anon_client: AsyncClient) -> None:
    response = await anon_client.get("/openapi.json")
    assert response.status_code == 404


async def test_ai_query_length_is_bounded(client: AsyncClient, test_company) -> None:
    response = await client.post(
        f"/api/ai/companies/{test_company.id}/analyze",
        json={"analysis_type": "summary", "query": "x" * 2001},
    )
    assert response.status_code == 422
