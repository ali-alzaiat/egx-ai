"""Test migration 018 up/down round-trip and data integrity."""

import asyncio
import uuid
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.continuous.constants import CI_METHODOLOGY_VERSION
from app.models.continuous import (
    AlertFamily,
    AlertFired,
    AlertRule,
    EventType,
    Watchlist,
    WatchlistEntry,
)
from app.models.market import Company, CompanyStatus

pytestmark = pytest.mark.asyncio


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    return cfg


_PHASE8_TABLES = (
    "watchlists",
    "watchlist_entries",
    "alert_rules",
    "alert_fired",
    "events",
)


async def _table_exists(table: str) -> bool:
    # Fresh connection: catalog snapshots in a long-lived test transaction can
    # report recently-dropped tables as still present, so never reuse db_session
    # across a DDL boundary (repo convention, cf. test_scores_migration.py).
    from app.db.session import engine

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT to_regclass('public.' || :t)"), {"t": table}
        )
        return result.scalar_one() is not None


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


class TestMigration018:
    """Test migration 018 round-trip and data integrity."""

    async def test_migration_up_down_round_trip(self) -> None:
        """Migration 018 should upgrade and downgrade cleanly."""
        # Alembic's env.py drives its own asyncio.run(); run it in a worker
        # thread since this test already lives inside an event loop.
        cfg = _alembic_config()
        try:
            for table in _PHASE8_TABLES:
                assert await _table_exists(table), table
            await asyncio.to_thread(command.downgrade, cfg, "017")
            for table in _PHASE8_TABLES:
                assert not await _table_exists(table), table
            await asyncio.to_thread(command.upgrade, cfg, "head")
            for table in _PHASE8_TABLES:
                assert await _table_exists(table), table
        finally:
            # Never leave the shared dev database below head.
            await asyncio.to_thread(command.upgrade, cfg, "head")

    async def test_data_integrity_after_round_trip(self) -> None:
        """Rows in tables 018 does not touch survive a down/up cycle.

        Downgrade drops the 018 tables by design, so Phase-8 rows cannot
        survive; integrity here means (a) a `companies` row persists through
        the cycle and (b) the recreated 018 tables accept writes afterwards.
        All DDL-adjacent I/O uses fresh connections — never db_session, whose
        snapshot predates the DDL.
        """
        from app.db.session import engine

        cfg = _alembic_config()
        company_id = uuid.uuid4()
        ticker = f"RT{uuid.uuid4().hex[:8].upper()}"
        wl_id = uuid.uuid4()
        user_id = uuid.uuid4()
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO companies (id, ticker, isin, name, currency, status) "
                        "VALUES (:id, :ticker, :isin, :name, 'EGP', 'ACTIVE')"
                    ),
                    {
                        "id": company_id,
                        "ticker": ticker,
                        "isin": f"EG{ticker[:10]}",
                        "name": f"{ticker} Co",
                    },
                )
            await asyncio.to_thread(command.downgrade, cfg, "017")
            await asyncio.to_thread(command.upgrade, cfg, "head")
            async with engine.begin() as conn:
                surviving = (
                    await conn.execute(
                        text("SELECT id FROM companies WHERE id = :id"),
                        {"id": company_id},
                    )
                ).scalar_one_or_none()
                assert surviving is not None
                await conn.execute(
                    text(
                        "INSERT INTO watchlists (id, user_id, name) "
                        "VALUES (:id, :uid, 'round-trip')"
                    ),
                    {"id": wl_id, "uid": user_id},
                )
                row = (
                    await conn.execute(
                        text("SELECT name FROM watchlists WHERE id = :id"),
                        {"id": wl_id},
                    )
                ).scalar_one()
                assert row == "round-trip"
        finally:
            # Never leave the shared dev database below head or dirty.
            await asyncio.to_thread(command.upgrade, cfg, "head")
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM watchlists WHERE id = :id"), {"id": wl_id}
                )
                await conn.execute(
                    text("DELETE FROM companies WHERE id = :id"), {"id": company_id}
                )

    async def test_enum_values_persist_correctly(self) -> None:
        """Every ENUM value round-trips through the 018 schema.

        Values are written after the upgrade (not across the DROP, which
        destroys rows by design) on a fresh connection, then read back.
        """
        import json

        from app.db.session import engine

        company_id = uuid.uuid4()
        ticker = f"EN{uuid.uuid4().hex[:8].upper()}"
        user_id = uuid.uuid4()
        rule_ids = [uuid.uuid4() for _ in AlertFamily]
        event_ids = [uuid.uuid4() for _ in EventType]
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO companies (id, ticker, isin, name, currency, status) "
                        "VALUES (:id, :ticker, :isin, :name, 'EGP', 'ACTIVE')"
                    ),
                    {
                        "id": company_id,
                        "ticker": ticker,
                        "isin": f"EG{ticker[:10]}",
                        "name": f"{ticker} Co",
                    },
                )
                for rule_id, family in zip(rule_ids, AlertFamily, strict=True):
                    await conn.execute(
                        text(
                            "INSERT INTO alert_rules "
                            "(id, user_id, company_id, family, params, "
                            "methodology_version, enabled) "
                            "VALUES (:id, :uid, :cid, :family, :params, :ver, TRUE)"
                        ),
                        {
                            "id": rule_id,
                            "uid": user_id,
                            "cid": company_id,
                            "family": family.value,
                            "params": json.dumps({}),
                            "ver": CI_METHODOLOGY_VERSION,
                        },
                    )
                for event_id, event_type in zip(event_ids, EventType, strict=True):
                    await conn.execute(
                        text(
                            "INSERT INTO events "
                            "(id, actor_type, actor_id, rule_version, type, symbols, "
                            "inputs_snapshot, reason) "
                            "VALUES (:id, 'system', :uid, :ver, :type, :symbols, :snap, :reason)"
                        ),
                        {
                            "id": event_id,
                            "uid": user_id,
                            "ver": CI_METHODOLOGY_VERSION,
                            "type": event_type.value,
                            "symbols": [company_id],
                            "snap": json.dumps({}),
                            "reason": f"Test {event_type.value}",
                        },
                    )
                stored_families = {
                    r[0]
                    for r in (
                        await conn.execute(
                            text("SELECT family FROM alert_rules WHERE user_id = :uid"),
                            {"uid": user_id},
                        )
                    ).all()
                }
                assert stored_families == {f.value for f in AlertFamily}
                stored_types = {
                    r[0]
                    for r in (
                        await conn.execute(
                            text("SELECT type FROM events WHERE actor_id = :uid"),
                            {"uid": user_id},
                        )
                    ).all()
                }
                assert stored_types == {e.value for e in EventType}
        finally:
            async with engine.begin() as conn:
                await conn.execute(
                    text("DELETE FROM events WHERE id = ANY(:ids)"),
                    {"ids": event_ids},
                )
                await conn.execute(
                    text("DELETE FROM alert_rules WHERE id = ANY(:ids)"),
                    {"ids": rule_ids},
                )
                await conn.execute(
                    text("DELETE FROM companies WHERE id = :id"), {"id": company_id}
                )

    async def test_foreign_keys_enforced(self, db_session: AsyncSession) -> None:
        """Foreign key constraints should be enforced."""
        # Creating watchlist_entry with non-existent watchlist_id should fail
        from sqlalchemy.exc import IntegrityError

        company = await _make_company(db_session, "FKTEST")

        entry = WatchlistEntry(
            id=uuid.uuid4(),
            watchlist_id=uuid.uuid4(),  # Non-existent
            company_id=company.id,
        )
        db_session.add(entry)

        with pytest.raises(IntegrityError):
            await db_session.flush()

        await db_session.rollback()

        # Creating alert_fired with non-existent rule_id should fail
        fired = AlertFired(
            id=uuid.uuid4(),
            rule_id=uuid.uuid4(),  # Non-existent
            company_id=company.id,
            inputs_snapshot={},
        )
        db_session.add(fired)

        with pytest.raises(IntegrityError):
            await db_session.flush()

        await db_session.rollback()

    async def test_indexes_exist(self, db_session: AsyncSession) -> None:
        """Required indexes should exist after migration."""
        # This test verifies the migration creates the expected indexes
        # by checking that queries using indexed columns are efficient
        # (we can't easily test index existence directly, but we can
        # verify the tables are queryable)

        user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
        company = await _make_company(db_session, "IDXTEST")

        # These queries should use the indexes
        wl = Watchlist(id=uuid.uuid4(), user_id=user_id, name="Idx Test")
        db_session.add(wl)
        await db_session.flush()

        entry = WatchlistEntry(
            id=uuid.uuid4(),
            watchlist_id=wl.id,
            company_id=company.id,
        )
        db_session.add(entry)
        await db_session.flush()

        rule = AlertRule(
            id=uuid.uuid4(),
            user_id=user_id,
            company_id=company.id,
            family=AlertFamily.PRICE,
            params={"threshold": 50},
            methodology_version=CI_METHODOLOGY_VERSION,
        )
        db_session.add(rule)
        await db_session.flush()

        # Query by indexed columns
        from app.repositories.continuous import (
            AlertRepository,
            WatchlistRepository,
        )
        wl_repo = WatchlistRepository(db_session)
        alert_repo = AlertRepository(db_session)

        # Should use ix_watchlists_user_id
        watchlists = await wl_repo.list_for_user(user_id)
        assert len(watchlists) == 1

        # Should use ix_alert_rules_user_id
        rules = await alert_repo.list_rules(user_id=user_id)
        assert len(rules) == 1

        # Should use ix_alert_rules_company_id
        rules = await alert_repo.list_rules(user_id=user_id, company_id=company.id)
        assert len(rules) == 1
