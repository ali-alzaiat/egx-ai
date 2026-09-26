import uuid
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine, get_session
from app.main import app
from app.models.market import Company, CompanyStatus


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


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with overridden session dependency."""

    async def _override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
