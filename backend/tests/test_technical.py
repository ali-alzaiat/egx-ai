"""Tests for technical indicators."""

from decimal import Decimal

from app.technical.indicators import (
    IndicatorStatus,
    IndicatorType,
    calculate_atr,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_macd,
    calculate_obv,
    calculate_rsi,
    calculate_sma,
    calculate_vwap,
)


class TestSMA:
    def test_basic_sma(self):
        prices = [Decimal("10"), Decimal("11"), Decimal("12"), Decimal("13"), Decimal("14")]
        result = calculate_sma(prices, period=5)
        assert result.status == IndicatorStatus.AVAILABLE
        assert result.value == Decimal("12.0000")

    def test_insufficient_data(self):
        prices = [Decimal("10"), Decimal("11")]
        result = calculate_sma(prices, period=5)
        assert result.status == IndicatorStatus.INSUFFICIENT_DATA

    def test_different_period(self):
        prices = [Decimal("10"), Decimal("20"), Decimal("30")]
        result = calculate_sma(prices, period=3)
        assert result.value == Decimal("20.0000")


class TestEMA:
    def test_basic_ema(self):
        prices = [Decimal("10"), Decimal("11"), Decimal("12"), Decimal("13"), Decimal("14")]
        result = calculate_ema(prices, period=3)
        assert result.status == IndicatorStatus.AVAILABLE
        assert result.value is not None

    def test_insufficient_data(self):
        prices = [Decimal("10")]
        result = calculate_ema(prices, period=5)
        assert result.status == IndicatorStatus.INSUFFICIENT_DATA


class TestRSI:
    def test_basic_rsi(self):
        # Prices that go up
        prices = [Decimal("10"), Decimal("11"), Decimal("12"), Decimal("13"), Decimal("14")]
        result = calculate_rsi(prices, period=3)
        assert result.status == IndicatorStatus.AVAILABLE
        assert result.value == Decimal("100.00")

    def test_rsi_with_losses(self):
        # Prices that go down
        prices = [Decimal("14"), Decimal("13"), Decimal("12"), Decimal("11"), Decimal("10")]
        result = calculate_rsi(prices, period=3)
        assert result.status == IndicatorStatus.AVAILABLE
        assert result.value == Decimal("0.00")

    def test_insufficient_data(self):
        prices = [Decimal("10"), Decimal("11")]
        result = calculate_rsi(prices, period=14)
        assert result.status == IndicatorStatus.INSUFFICIENT_DATA


class TestMACD:
    def test_basic_macd(self):
        # Generate enough prices for MACD
        prices = [Decimal(str(10 + i * 0.5)) for i in range(50)]
        result = calculate_macd(prices)
        assert result.status == IndicatorStatus.AVAILABLE
        assert result.value is not None

    def test_insufficient_data(self):
        prices = [Decimal("10"), Decimal("11"), Decimal("12")]
        result = calculate_macd(prices)
        assert result.status == IndicatorStatus.INSUFFICIENT_DATA


class TestBollingerBands:
    def test_basic_bollinger(self):
        prices = [Decimal(str(10 + i * 0.1)) for i in range(25)]
        result = calculate_bollinger_bands(prices)
        assert result.status == IndicatorStatus.AVAILABLE
        assert result.value is not None

    def test_insufficient_data(self):
        prices = [Decimal("10"), Decimal("11")]
        result = calculate_bollinger_bands(prices, period=20)
        assert result.status == IndicatorStatus.INSUFFICIENT_DATA


class TestOBV:
    def test_basic_obv(self):
        prices = [Decimal("10"), Decimal("11"), Decimal("10"), Decimal("11")]
        volumes = [100, 150, 120, 180]
        result = calculate_obv(prices, volumes)
        assert result.status == IndicatorStatus.AVAILABLE
        # 10->11 (up): +150, 11->10 (down): -120, 10->11 (up): +180
        # OBV = 150 - 120 + 180 = 210
        assert result.value == Decimal("210")

    def test_insufficient_data(self):
        prices = [Decimal("10")]
        volumes = [100]
        result = calculate_obv(prices, volumes)
        assert result.status == IndicatorStatus.INSUFFICIENT_DATA

    def test_mismatched_lengths(self):
        prices = [Decimal("10"), Decimal("11")]
        volumes = [100]
        result = calculate_obv(prices, volumes)
        # Returns INSUFFICIENT_DATA because volumes length < 2
        assert result.status == IndicatorStatus.INSUFFICIENT_DATA


