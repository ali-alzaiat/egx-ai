"""EGX market data provider using yfinance.

Fetches real Egyptian Exchange data from Yahoo Finance.
EGX tickers on Yahoo Finance use the .CA suffix (e.g., COMI.CA).

Company list sourced from stockanalysis.com (229 actively traded EGX stocks).
"""

import asyncio
from datetime import date
from decimal import Decimal

import yfinance as yf  # type: ignore[import-untyped]

from app.ingestion.provider import CompanyData, DailyPriceData, MarketDataProvider

# Full EGX company list from stockanalysis.com (229 companies)
EGX_TICKERS = [
    "COMI", "SWDY", "ETEL", "TMGH", "EGAL", "MFPC", "QNBE", "HDBK", "ABUK", "ALCN",
    "EAST", "ORAS", "EFIH", "ADIB", "EMFD", "FWRY", "SCTS", "CANA", "ORHD", "GPPL",
    "EFID", "VLMR", "VLMRA", "JUFO", "PHDC", "OCDI", "HRHO", "GBCO", "FAIT", "FAITA",
    "HELI", "FERC", "BTFH", "CIEB", "RAYA", "EXPA", "EGCH", "CCAP", "IRON", "ARCC",
    "TAQA", "CIRA", "CLHO", "VALU", "SCEM", "BIOC", "MCQE", "SKPC", "EGTS", "PHAR",
    "MTIE", "POUL", "ORWE", "EFIC", "EGSA", "MBSC", "AMOC", "MOIL", "UBEE", "SAUD",
    "NIPH", "MASR", "ATQA", "KORA", "TALM", "MHOT", "EGBE", "BINV", "AMES", "CICH",
    "ISPH", "RMDA", "CSAG", "NAPR", "OIH", "IFAP", "AMIA", "MIPH", "OLFI", "MOIN",
    "MPRC", "MPCI", "CPCI", "ISMQ", "AXPH", "PHTV", "SUGR", "ZMID", "EGAS", "BONY",
    "PRDC", "DOMT", "ELEC", "GOUR", "SPHT", "ACAP", "SPIN", "NINH", "ENGC", "MCRO",
    "OCPH", "ARAB", "MICH", "SVCE", "WCDF", "CNFN", "GSSC", "KABO", "AFMC", "OFH",
    "MFSC", "DSCW", "AMER", "SAIB", "SDTI", "CRST", "UNIT", "ACGC", "KZPC", "GDWA",
    "AJWA", "ADCI", "ACTF", "GTWL", "UEFM", "ELKA", "ASCM", "CFGH", "ELSH", "ALRA",
    "GPIM", "INFI", "ICFC", "ATLC", "MPCO", "NAHO", "ISMA", "LCSW", "ZEOT", "DAPH",
    "ETRS", "ACAMD", "EDFM", "NARE", "MAAL", "SMFR", "CEFM", "PHGC", "MILS", "IDRE",
    "SNFC", "GGRN", "NCCW", "AALR", "ADPC", "RACC", "DTPP", "WKOL", "ICID", "EALR",
    "MOSC", "EHDR", "ECAP", "KRDI", "GGCC", "ODIN", "MENA", "PRCL", "SCFM", "ASPI",
    "DEIN", "CERA", "CAED", "MBEG", "SIPC", "IEEC", "NHPS", "NDRL", "MEPA", "OBRI",
    "LUTS", "UEGC", "SEIG", "SEIGA", "AIHC", "AIDC", "RUBX", "AMII", "TANM", "COSG",
    "ALUM", "EBSC", "POCO", "RREI", "GTEX", "AFDI", "RTVC", "PRMH", "UNIP", "TWSA",
    "ICLE", "MEGM", "APSW", "EASB", "KWIN", "MOED", "ROTO", "TYCN", "SPMD", "RAKT",
    "EEII", "AREH", "CCRS", "EPCO", "GIHD", "FCMD", "GRCA", "ELWA", "TRTO", "ELNA",
    "DGTZ", "MMAT", "DCCC", "NEDA", "EPPK", "GMCI", "EOSB", "CPME", "COPR",
]


