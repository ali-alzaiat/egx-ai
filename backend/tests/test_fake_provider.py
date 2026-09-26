"""Tests for fake market data provider."""

from datetime import date

import pytest

from app.ingestion.fake_provider import FakeMarketDataProvider


@pytest.fixture
def provider() -> FakeMarketDataProvider:
    return FakeMarketDataProvider()


class TestFakeMarketDataProvider:
    @pytest.mark.asyncio
    async def test_get_companies(self, provider: FakeMarketDataProvider) -> None:
        companies = await provider.get_companies()
        assert len(companies) == 10
        assert all(c.ticker for c in companies)
        assert all(c.name for c in companies)
        assert all(c.currency == "EGP" for c in companies)

    @pytest.mark.asyncio
    async def test_get_companies_have_sectors(self, provider: FakeMarketDataProvider) -> None:
        companies = await provider.get_companies()
        for c in companies:
            assert c.sector is not None, f"{c.ticker} missing sector"

    @pytest.mark.asyncio
    async def test_get_daily_prices(self, provider: FakeMarketDataProvider) -> None:
        prices = await provider.get_daily_prices("COMI", date(2026, 1, 1), date(2026, 1, 31))
        assert len(prices) > 0
        for p in prices:
            assert p.ticker == "COMI"
            assert p.date >= date(2026, 1, 1)
            assert p.date <= date(2026, 1, 31)
            assert p.volume >= 0

    @pytest.mark.asyncio
    async def test_prices_only_weekdays(self, provider: FakeMarketDataProvider) -> None:
        prices = await provider.get_daily_prices("COMI", date(2026, 1, 1), date(2026, 1, 31))
        for p in prices:
            assert p.date.weekday() < 5, f"Price on weekend: {p.date}"

    @pytest.mark.asyncio
    async def test_ohlc_invariants(self, provider: FakeMarketDataProvider) -> None:
        prices = await provider.get_daily_prices("COMI", date(2026, 1, 1), date(2026, 1, 31))
        for p in prices:
            assert p.low <= p.open <= p.high, f"OHLC invariant failed for {p.date}"
            assert p.low <= p.close <= p.high, f"Close invariant failed for {p.date}"

    @pytest.mark.asyncio
    async def test_different_tickers_different_prices(
        self, provider: FakeMarketDataProvider
    ) -> None:
        prices_a = await provider.get_daily_prices("COMI", date(2026, 1, 5), date(2026, 1, 5))
        prices_b = await provider.get_daily_prices("HRHO", date(2026, 1, 5), date(2026, 1, 5))
        assert len(prices_a) == 1
        assert len(prices_b) == 1
        assert prices_a[0].close != prices_b[0].close
