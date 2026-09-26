import pytest
from decimal import Decimal
from app.ingestion.normalization import NormalizationService, normalize_financial_facts
from app.ingestion.validation import FinancialFactValidator, validate_financial_facts, ValidationSeverity
from app.models.financial import FactStatus, FactType, FinancialFact
import uuid
from datetime import datetime, timezone


class TestNormalizationService:
    def setup_method(self):
        self.service = NormalizationService()

    def test_normalize_revenue(self):
        fact = FinancialFact(
            id=uuid.uuid4(),
            period_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            fact_type=FactType.INCOME_STATEMENT,
            reported_label="Total Revenue",
            normalized_label=None,
            reported_value=Decimal("50000000000"),
            normalized_value=None,
            currency="EGP",
            unit=None,
            scale=None,
            status=FactStatus.REPORTED,
            source_page="15",
            source_line=None,
            reported_at=datetime.now(timezone.utc),
            normalized_at=None,
            created_at=datetime.now(timezone.utc),
        )

        result = self.service.normalize_fact(fact)
        assert result.normalized_label == "revenue"
        assert result.normalized_value == Decimal("50000000000")
        assert result.status == FactStatus.NORMALIZED

    def test_normalize_with_scale(self):
        fact = FinancialFact(
            id=uuid.uuid4(),
            period_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            fact_type=FactType.INCOME_STATEMENT,
            reported_label="Total Revenue",
            normalized_label=None,
            reported_value=Decimal("50"),
            normalized_value=None,
            currency="EGP",
            unit="millions",
            scale=1000000,
            status=FactStatus.REPORTED,
            source_page="15",
            source_line=None,
            reported_at=datetime.now(timezone.utc),
            normalized_at=None,
            created_at=datetime.now(timezone.utc),
        )

        result = self.service.normalize_fact(fact)
        assert result.normalized_label == "revenue"
        assert result.normalized_value == Decimal("50000000")

    def test_normalize_unknown_label(self):
        fact = FinancialFact(
            id=uuid.uuid4(),
            period_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            fact_type=FactType.INCOME_STATEMENT,
            reported_label="Some Unknown Label",
            normalized_label=None,
            reported_value=Decimal("1000"),
            normalized_value=None,
            currency="EGP",
            unit=None,
            scale=None,
            status=FactStatus.REPORTED,
            source_page="10",
            source_line=None,
            reported_at=datetime.now(timezone.utc),
            normalized_at=None,
            created_at=datetime.now(timezone.utc),
        )

        result = self.service.normalize_fact(fact)
        assert result.normalized_label == "Some Unknown Label"
        assert result.normalized_value == Decimal("1000")
        assert result.status == FactStatus.REPORTED

    def test_normalize_facts_batch(self):
        facts = [
            FinancialFact(
                id=uuid.uuid4(),
                period_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                company_id=uuid.uuid4(),
                fact_type=FactType.INCOME_STATEMENT,
                reported_label="Total Revenue",
                normalized_label=None,
                reported_value=Decimal("50000000000"),
                normalized_value=None,
                currency="EGP",
                unit=None,
                scale=None,
                status=FactStatus.REPORTED,
                source_page="15",
                source_line=None,
                reported_at=datetime.now(timezone.utc),
                normalized_at=None,
                created_at=datetime.now(timezone.utc),
            ),
            FinancialFact(
                id=uuid.uuid4(),
                period_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                company_id=uuid.uuid4(),
                fact_type=FactType.BALANCE_SHEET,
                reported_label="Total Assets",
                normalized_label=None,
                reported_value=Decimal("500000000000"),
                normalized_value=None,
                currency="EGP",
                unit=None,
                scale=None,
                status=FactStatus.REPORTED,
                source_page="45",
                source_line=None,
                reported_at=datetime.now(timezone.utc),
                normalized_at=None,
                created_at=datetime.now(timezone.utc),
            ),
        ]

        results = normalize_financial_facts(facts)
        assert len(results) == 2
        assert results[0].normalized_label == "revenue"
        assert results[1].normalized_label == "total_assets"


