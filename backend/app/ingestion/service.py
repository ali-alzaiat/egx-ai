import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.provider import MarketDataProvider
from app.models.market import CompanyStatus, DataSourceType
from app.repositories.company import CompanyRepository
from app.repositories.data_source import DataSourceRepository
from app.repositories.price import PriceRepository
from app.schemas.company import CompanyCreate
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
    ) -> None:
        self.session = session
        self.provider = provider
        self.company_repo = CompanyRepository(session)
        self.price_repo = PriceRepository(session)
        self.source_repo = DataSourceRepository(session)
        self.source_name = source_name
        self.source_type = source_type

    async def ingest_companies(self) -> int:
        """Ingest companies from the provider."""
        await self.source_repo.get_or_create(
            name=self.source_name,
            source_type=self.source_type,
        )
        companies = await self.provider.get_companies()
        count = 0

        for c in companies:
            existing = await self.company_repo.get_by_ticker(c.ticker)
            if existing:
                continue

            status_map = {
                "ACTIVE": CompanyStatus.ACTIVE,
                "SUSPENDED": CompanyStatus.SUSPENDED,
                "DELISTED": CompanyStatus.DELISTED,
            }
            status = status_map.get(c.status, CompanyStatus.UNKNOWN)

            await self.company_repo.create(
                CompanyCreate(
                    ticker=c.ticker,
                    isin=c.isin,
                    name=c.name,
                    name_ar=c.name_ar,
                    sector=c.sector,
                    industry=c.industry,
                    currency=c.currency,
                    shares_outstanding=c.shares_outstanding,
                    free_float=c.free_float,
                    listing_date=c.listing_date,
                    status=status,
                )
            )
            count += 1

        await self.session.commit()
        logger.info("Ingested %d companies from %s", count, self.source_name)
        return count

    async def ingest_prices(
        self,
        ticker: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> int:
        """Ingest daily prices for a ticker. Returns count of records upserted."""
        company = await self.company_repo.get_by_ticker(ticker)
        if not company:
            raise ValueError(f"Company with ticker '{ticker}' not found")

        data_source = await self.source_repo.get_or_create(
            name=self.source_name,
            source_type=self.source_type,
        )

        price_data = await self.provider.get_daily_prices(ticker, start_date, end_date)
        if not price_data:
            return 0

        records = []
        for p in price_data:
            records.append(
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
            )

        count = await self.price_repo.bulk_upsert(records)
        await self.session.commit()
        logger.info("Ingested %d price records for %s from %s", count, ticker, self.source_name)
        return count
