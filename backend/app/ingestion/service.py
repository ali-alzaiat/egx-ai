import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.provider import CompanyData, DailyPriceData, MarketDataProvider
from app.models.market import DataSourceType
from app.repositories.company import CompanyRepository
from app.repositories.data_source import DataSourceRepository
from app.repositories.price import PriceRepository
from app.schemas.price import DailyPriceCreate

logger = logging.getLogger(__name__)


class MarketDataIngestionService:
    """Orchestrates market data ingestion from a provider into the database.

    Responsibilities:
    1. Receive provider data.
    2. Validate it.
    3. Resolve companies (create if needed).
    4. Normalize fields.
    5. Persist data.
    6. Record source/provenance.
    7. Report failures.
    """

    def __init__(
        self,
        session: AsyncSession,
        provider: MarketDataProvider,
        source_name: str,
        source_type: DataSourceType,
        source_url: str | None = None,
    ) -> None:
        self.session = session
        self.provider = provider
        self.company_repo = CompanyRepository(session)
        self.price_repo = PriceRepository(session)
        self.source_repo = DataSourceRepository(session)
        self.source_name = source_name
        self.source_type = source_type
        self.source_url = source_url

    async def ingest_companies(self) -> int:
        """Ingest companies from the provider, refreshing existing metadata."""
        companies = await self.provider.get_companies()
        return await self.upsert_companies(companies)

    async def ingest_prices(
        self,
        ticker: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        """Fetch and persist daily prices for a ticker. Returns rows upserted."""
        price_data = await self.provider.get_daily_prices(ticker, start_date, end_date)
        return await self.write_prices(ticker, price_data)

    async def write_prices(
        self,
        ticker: str,
        price_data: list[DailyPriceData],
    ) -> int:
        """Persist already-fetched price rows for a ticker.

        Split out from :meth:`ingest_prices` so callers can do the slow network
        fetch concurrently and then write from a single session.
        """
        if not price_data:
            return 0

        company = await self.company_repo.get_by_ticker(ticker)
        if not company:
            raise ValueError(f"Company with ticker '{ticker}' not found")

        data_source = await self.source_repo.get_or_create(
            name=self.source_name,
            source_type=self.source_type,
            base_url=self.source_url,
        )

        records = [
            DailyPriceCreate(
                company_id=company.id,
                date=p.date,
                open=p.open,
                high=p.high,
                low=p.low,
                close=p.close,
                adjusted_close=p.adjusted_close,
                volume=p.volume,
                value_traded=p.value_traded,
                trades=p.trades,
                source_id=data_source.id,
            )
            for p in price_data
        ]

        count = await self.price_repo.bulk_upsert(records)
        from datetime import UTC, datetime

        data_source.last_synced_at = datetime.now(UTC)
        await self.session.commit()
        logger.debug("Wrote %d price records for %s", count, ticker)
        return count

    async def upsert_companies(self, companies: list[CompanyData]) -> int:
        """Create or refresh company metadata from provider data."""
        if not companies:
            return 0
        await self.source_repo.get_or_create(
            name=self.source_name,
            source_type=self.source_type,
            base_url=self.source_url,
        )
        rows = [
            {
                "ticker": c.ticker,
                "isin": c.isin,
                "name": c.name,
                "name_ar": c.name_ar,
                "sector": c.sector,
                "industry": c.industry,
                "currency": c.currency,
                "shares_outstanding": c.shares_outstanding,
                "free_float": c.free_float,
                "listing_date": c.listing_date,
                "status": c.status,
            }
            for c in companies
        ]
        count = await self.company_repo.upsert_many(rows)
        await self.session.commit()
        logger.info("Upserted %d companies from %s", count, self.source_name)
        return count
