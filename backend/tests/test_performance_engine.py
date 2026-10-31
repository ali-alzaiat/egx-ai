"""R50 performance engine: windows, relative returns, TTM/YoY growth (pure, synthetic values)."""

from datetime import date, timedelta
from decimal import Decimal

from app.performance.constants import PERFORMANCE_METHODOLOGY_VERSION, WINDOW_ORDER
from app.performance.engine import (
    PeriodValue,
    discrete_quarters,
    fundamentals_growth,
    performance_windows,
    price_returns,
    relative_returns,
    sector_peer_benchmark,
)

D = Decimal


def _series(n: int, end: date, start_close: str = "10", step: str = "0.1") -> list[tuple[date, D]]:
    """n consecutive calendar-day closes ending on ``end``, rising by ``step``."""
    return [
        (end - timedelta(days=n - 1 - i), D(start_close) + D(step) * i) for i in range(n)
    ]


def test_methodology_version_is_pinned() -> None:
    assert PERFORMANCE_METHODOLOGY_VERSION == "performance-1.1"
    assert WINDOW_ORDER == ("1M", "3M", "6M", "YTD", "1Y")


def test_window_returns_use_the_close_n_trading_days_back() -> None:
    end = date(2026, 10, 30)
    closes = _series(300, end)  # close_i = 10 + 0.1 i, last = 39.9
    out = price_returns(closes, end)
    # 1M = 21 bars back: close 39.9 - 2.1 = 37.8 -> 39.9/37.8 - 1 = 0.0556
    assert out["1M"]["return"] == D("0.0556")
    assert out["1M"]["end_date"] == "2026-10-30"
    assert out["1M"]["start_date"] == (end - timedelta(days=21)).isoformat()
    # 1Y = 252 bars back: close 39.9 - 25.2 = 14.7 -> 39.9/14.7 - 1 = 1.7143
    assert out["1Y"]["return"] == D("1.7143")


def test_short_series_is_insufficient_not_zero() -> None:
    end = date(2026, 10, 30)
    out = price_returns(_series(100, end), end)
    assert out["1M"]["return"] is not None
    assert out["3M"]["return"] is not None  # 63 bars back, 100 available
    assert out["6M"]["status"] == "INSUFFICIENT_DATA"
    assert out["6M"]["value"] is None and out["6M"]["reason"]
    assert out["1Y"]["status"] == "INSUFFICIENT_DATA"
    assert "return" not in out["1Y"]


def test_exactly_enough_closes_for_a_window() -> None:
    end = date(2026, 10, 30)
    assert "return" in price_returns(_series(22, end), end)["1M"]  # 21 back needs 22 closes
    assert price_returns(_series(21, end), end)["1M"]["status"] == "INSUFFICIENT_DATA"


def test_empty_series_is_insufficient_everywhere() -> None:
    out = price_returns([], date(2026, 10, 30))
    assert set(out) == set(WINDOW_ORDER)
    assert all(v["status"] == "INSUFFICIENT_DATA" for v in out.values())


def test_no_look_ahead_closes_after_as_of_are_ignored() -> None:
    end = date(2026, 10, 30)
    closes = _series(300, end)
    past = price_returns(closes, end - timedelta(days=10))
    assert past["1M"]["end_date"] == (end - timedelta(days=10)).isoformat()
    # Same answer as a series that never contained the later bars.
    trimmed = [row for row in closes if row[0] <= end - timedelta(days=10)]
    assert past == price_returns(trimmed, end - timedelta(days=10))


def test_ytd_starts_at_the_last_close_of_the_previous_year() -> None:
    closes = [
        (date(2025, 12, 29), D("20")),
        (date(2025, 12, 30), D("25")),  # last close of 2025 (31 Dec is not a trading day)
        (date(2026, 1, 5), D("30")),
        (date(2026, 3, 1), D("50")),
    ]
    out = price_returns(closes, date(2026, 3, 1))["YTD"]
    assert out["start_date"] == "2025-12-30" and out["end_date"] == "2026-03-01"
    assert out["return"] == D("1.0000")  # 50 / 25 - 1


