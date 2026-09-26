"""Seed development data with clearly labeled synthetic data."""

import asyncio
import logging

from app.db.session import async_session_factory
from app.ingestion.fake_financial_provider import FakeFinancialDataProvider
from app.ingestion.fake_provider import FakeMarketDataProvider
from app.ingestion.financial_service import FinancialDataIngestionService
from app.ingestion.service import MarketDataIngestionService
from app.models.market import DataSourceType

logger = logging.getLogger(__name__)


async def seed() -> None:
    """Seed synthetic development data."""
    market_provider = FakeMarketDataProvider()
    financial_provider = FakeFinancialDataProvider()

    async with async_session_factory() as session:
        # Seed companies and prices
        market_service = MarketDataIngestionService(
            session=session,
            provider=market_provider,
            source_name="SYNTHETIC_DEV",
            source_type=DataSourceType.SYNTHETIC,
        )

        logger.info("Seeding companies...")
        company_count = await market_service.ingest_companies()
        logger.info("Seeded %d companies", company_count)

        logger.info("Seeding price data for all companies...")
        total_prices = 0
        for company in market_provider.COMPANIES:
            count = await market_service.ingest_prices(company.ticker)
            total_prices += count
            logger.info("  %s: %d price records", company.ticker, count)

        # Seed financial data
        financial_service = FinancialDataIngestionService(
            session=session,
            provider=financial_provider,
            source_name="SYNTHETIC_FINANCIALS",
            source_type=DataSourceType.SYNTHETIC,
        )

        logger.info("Seeding financial data for all companies...")
        total_periods = 0
        total_documents = 0
        total_facts = 0
        for company in market_provider.COMPANIES:
            counts = await financial_service.ingest_financial_data(company.ticker)
            total_periods += counts["periods"]
            total_documents += counts["documents"]
            total_facts += counts["facts"]
            logger.info(
                "  %s: %d periods, %d documents, %d facts",
                company.ticker,
                counts["periods"],
                counts["documents"],
                counts["facts"],
            )

        logger.info(
            "Seed complete: %d companies, %d price records, %d periods, %d documents, %d facts",
            company_count,
            total_prices,
            total_periods,
            total_documents,
            total_facts,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed())
