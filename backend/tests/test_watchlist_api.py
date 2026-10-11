"""Tests for watchlist API (B1)."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.continuous import Watchlist, WatchlistEntry
from app.models.market import Company, CompanyStatus, DailyPrice, DataSource, DataSourceType
from app.models.scores import InvestmentScore
from app.models.screening import ShariahScreeningResult
from app.models.thesis import InvestmentThesis
from app.thesis.constants import THESIS_METHODOLOGY_VERSION

pytestmark = pytest.mark.asyncio


AS_OF = date(2026, 10, 10)


async def _make_company(db_session: AsyncSession, ticker: str) -> Company:
    company = Company(
        id=uuid.uuid4(),
        ticker=ticker,
        isin=f"EG{uuid.uuid4().hex[:10].upper()}",
        name=f"{ticker} Company",
        currency="EGP",
        status=CompanyStatus.ACTIVE,
        shares_outstanding=Decimal("1000000"),
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
            date=AS_OF,
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1000,
            source_id=source.id,
        )
    )
    await db_session.flush()


async def _add_score(db_session: AsyncSession, company: Company, headline: Decimal) -> None:
    db_session.add(
        InvestmentScore(
            id=uuid.uuid4(),
            company_id=company.id,
            profile_key="default",
            methodology_version="1.0",
            headline=headline,
            headline_status="AVAILABLE",
            components={},
            checks=[],
            confidence={"level": "High"},
            buy_zone={},
            n_with_data=10,
            margin_of_safety=Decimal("0.2"),
            inputs_echo={},
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.flush()


async def _add_shariah(db_session: AsyncSession, company: Company, compliant: bool | None) -> None:
    from app.models.screening import ScreeningStatusDB
    status = (
        ScreeningStatusDB.COMPLIANT
        if compliant is True
        else (
            ScreeningStatusDB.NON_COMPLIANT
            if compliant is False
            else ScreeningStatusDB.INSUFFICIENT_DATA
        )
    )
    db_session.add(
        ShariahScreeningResult(
            id=uuid.uuid4(),
            company_id=company.id,
            methodology_version="1.0",
            methodology_name="Test Methodology",
            is_compliant=compliant,
            status=status,
            rule_results=[],
            overall_reason="Test",
            screened_at=datetime.now(UTC),
            report_date=None,
            report_date_reason=None,
        )
    )
    await db_session.flush()


async def _add_thesis(db_session: AsyncSession, company: Company) -> InvestmentThesis:
    thesis = InvestmentThesis(
        id=uuid.uuid4(),
        company_id=company.id,
        methodology_version=THESIS_METHODOLOGY_VERSION,
        horizon_years=5,
        is_shareholder=None,
        fair_value=None,
        fair_value_status="INSUFFICIENT_DATA",
        assumptions=[],
        bulls=[],
        bears=[],
        scenarios={},
        sensitivity={},
        narrative="",
        confidence={},
        dq={},
        score=None,
        needs_reassessment=False,
        computed_at=datetime.now(UTC),
    )
    db_session.add(thesis)
    await db_session.flush()
    return thesis


async def test_create_watchlist(client: AsyncClient) -> None:
    """Create a watchlist."""
    response = await client.post("/api/watchlists", json={"name": "My Watchlist"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Watchlist"
    assert "id" in data
    assert "user_id" in data


async def test_list_watchlists(client: AsyncClient, db_session: AsyncSession) -> None:
    """List watchlists."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    wl1 = Watchlist(id=uuid.uuid4(), user_id=user_id, name="List 1")
    wl2 = Watchlist(id=uuid.uuid4(), user_id=user_id, name="List 2")
    db_session.add_all([wl1, wl2])
    await db_session.flush()

    response = await client.get("/api/watchlists")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = {w["name"] for w in data}
    assert names == {"List 1", "List 2"}


