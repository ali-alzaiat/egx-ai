"""Migration 027 (R49 A10 free-tier providers) up/down round-trip."""

import asyncio

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


async def _has_column() -> bool:
    from app.db.session import engine

    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'ai_settings' AND column_name = 'free_tier_providers'"
            )
        )
        return result.first() is not None


async def test_up_down_round_trip() -> None:
    cfg = Config("alembic.ini")
    try:
        assert await _has_column()
        await asyncio.to_thread(command.downgrade, cfg, "026")
        assert not await _has_column()
        await asyncio.to_thread(command.upgrade, cfg, "head")
        assert await _has_column()
    finally:
        await asyncio.to_thread(command.upgrade, cfg, "head")
