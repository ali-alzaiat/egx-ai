"""Synthetic financial data provider for development and testing.

Clearly labeled as SYNTHETIC — do not use for real financial data.
"""

import hashlib
from datetime import date
from decimal import Decimal

from app.ingestion.financial_provider import (
    FinancialDataProvider,
    FinancialDocumentData,
    FinancialFactData,
    FinancialPeriodData,
)


class FakeFinancialDataProvider(FinancialDataProvider):
    """Synthetic financial data provider for development and testing.

    Generates deterministic pseudo-random financial data based on ticker.
    Clearly labeled as SYNTHETIC — do not use for real financial data.
    """

    # Standard financial fact templates for each company type
    FINANCIAL_TEMPLATES = {
        "Financials": {
            "INCOME_STATEMENT": [
                ("Total Revenue", Decimal("50000000000"), "EGP", None, None, "15"),
                ("Cost of Revenue", Decimal("25000000000"), "EGP", None, None, "16"),
                ("Gross Profit", Decimal("25000000000"), "EGP", None, None, "17"),
                ("Operating Expenses", Decimal("15000000000"), "EGP", None, None, "18"),
                ("Operating Income", Decimal("10000000000"), "EGP", None, None, "19"),
                ("Net Income", Decimal("7500000000"), "EGP", None, None, "20"),
                ("Basic EPS", Decimal("2.50"), "EGP", "per share", None, "21"),
            ],
            "BALANCE_SHEET": [
                ("Total Assets", Decimal("500000000000"), "EGP", None, None, "45"),
                ("Total Liabilities", Decimal("450000000000"), "EGP", None, None, "46"),
                ("Total Equity", Decimal("50000000000"), "EGP", None, None, "47"),
                ("Cash and Cash Equivalents", Decimal("100000000000"), "EGP", None, None, "48"),
                ("Current Assets", Decimal("150000000000"), "EGP", None, None, "49"),
                ("Current Liabilities", Decimal("120000000000"), "EGP", None, None, "50"),
            ],
            "CASH_FLOW": [
                ("Operating Cash Flow", Decimal("12000000000"), "EGP", None, None, "65"),
                ("Capital Expenditures", Decimal("2000000000"), "EGP", None, None, "66"),
                ("Free Cash Flow", Decimal("10000000000"), "EGP", None, None, "67"),
                ("Dividends Paid", Decimal("3000000000"), "EGP", None, None, "68"),
            ],
        },
        "Consumer Staples": {
            "INCOME_STATEMENT": [
                ("Total Revenue", Decimal("20000000000"), "EGP", None, None, "15"),
                ("Cost of Revenue", Decimal("12000000000"), "EGP", None, None, "16"),
                ("Gross Profit", Decimal("8000000000"), "EGP", None, None, "17"),
                ("Operating Expenses", Decimal("4000000000"), "EGP", None, None, "18"),
                ("Operating Income", Decimal("4000000000"), "EGP", None, None, "19"),
                ("Net Income", Decimal("3000000000"), "EGP", None, None, "20"),
                ("Basic EPS", Decimal("1.50"), "EGP", "per share", None, "21"),
            ],
            "BALANCE_SHEET": [
                ("Total Assets", Decimal("100000000000"), "EGP", None, None, "45"),
                ("Total Liabilities", Decimal("60000000000"), "EGP", None, None, "46"),
                ("Total Equity", Decimal("40000000000"), "EGP", None, None, "47"),
                ("Cash and Cash Equivalents", Decimal("15000000000"), "EGP", None, None, "48"),
                ("Current Assets", Decimal("30000000000"), "EGP", None, None, "49"),
                ("Current Liabilities", Decimal("20000000000"), "EGP", None, None, "50"),
            ],
            "CASH_FLOW": [
                ("Operating Cash Flow", Decimal("5000000000"), "EGP", None, None, "65"),
                ("Capital Expenditures", Decimal("1000000000"), "EGP", None, None, "66"),
                ("Free Cash Flow", Decimal("4000000000"), "EGP", None, None, "67"),
                ("Dividends Paid", Decimal("1500000000"), "EGP", None, None, "68"),
            ],
        },
        "Industrials": {
            "INCOME_STATEMENT": [
                ("Total Revenue", Decimal("15000000000"), "EGP", None, None, "15"),
                ("Cost of Revenue", Decimal("10000000000"), "EGP", None, None, "16"),
                ("Gross Profit", Decimal("5000000000"), "EGP", None, None, "17"),
                ("Operating Expenses", Decimal("3000000000"), "EGP", None, None, "18"),
                ("Operating Income", Decimal("2000000000"), "EGP", None, None, "19"),
                ("Net Income", Decimal("1500000000"), "EGP", None, None, "20"),
                ("Basic EPS", Decimal("1.00"), "EGP", "per share", None, "21"),
            ],
            "BALANCE_SHEET": [
                ("Total Assets", Decimal("80000000000"), "EGP", None, None, "45"),
                ("Total Liabilities", Decimal("50000000000"), "EGP", None, None, "46"),
                ("Total Equity", Decimal("30000000000"), "EGP", None, None, "47"),
                ("Cash and Cash Equivalents", Decimal("8000000000"), "EGP", None, None, "48"),
                ("Current Assets", Decimal("20000000000"), "EGP", None, None, "49"),
                ("Current Liabilities", Decimal("15000000000"), "EGP", None, None, "50"),
            ],
            "CASH_FLOW": [
                ("Operating Cash Flow", Decimal("3000000000"), "EGP", None, None, "65"),
                ("Capital Expenditures", Decimal("800000000"), "EGP", None, None, "66"),
                ("Free Cash Flow", Decimal("2200000000"), "EGP", None, None, "67"),
                ("Dividends Paid", Decimal("800000000"), "EGP", None, None, "68"),
            ],
        },
    }

    def _get_sector_template(self, sector: str) -> dict:
        """Get the financial template for a sector."""
        return self.FINANCIAL_TEMPLATES.get(sector, self.FINANCIAL_TEMPLATES["Industrials"])

    def _generate_variation(self, ticker: str, year: int, base_value: Decimal) -> Decimal:
        """Generate deterministic variation based on ticker and year."""
        seed = int(hashlib.md5(f"{ticker}{year}".encode()).hexdigest()[:8], 16)
        variation = Decimal(str((seed % 200 - 100) / 1000))  # -10% to +10%
        return (base_value * (1 + variation)).quantize(Decimal("0.01"))

    async def get_financial_periods(
        self,
        ticker: str,
    ) -> list[FinancialPeriodData]:
        """Generate synthetic financial periods for a company."""
        periods = []
        current_year = date.today().year

        # Generate 5 years of annual periods
        for year in range(current_year - 4, current_year + 1):
            periods.append(
                FinancialPeriodData(
                    ticker=ticker,
                    period_type="ANNUAL",
                    fiscal_year=year,
                    fiscal_quarter=None,
                    start_date=date(year, 1, 1),
                    end_date=date(year, 12, 31),
                )
            )

        return periods

    async def get_financial_documents(
        self,
        ticker: str,
        fiscal_year: int | None = None,
    ) -> list[FinancialDocumentData]:
        """Generate synthetic financial documents for a company."""
        documents = []
        current_year = date.today().year
        years = [fiscal_year] if fiscal_year else range(current_year - 4, current_year + 1)

        for year in years:
            documents.append(
                FinancialDocumentData(
                    ticker=ticker,
                    period_type="ANNUAL",
                    fiscal_year=year,
                    document_type="ANNUAL_REPORT",
                    document_status="ORIGINAL",
                    filing_date=date(year + 1, 3, 31),  # Filed next year
                    publication_date=date(year + 1, 4, 15),  # Published after filing
                    fiscal_year_end=date(year, 12, 31),
                    notes=f"Synthetic annual report for {year}",
                )
            )

        return documents

    async def get_financial_facts(
        self,
        ticker: str,
        fiscal_year: int | None = None,
    ) -> list[FinancialFactData]:
        """Generate synthetic financial facts for a company."""
        facts = []
        current_year = date.today().year
        years = [fiscal_year] if fiscal_year else range(current_year - 4, current_year + 1)

        # Determine sector from ticker (simplified mapping)
        sector = self._guess_sector(ticker)
        template = self._get_sector_template(sector)

        for year in years:
            for fact_type, items in template.items():
                for label, base_value, currency, unit, scale, page in items:
                    # Generate deterministic variation
                    varied_value = self._generate_variation(ticker, year, base_value)

                    facts.append(
                        FinancialFactData(
                            ticker=ticker,
                            period_type="ANNUAL",
                            fiscal_year=year,
                            fact_type=fact_type,
                            reported_label=label,
                            reported_value=varied_value,
                            currency=currency,
                            unit=unit,
                            scale=scale,
                            source_page=page,
                            source_line=None,
                            reported_at=date(year + 1, 3, 31),
                            document_type="ANNUAL_REPORT",
                        )
                    )

        return facts

    def _guess_sector(self, ticker: str) -> str:
        """Simple heuristic to guess sector from ticker."""
        ticker_upper = ticker.upper()

        # Financial tickers
        if ticker_upper in ("COMI", "HRHO", "EFIH", "PHAR"):
            return "Financials"

        # Consumer Staples
        if ticker_upper in ("EAST", "JUFO"):
            return "Consumer Staples"

        # Industrials
        if ticker_upper in ("SWDY", "OLED"):
            return "Industrials"

        # Default
        return "Industrials"