class TestVWAP:
    def test_basic_vwap(self):
        prices = [Decimal("10"), Decimal("11"), Decimal("12")]
        volumes = [100, 150, 200]
        result = calculate_vwap(prices, volumes)
        assert result.status == IndicatorStatus.AVAILABLE
        # VWAP = (10*100 + 11*150 + 12*200) / (100+150+200)
        # = (1000 + 1650 + 2400) / 450 = 5050 / 450 = 11.2222
        assert result.value == Decimal("11.2222")

    def test_empty_data(self):
        prices = []
        volumes = []
        result = calculate_vwap(prices, volumes)
        assert result.status == IndicatorStatus.INSUFFICIENT_DATA


class TestIndicatorTypes:
    def test_all_indicators_have_types(self):
        assert IndicatorType.SMA.value == "sma"
        assert IndicatorType.EMA.value == "ema"
        assert IndicatorType.RSI.value == "rsi"
        assert IndicatorType.MACD.value == "macd"
        assert IndicatorType.BOLLINGER.value == "bollinger"
        assert IndicatorType.OBV.value == "obv"
        assert IndicatorType.VWAP.value == "vwap"
        assert IndicatorType.ATR.value == "atr"


class TestATR:
    def test_constant_range_equals_range(self):
        # Every bar spans 2.0 with no gaps, so every TR (and the ATR) is 2.0.
        closes = [Decimal("10")] * 16
        highs = [Decimal("11")] * 16
        lows = [Decimal("9")] * 16
        result = calculate_atr(highs, lows, closes, period=14)
        assert result.status == IndicatorStatus.AVAILABLE
        assert result.value == Decimal("2.0000")

    def test_gap_uses_previous_close(self):
        # Gap up: TR = |high - prev close| = 15 - 10 = 5, not high - low = 1.
        highs = [Decimal("10"), Decimal("15")]
        lows = [Decimal("10"), Decimal("14")]
        closes = [Decimal("10"), Decimal("14.5")]
        result = calculate_atr(highs, lows, closes, period=1)
        assert result.value == Decimal("5.0000")

    def test_wilder_smoothing(self):
        # TRs = 2, 2, 5 with period 2: seed (2+2)/2 = 2, then (2*1 + 5)/2 = 3.5.
        highs = [Decimal("10"), Decimal("11"), Decimal("11"), Decimal("14")]
        lows = [Decimal("10"), Decimal("9"), Decimal("9"), Decimal("9")]
        closes = [Decimal("10"), Decimal("10"), Decimal("10"), Decimal("12")]
        result = calculate_atr(highs, lows, closes, period=2)
        assert result.value == Decimal("3.5000")

    def test_insufficient_data(self):
        bars = [Decimal("10")] * 14
        result = calculate_atr(bars, bars, bars, period=14)
        assert result.status == IndicatorStatus.INSUFFICIENT_DATA
        assert result.value is None

    def test_empty_input(self):
        result = calculate_atr([], [], [], period=14)
        assert result.status == IndicatorStatus.INSUFFICIENT_DATA

    def test_mismatched_lengths_invalid(self):
        result = calculate_atr([Decimal("1")] * 3, [Decimal("1")] * 2, [Decimal("1")] * 3, 1)
        assert result.status == IndicatorStatus.INVALID

    def test_high_below_low_invalid(self):
        highs = [Decimal("10"), Decimal("8")]
        lows = [Decimal("9"), Decimal("9")]
        closes = [Decimal("10"), Decimal("9")]
        result = calculate_atr(highs, lows, closes, period=1)
        assert result.status == IndicatorStatus.INVALID

    def test_zero_range_is_zero_not_missing(self):
        bars = [Decimal("10")] * 5
        result = calculate_atr(bars, bars, bars, period=2)
        assert result.status == IndicatorStatus.AVAILABLE
        assert result.value == Decimal("0.0000")
