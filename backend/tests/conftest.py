from collections.abc import AsyncGenerator
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory, get_session
from app.main import app
from app.models.market import Company, CompanyStatus


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean database session for direct repository tests."""
    async with async_session_factory() as session:
        yield session
        await session.rollback()


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