class TestFinancialFactValidator:
    def setup_method(self):
        self.validator = FinancialFactValidator()

    def test_valid_fact(self):
        fact = FinancialFact(
            id=uuid.uuid4(),
            period_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            fact_type=FactType.INCOME_STATEMENT,
            reported_label="Total Revenue",
            normalized_label=None,
            reported_value=Decimal("50000000000"),
            normalized_value=None,
            currency="EGP",
            unit=None,
            scale=None,
            status=FactStatus.REPORTED,
            source_page="15",
            source_line=None,
            reported_at=datetime.now(timezone.utc),
            normalized_at=None,
            created_at=datetime.now(timezone.utc),
        )

        result = self.validator.validate(fact)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_missing_reported_label(self):
        fact = FinancialFact(
            id=uuid.uuid4(),
            period_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            fact_type=FactType.INCOME_STATEMENT,
            reported_label="",
            normalized_label=None,
            reported_value=Decimal("50000000000"),
            normalized_value=None,
            currency="EGP",
            unit=None,
            scale=None,
            status=FactStatus.REPORTED,
            source_page="15",
            source_line=None,
            reported_at=datetime.now(timezone.utc),
            normalized_at=None,
            created_at=datetime.now(timezone.utc),
        )

        result = self.validator.validate(fact)
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0].severity == ValidationSeverity.ERROR
        assert result.errors[0].field == "reported_label"

    def test_missing_reported_value_warning(self):
        fact = FinancialFact(
            id=uuid.uuid4(),
            period_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            fact_type=FactType.INCOME_STATEMENT,
            reported_label="Total Revenue",
            normalized_label=None,
            reported_value=None,
            normalized_value=None,
            currency="EGP",
            unit=None,
            scale=None,
            status=FactStatus.REPORTED,
            source_page="15",
            source_line=None,
            reported_at=datetime.now(timezone.utc),
            normalized_at=None,
            created_at=datetime.now(timezone.utc),
        )

        result = self.validator.validate(fact)
        assert result.is_valid  # Warnings don't make it invalid
        assert len(result.warnings) == 1
        assert result.warnings[0].severity == ValidationSeverity.WARNING

    def test_negative_revenue_warning(self):
        fact = FinancialFact(
            id=uuid.uuid4(),
            period_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            fact_type=FactType.INCOME_STATEMENT,
            reported_label="Total Revenue",
            normalized_label=None,
            reported_value=Decimal("-1000000"),
            normalized_value=None,
            currency="EGP",
            unit=None,
            scale=None,
            status=FactStatus.REPORTED,
            source_page="15",
            source_line=None,
            reported_at=datetime.now(timezone.utc),
            normalized_at=None,
            created_at=datetime.now(timezone.utc),
        )

        result = self.validator.validate(fact)
        assert result.is_valid
        assert len(result.warnings) == 1
        assert "Negative revenue" in result.warnings[0].message

    def test_invalid_currency_error(self):
        fact = FinancialFact(
            id=uuid.uuid4(),
            period_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            fact_type=FactType.INCOME_STATEMENT,
            reported_label="Total Revenue",
            normalized_label=None,
            reported_value=Decimal("50000000000"),
            normalized_value=None,
            currency="EG",
            unit=None,
            scale=None,
            status=FactStatus.REPORTED,
            source_page="15",
            source_line=None,
            reported_at=datetime.now(timezone.utc),
            normalized_at=None,
            created_at=datetime.now(timezone.utc),
        )

        result = self.validator.validate(fact)
        assert not result.is_valid
        assert any(e.field == "currency" for e in result.errors)

    def test_validate_facts_batch(self):
        facts = [
            FinancialFact(
                id=uuid.uuid4(),
                period_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                company_id=uuid.uuid4(),
                fact_type=FactType.INCOME_STATEMENT,
                reported_label="Total Revenue",
                normalized_label=None,
                reported_value=Decimal("50000000000"),
                normalized_value=None,
                currency="EGP",
                unit=None,
                scale=None,
                status=FactStatus.REPORTED,
                source_page="15",
                source_line=None,
                reported_at=datetime.now(timezone.utc),
                normalized_at=None,
                created_at=datetime.now(timezone.utc),
            ),
            FinancialFact(
                id=uuid.uuid4(),
                period_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                company_id=uuid.uuid4(),
                fact_type=FactType.BALANCE_SHEET,
                reported_label="",
                normalized_label=None,
                reported_value=Decimal("500000000000"),
                normalized_value=None,
                currency="EGP",
                unit=None,
                scale=None,
                status=FactStatus.REPORTED,
                source_page="45",
                source_line=None,
                reported_at=datetime.now(timezone.utc),
                normalized_at=None,
                created_at=datetime.now(timezone.utc),
            ),
        ]

        results = validate_financial_facts(facts)
        assert results["summary"]["total"] == 2
        assert results["summary"]["valid"] == 1
        assert results["summary"]["invalid"] == 1
        assert results["summary"]["total_errors"] == 1


class TestFakeFinancialProvider:
    @pytest.mark.asyncio
    async def test_get_periods(self):
        from app.ingestion.fake_financial_provider import FakeFinancialDataProvider
        provider = FakeFinancialDataProvider()
        periods = await provider.get_financial_periods("COMI")
        assert len(periods) == 5
        assert periods[0].period_type == "ANNUAL"
        assert periods[0].fiscal_year == 2022

    @pytest.mark.asyncio
    async def test_get_documents(self):
        from app.ingestion.fake_financial_provider import FakeFinancialDataProvider
        provider = FakeFinancialDataProvider()
        documents = await provider.get_financial_documents("COMI")
        assert len(documents) == 5
        assert documents[0].document_type == "ANNUAL_REPORT"
        assert documents[0].document_status == "ORIGINAL"

    @pytest.mark.asyncio
    async def test_get_facts(self):
        from app.ingestion.fake_financial_provider import FakeFinancialDataProvider
        provider = FakeFinancialDataProvider()
        facts = await provider.get_financial_facts("COMI")
        assert len(facts) > 0
        assert facts[0].currency == "EGP"
        assert facts[0].reported_value is not None

    @pytest.mark.asyncio
    async def test_get_facts_filtered_by_year(self):
        from app.ingestion.fake_financial_provider import FakeFinancialDataProvider
        provider = FakeFinancialDataProvider()
        facts = await provider.get_financial_facts("COMI", fiscal_year=2023)
        for fact in facts:
            assert fact.fiscal_year == 2023