def test_ytd_needs_a_close_before_the_year_and_one_inside_it() -> None:
    only_this_year = [(date(2026, 1, 5), D("30")), (date(2026, 3, 1), D("50"))]
    assert price_returns(only_this_year, date(2026, 3, 1))["YTD"]["status"] == "INSUFFICIENT_DATA"
    only_last_year = [(date(2025, 12, 29), D("20")), (date(2025, 12, 30), D("25"))]
    ytd = price_returns(only_last_year, date(2026, 1, 3))["YTD"]
    assert ytd["status"] == "INSUFFICIENT_DATA" and "current calendar year" in ytd["reason"]


def test_negative_return_and_non_positive_close() -> None:
    end = date(2026, 10, 30)
    falling = _series(30, end, start_close="20", step="-0.1")
    assert price_returns(falling, end)["1M"]["return"] < 0
    bad = _series(30, end)
    bad[-22] = (bad[-22][0], D("0"))  # the 1M start close
    out = price_returns(bad, end)["1M"]
    assert out["status"] == "INSUFFICIENT_DATA" and "non-positive" in out["reason"]


def test_relative_is_stock_minus_index_only_when_both_exist() -> None:
    end = date(2026, 10, 30)
    stock = price_returns(_series(300, end), end)
    index = price_returns(_series(300, end, start_close="100", step="0.1"), end)
    rel = relative_returns(stock, index)
    assert rel["1M"]["relative"] == stock["1M"]["return"] - index["1M"]["return"]
    missing = relative_returns(stock, price_returns([], end))
    assert missing["1M"]["status"] == "INSUFFICIENT_DATA" and "index" in missing["1M"]["reason"]
    assert "relative" not in missing["1M"]


def test_performance_windows_without_index_keeps_the_stock_side() -> None:
    end = date(2026, 10, 30)
    out = performance_windows(_series(300, end), [], end)
    assert out["1M"]["stock"]["return"] == D("0.0556")
    assert out["1M"]["index"]["status"] == "INSUFFICIENT_DATA"
    assert out["1M"]["relative"]["status"] == "INSUFFICIENT_DATA"


# --- fundamentals ----------------------------------------------------------------------------


def _quarters(year: int, values: list[str | None], start_q: int = 1) -> list[PeriodValue]:
    out: list[PeriodValue] = []
    for i, raw in enumerate(values):
        q = start_q + i
        y = year + (q - 1) // 4
        qn = (q - 1) % 4 + 1
        start = date(y, 3 * (qn - 1) + 1, 1)
        end = date(y + (1 if qn == 4 else 0), 1 if qn == 4 else 3 * qn + 1, 1) - timedelta(days=1)
        out.append(PeriodValue(f"Q{qn}", y, start, end, D(raw) if raw is not None else None))
    return out


def test_ttm_and_yoy_from_eight_quarters() -> None:
    rev = _quarters(2024, ["100", "110", "120", "130", "140", "150", "160", "170"])
    inc = _quarters(2024, ["10", "11", "12", "13", "14", "15", "16", "17"])
    out = fundamentals_growth(rev, inc)
    assert out["revenue"]["ttm"]["value"] == "620"  # 140+150+160+170
    assert out["revenue"]["ttm"]["quarters"] == ["Q1-2025", "Q2-2025", "Q3-2025", "Q4-2025"]
    assert out["revenue"]["yoy"]["current"] == "620" and out["revenue"]["yoy"]["prior"] == "460"
    assert out["revenue"]["yoy"]["delta_pct"] == "0.3478"  # 160 / 460
    assert out["ttm_net_margin"] == {"value": "0.1000", "status": "OK"}