async def test_get_watchlist(client: AsyncClient, db_session: AsyncSession) -> None:
    """Get a watchlist by ID."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    wl = Watchlist(id=uuid.uuid4(), user_id=user_id, name="Test List")
    db_session.add(wl)
    await db_session.flush()

    response = await client.get(f"/api/watchlists/{wl.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test List"
    assert data["id"] == str(wl.id)


async def test_get_watchlist_not_found(client: AsyncClient) -> None:
    """Get non-existent watchlist returns 404."""
    missing = uuid.uuid4()
    response = await client.get(f"/api/watchlists/{missing}")
    assert response.status_code == 404


async def test_add_entry(client: AsyncClient, db_session: AsyncSession) -> None:
    """Add entry to watchlist."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    wl = Watchlist(id=uuid.uuid4(), user_id=user_id, name="Test")
    db_session.add(wl)
    await db_session.flush()

    company = await _make_company(db_session, "ENTRYCO")
    await _add_price(db_session, company, Decimal("50"))
    await _add_score(db_session, company, Decimal("75"))
    await _add_shariah(db_session, company, True)

    response = await client.post(
        f"/api/watchlists/{wl.id}/entries",
        json={"company_id": str(company.id), "group": "core", "note": "Good company"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["company_id"] == str(company.id)
    assert data["group"] == "core"
    assert data["note"] == "Good company"
    assert data["company_ticker"] == "ENTRYCO"
    # Badges populated
    assert data["price"]["status"] == "AVAILABLE"
    assert data["score"]["status"] == "AVAILABLE"
    assert data["shariah_state"]["status"] == "AVAILABLE"


async def test_add_entry_company_not_found(client: AsyncClient, db_session: AsyncSession) -> None:
    """Add entry with non-existent company returns 404."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    wl = Watchlist(id=uuid.uuid4(), user_id=user_id, name="Test")
    db_session.add(wl)
    await db_session.flush()

    missing = uuid.uuid4()
    response = await client.post(
        f"/api/watchlists/{wl.id}/entries",
        json={"company_id": str(missing)},
    )
    assert response.status_code == 404


async def test_add_entry_watchlist_not_found(client: AsyncClient) -> None:
    """Add entry to non-existent watchlist returns 404."""
    missing = uuid.uuid4()
    company_id = uuid.uuid4()
    response = await client.post(
        f"/api/watchlists/{missing}/entries",
        json={"company_id": str(company_id)},
    )
    assert response.status_code == 404


async def test_list_entries_with_badges(client: AsyncClient, db_session: AsyncSession) -> None:
    """List entries with badges populated or INSUFFICIENT_DATA."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    wl = Watchlist(id=uuid.uuid4(), user_id=user_id, name="Test")
    db_session.add(wl)
    await db_session.flush()

    # Company with full data
    company1 = await _make_company(db_session, "FULLDATA")
    await _add_price(db_session, company1, Decimal("100"))
    await _add_score(db_session, company1, Decimal("80"))
    await _add_shariah(db_session, company1, True)
    await _add_thesis(db_session, company1)

    # Company with no data
    company2 = await _make_company(db_session, "NODATA")

    entry1 = WatchlistEntry(
        id=uuid.uuid4(), watchlist_id=wl.id, company_id=company1.id, group="core"
    )
    entry2 = WatchlistEntry(
        id=uuid.uuid4(), watchlist_id=wl.id, company_id=company2.id, group="watch"
    )
    db_session.add_all([entry1, entry2])
    await db_session.flush()

    response = await client.get(f"/api/watchlists/{wl.id}/entries")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Find entries
    full_entry = next(e for e in data if e["company_ticker"] == "FULLDATA")
    no_entry = next(e for e in data if e["company_ticker"] == "NODATA")

    # Full data entry has AVAILABLE badges
    assert full_entry["price"]["status"] == "AVAILABLE"
    assert full_entry["score"]["status"] == "AVAILABLE"
    assert full_entry["shariah_state"]["status"] == "AVAILABLE"
    assert full_entry["thesis_link_badge"]["status"] == "AVAILABLE"

    # No data entry has INSUFFICIENT_DATA badges
    for badge in [
        "price",
        "change",
        "as_of",
        "staleness",
        "score",
        "shariah_state",
        "thesis_link_badge",
    ]:
        assert no_entry[badge]["status"] == "INSUFFICIENT_DATA"
        assert no_entry[badge]["value"] is None
        assert no_entry[badge]["reason"] is not None


async def test_update_entry(client: AsyncClient, db_session: AsyncSession) -> None:
    """Update watchlist entry."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    wl = Watchlist(id=uuid.uuid4(), user_id=user_id, name="Test")
    db_session.add(wl)
    await db_session.flush()

    company = await _make_company(db_session, "UPDCO")
    entry = WatchlistEntry(id=uuid.uuid4(), watchlist_id=wl.id, company_id=company.id)
    db_session.add(entry)
    await db_session.flush()

    response = await client.patch(
        f"/api/watchlists/{wl.id}/entries/{entry.id}",
        json={"group": "updated", "note": "Updated note"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["group"] == "updated"
    assert data["note"] == "Updated note"


async def test_update_entry_thesis_link(client: AsyncClient, db_session: AsyncSession) -> None:
    """Update entry thesis_link."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    wl = Watchlist(id=uuid.uuid4(), user_id=user_id, name="Test")
    db_session.add(wl)
    await db_session.flush()

    company = await _make_company(db_session, "THESISCO")
    thesis = await _add_thesis(db_session, company)
    entry = WatchlistEntry(id=uuid.uuid4(), watchlist_id=wl.id, company_id=company.id)
    db_session.add(entry)
    await db_session.flush()

    response = await client.patch(
        f"/api/watchlists/{wl.id}/entries/{entry.id}",
        json={"thesis_link": str(thesis.id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["thesis_link"] == str(thesis.id)
    assert data["thesis_link_badge"]["status"] == "AVAILABLE"


async def test_update_entry_invalid_thesis_link(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Update entry with invalid thesis_link returns 404."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    wl = Watchlist(id=uuid.uuid4(), user_id=user_id, name="Test")
    db_session.add(wl)
    await db_session.flush()

    company = await _make_company(db_session, "BADTHESIS")
    entry = WatchlistEntry(id=uuid.uuid4(), watchlist_id=wl.id, company_id=company.id)
    db_session.add(entry)
    await db_session.flush()

    bad_thesis = uuid.uuid4()
    response = await client.patch(
        f"/api/watchlists/{wl.id}/entries/{entry.id}",
        json={"thesis_link": str(bad_thesis)},
    )
    assert response.status_code == 404


async def test_delete_entry(client: AsyncClient, db_session: AsyncSession) -> None:
    """Delete watchlist entry."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    wl = Watchlist(id=uuid.uuid4(), user_id=user_id, name="Test")
    db_session.add(wl)
    await db_session.flush()

    company = await _make_company(db_session, "DELCO")
    entry = WatchlistEntry(id=uuid.uuid4(), watchlist_id=wl.id, company_id=company.id)
    db_session.add(entry)
    await db_session.flush()

    response = await client.delete(f"/api/watchlists/{wl.id}/entries/{entry.id}")
    assert response.status_code == 204

    # Verify deleted
    result = await db_session.execute(select(WatchlistEntry).where(WatchlistEntry.id == entry.id))
    assert result.scalars().first() is None


async def test_delete_entry_logs_event(client: AsyncClient, db_session: AsyncSession) -> None:
    """Delete entry logs watchlist.remove event."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    wl = Watchlist(id=uuid.uuid4(), user_id=user_id, name="Test")
    db_session.add(wl)
    await db_session.flush()

    company = await _make_company(db_session, "DELCO2")
    entry = WatchlistEntry(id=uuid.uuid4(), watchlist_id=wl.id, company_id=company.id)
    db_session.add(entry)
    await db_session.flush()

    await client.delete(f"/api/watchlists/{wl.id}/entries/{entry.id}")

    from app.models.continuous import Event, EventType
    result = await db_session.execute(
        select(Event).where(Event.type == EventType.WATCHLIST_REMOVE)
    )
    events = result.scalars().all()
    assert len(events) == 1
    assert events[0].symbols[0] == company.id


async def test_badge_never_blank(client: AsyncClient, db_session: AsyncSession) -> None:
    """Every badge field is INSUFFICIENT_DATA with reason, never blank."""
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    wl = Watchlist(id=uuid.uuid4(), user_id=user_id, name="Test")
    db_session.add(wl)
    await db_session.flush()

    company = await _make_company(db_session, "BLANKTEST")
    entry = WatchlistEntry(id=uuid.uuid4(), watchlist_id=wl.id, company_id=company.id)
    db_session.add(entry)
    await db_session.flush()

    response = await client.get(f"/api/watchlists/{wl.id}/entries")
    assert response.status_code == 200
    data = response.json()
    entry_data = data[0]

    for badge in [
        "price",
        "change",
        "as_of",
        "staleness",
        "score",
        "shariah_state",
        "thesis_link_badge",
    ]:
        badge_data = entry_data[badge]
        assert badge_data["status"] == "INSUFFICIENT_DATA"
        assert badge_data["value"] is None
        assert badge_data["reason"] is not None
        assert len(badge_data["reason"]) > 0
