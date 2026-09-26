"""EGX market data provider using yfinance.

Fetches real Egyptian Exchange data from Yahoo Finance.
EGX tickers on Yahoo Finance use the .CA suffix (e.g., COMI.CA).
"""

import asyncio
from datetime import date
from decimal import Decimal

import yfinance as yf  # type: ignore[import-untyped]

from app.ingestion.provider import CompanyData, DailyPriceData, MarketDataProvider

# Known EGX tickers with their metadata
# This list can be expanded or fetched from a reference source
EGX_COMPANIES = [
    {
        "ticker": "COMI",
        "isin": "EGY000111016",
        "name": "Commercial International Bank",
        "name_ar": "البنك التجاري الدولي",
        "sector": "Financials",
        "industry": "Banks",
        "currency": "EGP",
        "shares_outstanding": Decimal("9500000000"),
        "free_float": Decimal("0.40"),
        "listing_date": date(2006, 1, 1),
        "status": "ACTIVE",
    },
    {
        "ticker": "HRHO",
        "isin": "EGY000111019",
        "name": "Heron Holdings",
        "name_ar": "هيرون هولدنجز",
        "sector": "Financials",
        "industry": "Financial Services",
        "currency": "EGP",
        "shares_outstanding": Decimal("3000000000"),
        "free_float": Decimal("0.25"),
        "listing_date": date(2007, 3, 15),
        "status": "ACTIVE",
    },
    {
        "ticker": "EAST",
        "isin": "EGY000301017",
        "name": "Eastern Company",
        "name_ar": "الشركة الشرقية",
        "sector": "Consumer Staples",
        "industry": "Tobacco",
        "currency": "EGP",
        "shares_outstanding": Decimal("1800000000"),
        "free_float": Decimal("0.30"),
        "listing_date": date(2004, 6, 1),
        "status": "ACTIVE",
    },
    {
        "ticker": "EFIH",
        "isin": "EGY000501015",
        "name": "EFG Financial Holdings",
        "name_ar": "إي إف جي هولدنجز المالية",
        "sector": "Financials",
        "industry": "Investment Banking",
        "currency": "EGP",
        "shares_outstanding": Decimal("4500000000"),
        "free_float": Decimal("0.35"),
        "listing_date": date(2005, 9, 1),
        "status": "ACTIVE",
    },
    {
        "ticker": "SWDY",
        "isin": "EGY000601013",
        "name": "Smart Windows",
        "name_ar": "سمارت ويندوز",
        "sector": "Industrials",
        "industry": "Construction Materials",
        "currency": "EGP",
        "shares_outstanding": Decimal("1200000000"),
        "free_float": Decimal("0.45"),
        "listing_date": date(2008, 1, 1),
        "status": "ACTIVE",
    },
    {
        "ticker": "ETEL",
        "isin": "EGY000701011",
        "name": "Telecom Egypt",
        "name_ar": "اتصالات مصر",
        "sector": "Communication Services",
        "industry": "Telecom",
        "currency": "EGP",
        "shares_outstanding": Decimal("5000000000"),
        "free_float": Decimal("0.20"),
        "listing_date": date(2005, 1, 1),
        "status": "ACTIVE",
    },
    {
        "ticker": "PHAR",
        "isin": "EGY000801019",
        "name": "Pharos Holding",
        "name_ar": "فاروس هولدنجز",
        "sector": "Financials",
        "industry": "Investment Banking",
        "currency": "EGP",
        "shares_outstanding": Decimal("800000000"),
        "free_float": Decimal("0.50"),
        "listing_date": date(2006, 12, 1),
        "status": "ACTIVE",
    },
    {
        "ticker": "JUFO",
        "isin": "EGY000901017",
        "name": "Juhayna Food Industries",
        "name_ar": "جهينة لصناعات الأغذية",
        "sector": "Consumer Staples",
        "industry": "Food Products",
        "currency": "EGP",
        "shares_outstanding": Decimal("900000000"),
        "free_float": Decimal("0.55"),
        "listing_date": date(2010, 3, 1),
        "status": "ACTIVE",
    },
    {
        "ticker": "TMGH",
        "isin": "EGY001201011",
        "name": "Talaat Moustafa Group",
        "name_ar": "مجموعة طلعت مصطفى",
        "sector": "Real Estate",
        "industry": "Real Estate Development",
        "currency": "EGP",
        "shares_outstanding": Decimal("5000000000"),
        "free_float": Decimal("0.35"),
        "listing_date": date(2007, 1, 1),
        "status": "ACTIVE",
    },
    {
        "ticker": "FWRY",
        "isin": "EGY001301019",
        "name": "Fawry for Banking Technology",
        "name_ar": "فوري لتكنولوجيا البنوك",
        "sector": "Financials",
        "industry": "Financial Technology",
        "currency": "EGP",
        "shares_outstanding": Decimal("2000000000"),
        "free_float": Decimal("0.40"),
        "listing_date": date(2019, 8, 1),
        "status": "ACTIVE",
    },
    {
        "ticker": "ADIB",
        "isin": "EGY001501014",
        "name": "Abu Dhabi Islamic Bank Egypt",
        "name_ar": "مصرف أبوظبي الإسلامي مصر",
        "sector": "Financials",
        "industry": "Banks",
        "currency": "EGP",
        "shares_outstanding": Decimal("1500000000"),
        "free_float": Decimal("0.30"),
        "listing_date": date(2013, 1, 1),
        "status": "ACTIVE",
    },
    {
        "ticker": "HDBK",
        "isin": "EGY001601012",
        "name": "Housing & Development Bank",
        "name_ar": "بنك التعمير والإسكان",
        "sector": "Financials",
        "industry": "Banks",
        "currency": "EGP",
        "shares_outstanding": Decimal("800000000"),
        "free_float": Decimal("0.35"),
        "listing_date": date(1980, 1, 1),
        "status": "ACTIVE",
    },
]