def test_ttm_with_fewer_than_four_quarters_is_insufficient() -> None:
    rev = _quarters(2025, ["100", "110", "120"])
    out = fundamentals_growth(rev, rev)
    assert out["revenue"]["ttm"]["status"] == "INSUFFICIENT_DATA"
    assert out["revenue"]["yoy"]["status"] == "INSUFFICIENT_DATA"
    assert out["ttm_net_margin"]["status"] == "INSUFFICIENT_DATA"
    assert out["revenue"]["ttm"]["value"] is None


def test_ttm_refuses_a_gap_in_the_quarters() -> None:
    rev = _quarters(2025, ["100", "110", "120", "130"])
    gapped = [rev[0], rev[1], rev[3], *_quarters(2026, ["140"])]  # Q3-2025 missing
    out = fundamentals_growth(gapped, gapped)
    assert out["revenue"]["ttm"]["status"] == "INSUFFICIENT_DATA"
    assert "gap" in out["revenue"]["ttm"]["reason"]


def test_missing_leg_and_zero_values() -> None:
    with_hole = _quarters(2025, ["100", None, "120", "130"])  # None is dropped -> 3 quarters
    assert fundamentals_growth(with_hole, with_hole)["revenue"]["ttm"]["status"] == (
        "INSUFFICIENT_DATA"
    )
    zero_rev = _quarters(2025, ["0", "0", "0", "0"])
    inc = _quarters(2025, ["5", "5", "5", "5"])
    out = fundamentals_growth(zero_rev, inc)
    assert out["revenue"]["ttm"]["value"] == "0"  # a genuine zero stays a zero
    assert out["ttm_net_margin"]["status"] == "INSUFFICIENT_DATA"  # margin off zero revenue


def test_negative_net_income_gives_a_negative_margin() -> None:
    rev = _quarters(2025, ["100", "100", "100", "100"])
    inc = _quarters(2025, ["-5", "-5", "-5", "-5"])
    assert fundamentals_growth(rev, inc)["ttm_net_margin"]["value"] == "-0.0500"


def test_cumulative_quarters_are_not_summed() -> None:
    # Q2 reported as 6 months year-to-date (start 1 Jan) cannot enter a TTM.
    ytd = PeriodValue("Q2", 2025, date(2025, 1, 1), date(2025, 6, 30), D("250"))
    assert discrete_quarters([ytd]) == []
    assert fundamentals_growth([ytd], [ytd])["revenue"]["ttm"]["status"] == "INSUFFICIENT_DATA"


def test_annual_figures_and_yoy() -> None:
    annual = [
        PeriodValue("ANNUAL", 2024, date(2024, 1, 1), date(2024, 12, 31), D("1000")),
        PeriodValue("ANNUAL", 2025, date(2025, 1, 1), date(2025, 12, 31), D("1200")),
    ]
    block = fundamentals_growth(annual, annual)["revenue"]["annual"]
    assert block["fiscal_year"] == 2025 and block["value"] == "1200"
    assert block["yoy"]["delta_pct"] == "0.2000"
    lone = fundamentals_growth(annual[1:], annual[1:])["revenue"]["annual"]["yoy"]
    assert lone["status"] == "INSUFFICIENT_DATA"
    none = fundamentals_growth([], [])["revenue"]["annual"]
    assert none["status"] == "INSUFFICIENT_DATA" and none["value"] is None


# --- sector peer benchmark (R50 B14) -----------------------------------------------------------

END = date(2026, 10, 30)


def _flat_then(r: str, n: int = 400, end: date = END) -> list[tuple[date, D]]:
    """n daily closes at 100, the last one at 100 * (1 + r): every window returns exactly r."""
    rows = [(end - timedelta(days=n - 1 - i), D("100")) for i in range(n)]
    rows[-1] = (end, D("100") * (D(1) + D(r)))
    return rows


def _peers(returns: list[str]) -> dict[str, list[tuple[date, D]]]:
    return {f"p{i}": _flat_then(r) for i, r in enumerate(returns)}


def _own(r: str) -> dict[str, dict[str, object]]:
    return price_returns(_flat_then(r), END)


