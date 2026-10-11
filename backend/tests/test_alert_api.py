"""Tests for alert API (B2)."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.continuous import AlertFamily, AlertFired, AlertRule, Event, EventType
from app.models.market import Company, CompanyStatus, DailyPrice, DataSource, DataSourceType
from app.models.valuation import ValuationFairValue

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


async def _add_price(db_session: AsyncSession, company: Company, close: Decimal) -> None:
    source = DataSource(
        id=uuid.uuid4(),
        name=f"Price Source {uuid.uuid4().hex[:8]}",
        source_type=DataSourceType.EGX,
    )
    db_session.add(source)
    await db_session.flush()
    db_session.add(
        DailyPrice(
            id=uuid.uuid4(),
            company_id=company.id,
            date=date(2026, 10, 10),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1000,
            source_id=source.id,
        )
    )
    await db_session.flush()


async def _add_fair_value(db_session: AsyncSession, company: Company, fv: Decimal) -> None:
    db_session.add(
        ValuationFairValue(
            id=uuid.uuid4(),
            company_id=company.id,
            profile_key="default",
            methodology_version="1.0",
            fair_value=fv,
            fair_value_status="AVAILABLE",
            legs={},
            weights={},
            scenarios={},
            sensitivity=[],
            confidence={},
            verdict="neutral",
            inputs_echo={},
            current_price=None,
            price_as_of=None,
            computed_at=datetime(2026, 10, 10, tzinfo=UTC),
        )
    )
    await db_session.flush()


async def test_create_price_alert(client: AsyncClient, db_session: AsyncSession) -> None:
    """Create a price crossing alert."""
    company = await _make_company(db_session, "ALERTCO")
    await _add_price(db_session, company, Decimal("50"))

    response = await client.post(
        "/api/alerts",
        json={
            "family": "price",
            "params": {"threshold": 55, "direction": "above"},
            "company_id": str(company.id),
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["family"] == "price"
    assert data["params"]["threshold"] == 55
    assert data["params"]["direction"] == "above"
    assert data["company_id"] == str(company.id)
    assert data["methodology_version"] == "CI-1.0"
    assert data["enabled"] is True


async def test_create_price_alert_missing_threshold(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Create price alert without threshold returns 400."""
    company = await _make_company(db_session, "BADALERT")

    response = await client.post(
        "/api/alerts",
        json={
            "family": "price",
            "params": {"direction": "above"},
            "company_id": str(company.id),
        },
    )
    assert response.status_code == 400
    assert "threshold" in response.json()["detail"]


