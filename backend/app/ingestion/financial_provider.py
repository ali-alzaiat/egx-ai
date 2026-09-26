from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import NamedTuple


class FinancialPeriodData(NamedTuple):
    """Represents a reporting period from a financial data provider."""
    ticker: str
    period_type: str
    fiscal_year: int
    fiscal_quarter: int | None
    start_date: date
    end_date: date


class FinancialDocumentData(NamedTuple):
    """Represents a source document from a financial data provider."""
    ticker: str
    period_type: str
    fiscal_year: int
    document_type: str
    document_status: str
    filing_date: date | None
    publication_date: date | None
    fiscal_year_end: date | None
    notes: str | None


class FinancialFactData(NamedTuple):
    """Represents an individual financial fact from a source document."""
    ticker: str
    period_type: str
    fiscal_year: int
    fact_type: str
    reported_label: str
    reported_value: Decimal | None
    currency: str
    unit: str | None
    scale: int | None
    source_page: str | None
    source_line: str | None
    reported_at: date | None


class FinancialDataProvider(ABC):
    """Protocol for financial data providers.

    Implementations fetch financial statement data from external sources
    (FRA, company IR pages, financial data providers, etc.).
    This is separate from MarketDataProvider which handles market prices.
    """

    @abstractmethod
    async def get_financial_periods(
        self,
        ticker: str,
    ) -> list[FinancialPeriodData]:
        """Fetch all available reporting periods for a company."""
        ...

    @abstractmethod
    async def get_financial_documents(
        self,
        ticker: str,
        fiscal_year: int | None = None,
    ) -> list[FinancialDocumentData]:
        """Fetch source documents for a company, optionally filtered by fiscal year."""
        ...

    @abstractmethod
    async def get_financial_facts(
        self,
        ticker: str,
        fiscal_year: int | None = None,
    ) -> list[FinancialFactData]:
        """Fetch individual financial facts from source documents."""
        ...
