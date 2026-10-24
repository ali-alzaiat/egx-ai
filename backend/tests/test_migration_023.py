"""Migration 023 (R43) up/down round-trip."""

import asyncio

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

pytestmark = pytest.mark.asyncio

_TABLES = ("company_compute_state", "valuation_assumptions")


async def _table_exists(table: str) -> bool:
    from app.db.session import engine

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT to_regclass('public.' || :t)"), {"t": table})
        return result.scalar_one() is not None


async def _column_exists(table: str, column: str) -> bool:
    from app.db.session import engine

    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": table, "c": column},
        )
        return result.scalar_one_or_none() is not None


async def test_tables_and_columns_at_head() -> None:
    for table in _TABLES:
        assert await _table_exists(table), table
    assert await _column_exists("financial_metric_inputs", "statement_line_id")
    assert await _column_exists("financial_metrics", "provisional")


async def test_up_down_round_trip() -> None:
    cfg = Config("alembic.ini")
    try:
        await asyncio.to_thread(command.downgrade, cfg, "022")
        for table in _TABLES:
            assert not await _table_exists(table), table
        assert not await _column_exists("financial_metric_inputs", "statement_line_id")
        await asyncio.to_thread(command.upgrade, cfg, "head")
        for table in _TABLES:
            assert await _table_exists(table), table
    finally:
        await asyncio.to_thread(command.upgrade, cfg, "head")
