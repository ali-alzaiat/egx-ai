from app.models.financial import (
    DocumentStatus,
    FactStatus,
    FactType,
    ReportingPeriodType,
)
from app.schemas.financial import (
    FinancialDocumentCreate,
    FinancialFactCreate,
    FinancialPeriodCreate,
)


class TestFinancialPeriod:
    def test_create_period(self):
        period = FinancialPeriodCreate(
            company_id="123e4567-e89b-12d3-a456-426614174000",
            period_type=ReportingPeriodType.ANNUAL,
            fiscal_year=2023,
            fiscal_quarter=None,
            start_date="2023-01-01",
            end_date="2023-12-31",
        )
        assert period.period_type == ReportingPeriodType.ANNUAL
        assert period.fiscal_year == 2023
        assert period.fiscal_quarter is None

    def test_create_quarterly_period(self):
        period = FinancialPeriodCreate(
            company_id="123e4567-e89b-12d3-a456-426614174000",
            period_type=ReportingPeriodType.Q1,
            fiscal_year=2023,
            fiscal_quarter=1,
            start_date="2023-01-01",
            end_date="2023-03-31",
        )
        assert period.period_type == ReportingPeriodType.Q1
        assert period.fiscal_quarter == 1


class TestFinancialDocument:
    def test_create_document(self):
        doc = FinancialDocumentCreate(
            period_id="123e4567-e89b-12d3-a456-426614174000",
            source_id="123e4567-e89b-12d3-a456-426614174001",
            document_status=DocumentStatus.ORIGINAL,
            document_type="ANNUAL_REPORT",
            filing_date="2024-03-31",
            publication_date="2024-04-15",
        )
        assert doc.document_status == DocumentStatus.ORIGINAL
        assert doc.document_type == "ANNUAL_REPORT"

    def test_create_restated_document(self):
        doc = FinancialDocumentCreate(
            period_id="123e4567-e89b-12d3-a456-426614174000",
            source_id="123e4567-e89b-12d3-a456-426614174001",
            document_status=DocumentStatus.RESTATED,
            document_type="ANNUAL_REPORT",
            filing_date="2024-06-30",
            publication_date="2024-07-15",
        )
        assert doc.document_status == DocumentStatus.RESTATED


class TestFinancialFact:
    def test_create_fact(self):
        from decimal import Decimal
        fact = FinancialFactCreate(
            period_id="123e4567-e89b-12d3-a456-426614174000",
            document_id="123e4567-e89b-12d3-a456-426614174002",
            company_id="123e4567-e89b-12d3-a456-426614174000",
            fact_type=FactType.INCOME_STATEMENT,
            reported_label="Total Revenue",
            reported_value=Decimal("50000000000"),
            currency="EGP",
            status=FactStatus.REPORTED,
        )
        assert fact.fact_type == FactType.INCOME_STATEMENT
        assert fact.reported_label == "Total Revenue"
        assert fact.reported_value == Decimal("50000000000")
        assert fact.currency == "EGP"
        assert fact.status == FactStatus.REPORTED

    def test_create_fact_with_normalization(self):
        from decimal import Decimal
        fact = FinancialFactCreate(
            period_id="123e4567-e89b-12d3-a456-426614174000",
            document_id="123e4567-e89b-12d3-a456-426614174002",
            company_id="123e4567-e89b-12d3-a456-426614174000",
            fact_type=FactType.INCOME_STATEMENT,
            reported_label="Total Revenue",
            normalized_label="revenue",
            reported_value=Decimal("50000000000"),
            normalized_value=Decimal("50000000000"),
            currency="EGP",
            status=FactStatus.NORMALIZED,
        )
        assert fact.normalized_label == "revenue"
        assert fact.normalized_value == Decimal("50000000000")
        assert fact.status == FactStatus.NORMALIZED


class TestFactTypeEnum:
    def test_fact_types(self):
        assert FactType.INCOME_STATEMENT == "INCOME_STATEMENT"
        assert FactType.BALANCE_SHEET == "BALANCE_SHEET"
        assert FactType.CASH_FLOW == "CASH_FLOW"
        assert FactType.SHAREHOLDERS_EQUITY == "SHAREHOLDERS_EQUITY"
        assert FactType.NOTES == "NOTES"


class TestReportingPeriodType:
    def test_period_types(self):
        assert ReportingPeriodType.ANNUAL == "ANNUAL"
        assert ReportingPeriodType.Q1 == "Q1"
        assert ReportingPeriodType.Q2 == "Q2"
        assert ReportingPeriodType.Q3 == "Q3"
        assert ReportingPeriodType.Q4 == "Q4"
        assert ReportingPeriodType.SEMI_ANNUAL == "SEMI_ANNUAL"
        assert ReportingPeriodType.INTERIM == "INTERIM"


class TestDocumentStatus:
    def test_document_statuses(self):
        assert DocumentStatus.ORIGINAL == "ORIGINAL"
        assert DocumentStatus.RESTATED == "RESTATED"
        assert DocumentStatus.AMENDED == "AMENDED"
        assert DocumentStatus.ADJUSTED == "ADJUSTED"


class TestFactStatus:
    def test_fact_statuses(self):
        assert FactStatus.REPORTED == "REPORTED"
        assert FactStatus.NORMALIZED == "NORMALIZED"
        assert FactStatus.CALCULATED == "CALCULATED"
        assert FactStatus.INSUFFICIENT_DATA == "INSUFFICIENT_DATA"
