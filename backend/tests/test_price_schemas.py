"""Tests for daily price schemas."""

from decimal import Decimal

import pytest

from app.schemas.price import DailyPriceBase


class TestDailyPriceValidation:
    def test_valid_ohlc(self) -> None:
        price = DailyPriceBase(
            date="2026-01-15",
            open=Decimal("100.0000"),
            high=Decimal("105.0000"),
            low=Decimal("98.0000"),
            close=Decimal("103.0000"),
            volume=1000000,
        )
        assert price.open == Decimal("100.0000")
        assert price.volume == 1000000

    def test_low_equals_open_equals_high(self) -> None:
        price = DailyPriceBase(
            date="2026-01-15",
            open=Decimal("100.0000"),
            high=Decimal("100.0000"),
            low=Decimal("100.0000"),
            close=Decimal("100.0000"),
            volume=500000,
        )
        assert price.low == price.open == price.high == price.close

    def test_low_greater_than_open_raises(self) -> None:
        with pytest.raises(ValueError, match="low must be <= open"):
            DailyPriceBase(
                date="2026-01-15",
                open=Decimal("98.0000"),
                high=Decimal("105.0000"),
                low=Decimal("99.0000"),
                close=Decimal("103.0000"),
                volume=1000000,
            )

    def test_open_greater_than_high_raises(self) -> None:
        with pytest.raises(ValueError, match="open must be <= high"):
            DailyPriceBase(
                date="2026-01-15",
                open=Decimal("106.0000"),
                high=Decimal("105.0000"),
                low=Decimal("98.0000"),
                close=Decimal("103.0000"),
                volume=1000000,
            )

    def test_close_greater_than_high_raises(self) -> None:
        with pytest.raises(ValueError, match="close must be <= high"):
            DailyPriceBase(
                date="2026-01-15",
                open=Decimal("100.0000"),
                high=Decimal("105.0000"),
                low=Decimal("98.0000"),
                close=Decimal("106.0000"),
                volume=1000000,
            )

    def test_close_less_than_low_raises(self) -> None:
        with pytest.raises(ValueError, match="close must be >= low"):
            DailyPriceBase(
                date="2026-01-15",
                open=Decimal("100.0000"),
                high=Decimal("105.0000"),
                low=Decimal("98.0000"),
                close=Decimal("97.0000"),
                volume=1000000,
            )

    def test_negative_volume_raises(self) -> None:
        with pytest.raises(ValueError):
            DailyPriceBase(
                date="2026-01-15",
                open=Decimal("100.0000"),
                high=Decimal("105.0000"),
                low=Decimal("98.0000"),
                close=Decimal("103.0000"),
                volume=-1,
            )

    def test_zero_volume_valid(self) -> None:
        price = DailyPriceBase(
            date="2026-01-15",
            open=Decimal("100.0000"),
            high=Decimal("105.0000"),
            low=Decimal("98.0000"),
            close=Decimal("103.0000"),
            volume=0,
        )
        assert price.volume == 0

    def test_negative_trades_raises(self) -> None:
        with pytest.raises(ValueError):
            DailyPriceBase(
                date="2026-01-15",
                open=Decimal("100.0000"),
                high=Decimal("105.0000"),
                low=Decimal("98.0000"),
                close=Decimal("103.0000"),
                volume=1000000,
                trades=-5,
            )