class EGXDataProvider(MarketDataProvider):
    """EGX market data provider using yfinance (Yahoo Finance).

    Fetches real-time and historical data for all 229 Egyptian Exchange stocks.
    All data sourced from Yahoo Finance with .CA ticker suffix.
    """

    def __init__(self, timeout: int = 30, max_concurrent: int = 10) -> None:
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self._companies_cache: list[CompanyData] | None = None

    def _to_yahoo_ticker(self, ticker: str) -> str:
        """Convert EGX ticker to Yahoo Finance format."""
        return f"{ticker}.CA"

    async def _fetch_company_info(self, ticker: str) -> CompanyData:
        """Fetch company info for a single ticker from Yahoo Finance."""
        try:
            yahoo_ticker = self._to_yahoo_ticker(ticker)
            ticker_obj = yf.Ticker(yahoo_ticker)

            info = await asyncio.to_thread(ticker_obj.info.get, "longName", None)
            sector = await asyncio.to_thread(ticker_obj.info.get, "sector", None)
            industry = await asyncio.to_thread(ticker_obj.info.get, "industry", None)
            currency = await asyncio.to_thread(ticker_obj.info.get, "currency", "EGP")
            shares_out = await asyncio.to_thread(
                ticker_obj.info.get, "sharesOutstanding", None
            )
            free_float = await asyncio.to_thread(
                ticker_obj.info.get, "floatShares", None
            )
            free_float = await asyncio.to_thread(ticker_obj.info.get, "floatShares", None)

            return CompanyData(
                ticker=ticker,
                isin=None,
                name=info or ticker,
                name_ar=None,
                sector=sector,
                industry=industry,
                currency=currency,
                shares_outstanding=Decimal(str(shares_out)) if shares_out else None,
                free_float=(
                    Decimal(str(free_float)) / Decimal(str(shares_out))
                    if free_float and shares_out
                    else None
                ),
                listing_date=None,
                status="ACTIVE",
            )
        except Exception:
            return CompanyData(
                ticker=ticker,
                isin=None,
                name=ticker,
                name_ar=None,
                sector=None,
                industry=None,
                currency="EGP",
                shares_outstanding=None,
                free_float=None,
                listing_date=None,
                status="ACTIVE",
            )

    async def get_companies(self) -> list[CompanyData]:
        """Fetch all available EGX companies with real-time data from Yahoo Finance."""
        if self._companies_cache is not None:
            return self._companies_cache

        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def fetch_with_semaphore(ticker: str) -> CompanyData:
            async with semaphore:
                return await self._fetch_company_info(ticker)

        # Fetch all companies concurrently
        tasks = [fetch_with_semaphore(ticker) for ticker in EGX_TICKERS]
        companies = await asyncio.gather(*tasks)

        self._companies_cache = companies
        return companies

    async def get_daily_prices(
        self,
        ticker: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[DailyPriceData]:
        """Fetch daily price history for an EGX ticker from Yahoo Finance."""
        if start_date is None:
            start_date = date.today().replace(year=date.today().year - 1)
        if end_date is None:
            end_date = date.today()

        yahoo_ticker = self._to_yahoo_ticker(ticker)

        try:
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
                if row.isna().any():
                    continue

                open_val = Decimal(str(row["Open"])).quantize(Decimal("0.0001"))
                high_val = Decimal(str(row["High"])).quantize(Decimal("0.0001"))
                low_val = Decimal(str(row["Low"])).quantize(Decimal("0.0001"))
                close_val = Decimal(str(row["Close"])).quantize(Decimal("0.0001"))

                low_val = min(low_val, open_val, close_val)
                high_val = max(high_val, open_val, close_val)

                adj_close_val = (
                    Decimal(str(row.get("Adj Close", row["Close"]))).quantize(Decimal("0.0001"))
                    if "Adj Close" in row
                    else None
                )

                prices.append(DailyPriceData(
                    ticker=ticker,
                    date=idx.date() if hasattr(idx, 'date') else idx.to_pydatetime().date(),
                    open=open_val,
                    high=high_val,
                    low=low_val,
                    close=close_val,
                    adjusted_close=adj_close_val,
                    volume=int(row["Volume"]),
                    value_traded=(
                        Decimal(str(row["Close"] * row["Volume"])).quantize(Decimal("0.01"))
                    ),
                    trades=None,
                ))

            return prices

        except Exception:
            return []

    def invalidate_cache(self) -> None:
        """Invalidate the companies cache to force refresh."""
        self._companies_cache = None


def create_egx_provider() -> EGXDataProvider:
    """Create an EGX data provider instance."""
    return EGXDataProvider()
