"""Shared fixtures. Tests run against their own database, never the dev one.

The test database URL is ``TEST_DATABASE_URL`` when set, else the configured
``DATABASE_URL`` with ``_test`` appended to the database name. It is pointed
at *before* anything imports the engine, then created (if missing) and
migrated to head once per session.
"""

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.engine import make_url

from app.core.config import settings


def _test_database_url() -> str:
    dev = make_url(settings.DATABASE_URL)
    explicit = os.environ.get("TEST_DATABASE_URL")
    url = make_url(explicit) if explicit else dev.set(database=f"{dev.database}_test")
    if url.database == dev.database:
        raise RuntimeError("refusing to run tests against the dev database")
    return url.render_as_string(hide_password=False)


TEST_DATABASE_URL = _test_database_url()
# Both the app engine (via settings) and alembic's env.py (via the env var) read this.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
settings.DATABASE_URL = TEST_DATABASE_URL
# Each async test runs on its own event loop; pooled connections are loop-bound.
settings.DATABASE_NULLPOOL = True

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine, get_session
from app.main import app
from app.models.financial import FinancialDocument, FinancialFact, FinancialPeriod
from app.models.market import Company, CompanyStatus, DataSource


async def _create_database_if_missing(url: str) -> None:
    import asyncpg

    target = make_url(url)
    admin = target.set(drivername="postgresql", database="postgres")
    conn = await asyncpg.connect(admin.render_as_string(hide_password=False))
    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", target.database
        )
        if not exists:
            await conn.execute(f'CREATE DATABASE "{target.database}"')
    finally:
        await conn.close()


def pytest_sessionstart(session: pytest.Session) -> None:
    """Create the test database if needed and migrate it to head."""
    import alembic.command
    import alembic.config

    asyncio.run(_create_database_if_missing(TEST_DATABASE_URL))
    cfg = alembic.config.Config(str(Path(__file__).parent.parent / "alembic.ini"))
    alembic.command.upgrade(cfg, "head")


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session that is fully rolled back after the test.

    Services under test call ``session.commit()`` internally, which would
    normally persist their writes. Binding the session to an externally managed
    transaction means those commits only release an inner savepoint, so rolling
    back the outer transaction discards every row the test created.
    """
    connection = await engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def test_company(db_session: AsyncSession) -> AsyncGenerator[Company, None]:
    """Create a test company for AI and integration tests."""
    ticker = f"TEST_{uuid.uuid4().hex[:8].upper()}"
    company = Company(
        id=uuid.uuid4(),
        ticker=ticker,
        isin=f"EG{uuid.uuid4().hex[:10].upper()}",
        name="Test Company",
        name_ar=None,
        sector="Technology",
        industry="Software",
        currency="EGP",
        shares_outstanding=1000000,
        free_float=500000,
        listing_date=None,
        status=CompanyStatus.ACTIVE,
    )
    db_session.add(company)
    await db_session.flush()
    yield company


TEST_API_TOKEN = "test-token-" + "x" * 32


@pytest.fixture(autouse=True)
def _clear_stance_cache() -> None:
    """Cached stances must never leak between tests (they roll back their rows)."""
    from app.signals import stance_cache

    stance_cache.clear()


@pytest.fixture(autouse=True)
def api_token(monkeypatch: pytest.MonkeyPatch) -> str:
    """Configure a known API token for every test (the real one is env-only)."""
    monkeypatch.setattr(settings, "API_TOKEN", TEST_API_TOKEN)
    return TEST_API_TOKEN


@pytest_asyncio.fixture
async def anon_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Async test client with the session override and no credentials."""

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(anon_client: AsyncClient, api_token: str) -> AsyncClient:
    """Authenticated async test client (bearer API token)."""
    anon_client.headers["Authorization"] = f"Bearer {api_token}"
    return anon_client


@pytest_asyncio.fixture
async def zero_value_facts(
    db_session: AsyncSession, test_company: Company
) -> list[FinancialFact]:
    """Facts whose normalized value is a legitimate 0 but whose reported value is not.

    Every value fallback (`normalized_value or reported_value`) must keep the 0
    instead of silently falling back to the reported value (ruling R5).
    """
    period = FinancialPeriod(
        id=uuid.uuid4(),
        company_id=test_company.id,
        period_type="ANNUAL",
        fiscal_year=2024,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    db_session.add(period)
    await db_session.flush()

    source = DataSource(
        id=uuid.uuid4(),
        name=f"Zero Value Source {uuid.uuid4().hex[:8]}",
        source_type="SYNTHETIC",
    )
    db_session.add(source)
    await db_session.flush()

    document = FinancialDocument(
        id=uuid.uuid4(),
        period_id=period.id,
        source_id=source.id,
        document_type="ANNUAL_REPORT",
        document_status="ORIGINAL",
    )
    db_session.add(document)
    await db_session.flush()

    facts = [
        FinancialFact(
            id=uuid.uuid4(),
            period_id=period.id,
            document_id=document.id,
            company_id=test_company.id,
            fact_type="BALANCE_SHEET",
            reported_label="total_debt",
            normalized_label="total_debt",
            reported_value=Decimal("999"),
            normalized_value=Decimal("0"),
            currency="EGP",
        ),
        FinancialFact(
            id=uuid.uuid4(),
            period_id=period.id,
            document_id=document.id,
            company_id=test_company.id,
            fact_type="BALANCE_SHEET",
            reported_label="total_assets",
            normalized_label="total_assets",
            reported_value=Decimal("100"),
            normalized_value=Decimal("100"),
            currency="EGP",
        ),
    ]
    for fact in facts:
        db_session.add(fact)
    await db_session.flush()
    return facts
