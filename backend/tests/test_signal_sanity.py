"""Real-data sanity check: distribution and concentration flag."""

from decimal import Decimal

from app.signals.sanity import CONCENTRATION_THRESHOLD, distribution_report


def test_empty_is_not_concentrated() -> None:
    report = distribution_report({})
    assert report.total == 0
    assert report.dominant is None
    assert report.concentrated is False


def test_balanced_is_ok() -> None:
    report = distribution_report({"buy": 10, "hold": 20, "reduce": 20})
    assert report.total == 50
    assert report.shares["hold"] == Decimal("0.4")
    assert report.concentrated is False


def test_v1_failure_mode_is_flagged() -> None:
    # signal-rules-1.0 showed "reduce" for every stock: the check must catch it.
    report = distribution_report({"reduce": 50})
    assert report.dominant == "reduce"
    assert report.concentrated is True


def test_threshold_is_exclusive() -> None:
    at = distribution_report({"reduce": 40, "hold": 10})  # exactly 80%
    assert at.shares["reduce"] == CONCENTRATION_THRESHOLD
    assert at.concentrated is False
    above = distribution_report({"reduce": 41, "hold": 9})
    assert above.concentrated is True


def test_zero_counts_kept_not_dropped() -> None:
    report = distribution_report({"buy": 0, "hold": 5, "reduce": 5})
    assert report.shares["buy"] == Decimal("0")
