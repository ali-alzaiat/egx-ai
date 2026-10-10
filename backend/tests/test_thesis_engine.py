"""Unit tests for the pure thesis builders (no I/O, deterministic)."""

from decimal import Decimal

import pytest

from app.thesis import thesis as engine
from app.thesis.constants import THESIS_METHODOLOGY_VERSION


def test_breach_below_fires_and_holds() -> None:
    breached, note = engine.evaluate_breach(Decimal("-0.05"), Decimal("0"), "below")
    assert breached is True
    assert "-0.05" in note and "0" in note

    held, _ = engine.evaluate_breach(Decimal("0.05"), Decimal("0"), "below")
    assert held is False


def test_breach_above_with_negative_threshold() -> None:
    breached, _ = engine.evaluate_breach(Decimal("1.5"), Decimal("1.25"), "above")
    assert breached is True
    held, _ = engine.evaluate_breach(Decimal("1.0"), Decimal("1.25"), "above")
    assert held is False


def test_breach_at_threshold_does_not_fire() -> None:
    breached, _ = engine.evaluate_breach(Decimal("0"), Decimal("0"), "below")
    assert breached is False
    breached, _ = engine.evaluate_breach(Decimal("0"), Decimal("0"), "above")
    assert breached is False


def test_breach_missing_never_fires_and_never_zero_fills() -> None:
    breached, note = engine.evaluate_breach(None, Decimal("0"), "below")
    assert breached is False
    assert "INSUFFICIENT_DATA" in note
    assert "stays Active" in note


def test_pad_specs_adds_methodology_defaults() -> None:
    padded = engine.pad_invalidation_specs([])
    assert len(padded) == 2
    assert [s.metric for s in padded] == ["revenue_growth_yoy", "operating_margin"]
    assert all(s.threshold == Decimal("0") for s in padded)


def test_pad_specs_skips_duplicate_default_metric() -> None:
    custom = engine.InvalidationSpec(
        metric="revenue_growth_yoy",
        threshold=Decimal("0.10"),
        direction="below",
        period="annual",
        evidence_source="annual_financial_statements",
    )
    padded = engine.pad_invalidation_specs([custom])
    assert len(padded) == 2
    assert padded[0] == custom
    assert padded[1].metric == "operating_margin"


def test_pad_specs_rejects_more_than_four() -> None:
    specs = [
        engine.InvalidationSpec(
            metric=f"m{i}",
            threshold=Decimal("0"),
            direction="below",
            period="annual",
            evidence_source="annual_financial_statements",
        )
        for i in range(5)
    ]
    with pytest.raises(ValueError, match="At most 4"):
        engine.pad_invalidation_specs(specs)


def test_shariah_confirmed_rejected_tentative_allowed() -> None:
    with pytest.raises(ValueError, match="Tentative only"):
        engine.check_catalyst_label("Shariah33 index out", "Confirmed")
    with pytest.raises(ValueError, match="Tentative only"):
        engine.check_catalyst_label("shariah membership review", "Confirmed")
    engine.check_catalyst_label("Shariah33 index out", "Tentative")
    engine.check_catalyst_label("Q2 earnings release", "Confirmed")


def test_extraction_confidence_mapping() -> None:
    assert engine.extraction_confidence_for("OK") == "High"
    assert engine.extraction_confidence_for("DEGRADED") == "Medium"
    assert engine.extraction_confidence_for("POOR") == "Low"
    assert engine.extraction_confidence_for("MISSING") == "Low"
    assert engine.extraction_confidence_for(None) == "Low"


def test_thesis_confidence_caps() -> None:
    missing = engine.thesis_confidence_for(0.0, "MISSING", True)
    assert missing.level == "MISSING"

    no_assessment = engine.thesis_confidence_for(None, None, True)
    assert no_assessment.level == "POOR"

    capped = engine.thesis_confidence_for(85.0, "OK", False)
    assert capped.level == "POOR"
    assert "no investment-score assessment" in capped.reason

    kept = engine.thesis_confidence_for(85.0, "OK", True)
    assert kept.level == "VeryHigh"


