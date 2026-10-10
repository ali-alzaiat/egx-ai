"""Pure, deterministic peer-percentile math.

Total functions over their arguments: no I/O, no clock, no database, no
randomness. Ordering-only — zero and negative values rank naturally, missing
(None) values are excluded, never zero-filled.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from app.industry.constants import MIN_VALUES_WITH_DATA

if TYPE_CHECKING:
    from collections.abc import Sequence


class PeerPercentileStatus(enum.StrEnum):
    OK = "OK"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True, slots=True)
class PeerPercentile:
    """Percentile of one target value within its peer set for one metric."""

    metric_key: str
    value: float | None
    status: PeerPercentileStatus
    n_peers: int
    n_with_data: int


def peer_percentile(
    metric_key: str,
    target: Decimal | None,
    peer_values: Sequence[Decimal | None],
    *,
    min_values_with_data: int = MIN_VALUES_WITH_DATA,
) -> PeerPercentile:
    """Rank ``target`` among itself plus ``peer_values`` (peers-with-data only).

    ``value`` is the share (0-100) of values-with-data at or below the target.
    Returns INSUFFICIENT_DATA with ``value=None`` when the target is missing
    or fewer than ``min_values_with_data`` values exist — never a 1-of-1 rank.
    """
    n_peers = len(peer_values)
    if target is None:
        return PeerPercentile(
            metric_key=metric_key,
            value=None,
            status=PeerPercentileStatus.INSUFFICIENT_DATA,
            n_peers=n_peers,
            n_with_data=sum(1 for v in peer_values if v is not None),
        )
    with_data = [target, *(v for v in peer_values if v is not None)]
    if len(with_data) < min_values_with_data:
        return PeerPercentile(
            metric_key=metric_key,
            value=None,
            status=PeerPercentileStatus.INSUFFICIENT_DATA,
            n_peers=n_peers,
            n_with_data=len(with_data),
        )
    at_or_below = sum(1 for v in with_data if v <= target)
    return PeerPercentile(
        metric_key=metric_key,
        value=round(float(Decimal(at_or_below) / Decimal(len(with_data)) * Decimal(100)), 2),
        status=PeerPercentileStatus.OK,
        n_peers=n_peers,
        n_with_data=len(with_data),
    )


def explain_percentile(
    company_ticker: str,
    display_name: str,
    target_text: str | None,
    result: PeerPercentile,
    profile_key: str,
    methodology_version: str,
    as_of_text: str,
) -> str:
    """Human-readable explanation pinned to the same counts as the response."""
    if result.status is PeerPercentileStatus.INSUFFICIENT_DATA or target_text is None:
        return (
            f"{company_ticker} {display_name}: insufficient data "
            f"({result.n_with_data} of {result.n_peers + 1} companies with data; "
            f"need {MIN_VALUES_WITH_DATA}) under profile '{profile_key}' "
            f"v{methodology_version} as of {as_of_text}."
        )
    assert result.value is not None
    return (
        f"{company_ticker} {display_name} {target_text} is at or above "
        f"{result.value:.2f}% of {result.n_with_data} companies with data "
        f"({result.n_peers} peers) under profile '{profile_key}' "
        f"v{methodology_version} as of {as_of_text}."
    )
