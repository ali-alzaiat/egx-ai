"""Tests for the pure, deterministic data-quality scoring functions."""

from datetime import date

from app.dataquality.scores import (
    COMPONENT_WEIGHTS,
    METHODOLOGY_VERSION,
    DataQualityScore,
    DataQualityStatus,
    QualityComponent,
    aggregate,
    completeness_score,
    depth_score,
    freshness_score,
    score_for,
    source_reliability,
    validation_score,
)
from app.models.market import DataSourceType

AS_OF = date(2026, 10, 8)


def _score(
    present: int = 10,
    required: int = 10,
    expected_depth: int = 10,
    days_stale: int | None = 0,
    errors: int = 0,
    warnings: int = 0,
    source_type: DataSourceType | str | None = DataSourceType.EGX,
    no_rows: bool = False,
    scope: str = "price_history",
) -> DataQualityScore:
    """Score a scope with defaults that yield a near-perfect result."""
    return score_for(
        scope=scope,
        as_of=AS_OF,
        present=present,
        required=required,
        expected_depth=expected_depth,
        days_stale=days_stale,
        errors=errors,
        warnings=warnings,
        source_type=source_type,
        no_rows=no_rows,
    )


class TestWeights:
    def test_weights_sum_to_exactly_one(self):
        assert sum(COMPONENT_WEIGHTS.values()) == 1.0

    def test_weights_cover_every_component_key(self):
        assert set(COMPONENT_WEIGHTS) == {
            "completeness",
            "freshness",
            "validation",
            "historical_depth",
            "source_reliability",
        }


class TestFreshnessScore:
    def test_boundaries(self):
        assert freshness_score(0) == 100.0
        assert freshness_score(30) == 90.0
        assert freshness_score(31) == 70.0
        assert freshness_score(90) == 70.0
        assert freshness_score(91) == 50.0
        assert freshness_score(180) == 50.0
        assert freshness_score(181) == 30.0
        assert freshness_score(365) == 30.0
        assert freshness_score(366) == 10.0

    def test_unknown_age_scores_zero(self):
        assert freshness_score(None) == 0.0

    def test_negative_age_scores_zero(self):
        assert freshness_score(-1) == 0.0


class TestValidationScore:
    def test_one_error_costs_twenty(self):
        assert validation_score(1, 0) == 80.0

    def test_five_warnings_cost_twenty_five(self):
        assert validation_score(0, 5) == 75.0

    def test_combined_penalties(self):
        assert validation_score(1, 5) == 55.0

    def test_floors_at_zero(self):
        assert validation_score(10, 0) == 0.0
        assert validation_score(0, 40) == 0.0


class TestDepthScore:
    def test_observed_above_expected_clamps_at_100(self):
        assert depth_score(15, 10) == 100.0

    def test_proportional_below_expected(self):
        assert depth_score(5, 10) == 50.0

    def test_zero_inputs_score_zero(self):
        assert depth_score(0, 0) == 0.0
        assert depth_score(0, 10) == 0.0
        assert depth_score(5, 0) == 0.0


class TestCompletenessScore:
    def test_three_of_five_present_when_two_missing(self):
        assert completeness_score(3, 5) == 60.0

    def test_all_present(self):
        assert completeness_score(5, 5) == 100.0

    def test_non_positive_requirement_scores_zero(self):
        assert completeness_score(0, 0) == 0.0
        assert completeness_score(5, 0) == 0.0


class TestSourceReliability:
    def test_synthetic_is_at_most_twenty(self):
        assert source_reliability(DataSourceType.SYNTHETIC) <= 20.0

    def test_egx_is_at_least_ninety(self):
        assert source_reliability(DataSourceType.EGX) >= 90.0

    def test_pinned_values(self):
        assert source_reliability(DataSourceType.FRA) == 95.0
        assert source_reliability(DataSourceType.COMPANY) == 90.0
        assert source_reliability(DataSourceType.DATA_PROVIDER) == 75.0
        assert source_reliability(DataSourceType.MANUAL) == 60.0

    def test_plain_strings_match_members_case_insensitively(self):
        assert source_reliability("egx") == source_reliability(DataSourceType.EGX)
        assert source_reliability("Synthetic") == 20.0
        assert source_reliability("data_provider") == 75.0

    def test_unknown_falls_back_to_forty(self):
        assert source_reliability(None) == 40.0
        assert source_reliability("not_a_source") == 40.0
        assert source_reliability("") == 40.0