def _narrative(**overrides: object) -> str:
    base: dict[str, object] = {
        "ticker": "COMI",
        "horizon_years": 5,
        "is_shareholder": None,
        "fair_value": "60.00",
        "fair_value_status": "AVAILABLE",
        "fair_value_reason": None,
        "fair_value_version": "1.0",
        "fair_value_sources": "inputs revenue_growth via metric:revenue_growth_yoy",
        "assumptions": [
            engine.AssumptionRow(
                metric="revenue",
                value="5%/yr",
                horizon="5 years",
                source="filing.pdf",
                author="caller",
            )
        ],
        "bulls": ["Ecosystem lock-in"],
        "bears": ["Regulation"],
        "scenarios": {"bear": "40", "base": "60", "bull": "85"},
        "scenario_statuses": {
            "bear": "AVAILABLE",
            "base": "AVAILABLE",
            "bull": "AVAILABLE",
        },
        "scenarios_note": "A range, not a target.",
        "invalidations": [
            engine.InvalidationView(
                metric="revenue_growth_yoy",
                threshold=Decimal("0"),
                direction="below",
                period="two consecutive quarters",
                evidence_source="quarterly_financial_statements",
                status="Active",
                extraction_confidence="High",
            )
        ],
        "catalysts": [
            engine.CatalystView(
                event="Q2 results",
                window="quarterly",
                variable="earnings_power",
                expectation="in line",
                outcome="Pending",
                label="Tentative",
                provenance="https://example.com/disclosure",
            )
        ],
        "dq_summary": "financial-statements 85.0/OK",
        "confidence_level": "High",
        "confidence_reason": "Financial-statements quality score 85.0/100",
    }
    base.update(overrides)
    return engine.render_narrative(**base)  # type: ignore[arg-type]


def test_narrative_is_deterministic_template() -> None:
    assert _narrative() == _narrative()
    text = _narrative()
    assert "Investment thesis for COMI" in text
    assert "documented_reassessment, never a sale" in text
    assert "potentially informative, not a recommendation" in text
    assert "BUY" not in text and "SELL" not in text


def test_narrative_missing_renders_insufficient_data() -> None:
    text = _narrative(
        fair_value=None,
        fair_value_status="INSUFFICIENT_DATA",
        fair_value_reason="No model leg produced a value.",
        assumptions=[],
        bulls=[],
        scenarios={"bear": None, "base": None, "bull": None},
        scenario_statuses={},
        invalidations=[],
        catalysts=[],
    )
    assert "Own fair value: INSUFFICIENT_DATA [INSUFFICIENT_DATA]" in text
    assert "no labelled assumptions on file" in text
    assert "INSUFFICIENT_DATA: no case supplied" in text
    assert "no stored conditions" in text
    assert "no catalyst records" in text
    assert "0" not in text.split("INSUFFICIENT_DATA")[0].split("horizon")[0]


def test_skeleton_catalysts_all_tentative_with_provenance() -> None:
    skeleton = engine.skeleton_catalysts()
    assert len(skeleton) == 5
    for row in skeleton:
        assert row.label == "Tentative"
        assert row.outcome == "Pending"
        assert row.provenance.startswith("http")


def test_refresh_stored_lines_keeps_history_intact() -> None:
    before = _narrative()
    views = [
        engine.InvalidationView(
            metric="revenue_growth_yoy",
            threshold=Decimal("0"),
            direction="below",
            period="two consecutive quarters",
            evidence_source="quarterly_financial_statements",
            status="Reassessed",
            extraction_confidence="High",
        )
    ]
    catalysts = engine.skeleton_catalysts()
    after = engine.refresh_stored_lines(before, views, catalysts)
    assert "status: Reassessed" in after
    assert "Investment thesis for COMI" in after
    assert after.count("Business evolution:") == 1
    assert THESIS_METHODOLOGY_VERSION is not None
