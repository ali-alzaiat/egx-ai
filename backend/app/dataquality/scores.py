"""Pure, deterministic data-quality scoring.

Every function here is a total function over its arguments: no I/O, no clock,
no database, no randomness, no network. Thresholds and weights are pinned by
methodology version 1.0 so scores stay comparable across runs; changing any
value requires bumping METHODOLOGY_VERSION.

Missing information is never silently replaced with zero by callers: unknown
freshness and unknown source types map to their own explicit scores (0 and 40),
and ``score_for`` reports ``MISSING`` when there are no underlying rows at all.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.models.market import DataSourceType

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

METHODOLOGY_VERSION = "1.0"

# Pinned component weights; they sum to exactly 1.0 in this order.
COMPONENT_WEIGHTS: dict[str, float] = {
    "completeness": 0.30,
    "freshness": 0.25,
    "validation": 0.20,
    "historical_depth": 0.15,
    "source_reliability": 0.10,
}

# Pinned reliability per source type; anything unknown scores 40, not zero.
SOURCE_RELIABILITY: dict[DataSourceType, float] = {
    DataSourceType.EGX: 95.0,
    DataSourceType.FRA: 95.0,
    DataSourceType.COMPANY: 90.0,
    DataSourceType.DATA_PROVIDER: 75.0,
    DataSourceType.MANUAL: 60.0,
    DataSourceType.SYNTHETIC: 20.0,
}
UNKNOWN_SOURCE_RELIABILITY = 40.0

OK_THRESHOLD = 70.0
DEGRADED_THRESHOLD = 40.0
ISSUE_THRESHOLD = 40.0


class DataQualityStatus(enum.StrEnum):
    """Overall verdict for one scope on one date."""

    OK = "OK"
    DEGRADED = "DEGRADED"
    POOR = "POOR"
    MISSING = "MISSING"


@dataclass(frozen=True, slots=True)
class QualityComponent:
    """One weighted input to the overall score; ``score`` is on a 0-100 scale."""

    key: str
    label: str
    score: float
    weight: float
    reason: str


@dataclass(frozen=True, slots=True)
class DataQualityScore:
    """The assessed quality of one scope as of one date."""

    scope: str
    as_of: date
    status: DataQualityStatus
    score: float
    components: tuple[QualityComponent, ...]
    issues: tuple[str, ...]
    methodology_version: str = METHODOLOGY_VERSION

    def as_dict(self) -> dict[str, object]:
        return {
            "scope": self.scope,
            "as_of": self.as_of.isoformat(),
            "status": self.status.value,
            "score": self.score,
            "components": [
                {
                    "key": c.key,
                    "label": c.label,
                    "score": c.score,
                    "weight": c.weight,
                    "reason": c.reason,
                }
                for c in self.components
            ],
            "issues": list(self.issues),
            "methodology_version": self.methodology_version,
        }


def freshness_score(days_stale: int | None) -> float:
    """Map age in days to 0-100; an unknown or negative age scores 0."""
    if days_stale is None or days_stale < 0:
        return 0.0
    if days_stale == 0:
        return 100.0
    if days_stale <= 30:
        return 90.0
    if days_stale <= 90:
        return 70.0
    if days_stale <= 180:
        return 50.0
    if days_stale <= 365:
        return 30.0
    return 10.0


def validation_score(errors: int, warnings: int) -> float:
    """Validation quality: 20 points per error, 5 per warning, floored at 0."""
    return max(0.0, 100.0 - 20.0 * errors - 5.0 * warnings)


def depth_score(observed: int, expected: int) -> float:
    """Share of expected history actually present, clamped to 100."""
    if expected <= 0 or observed <= 0:
        return 0.0
    return min(100.0, 100.0 * observed / expected)


def completeness_score(present: int, required: int) -> float:
    """Share of required items present; a non-positive requirement scores 0."""
    if required <= 0:
        return 0.0
    return 100.0 * present / required


def source_reliability(source_type: DataSourceType | str | None) -> float:
    """Pinned reliability for a source type; unknown, None or unparsable -> 40."""
    member = _source_member(source_type)
    if member is None:
        return UNKNOWN_SOURCE_RELIABILITY
    return SOURCE_RELIABILITY[member]


def aggregate(components: Sequence[QualityComponent]) -> float:
    """Weighted overall score rounded to one decimal.

    Weights sum to 1 and component scores are already 0-100, so the weighted
    sum is itself the 0-100 overall score.
    """
    return round(sum(c.weight * c.score for c in components), 1)


def score_for(
    scope: str,
    as_of: date,
    present: int,
    required: int,
    expected_depth: int,
    days_stale: int | None,
    errors: int,
    warnings: int,
    source_type: DataSourceType | str | None,
    no_rows: bool,
) -> DataQualityScore:
    """Score one scope as of one date; ``no_rows`` forces MISSING with 0.0."""
    completeness = completeness_score(present, required)
    freshness = freshness_score(days_stale)
    validation = validation_score(errors, warnings)
    depth = depth_score(present, expected_depth)
    reliability = source_reliability(source_type)

    components = (
        QualityComponent(
            "completeness",
            "Completeness",
            completeness,
            COMPONENT_WEIGHTS["completeness"],
            f"{present} of {required} required items present",
        ),
        QualityComponent(
            "freshness",
            "Freshness",
            freshness,
            COMPONENT_WEIGHTS["freshness"],
            "age unknown: no reference date"
            if days_stale is None
            else f"{days_stale} days stale",
        ),
        QualityComponent(
            "validation",
            "Validation",
            validation,
            COMPONENT_WEIGHTS["validation"],
            f"{errors} errors, {warnings} warnings",
        ),
        QualityComponent(
            "historical_depth",
            "Historical depth",
            depth,
            COMPONENT_WEIGHTS["historical_depth"],
            f"{present} of {expected_depth} expected periods present",
        ),
        QualityComponent(
            "source_reliability",
            "Source reliability",
            reliability,
            COMPONENT_WEIGHTS["source_reliability"],
            f"source type: {_source_label(source_type)}",
        ),
    )
    issues = tuple(
        f"{c.label} below threshold ({c.score:.0f}/100)"
        for c in components
        if c.score < ISSUE_THRESHOLD
    )

    if no_rows:
        status, score = DataQualityStatus.MISSING, 0.0
    else:
        score = aggregate(components)
        status = _status_for(score)

    return DataQualityScore(
        scope=scope,
        as_of=as_of,
        status=status,
        score=score,
        components=components,
        issues=issues,
    )


def _source_member(source_type: DataSourceType | str | None) -> DataSourceType | None:
    """Resolve an enum member or a case-insensitive string; None when unknown."""
    if source_type is None:
        return None
    if isinstance(source_type, DataSourceType):
        return source_type
    try:
        return DataSourceType(source_type.strip().upper())
    except ValueError:
        return None


def _source_label(source_type: DataSourceType | str | None) -> str:
    member = _source_member(source_type)
    return str(member.value) if member is not None else "unknown"


def _status_for(score: float) -> DataQualityStatus:
    if score >= OK_THRESHOLD:
        return DataQualityStatus.OK
    if score >= DEGRADED_THRESHOLD:
        return DataQualityStatus.DEGRADED
    return DataQualityStatus.POOR
