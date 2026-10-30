"""Migration 025 (R47 S1: companies.sector_match_basis) up/down round-trip."""

import asyncio

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

pytestmark = pytest.mark.asyncio


async def _column_exists(column: str) -> bool:
    from app.db.session import engine

    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'companies' AND column_name = :c"
            ),
            {"c": column},
        )
        return result.scalar_one_or_none() is not None


async def test_column_exists_at_head() -> None:
    assert await _column_exists("sector_match_basis")


async def test_up_down_round_trip() -> None:
    cfg = Config("alembic.ini")
    try:
        await asyncio.to_thread(command.downgrade, cfg, "024")
        assert not await _column_exists("sector_match_basis")
        await asyncio.to_thread(command.upgrade, cfg, "head")
        assert await _column_exists("sector_match_basis")
    finally:
        await asyncio.to_thread(command.upgrade, cfg, "head")