class TestAggregate:
    def test_rounds_to_one_decimal(self):
        third = QualityComponent("x", "X", 100.0 / 3.0, 1.0, "a third")
        assert aggregate([third]) == 33.3

    def test_weighted_sum_over_pinned_weights(self):
        components = tuple(
            QualityComponent(key, key, score, COMPONENT_WEIGHTS[key], "pinned weight")
            for key, score in zip(
                COMPONENT_WEIGHTS,
                (7.0, 11.0, 13.0, 17.0, 19.0),
                strict=True,
            )
        )
        assert aggregate(components) == 11.9

    def test_no_components_scores_zero(self):
        assert aggregate([]) == 0.0


class TestScoreFor:
    def test_healthy_inputs_are_ok(self):
        result = _score()
        assert result.status is DataQualityStatus.OK
        assert result.score == 99.5

    def test_no_rows_is_missing_with_zero_score(self):
        result = _score(no_rows=True, present=0, days_stale=None, source_type=None)
        assert result.status is DataQualityStatus.MISSING
        assert result.score == 0.0

    def test_degraded_band(self):
        result = _score(
            present=5,
            required=10,
            days_stale=100,
            errors=1,
            source_type=DataSourceType.MANUAL,
        )
        assert result.status is DataQualityStatus.DEGRADED
        assert result.score == 57.0

    def test_poor_band(self):
        result = _score(
            present=1,
            required=10,
            days_stale=400,
            errors=5,
            source_type=DataSourceType.SYNTHETIC,
        )
        assert result.status is DataQualityStatus.POOR
        assert result.score == 9.0

    def test_seventy_is_ok(self):
        result = _score(
            days_stale=50,
            errors=5,
            source_type=DataSourceType.DATA_PROVIDER,
        )
        assert result.score == 70.0
        assert result.status is DataQualityStatus.OK

    def test_forty_is_degraded(self):
        result = _score(
            present=0,
            required=10,
            days_stale=180,
            source_type=DataSourceType.DATA_PROVIDER,
        )
        assert result.score == 40.0
        assert result.status is DataQualityStatus.DEGRADED

    def test_components_use_pinned_weights_in_order(self):
        result = _score()
        assert [c.key for c in result.components] == list(COMPONENT_WEIGHTS)
        assert [c.weight for c in result.components] == list(COMPONENT_WEIGHTS.values())

    def test_depth_component_observed_comes_from_present(self):
        result = _score(present=20, required=20, expected_depth=10)
        depth = next(c for c in result.components if c.key == "historical_depth")
        assert depth.score == 100.0
        assert result.score == 99.5

    def test_issues_list_components_below_forty(self):
        result = _score(
            present=1,
            required=10,
            days_stale=400,
            errors=5,
            source_type=DataSourceType.SYNTHETIC,
        )
        assert len(result.issues) == 5

    def test_healthy_inputs_produce_no_issues(self):
        assert _score().issues == ()

    def test_as_dict_exposes_every_component_key(self):
        data = _score().as_dict()
        assert set(data) == {
            "scope",
            "as_of",
            "status",
            "score",
            "components",
            "issues",
            "methodology_version",
        }
        component_keys = {component["key"] for component in data["components"]}
        assert component_keys == set(COMPONENT_WEIGHTS)

    def test_as_dict_serialises_scalars(self):
        data = _score(scope="company_profile").as_dict()
        assert data["scope"] == "company_profile"
        assert data["as_of"] == "2026-10-08"
        assert data["status"] == "OK"
        assert data["methodology_version"] == METHODOLOGY_VERSION == "1.0"
        for component in data["components"]:
            assert set(component) == {"key", "label", "score", "weight", "reason"}
            assert component["reason"]

    def test_methodology_version_defaults_on_the_score(self):
        assert _score().methodology_version == "1.0"
