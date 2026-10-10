"""Migration 012 round-trip: chain linkage + up/down against the dev database."""

import asyncio
import importlib.util
from pathlib import Path
from types import ModuleType

import alembic.command
import alembic.config
import pytest
from sqlalchemy import text


def _load_migration() -> ModuleType:
    path = Path(__file__).parent.parent / "alembic" / "versions" / "012_industry.py"
    spec = importlib.util.spec_from_file_location("m012_industry", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m012 = _load_migration()


def test_revision_chain() -> None:
    assert m012.revision == "012"
    assert m012.down_revision == "011"


async def _table_exists(table: str) -> bool:
    # Fresh connection: catalog caches in a long-lived test transaction can
    # report recently-dropped tables as still present, so never reuse db_session.
    from app.db.session import engine

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT to_regclass('public.' || :t)"), {"t": table}
        )
        return result.scalar_one() is not None


@pytest.mark.asyncio
async def test_migration_up_down_round_trip() -> None:
    # Alembic's env.py drives its own asyncio.run(); run it in a worker
    # thread since this test already lives inside an event loop.
    cfg = alembic.config.Config(str(Path(__file__).parent.parent / "alembic.ini"))
    try:
        assert await _table_exists( "gics_sectors")

        # Pin the base revision: later migrations (013+) stack on top of 012,
        # so a relative "-1" would only revert the newest one, not 012.
        await asyncio.to_thread(alembic.command.downgrade, cfg, "011")
        assert not await _table_exists( "gics_sectors")
        assert not await _table_exists( "industry_metric_profiles")

        await asyncio.to_thread(alembic.command.upgrade, cfg, "head")
        assert await _table_exists( "gics_sectors")
        assert await _table_exists( "gics_sub_industries")
        assert await _table_exists( "egx_sectors")
        assert await _table_exists( "egx_sector_gics_map")
        assert await _table_exists( "company_peer_overrides")
        assert await _table_exists( "industry_metric_profiles")
    finally:
        # Never leave the shared dev database below head.
        await asyncio.to_thread(alembic.command.upgrade, cfg, "head")
