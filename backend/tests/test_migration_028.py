"""Migration 028 (R50 index_prices and data_crosschecks) up/down round-trip."""

import asyncio

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


async def _tables() -> set[str]:
    from app.db.session import engine

    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_name IN ('index_prices', 'data_crosschecks')"
            )
        )
        return {row[0] for row in result}


async def test_up_down_round_trip() -> None:
    cfg = Config("alembic.ini")
    try:
        assert await _tables() == {"index_prices", "data_crosschecks"}
        await asyncio.to_thread(command.downgrade, cfg, "027")
        assert await _tables() == set()
        await asyncio.to_thread(command.upgrade, cfg, "head")
        assert await _tables() == {"index_prices", "data_crosschecks"}
    finally:
        await asyncio.to_thread(command.upgrade, cfg, "head")
