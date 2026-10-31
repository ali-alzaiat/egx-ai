"""Migration 026 (R49 assistant tables) up/down round-trip."""

import asyncio

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

pytestmark = pytest.mark.asyncio

TABLES = ("ai_provider_keys", "ai_settings", "ai_conversations", "ai_messages")


async def _tables() -> set[str]:
    from app.db.session import engine

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_name = ANY(:t)"),
            {"t": list(TABLES)},
        )
        return {row[0] for row in result}


async def test_tables_exist_at_head() -> None:
    assert await _tables() == set(TABLES)


async def test_up_down_round_trip() -> None:
    cfg = Config("alembic.ini")
    try:
        await asyncio.to_thread(command.downgrade, cfg, "025")
        assert await _tables() == set()
        await asyncio.to_thread(command.upgrade, cfg, "head")
        assert await _tables() == set(TABLES)
    finally:
        await asyncio.to_thread(command.upgrade, cfg, "head")
