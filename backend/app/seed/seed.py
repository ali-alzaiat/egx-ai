"""Seed development data with real EGX market data from Yahoo Finance."""

import asyncio
import logging

from app.db.session import async_session_factory
from app.ingestion.egx_provider import create_egx_provider
from app.ingestion.service import MarketDataIngestionService
from app.models.market import DataSourceType

logger = logging.getLogger(__name__)


async def seed() -> None:
    """Seed development data using real EGX market data from Yahoo Finance."""
    market_provider = create_egx_provider()

    async with async_session_factory() as session:
        # Seed companies and prices from Yahoo Finance
        market_service = MarketDataIngestionService(
            session=session,
            provider=market_provider,
            source_name="YAHOO_FINANCE_EGX",
            source_type=DataSourceType.DATA_PROVIDER,
        )

        logger.info("Seeding companies from EGX (Yahoo Finance)...")
        company_count = await market_service.ingest_companies()
        logger.info("Seeded %d companies", company_count)

        logger.info("Seeding price data for all companies...")
        total_prices = 0
        companies = await market_provider.get_companies()
        for company in companies:
            count = await market_service.ingest_prices(company.ticker)
            total_prices += count
            if count > 0:
                logger.info("  %s: %d price records", company.ticker, count)
            else:
                logger.debug("  %s: no price data available on Yahoo Finance", company.ticker)

        logger.info(
            "Seed complete: %d companies, %d price records",
            company_count,
            total_prices,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed())