async def test_create_valuation_gap_alert(client: AsyncClient, db_session: AsyncSession) -> None:
    """Create a valuation gap alert."""
    company = await _make_company(db_session, "VGAPCO")
    await _add_price(db_session, company, Decimal("50"))
    await _add_fair_value(db_session, company, Decimal("100"))

    response = await client.post(
        "/api/alerts",
        json={
            "family": "valuation_gap",
            "params": {"gap_pct": 30},
            "company_id": str(company.id),
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["family"] == "valuation_gap"
    assert data["params"]["gap_pct"] == 30


async def test_create_document_alert(client: AsyncClient, db_session: AsyncSession) -> None:
    """Create a document toggle alert."""
    company = await _make_company(db_session, "DOCALERT")

    response = await client.post(
        "/api/alerts",
        json={
            "family": "document",
            "params": {},
            "company_id": str(company.id),
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["family"] == "document"


async def test_create_score_change_alert(client: AsyncClient, db_session: AsyncSession) -> None:
    """Create a score change alert."""
    company = await _make_company(db_session, "SCOREALERT")

    response = await client.post(
        "/api/alerts",
        json={
            "family": "score_change",
            "params": {"threshold_pct": 10},
            "company_id": str(company.id),
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["family"] == "score_change"
    assert data["params"]["threshold_pct"] == 10


async def test_create_alert_invalid_family(client: AsyncClient, db_session: AsyncSession) -> None:
    """Create alert with invalid family returns 400."""
    company = await _make_company(db_session, "BADFAM")

    response = await client.post(
        "/api/alerts",
        json={
            "family": "invalid_family",
            "params": {},
            "company_id": str(company.id),
        },
    )
    assert response.status_code == 400


async def test_create_alert_company_not_found(client: AsyncClient) -> None:
    """Create alert for non-existent company returns 404."""
    missing = uuid.uuid4()
    response = await client.post(
        "/api/alerts",
        json={
            "family": "price",
            "params": {"threshold": 50},
            "company_id": str(missing),
        },
    )
    assert response.status_code == 404


async def test_list_alerts(client: AsyncClient, db_session: AsyncSession) -> None:
    """List alerts with filters."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    company = await _make_company(db_session, "LISTALERT")

    rule1 = AlertRule(
        id=uuid.uuid4(),
        user_id=user_id,
        company_id=company.id,
        family=AlertFamily.PRICE,
        params={"threshold": 50},
        methodology_version="CI-1.0",
    )
    rule2 = AlertRule(
        id=uuid.uuid4(),
        user_id=user_id,
        company_id=company.id,
        family=AlertFamily.VALUATION_GAP,
        params={"gap_pct": 20},
        methodology_version="CI-1.0",
    )
    db_session.add_all([rule1, rule2])
    await db_session.flush()

    response = await client.get("/api/alerts")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Filter by family
    response = await client.get("/api/alerts?family=price")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["family"] == "price"


async def test_get_alert(client: AsyncClient, db_session: AsyncSession) -> None:
    """Get alert by ID."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    company = await _make_company(db_session, "GETALERT")
    rule = AlertRule(
        id=uuid.uuid4(),
        user_id=user_id,
        company_id=company.id,
        family=AlertFamily.PRICE,
        params={"threshold": 50},
        methodology_version="CI-1.0",
    )
    db_session.add(rule)
    await db_session.flush()

    response = await client.get(f"/api/alerts/{rule.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(rule.id)
    assert data["family"] == "price"


async def test_update_alert(client: AsyncClient, db_session: AsyncSession) -> None:
    """Update alert rule."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    company = await _make_company(db_session, "UPDALERT")
    rule = AlertRule(
        id=uuid.uuid4(),
        user_id=user_id,
        company_id=company.id,
        family=AlertFamily.PRICE,
        params={"threshold": 50},
        methodology_version="CI-1.0",
    )
    db_session.add(rule)
    await db_session.flush()

    response = await client.patch(
        f"/api/alerts/{rule.id}",
        json={"params": {"threshold": 60, "direction": "below"}, "enabled": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["params"]["threshold"] == 60
    assert data["params"]["direction"] == "below"
    assert data["enabled"] is False

    # Verify rule.changed event logged
    result = await db_session.execute(select(Event).where(Event.type == EventType.RULE_CHANGED))
    events = result.scalars().all()
    assert len(events) == 1


async def test_delete_alert(client: AsyncClient, db_session: AsyncSession) -> None:
    """Delete alert rule."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    company = await _make_company(db_session, "DELALERT")
    rule = AlertRule(
        id=uuid.uuid4(),
        user_id=user_id,
        company_id=company.id,
        family=AlertFamily.PRICE,
        params={"threshold": 50},
        methodology_version="CI-1.0",
    )
    db_session.add(rule)
    await db_session.flush()

    response = await client.delete(f"/api/alerts/{rule.id}")
    assert response.status_code == 204

    result = await db_session.execute(select(AlertRule).where(AlertRule.id == rule.id))
    assert result.scalars().first() is None


async def test_list_fired_alerts(client: AsyncClient, db_session: AsyncSession) -> None:
    """List fired alerts."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    company = await _make_company(db_session, "FIREDALERT")
    rule = AlertRule(
        id=uuid.uuid4(),
        user_id=user_id,
        company_id=company.id,
        family=AlertFamily.PRICE,
        params={"threshold": 50},
        methodology_version="CI-1.0",
    )
    db_session.add(rule)
    await db_session.flush()

    fired1 = AlertFired(
        id=uuid.uuid4(),
        rule_id=rule.id,
        company_id=company.id,
        inputs_snapshot={"threshold": 50, "current_close": "55"},
    )
    fired2 = AlertFired(
        id=uuid.uuid4(),
        rule_id=rule.id,
        company_id=company.id,
        inputs_snapshot={"threshold": 50, "current_close": "60"},
        acked_at=datetime.now(UTC),
    )
    db_session.add_all([fired1, fired2])
    await db_session.flush()

    response = await client.get("/api/alerts/fired")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Filter by acked
    response = await client.get("/api/alerts/fired?acked=false")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["acked_at"] is None


async def test_ack_fired_alert(client: AsyncClient, db_session: AsyncSession) -> None:
    """Acknowledge fired alert."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    company = await _make_company(db_session, "ACKALERT")
    rule = AlertRule(
        id=uuid.uuid4(),
        user_id=user_id,
        company_id=company.id,
        family=AlertFamily.PRICE,
        params={"threshold": 50},
        methodology_version="CI-1.0",
    )
    db_session.add(rule)
    await db_session.flush()

    fired = AlertFired(
        id=uuid.uuid4(),
        rule_id=rule.id,
        company_id=company.id,
        inputs_snapshot={"threshold": 50},
    )
    db_session.add(fired)
    await db_session.flush()

    response = await client.post(f"/api/alerts/{fired.id}/ack")
    assert response.status_code == 200
    data = response.json()
    assert data["acked_at"] is not None

    # Verify alert.acked event logged
    result = await db_session.execute(select(Event).where(Event.type == EventType.ALERT_ACKED))
    events = result.scalars().all()
    assert len(events) == 1
