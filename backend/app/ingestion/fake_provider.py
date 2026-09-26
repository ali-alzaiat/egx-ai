from datetime import date, timedelta
from decimal import Decimal

from app.ingestion.provider import CompanyData, DailyPriceData, MarketDataProvider


class FakeMarketDataProvider(MarketDataProvider):
    """Synthetic data provider for development and testing.

    Clearly labeled as SYNTHETIC — do not use for real market data.
    """

    COMPANIES = [
        CompanyData(
            ticker="COMI",
            isin="EGY000111016",
            name="Commercial International Bank",
            name_ar="البنك التجاري الدولي",
            sector="Financials",
            industry="Banks",
            currency="EGP",
            shares_outstanding=Decimal("9500000000"),
            free_float=Decimal("0.40"),
            listing_date=date(2006, 1, 1),
            status="ACTIVE",
        ),
        CompanyData(
            ticker="HRHO",
            isin="EGY000111019",
            name="Heron Holdings",
            name_ar="هيرون هولدنجز",
            sector="Financials",
            industry="Financial Services",
            currency="EGP",
            shares_outstanding=Decimal("3000000000"),
            free_float=Decimal("0.25"),
            listing_date=date(2007, 3, 15),
            status="ACTIVE",
        ),
        CompanyData(
            ticker="EAST",
            isin="EGY000301017",
            name="Eastern Company",
            name_ar="الشركة الشرقية",
            sector="Consumer Staples",
            industry="Tobacco",
            currency="EGP",
            shares_outstanding=Decimal("1800000000"),
            free_float=Decimal("0.30"),
            listing_date=date(2004, 6, 1),
            status="ACTIVE",
        ),
        CompanyData(
            ticker="EFIH",
            isin="EGY000501015",
            name="EFG Financial Holdings",
            name_ar="إي إف جي هولدنجز المالية",
            sector="Financials",
            industry="Investment Banking",
            currency="EGP",
            shares_outstanding=Decimal("4500000000"),
            free_float=Decimal("0.35"),
            listing_date=date(2005, 9, 1),
            status="ACTIVE",
        ),
        CompanyData(
            ticker="SWDY",
            isin="EGY000601013",
            name="Smart Windows",
            name_ar="سمارت ويندوز",
            sector="Industrials",
            industry="Construction Materials",
            currency="EGP",
            shares_outstanding=Decimal("1200000000"),
            free_float=Decimal("0.45"),
            listing_date=date(2008, 1, 1),
            status="ACTIVE",
        ),
        CompanyData(
            ticker="ETEL",
            isin="EGY000701011",
            name="Telecom Egypt",
            name_ar="اتصالات مصر",
            sector="Communication Services",
            industry="Telecom",
            currency="EGP",
            shares_outstanding=Decimal("5000000000"),
            free_float=Decimal("0.20"),
            listing_date=date(2005, 1, 1),
            status="ACTIVE",
        ),
        CompanyData(
            ticker="PHAR",
            isin="EGY000801019",
            name="Pharos Holding",
            name_ar="فاروس هولدنجز",
            sector="Financials",
            industry="Investment Banking",
            currency="EGP",
            shares_outstanding=Decimal("800000000"),
            free_float=Decimal("0.50"),
            listing_date=date(2006, 12, 1),
            status="ACTIVE",
        ),
        CompanyData(
            ticker="JUFO",
            isin="EGY000901017",
            name="Juhayna Food Industries",
            name_ar="جهينة لصناعات الأغذية",
            sector="Consumer Staples",
            industry="Food Products",
            currency="EGP",
            shares_outstanding=Decimal("900000000"),
            free_float=Decimal("0.55"),
            listing_date=date(2010, 3, 1),
            status="ACTIVE",
        ),
        CompanyData(
            ticker="OLED",
            isin="EGY001001015",
            name="Oriental Weavers",
            name_ar="الoriental weavers",
            sector="Consumer Discretionary",
            industry="Home Furnishings",
            currency="EGP",
            shares_outstanding=Decimal("700000000"),
            free_float=Decimal("0.40"),
            listing_date=date(2005, 5, 1),
            status="ACTIVE",
        ),
        CompanyData(
            ticker="SSMC",
            isin="EGY001101013",
            name="Sixth of October for Development",
            name_ar="سادس أكتوبر للتنمية",
            sector="Real Estate",
            industry="Real Estate Development",
            currency="EGP",
            shares_outstanding=Decimal("2000000000"),
            free_float=Decimal("0.30"),
            listing_date=date(2007, 7, 1),
            status="ACTIVE",
        ),
    ]

    def _generate_prices(self, ticker: str, start: date, end: date) -> list[DailyPriceData]:
        """Generate pseudo-random but deterministic prices using ticker hash."""
        import hashlib

        seed = int(hashlib.md5(ticker.encode()).hexdigest()[:8], 16)
        prices: list[DailyPriceData] = []

        base_price = Decimal(str(10 + (seed % 200)))
        current = start
        price = base_price

        while current <= end:
            if current.weekday() < 5:
                day_hash = int(
                    hashlib.md5(f"{ticker}{current.isoformat()}".encode()).hexdigest()[:8],
                    16,
                )
                change_pct = Decimal(str(((day_hash % 400) - 200) / 10000))
                price = price * (1 + change_pct)
                price = max(price, Decimal("1.00"))

                intra_high = price * (1 + Decimal(str(day_hash % 50)) / Decimal("10000"))
                intra_low = price * (1 - Decimal(str(day_hash % 50)) / Decimal("10000"))
                spread = intra_high - intra_low
                open_price = intra_low + spread * Decimal(str(day_hash % 100)) / Decimal("100")

                volume = 100000 + (day_hash % 5000000)
                value_traded = price * Decimal(str(volume))

                prices.append(
                    DailyPriceData(
                        ticker=ticker,
                        date=current,
                        open=open_price.quantize(Decimal("0.0001")),
                        high=intra_high.quantize(Decimal("0.0001")),
                        low=intra_low.quantize(Decimal("0.0001")),
                        close=price.quantize(Decimal("0.0001")),
                        adjusted_close=price.quantize(Decimal("0.0001")),
                        volume=volume,
                        value_traded=value_traded.quantize(Decimal("0.01")),
                        trades=100 + (day_hash % 5000),
                    )
                )

            current += timedelta(days=1)

        return prices

    async def get_companies(self) -> list[CompanyData]:
        return list(self.COMPANIES)

    async def get_daily_prices(
        self,
        ticker: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[DailyPriceData]:
        if start_date is None:
            start_date = date(2025, 1, 1)
        if end_date is None:
            end_date = date.today()

        return self._generate_prices(ticker, start_date, end_date)
