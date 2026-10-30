"""Migration 024 (R46 C1: companies.trading_currency) up/down round-trip."""

import asyncio

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

pytestmark = pytest.mark.asyncio

_COLUMNS = ("trading_currency", "trading_currency_checked_at")


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


async def test_columns_exist_at_head() -> None:
    for column in _COLUMNS:
        assert await _column_exists(column), column


async def test_up_down_round_trip() -> None:
    cfg = Config("alembic.ini")
    try:
        await asyncio.to_thread(command.downgrade, cfg, "023")
        for column in _COLUMNS:
            assert not await _column_exists(column), column
        await asyncio.to_thread(command.upgrade, cfg, "head")
        for column in _COLUMNS:
            assert await _column_exists(column), column
    finally:
        await asyncio.to_thread(command.upgrade, cfg, "head")
