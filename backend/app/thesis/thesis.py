"""Pure, deterministic investment-thesis builders.

No I/O, no clock, no database, no LLM: every string returned here is a
template filled from caller-supplied rows. Numbers that cannot resolve to a
stored row render INSUFFICIENT_DATA — never zero, never guessed.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.thesis.constants import (
    CATALYST_SKELETON,
    DEFAULT_INVALIDATIONS,
    INVALIDATION_STATUSES,
    MAX_BULL_BEAR_CASES,
    MAX_INVALIDATIONS,
    MIN_INVALIDATIONS,
    PRECOMMITTED_ACTION,
    SKELETON_PROVENANCE,
    THESIS_DISCLAIMER,
)
from app.valuation.fairvalue import Confidence, confidence_for_dq


@dataclass(frozen=True, slots=True)
class AssumptionRow:
    """One labelled thesis assumption (SWS 5-question worksheet unit)."""

    metric: str
    value: str | None
    horizon: str | None
    source: str
    author: str


@dataclass(frozen=True, slots=True)
class InvalidationSpec:
    """One stored invalidation condition (ThesisCheck/Synoptiv shape)."""

    metric: str
    threshold: Decimal
    direction: str
    period: str
    evidence_source: str


@dataclass(frozen=True, slots=True)
class InvalidationView:
    """Invalidation condition plus its evaluated status for rendering."""

    metric: str
    threshold: Decimal
    direction: str
    period: str
    evidence_source: str
    status: str
    extraction_confidence: str


@dataclass(frozen=True, slots=True)
class CatalystView:
    """One catalyst record for rendering."""

    event: str
    window: str | None
    variable: str | None
    expectation: str | None
    outcome: str
    label: str
    provenance: str


def evaluate_breach(
    latest: Decimal | None, threshold: Decimal, direction: str
) -> tuple[bool, str]:
    """Compare the latest stored metric against a threshold.

    Missing data never breaches: the condition stays Active with an
    INSUFFICIENT_DATA note instead of defaulting to zero or firing.
    """
    if latest is None:
        return (
            False,
            "INSUFFICIENT_DATA: no latest metric value on file; "
            "nothing is assumed and the condition stays Active.",
        )
    breached = latest < threshold if direction == "below" else latest > threshold
    verb = "breaches" if breached else "holds against"
    return (
        breached,
        f"Latest {latest} {verb} {direction} {threshold}; "
        "filing-lag applies (EGX disclosures are PDF-only).",
    )


def pad_invalidation_specs(
    specs: list[InvalidationSpec],
) -> list[InvalidationSpec]:
    """Pad caller specs with methodology defaults up to the 2-condition minimum.

    Raises ValueError when more than the 4-condition maximum is supplied.
    """
    if len(specs) > MAX_INVALIDATIONS:
        raise ValueError(
            f"At most {MAX_INVALIDATIONS} invalidation conditions per thesis; "
            f"got {len(specs)}."
        )
    padded = list(specs)
    for metric, threshold, direction, period, evidence_source in DEFAULT_INVALIDATIONS:
        if len(padded) >= MIN_INVALIDATIONS:
            break
        if any(s.metric == metric for s in padded):
            continue
        padded.append(
            InvalidationSpec(
                metric=metric,
                threshold=Decimal(threshold),
                direction=direction,
                period=period,
                evidence_source=evidence_source,
            )
        )
    return padded


def check_catalyst_label(event: str, label: str) -> None:
    """Enforce Tentative-only Shariah33 membership catalysts.

    The EGX33 methodology PDF is `no data` (research §5), so an index
    in/out event must never be presented as Confirmed.
    """
    if "shariah" in event.casefold() and label == "Confirmed":
        raise ValueError(
            "Shariah33 membership catalysts are Tentative only: "
            "the index methodology is not on file."
        )


def extraction_confidence_for(dq_status: str | None) -> str:
    """Map a filings data-quality status onto per-check extraction confidence."""
    if dq_status == "OK":
        return "High"
    if dq_status == "DEGRADED":
        return "Medium"
    return "Low"


def thesis_confidence_for(
    dq_score: float | None,
    dq_status: str | None,
    score_present: bool,
) -> Confidence:
    """DataQualityScore-fed confidence ladder (caps at POOR/MISSING).

    Reuses the Phase-3 ladder, then caps at POOR when no investment-score
    assessment is on file: a thesis without a score must not read confident.
    """
    base = confidence_for_dq(dq_score, dq_status)
    if score_present or base.level in ("POOR", "MISSING"):
        return base
    return Confidence(
        level="POOR",
        required_discount=base.required_discount,
        dq_score=base.dq_score,
        dq_status=base.dq_status,
        reason=base.reason + "; no investment-score assessment on file",
    )


def skeleton_catalysts() -> list[CatalystView]:
    """Deterministic catalyst skeleton from the mandated EGX cadence."""
    return [
        CatalystView(
            event=event,
            window=window,
            variable=variable,
            expectation=expectation,
            outcome="Pending",
            label="Tentative",
            provenance=SKELETON_PROVENANCE,
        )
        for event, window, variable, expectation in CATALYST_SKELETON
    ]


def _pad_cases(cases: list[str]) -> list[str | None]:
    """Pad bull/bear cases to three slots; missing slots stay explicit nulls."""
    padded: list[str | None] = list(cases[:MAX_BULL_BEAR_CASES])
    while len(padded) < MAX_BULL_BEAR_CASES:
        padded.append(None)
    return padded


def render_invalidation_line(invalidations: list[InvalidationView]) -> str:
    """Render the stored-invalidation sentence shared by assess and update."""
    if invalidations:
        inv = " ".join(
            f"({i}) {v.metric} {v.direction} {v.threshold} over {v.period} "
            f"(evidence: {v.evidence_source}; status: {v.status}; "
            f"extraction confidence: {v.extraction_confidence})."
            for i, v in enumerate(invalidations, start=1)
        )
    else:
        inv = "INSUFFICIENT_DATA: no stored conditions."
    return (
        f"Invalidation ({len(invalidations)} stored conditions; a trigger forces "
        f"{PRECOMMITTED_ACTION}, never a sale): {inv}"
    )


def render_catalyst_line(catalysts: list[CatalystView]) -> str:
    """Render the catalyst sentence shared by assess and update."""
    if catalysts:
        cat = " ".join(
            f"({i}) {c.event} [{c.window or 'undated'}] tests "
            f"{c.variable or 'unstated variable'}; expects "
            f"{c.expectation or 'unstated expectation'}; outcome {c.outcome}; "
            f"{c.label} (provenance: {c.provenance})."
            for i, c in enumerate(catalysts, start=1)
        )
    else:
        cat = "INSUFFICIENT_DATA: no catalyst records."
    return f"Catalysts ({len(catalysts)} tracked): {cat}"


def refresh_stored_lines(
    narrative: str,
    invalidations: list[InvalidationView],
    catalysts: list[CatalystView],
) -> str:
    """Re-render the invalidation + catalyst sentences inside a saved narrative.

    Updates never rewrite history: only the two stored-record sentences are
    replaced so the narrative keeps matching the rows after a status change.
    """
    text = narrative
    start = text.find("Invalidation (")
    end = text.find(" Catalysts (")
    if start != -1 and end != -1:
        text = text[:start] + render_invalidation_line(invalidations) + text[end + 1 :]
    start = text.find("Catalysts (")
    end = text.find(" Data quality: ")
    if start != -1 and end != -1:
        text = text[:start] + render_catalyst_line(catalysts) + text[end + 1 :]
    return text


def render_narrative(
    ticker: str,
    horizon_years: int,
    is_shareholder: bool | None,
    fair_value: str | None,
    fair_value_status: str,
    fair_value_reason: str | None,
    fair_value_version: str | None,
    fair_value_sources: str,
    assumptions: list[AssumptionRow],
    bulls: list[str],
    bears: list[str],
    scenarios: dict[str, str | None],
    scenario_statuses: dict[str, str],
    scenarios_note: str,
    invalidations: list[InvalidationView],
    catalysts: list[CatalystView],
    dq_summary: str,
    confidence_level: str,
    confidence_reason: str,
) -> str:
    """Render the structured thesis as deterministic template text.

    Every number comes from a stored row passed in by the caller; anything
    unresolvable renders INSUFFICIENT_DATA. No LLM, no invented facts.
    """
    shareholder = (
        "shareholder: yes"
        if is_shareholder is True
        else ("shareholder: no" if is_shareholder is False else "shareholder: undisclosed")
    )
    fv_line = (
        f"Own fair value: {fair_value} [{fair_value_status}]"
        if fair_value is not None
        else f"Own fair value: INSUFFICIENT_DATA [{fair_value_status}]"
    )
    if fair_value_reason:
        fv_line += f" ({fair_value_reason})"
    fv_line += f" (valuation {fair_value_version or 'unassessed'}; {fair_value_sources})."

    if assumptions:
        evolution = " ".join(
            f"{a.metric} {a.value} over {a.horizon or 'unstated horizon'} "
            f"(source: {a.source}; author: {a.author})."
            if a.value is not None
            else f"{a.metric}: INSUFFICIENT_DATA over {a.horizon or 'unstated horizon'} "
            f"(source: {a.source}; author: {a.author})."
            for a in assumptions
        )
    else:
        evolution = "INSUFFICIENT_DATA: no labelled assumptions on file."

    def _cases(label: str, cases: list[str]) -> str:
        lines = []
        for i, case in enumerate(_pad_cases(cases), start=1):
            lines.append(f"({i}) {case}" if case else f"({i}) INSUFFICIENT_DATA: no case supplied")
        return f"{label} (assumption-shifters): " + " ".join(lines) + "."

    impact = (
        f"Bear {scenarios.get('bear') or 'INSUFFICIENT_DATA'} "
        f"[{scenario_statuses.get('bear', 'INSUFFICIENT_DATA')}] / "
        f"Base {scenarios.get('base') or 'INSUFFICIENT_DATA'} "
        f"[{scenario_statuses.get('base', 'INSUFFICIENT_DATA')}] / "
        f"Bull {scenarios.get('bull') or 'INSUFFICIENT_DATA'} "
        f"[{scenario_statuses.get('bull', 'INSUFFICIENT_DATA')}]. {scenarios_note}"
    )

    inv_line = render_invalidation_line(invalidations)

    cat_line = render_catalyst_line(catalysts)

    return (
        f"Investment thesis for {ticker} ({horizon_years}-year horizon; {shareholder}). "
        f"{fv_line} "
        f"Business evolution: {evolution} "
        f"{_cases('Bull cases', bulls)} {_cases('Bear cases', bears)} "
        f"Revenue, margin, and earning-power impact: {impact} "
        f"{inv_line} "
        f"{cat_line} "
        f"Data quality: {dq_summary}; confidence {confidence_level} ({confidence_reason}). "
        f"{THESIS_DISCLAIMER}"
    )


def validate_statuses(statuses: tuple[str, ...]) -> None:
    """Reject unknown invalidation statuses (kept explicit, never coerced)."""
    for status in statuses:
        if status not in INVALIDATION_STATUSES:
            raise ValueError(
                f"Unknown invalidation status {status!r}; "
                f"expected one of {', '.join(INVALIDATION_STATUSES)}."
            )