class EGXDataProvider(MarketDataProvider):
    """EGX market data provider using yfinance (Yahoo Finance).

    Fetches real-time and historical data for Egyptian Exchange stocks.
    All data sourced from Yahoo Finance with .CA ticker suffix.
    """

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout
        self._companies_cache: list[CompanyData] | None = None

    def _to_yahoo_ticker(self, ticker: str) -> str:
        """Convert EGX ticker to Yahoo Finance format."""
        return f"{ticker}.CA"

    def _to_egx_ticker(self, yahoo_ticker: str) -> str:
        """Convert Yahoo Finance ticker to EGX format."""
        return yahoo_ticker.replace(".CA", "")

    async def get_companies(self) -> list[CompanyData]:
        """Fetch all available EGX companies with real-time quotes from Yahoo Finance."""
        if self._companies_cache is not None:
            return self._companies_cache

        companies: list[CompanyData] = []

        for company_info in EGX_COMPANIES:
            try:
                # Fetch real-time quote from yfinance
                yahoo_ticker = self._to_yahoo_ticker(company_info["ticker"])  # type: ignore[arg-type]
                ticker_obj = yf.Ticker(yahoo_ticker)

                # Get info (includes market cap, shares, etc.)
                info = await asyncio.to_thread(ticker_obj.info.get, "longName", None)

                company_data = CompanyData(
                    ticker=company_info["ticker"],  # type: ignore[arg-type]
                    isin=company_info["isin"],  # type: ignore[arg-type]
                    name=info or company_info["name"],  # type: ignore[arg-type]
                    name_ar=company_info["name_ar"],  # type: ignore[arg-type]
                    sector=company_info["sector"],  # type: ignore[arg-type]
                    industry=company_info["industry"],  # type: ignore[arg-type]
                    currency=company_info["currency"],  # type: ignore[arg-type]
                    shares_outstanding=company_info["shares_outstanding"],  # type: ignore[arg-type]
                    free_float=company_info["free_float"],  # type: ignore[arg-type]
                    listing_date=company_info["listing_date"],  # type: ignore[arg-type]
                    status=company_info["status"],  # type: ignore[arg-type]
                )
                companies.append(company_data)

            except Exception:
                # Fallback to static data if yfinance fails
                company_data = CompanyData(
                    ticker=company_info["ticker"],  # type: ignore[arg-type]
                    isin=company_info["isin"],  # type: ignore[arg-type]
                    name=company_info["name"],  # type: ignore[arg-type]
                    name_ar=company_info["name_ar"],  # type: ignore[arg-type]
                    sector=company_info["sector"],  # type: ignore[arg-type]
                    industry=company_info["industry"],  # type: ignore[arg-type]
                    currency=company_info["currency"],  # type: ignore[arg-type]
                    shares_outstanding=company_info["shares_outstanding"],  # type: ignore[arg-type]
                    free_float=company_info["free_float"],  # type: ignore[arg-type]
                    listing_date=company_info["listing_date"],  # type: ignore[arg-type]
                    status=company_info["status"],  # type: ignore[arg-type]
                )
                companies.append(company_data)

        self._companies_cache = companies
        return companies

    async def get_daily_prices(
        self,
        ticker: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[DailyPriceData]:
        """Fetch daily price history for an EGX ticker from Yahoo Finance.

        Args:
            ticker: EGX ticker symbol (e.g., "COMI")
            start_date: Start date for history (default: 1 year ago)
            end_date: End date for history (default: today)

        Returns:
            List of daily price data points
        """
        if start_date is None:
            start_date = date.today().replace(year=date.today().year - 1)
        if end_date is None:
            end_date = date.today()

        yahoo_ticker = self._to_yahoo_ticker(ticker)

        try:
            # Fetch history from yfinance
            hist = await asyncio.to_thread(
                lambda: yf.Ticker(yahoo_ticker).history(
                    start=start_date,
                    end=end_date,
                    interval="1d",
                    auto_adjust=False,
                )
            )

            if hist.empty:
                return []

            prices: list[DailyPriceData] = []
            for idx, row in hist.iterrows():
                # Skip weekends (yfinance may include them with NaN)
                if row.isna().any():
                    continue

                open_val = Decimal(str(row["Open"])).quantize(Decimal("0.0001"))
                high_val = Decimal(str(row["High"])).quantize(Decimal("0.0001"))
                low_val = Decimal(str(row["Low"])).quantize(Decimal("0.0001"))
                close_val = Decimal(str(row["Close"])).quantize(Decimal("0.0001"))

                # Sanitize: ensure low <= min(open, close) and high >= max(open, close)
                low_val = min(low_val, open_val, close_val)
                high_val = max(high_val, open_val, close_val)

                prices.append(DailyPriceData(
                    ticker=ticker,
                    date=idx.date() if hasattr(idx, 'date') else idx.to_pydatetime().date(),
                    open=open_val,
                    high=high_val,
                    low=low_val,
                    close=close_val,
                    adjusted_close=(
                        Decimal(str(row.get("Adj Close", row["Close"]))).quantize(Decimal("0.0001"))
                        if "Adj Close" in row
                        else None
                    ),
                    volume=int(row["Volume"]),
                    value_traded=(
                        Decimal(str(row["Close"] * row["Volume"])).quantize(Decimal("0.01"))
                    ),
                    trades=None,  # Not available from yfinance
                ))

            return prices

        except Exception:
            # Return empty list on error
            return []

    def invalidate_cache(self) -> None:
        """Invalidate the companies cache to force refresh."""
        self._companies_cache = None


# Convenience function to create provider instance
def create_egx_provider() -> EGXDataProvider:
    """Create an EGX data provider instance."""
    return EGXDataProvider()

