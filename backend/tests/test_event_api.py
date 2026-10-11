"""Tests for event ledger API (B6)."""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.continuous.constants import CI_METHODOLOGY_VERSION
from app.models.continuous import ActorType, Event, EventType
from app.models.market import Company, CompanyStatus

pytestmark = pytest.mark.asyncio


async def _make_company(db_session: AsyncSession, ticker: str) -> Company:
    company = Company(
        id=uuid.uuid4(),
        ticker=ticker,
        isin=f"EG{uuid.uuid4().hex[:10].upper()}",
        name=f"{ticker} Company",
        currency="EGP",
        status=CompanyStatus.ACTIVE,
    )
    db_session.add(company)
    await db_session.flush()
    return company


class TestEventAPI:
    """Tests for event ledger API endpoints."""

    async def test_list_events(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """List events with filters."""
        company = await _make_company(db_session, "EVTCO")

        # Create test events
        event1 = Event(
            id=uuid.uuid4(),
            actor_type=ActorType.USER,
            actor_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            rule_version=CI_METHODOLOGY_VERSION,
            type=EventType.WATCHLIST_ADD,
            symbols=[company.id],
            inputs_snapshot={"test": "data1"},
            reason="Added to watchlist",
        )
        event2 = Event(
            id=uuid.uuid4(),
            actor_type=ActorType.SYSTEM,
            actor_id=uuid.uuid4(),
            rule_version=CI_METHODOLOGY_VERSION,
            type=EventType.CHECK_EVALUATED,
            symbols=[company.id],
            inputs_snapshot={"test": "data2"},
            reason="Check evaluated",
        )
        event3 = Event(
            id=uuid.uuid4(),
            actor_type=ActorType.USER,
            actor_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            rule_version=CI_METHODOLOGY_VERSION,
            type=EventType.ALERT_FIRED,
            symbols=[company.id],
            inputs_snapshot={"test": "data3"},
            reason="Alert fired",
        )
        db_session.add_all([event1, event2, event3])
        await db_session.flush()

        # List all events
        response = await client.get("/api/events")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # Filter by symbol
        response = await client.get(f"/api/events?symbol={company.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        for e in data:
            assert company.id in [uuid.UUID(s) for s in e["symbols"]]

        # Filter by type
        response = await client.get(f"/api/events?type={EventType.WATCHLIST_ADD.value}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == EventType.WATCHLIST_ADD.value

        # Filter by actor_type
        response = await client.get("/api/events?type=check.evaluated")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == EventType.CHECK_EVALUATED.value

        # Pagination
        response = await client.get("/api/events?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        response = await client.get("/api/events?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    async def test_list_events_invalid_type(self, client: AsyncClient) -> None:
        """Invalid event type should return 400."""
        response = await client.get("/api/events?type=invalid_type")
        assert response.status_code == 400
        assert "Invalid event type" in response.json()["detail"]

    async def test_list_events_date_filters(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Date filters should work."""
        company = await _make_company(db_session, "DATEEVT")

        event1 = Event(
            id=uuid.uuid4(),
            actor_type=ActorType.USER,
            actor_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            rule_version=CI_METHODOLOGY_VERSION,
            type=EventType.WATCHLIST_ADD,
            symbols=[company.id],
            inputs_snapshot={},
            reason="Old event",
        )
        event2 = Event(
            id=uuid.uuid4(),
            actor_type=ActorType.USER,
            actor_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            rule_version=CI_METHODOLOGY_VERSION,
            type=EventType.WATCHLIST_ADD,
            symbols=[company.id],
            inputs_snapshot={},
            reason="New event",
        )
        db_session.add_all([event1, event2])
        await db_session.flush()

        # Filter by date_from
        yesterday = date.today()
        response = await client.get(f"/api/events?date_from={yesterday.isoformat()}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        tomorrow = date(2099, 1, 1)
        response = await client.get(f"/api/events?date_from={tomorrow.isoformat()}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    async def test_export_events(self, client: AsyncClient, db_session: AsyncSession) -> None:
        """Export events as JSON."""
        company = await _make_company(db_session, "EXPORTEVT")

        event1 = Event(
            id=uuid.uuid4(),
            actor_type=ActorType.USER,
            actor_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            rule_version=CI_METHODOLOGY_VERSION,
            type=EventType.WATCHLIST_ADD,
            symbols=[company.id],
            inputs_snapshot={"key": "value"},
            reason="Test export",
        )
        db_session.add(event1)
        await db_session.flush()

        response = await client.get("/api/events/export")
        assert response.status_code == 200
        data = response.json()

        assert "events" in data
        assert "total" in data
        assert "filters" in data
        assert data["total"] == 1
        assert len(data["events"]) == 1

        exported_event = data["events"][0]
        assert exported_event["type"] == EventType.WATCHLIST_ADD.value
        assert exported_event["symbols"] == [str(company.id)]
        assert exported_event["inputs_snapshot"] == {"key": "value"}
        assert exported_event["reason"] == "Test export"

    async def test_export_events_with_filters(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Export with filters should respect filters."""
        company1 = await _make_company(db_session, "EXPORT1")
        company2 = await _make_company(db_session, "EXPORT2")

        event1 = Event(
            id=uuid.uuid4(),
            actor_type=ActorType.USER,
            actor_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            rule_version=CI_METHODOLOGY_VERSION,
            type=EventType.WATCHLIST_ADD,
            symbols=[company1.id],
            inputs_snapshot={},
            reason="Company 1",
        )
        event2 = Event(
            id=uuid.uuid4(),
            actor_type=ActorType.USER,
            actor_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            rule_version=CI_METHODOLOGY_VERSION,
            type=EventType.WATCHLIST_ADD,
            symbols=[company2.id],
            inputs_snapshot={},
            reason="Company 2",
        )
        db_session.add_all([event1, event2])
        await db_session.flush()

        # Export filtered by symbol
        response = await client.get(f"/api/events/export?symbol={company1.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["events"]) == 1
        assert data["events"][0]["symbols"] == [str(company1.id)]

    async def test_event_supersedes_chain(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        """Events with supersedes chain should export correctly."""
        company = await _make_company(db_session, "SUPEREVT")

        event1 = Event(
            id=uuid.uuid4(),
            actor_type=ActorType.USER,
            actor_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            rule_version=CI_METHODOLOGY_VERSION,
            type=EventType.WATCHLIST_ADD,
            symbols=[company.id],
            inputs_snapshot={},
            reason="Original",
        )
        event2 = Event(
            id=uuid.uuid4(),
            actor_type=ActorType.USER,
            actor_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            rule_version=CI_METHODOLOGY_VERSION,
            type=EventType.WATCHLIST_REMOVE,
            symbols=[company.id],
            inputs_snapshot={},
            reason="Correction",
            supersedes_id=event1.id,
        )
        db_session.add_all([event1, event2])
        await db_session.flush()

        response = await client.get("/api/events/export")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

        events_by_id = {e["id"]: e for e in data["events"]}
        assert events_by_id[str(event1.id)]["supersedes_id"] is None
        assert events_by_id[str(event2.id)]["supersedes_id"] == str(event1.id)
