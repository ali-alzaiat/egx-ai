"""Unit tests for deterministic peer-percentile math (no I/O)."""

from decimal import Decimal

from app.industry.percentiles import (
    PeerPercentileStatus,
    explain_percentile,
    peer_percentile,
)


def test_target_highest_scores_100() -> None:
    result = peer_percentile("roe", Decimal("20"), [Decimal("5"), Decimal("10"), Decimal("15")])
    assert result.status is PeerPercentileStatus.OK
    assert result.value == 100.00
    assert result.n_peers == 3
    assert result.n_with_data == 4


def test_middle_rank_math() -> None:
    result = peer_percentile("roe", Decimal("10"), [Decimal("5"), Decimal("15"), Decimal("20")])
    assert result.status is PeerPercentileStatus.OK
    assert result.value == 50.00


def test_ties_count_at_or_below() -> None:
    result = peer_percentile("roe", Decimal("10"), [Decimal("10"), Decimal("20")])
    assert result.status is PeerPercentileStatus.OK
    assert result.value == 66.67
    assert result.n_with_data == 3


def test_zero_and_negative_values_rank_naturally() -> None:
    result = peer_percentile(
        "net_margin", Decimal("0"), [Decimal("-5"), Decimal("-1"), Decimal("3")]
    )
    assert result.status is PeerPercentileStatus.OK
    assert result.value == 75.00


def test_zero_target_is_not_missing() -> None:
    result = peer_percentile("roe", Decimal("0"), [Decimal("1"), Decimal("2")])
    assert result.status is PeerPercentileStatus.OK
    assert result.value == 33.33


def test_missing_target_is_insufficient() -> None:
    result = peer_percentile("roe", None, [Decimal("5"), Decimal("10"), Decimal("15")])
    assert result.status is PeerPercentileStatus.INSUFFICIENT_DATA
    assert result.value is None


def test_missing_peer_values_excluded_not_zero_filled() -> None:
    result = peer_percentile("roe", Decimal("10"), [None, Decimal("5"), Decimal("15")])
    assert result.status is PeerPercentileStatus.OK
    assert result.n_peers == 3
    assert result.n_with_data == 3
    assert result.value == 66.67


def test_single_peer_universe_is_insufficient() -> None:
    """Never rank 1-of-1 as a top decile."""
    result = peer_percentile("roe", Decimal("10"), [Decimal("5")])
    assert result.status is PeerPercentileStatus.INSUFFICIENT_DATA
    assert result.value is None


def test_no_peers_is_insufficient() -> None:
    result = peer_percentile("roe", Decimal("10"), [])
    assert result.status is PeerPercentileStatus.INSUFFICIENT_DATA
    assert result.value is None


def test_all_peers_missing_is_insufficient() -> None:
    result = peer_percentile("roe", Decimal("10"), [None, None])
    assert result.status is PeerPercentileStatus.INSUFFICIENT_DATA
    assert result.value is None
    assert result.n_with_data == 1


def test_explanation_ok_names_counts_and_version() -> None:
    result = peer_percentile("roe", Decimal("10"), [Decimal("5"), Decimal("15"), Decimal("20")])
    text = explain_percentile("COMI", "roe", "10", result, "banks", "1.0", "2026-10-10")
    assert "COMI" in text
    assert "banks" in text
    assert "1.0" in text
    assert "2026-10-10" in text
    assert "50.00%" in text


def test_explanation_insufficient_states_floor() -> None:
    result = peer_percentile("roe", Decimal("10"), [Decimal("5")])
    text = explain_percentile("COMI", "roe", "10", result, "banks", "1.0", "2026-10-10")
    assert "insufficient data" in text
    assert "need 3" in text
