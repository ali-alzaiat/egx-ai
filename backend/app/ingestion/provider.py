from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import NamedTuple


class CompanyData(NamedTuple):
    ticker: str
    isin: str | None
    name: str
    name_ar: str | None
    sector: str | None
    industry: str | None
    currency: str
    shares_outstanding: Decimal | None
    free_float: Decimal | None
    listing_date: date | None
    status: str


class DailyPriceData(NamedTuple):
    ticker: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    adjusted_close: Decimal | None
    volume: int
    value_traded: Decimal | None
    trades: int | None


class MarketDataProvider(ABC):
    """Protocol for market data providers.

    Implementations fetch data from external sources (EGX, FRA, etc.)
    and return normalized data. The domain layer depends on this interface,
    not on specific provider implementations.
    """

    @abstractmethod
    async def get_companies(self) -> list[CompanyData]:
        """Fetch all available companies from the provider."""
        ...

    @abstractmethod
    async def get_daily_prices(
        self,
        ticker: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[DailyPriceData]:
        """Fetch daily price history for a specific ticker."""
        ...
