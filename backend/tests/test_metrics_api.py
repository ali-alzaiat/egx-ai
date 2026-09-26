"""Tests for metrics API endpoints."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import FinancialDocument, FinancialFact, FinancialPeriod
from app.models.market import Company


@pytest.fixture
async def sample_company(db_session: AsyncSession) -> Company:
    """Create a sample company for testing."""
    unique_ticker = f"T{uuid.uuid4().hex[:8].upper()}"
    company = Company(
        id=uuid.uuid4(),
        ticker=unique_ticker,
        name="Test Company",
        isin=f"EG{uuid.uuid4().hex[:10].upper()}",
        sector="Test",
        industry="Test",
        currency="EGP",
        status="ACTIVE",
    )
    db_session.add(company)
    await db_session.commit()
    return company


@pytest.fixture
async def sample_period(db_session: AsyncSession, sample_company: Company) -> FinancialPeriod:
    """Create a sample financial period."""
    period = FinancialPeriod(
        id=uuid.uuid4(),
        company_id=sample_company.id,
        period_type="ANNUAL",
        fiscal_year=2024,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    db_session.add(period)
    await db_session.commit()
    return period


@pytest.fixture
async def sample_document(
    db_session: AsyncSession,
    sample_period: FinancialPeriod,
) -> FinancialDocument:
    """Create a sample financial document."""
    import uuid as uuid_mod

    from app.models.market import DataSource

    source_name = f"Test Source {uuid_mod.uuid4().hex[:8]}"
    source = DataSource(
        id=uuid.uuid4(),
        name=source_name,
        source_type="SYNTHETIC",
    )
    db_session.add(source)
    await db_session.flush()

    doc = FinancialDocument(
        id=uuid.uuid4(),
        period_id=sample_period.id,
        source_id=source.id,
        document_type="ANNUAL_REPORT",
        document_status="ORIGINAL",
    )
    db_session.add(doc)
    await db_session.commit()
    return doc


@pytest.fixture
async def sample_facts(
    db_session: AsyncSession,
    sample_period: FinancialPeriod,
    sample_document: FinancialDocument,
    sample_company: Company,
) -> list[FinancialFact]:
    """Create sample financial facts for testing."""
    facts = [
        FinancialFact(
            id=uuid.uuid4(),
            period_id=sample_period.id,
            document_id=sample_document.id,
            company_id=sample_company.id,
            fact_type="INCOME_STATEMENT",
            reported_label="revenue",
            normalized_label="revenue",
            reported_value=Decimal("1000000"),
            normalized_value=Decimal("1000000"),
            currency="EGP",
        ),
        FinancialFact(
            id=uuid.uuid4(),
            period_id=sample_period.id,
            document_id=sample_document.id,
            company_id=sample_company.id,
            fact_type="INCOME_STATEMENT",
            reported_label="net_income",
            normalized_label="net_income",
            reported_value=Decimal("100000"),
            normalized_value=Decimal("100000"),
            currency="EGP",
        ),
        FinancialFact(
            id=uuid.uuid4(),
            period_id=sample_period.id,
            document_id=sample_document.id,
            company_id=sample_company.id,
            fact_type="BALANCE_SHEET",
            reported_label="total_assets",
            normalized_label="total_assets",
            reported_value=Decimal("2000000"),
            normalized_value=Decimal("2000000"),
            currency="EGP",
        ),
    ]
    for fact in facts:
        db_session.add(fact)
    await db_session.commit()
    return facts


class TestMetricsAPI:
    async def test_list_company_metrics_empty(
        self, client: AsyncClient, sample_company: Company
    ):
        """Test listing metrics for a company with no metrics."""
        response = await client.get(f"/api/metrics/companies/{sample_company.id}")
        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_list_company_metrics_not_found(self, client: AsyncClient):
        """Test listing metrics for a non-existent company."""
        fake_id = uuid.uuid4()
        response = await client.get(f"/api/metrics/companies/{fake_id}")
        assert response.status_code == 404

    async def test_list_period_metrics_empty(
        self,
        client: AsyncClient,
        sample_company: Company,
        sample_period: FinancialPeriod,
    ):
        """Test listing metrics for a period with no metrics."""
        response = await client.get(
            f"/api/metrics/companies/{sample_company.id}/periods/{sample_period.id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data == []

    async def test_get_specific_metric_not_found(
        self,
        client: AsyncClient,
        sample_company: Company,
        sample_period: FinancialPeriod,
    ):
        """Test getting a specific metric that doesn't exist."""
        response = await client.get(
            f"/api/metrics/companies/{sample_company.id}/periods/{sample_period.id}/roe"
        )
        assert response.status_code == 404

    async def test_calculate_metrics_for_company(
        self,
        client: AsyncClient,
        sample_company: Company,
        sample_period: FinancialPeriod,
        sample_facts: list[FinancialFact],
    ):
        """Test calculating metrics for a company."""
        response = await client.post(
            f"/api/metrics/companies/{sample_company.id}/calculate"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["company_id"] == str(sample_company.id)
        assert data["periods_calculated"] >= 1
        assert data["metrics_persisted"] >= 1

    async def test_calculate_metrics_for_period(
        self,
        client: AsyncClient,
        sample_company: Company,
        sample_period: FinancialPeriod,
        sample_facts: list[FinancialFact],
    ):
        """Test calculating metrics for a specific period."""
        response = await client.post(
            f"/api/metrics/companies/{sample_company.id}/periods/{sample_period.id}/calculate"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["company_id"] == str(sample_company.id)
        assert data["period_id"] == str(sample_period.id)
        assert data["metrics_persisted"] >= 1

    async def test_calculate_and_retrieve_metrics(
        self,
        client: AsyncClient,
        sample_company: Company,
        sample_period: FinancialPeriod,
        sample_facts: list[FinancialFact],
    ):
        """Test calculating metrics then retrieving them."""
        # Calculate
        calc_response = await client.post(
            f"/api/metrics/companies/{sample_company.id}/calculate"
        )
        assert calc_response.status_code == 200

        # Retrieve
        list_response = await client.get(
            f"/api/metrics/companies/{sample_company.id}"
        )
        assert list_response.status_code == 200
        metrics = list_response.json()
        assert len(metrics) > 0

        # Check metric structure
        metric = metrics[0]
        assert "id" in metric
        assert "metric_code" in metric
        assert "display_name" in metric
        assert "status" in metric
        assert "formula_version" in metric
