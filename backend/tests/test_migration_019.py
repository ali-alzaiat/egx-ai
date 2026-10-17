"""Test migration 019 up/down round-trip and data integrity."""

import asyncio
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

pytestmark = pytest.mark.asyncio

_STATEMENT_TABLES = ("financial_statement_lines", "financial_document_blobs")

_DOCUMENT_COLUMNS = ("source_kind", "fetched_at", "content_hash")


def _alembic_config() -> Config:
    return Config("alembic.ini")


async def _table_exists(table: str) -> bool:
    from app.db.session import engine

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT to_regclass('public.' || :t)"), {"t": table})
        return result.scalar_one() is not None


class TestMigration019:
    """Migration 019 round-trip: new tables, enum types, document columns."""

    async def test_tables_exist_at_head(self) -> None:
        for table in _STATEMENT_TABLES:
            assert await _table_exists(table), table

    async def test_up_down_round_trip(self) -> None:
        cfg = _alembic_config()
        try:
            await asyncio.to_thread(command.downgrade, cfg, "018")
            for table in _STATEMENT_TABLES:
                assert not await _table_exists(table), table
            await asyncio.to_thread(command.upgrade, cfg, "head")
            for table in _STATEMENT_TABLES:
                assert await _table_exists(table), table
        finally:
            await asyncio.to_thread(command.upgrade, cfg, "head")

    async def test_financial_documents_gains_fetch_columns(self) -> None:
        from app.db.session import engine

        async with engine.connect() as conn:
            for column in _DOCUMENT_COLUMNS:
                result = await conn.execute(
                    text(
                        "SELECT 1 FROM information_schema.columns "
                        "WHERE table_name = 'financial_documents' AND column_name = :c"
                    ),
                    {"c": column},
                )
                assert result.scalar_one_or_none() is not None, column

    async def test_enum_types_created(self) -> None:
        from app.db.session import engine

        async with engine.connect() as conn:
            for enum_type in ("extraction_method", "ext_status"):
                result = await conn.execute(
                    text("SELECT 1 FROM pg_type WHERE typname = :t"), {"t": enum_type}
                )
                assert result.scalar_one_or_none() is not None, enum_type

    async def test_unique_constraints_exist(self) -> None:
        from app.db.session import engine

        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT constraint_name FROM information_schema.table_constraints "
                    "WHERE constraint_type = 'UNIQUE' AND constraint_name IN "
                    "('uq_stmt_line', 'uq_statement_blob_hash')"
                )
            )
            names = {row[0] for row in result}
        assert "uq_stmt_line" in names
        assert "uq_statement_blob_hash" in names

    async def test_write_after_round_trip(self) -> None:
        """A company row survives the cycle; recreated 019 tables accept writes."""
        from app.db.session import engine

        cfg = _alembic_config()
        company_id = uuid.uuid4()
        ticker = f"RT9{uuid.uuid4().hex[:6].upper()}"
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO companies (id, ticker, isin, name, currency, status) "
                        "VALUES (:id, :ticker, :isin, :name, 'EGP', 'ACTIVE')"
                    ),
                    {"id": company_id, "ticker": ticker, "isin": ticker, "name": f"{ticker} Co"},
                )
            await asyncio.to_thread(command.downgrade, cfg, "018")
            await asyncio.to_thread(command.upgrade, cfg, "head")
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO financial_periods (id, company_id, period_type, fiscal_year, "
                        "fiscal_quarter, start_date, end_date) "
                        "VALUES (:pid, :company_id, 'ANNUAL', 2024, NULL, "
                        "'2024-01-01', '2024-12-31')"
                    ),
                    {"pid": uuid.uuid4(), "company_id": company_id},
                )
                line_id = uuid.uuid4()
                await conn.execute(
                    text(
                        "INSERT INTO financial_statement_lines "
                        "(id, period_id, company_id, ontology_code, ontology_version, value, "
                        " currency, extraction_method, ext_status) "
                        "SELECT :id, p.id, :company_id, 'net_income', 'stmt-ontology-1.0', "
                        "       12345.67, 'EGP', 'manual_seed', 'approved' "
                        "FROM financial_periods p WHERE p.company_id = :company_id LIMIT 1"
                    ),
                    {"id": line_id, "company_id": company_id},
                )
                row = (
                    await conn.execute(
                        text("SELECT ontology_code FROM financial_statement_lines WHERE id = :id"),
                        {"id": line_id},
                    )
                ).scalar_one_or_none()
                assert row == "net_income"
        finally:
            await asyncio.to_thread(command.upgrade, cfg, "head")
