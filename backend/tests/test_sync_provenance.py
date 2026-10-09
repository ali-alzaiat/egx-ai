"""Tests for sync provenance: source base_url and last_synced_at."""

from datetime import UTC

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.ingestion.fake_provider import FakeMarketDataProvider
from app.ingestion.service import MarketDataIngestionService
from app.models.market import DataSource, DataSourceType


class TestSyncProvenance:
    @pytest_asyncio.fixture
    async def service(
        self, db_session, test_company
    ) -> MarketDataIngestionService:
        """Service with a unique source name to avoid collisions."""
        provider = FakeMarketDataProvider()
        # Ensure test company exists (fixture already does)
        return MarketDataIngestionService(
            db_session,
            provider,
            source_name=f"TEST_YAHOO_EGX_{test_company.ticker}",
            source_type=DataSourceType.DATA_PROVIDER,
            source_url="https://finance.yahoo.com",
        )

    @pytest.mark.asyncio
    async def test_write_prices_stamps_source_provenance(
        self, db_session, test_company, service: MarketDataIngestionService
    ) -> None:
        """Production path: write_prices stamps base_url and last_synced_at."""
        prices = await service.provider.get_daily_prices(
            test_company.ticker, None, None
        )
        count = await service.write_prices(test_company.ticker, prices)
        assert count > 0

        result = await db_session.execute(
            select(DataSource).where(DataSource.name == service.source_name)
        )
        ds = result.scalar_one()
        assert ds.base_url == "https://finance.yahoo.com"
        assert ds.last_synced_at is not None
        assert ds.last_synced_at.tzinfo is UTC or ds.last_synced_at.tzinfo == UTC

    @pytest.mark.asyncio
    async def test_ingest_prices_stamps_same_way(
        self, db_session, test_company, service: MarketDataIngestionService
    ) -> None:
        """Public ingest path: ingest_prices stamps the same way."""
        count = await service.ingest_prices(test_company.ticker)
        assert count > 0

        result = await db_session.execute(
            select(DataSource).where(DataSource.name == service.source_name)
        )
        ds = result.scalar_one()
        assert ds.base_url == "https://finance.yahoo.com"
        assert ds.last_synced_at is not None

    @pytest.mark.asyncio
    async def test_no_write_no_stamp(
        self, db_session, test_company, service: MarketDataIngestionService
    ) -> None:
        """No write, no stamp: empty price data creates no data_sources row."""
        count = await service.write_prices(test_company.ticker, [])
        assert count == 0

        result = await db_session.execute(
            select(DataSource).where(DataSource.name == service.source_name)
        )
        assert result.scalar_one_or_none() is None
