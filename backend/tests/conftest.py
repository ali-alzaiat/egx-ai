import uuid
from collections.abc import AsyncGenerator
from datetime import date
from decimal import Decimal

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine, get_session
from app.main import app
from app.models.financial import FinancialDocument, FinancialFact, FinancialPeriod
from app.models.market import Company, CompanyStatus, DataSource


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