def test_sector_median_with_an_odd_count() -> None:
    peers = _peers(["0.01", "0.30", "0.05", "-0.02", "0.10"])
    out = sector_peer_benchmark(_own("0.20"), peers, END)
    one_month = out["1M"]
    assert one_month["median"] == D("0.0500") and one_month["peer_count"] == 5
    assert one_month["relative_to_sector"] == D("0.1500")  # 0.20 - 0.05
    assert set(out) == set(WINDOW_ORDER)
    assert out["1Y"]["median"] == D("0.0500")


def test_sector_median_with_an_even_count_averages_the_middle_two() -> None:
    out = sector_peer_benchmark(
        _own("0.10"), _peers(["0.01", "0.02", "0.04", "0.10", "0.30", "-0.05"]), END
    )
    assert out["3M"]["median"] == D("0.0300")  # (0.02 + 0.04) / 2
    assert out["3M"]["peer_count"] == 6
    assert out["3M"]["relative_to_sector"] == D("0.0700")


def test_fewer_than_five_peers_is_insufficient_with_the_count_and_reason() -> None:
    out = sector_peer_benchmark(_own("0.10"), _peers(["0.01", "0.02", "0.03", "0.04"]), END)
    block = out["1M"]
    assert block["status"] == "INSUFFICIENT_DATA" and block["value"] is None
    assert block["peer_count"] == 4 and "at least 5" in block["reason"]
    assert "median" not in block and "relative_to_sector" not in block
    empty = sector_peer_benchmark(_own("0.10"), {}, END)
    assert empty["1Y"]["status"] == "INSUFFICIENT_DATA" and empty["1Y"]["peer_count"] == 0


def test_a_peer_that_does_not_reach_a_window_is_left_out_of_that_window_only() -> None:
    peers = _peers(["0.01", "0.02", "0.03", "0.04", "0.05"])
    peers["short"] = _flat_then("0.50", n=100)  # reaches 1M and 3M, not 6M / 1Y
    out = sector_peer_benchmark(_own("0.10"), peers, END)
    assert out["1M"]["peer_count"] == 6 and out["1M"]["median"] == D("0.0350")
    assert out["6M"]["peer_count"] == 5 and out["6M"]["median"] == D("0.0300")
    assert out["1Y"]["peer_count"] == 5
    # With only four full-history peers plus the short one, 1Y drops below the minimum.
    thin = _peers(["0.01", "0.02", "0.03", "0.04"])
    thin["short"] = _flat_then("0.50", n=100)
    result = sector_peer_benchmark(_own("0.10"), thin, END)
    assert result["1M"]["peer_count"] == 5 and "median" in result["1M"]
    assert result["1Y"]["status"] == "INSUFFICIENT_DATA" and result["1Y"]["peer_count"] == 4


def test_stale_peers_and_closes_after_as_of_are_ignored() -> None:
    peers = _peers(["0.01", "0.02", "0.03", "0.04", "0.05"])
    peers["stale"] = _flat_then("0.90", end=END - timedelta(days=30))
    peers["future"] = _flat_then("0.70", end=END + timedelta(days=5))
    out = sector_peer_benchmark(_own("0.10"), peers, END)
    # 'future' counts with its closes up to the as-of date only (flat 100: return 0), and
    # 'stale' (last close 30 days old) is out.
    assert out["1M"]["peer_count"] == 6
    assert out["1M"]["median"] == D("0.0250")  # 0, .01, .02, .03, .04, .05


def test_the_stock_missing_a_window_gives_a_median_without_a_relative() -> None:
    own = price_returns(_flat_then("0.10", n=30), END)  # no 6M / 1Y
    out = sector_peer_benchmark(own, _peers(["0.01", "0.02", "0.03", "0.04", "0.05"]), END)
    assert out["1Y"]["median"] == D("0.0300")
    assert out["1Y"]["relative_to_sector"]["status"] == "INSUFFICIENT_DATA"
