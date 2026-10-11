"""Diff ledger rows + restatement detector (R34 P0-6). Pure logic only.

Period-over-period diffs link consecutive reported periods; restatements link
a republished (company, metric, period) to the row it supersedes. Priors are
never deleted — the new row carries ``supersedes`` + the As-Restated flag, so
``as_of`` reads can still return the pre-restatement value. Beat/miss is only
written where the caller supplied an estimate.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any, NamedTuple

from app.ingestion.disclosures.comparison import quantize4
from app.ingestion.disclosures.constants import BEAT_MISS_LABELS, DISCLOSURE_METHODOLOGY_VERSION


class RestatementDecision(NamedTuple):
    """Outcome of comparing a new fact against the latest stored row."""

    action: str  # "insert" | "duplicate" | "restate"
    supersedes_id: uuid.UUID | None


class FactVersion(NamedTuple):
    """Minimal row shape the as-of selector needs (no ORM import)."""

    id: uuid.UUID
    value: Decimal | None
    created_at: datetime
    supersedes_id: uuid.UUID | None


def restatement_decision(
    *,
    new_value: Decimal | None,
    latest_value: Decimal | None,
    latest_id: uuid.UUID | None,
) -> RestatementDecision:
    """Same (company, metric, period) republished: duplicate, or restate.

    No stored row → insert. Equal values (including both-missing) → duplicate:
    the caller keeps the existing row. Anything else → restate, superseding
    the latest row while it stays stored for backtest point-in-time reads.
    """
    if latest_id is None:
        return RestatementDecision(action="insert", supersedes_id=None)
    if new_value == latest_value:
        return RestatementDecision(action="duplicate", supersedes_id=None)
    return RestatementDecision(action="restate", supersedes_id=latest_id)


def beat_or_miss(
    current_value: Decimal | None, estimate: Decimal | None
) -> str | None:
    """Beat/miss only where an estimate exists and the current value is known."""
    if estimate is None or current_value is None:
        return None
    label = "beat" if current_value >= estimate else "miss"
    assert label in BEAT_MISS_LABELS  # methodology literals, never caller text
    return label


def build_diff_row(
    *,
    metric: str,
    prior_value: Decimal | None,
    current_value: Decimal | None,
    prior_period: str,
    current_period: str,
    kind: str,
    estimate: Decimal | None = None,
    methodology_version: str = DISCLOSURE_METHODOLOGY_VERSION,
) -> dict[str, Any]:
    """One diff-ledger row: delta + delta_pct are None unless both legs exist."""
    delta: Decimal | None = None
    delta_pct: Decimal | None = None
    if prior_value is not None and current_value is not None:
        delta = current_value - prior_value
        if prior_value != 0:
            delta_pct = quantize4(delta / prior_value)
    return {
        "metric": metric,
        "kind": kind,
        "prior_value": str(prior_value) if prior_value is not None else None,
        "current_value": str(current_value) if current_value is not None else None,
        "delta": str(delta) if delta is not None else None,
        "delta_pct": str(delta_pct) if delta_pct is not None else None,
        "prior_period": prior_period,
        "current_period": current_period,
        "estimate": str(estimate) if estimate is not None else None,
        "beat_miss": beat_or_miss(current_value, estimate),
        "methodology_version": methodology_version,
    }


def select_as_of(
    versions: Sequence[FactVersion], *, as_of: datetime
) -> FactVersion | None:
    """Latest row visible at ``as_of``: created then, and not yet superseded.

    A restated-away row stays visible for reads dated before its replacement;
    once the replacement exists at ``as_of``, the replacement wins. Input is
    read oldest-first so timestamp ties resolve deterministically.
    """
    known = [version for version in versions if version.created_at <= as_of]
    if not known:
        return None
    superseded = {
        version.supersedes_id for version in known if version.supersedes_id is not None
    }
    visible = [version for version in known if version.id not in superseded]
    if not visible:
        return None
    return visible[-1]
