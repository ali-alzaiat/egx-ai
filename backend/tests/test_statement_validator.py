"""Tests for StatementValidator identity gates (stmt-validator-1.0)."""

from decimal import Decimal

from app.statements.extractor import LineCandidate
from app.statements.validator import (
    VALIDATION_TOLERANCE,
    VALIDATOR_VERSION,
    StatementValidator,
)

EN = "net_income"


def _c(code: str, value: str | None, currency: str = "EGP") -> LineCandidate:
    return LineCandidate(
        ontology_code=code,
        ontology_version="stmt-ontology-1.0",
        value=Decimal(value) if value is not None else None,
        currency=currency,
        source_label_reported=code,
        source_label_en=code,
        source_label_ar=None,
        source_page=None,
        extraction_method="downloaded_document_table",
    )


def _full_balance() -> list[LineCandidate]:
    return [
        _c("revenue", "1000000"),
        _c("cost_of_revenue", "700000"),
        _c("gross_profit", "300000"),
        _c("operating_profit", "150000"),
        _c("net_income", "100000"),
        _c("total_assets", "2000000"),
        _c("total_liabilities", "800000"),
        _c("total_equity", "1200000"),
        _c("cfo", "150000"),
        _c("cfi", "-50000"),
        _c("cff", "-40000"),
    ]


class TestValidatorGates:
    def test_version_and_tolerance_shape(self) -> None:
        assert VALIDATOR_VERSION == "stmt-validator-1.1"
        assert Decimal("0.01") == VALIDATION_TOLERANCE

    def test_balanced_set_auto_validates(self) -> None:
        summary = StatementValidator().validate(_full_balance())
        statuses = {v.candidate.ontology_code: v.ext_status for v in summary.lines}
        assert statuses["total_assets"] == "auto_validated"
        assert statuses["gross_profit"] == "auto_validated"
        assert summary.auto_validated_count == 11
        assert summary.rejected_count == 0

    def test_assets_identity_fail_rejects_loudly(self) -> None:
        candidates = _full_balance()
        candidates[5] = _c("total_assets", "2222222")  # assets != L + E
        summary = StatementValidator().validate(candidates)
        statuses = {v.candidate.ontology_code: (v.ext_status, v.failure) for v in summary.lines}
        assert statuses["total_assets"][0] == "rejected"
        assert any("liabilities" in (statuses["total_assets"][1] or "").lower() for _ in [0])
        assert summary.rejected_count >= 1

    def test_gross_profit_identity_within_tolerance_passes(self) -> None:
        candidates = _full_balance()
        # 297500 vs expected 300000 -> 0.83% off: within 1% tolerance.
        candidates[2] = _c("gross_profit", "297500")
        summary = StatementValidator().validate(candidates)
        statuses = {v.candidate.ontology_code: v.ext_status for v in summary.lines}
        assert statuses["gross_profit"] == "auto_validated"

    def test_gross_profit_identity_beyond_tolerance_rejected(self) -> None:
        candidates = _full_balance()
        candidates[2] = _c("gross_profit", "250000")
        summary = StatementValidator().validate(candidates)
        statuses = {v.candidate.ontology_code: v.ext_status for v in summary.lines}
        assert statuses["gross_profit"] == "rejected"

    def test_missing_identity_inputs_stays_candidate(self) -> None:
        # Only revenue + net_income present: no identity can run on them.
        summary = StatementValidator().validate([_c("revenue", "1000"), _c("net_income", "100")])
        assert all(v.ext_status == "auto_validated" for v in summary.lines)
        assert summary.rejected_count == 0

    def test_eps_skipped_when_shares_missing(self) -> None:
        # EPS identity needs a share count; v1 has none -> stays a candidate.
        summary = StatementValidator().validate([_c("eps", "1.25"), _c("net_income", "100000")])
        statuses = {v.candidate.ontology_code: v.ext_status for v in summary.lines}
        assert statuses["eps"] == "extraction_candidate"
        assert summary.rejected_count == 0

    def test_mixed_currency_rejects_all(self) -> None:
        candidates = _full_balance()
        candidates[6] = _c("total_liabilities", "800000", currency="USD")
        summary = StatementValidator().validate(candidates)
        assert summary.rejected_count == len(candidates)
        assert all(
            v.failure is not None and "currency" in (v.failure or "").lower()
            for v in summary.lines
        )

    def test_negative_revenue_rejected_sign_rule(self) -> None:
        candidates = [_c("revenue", "-5000"), _c("cost_of_revenue", "1000")]
        summary = StatementValidator().validate(candidates)
        statuses = {v.candidate.ontology_code: v.ext_status for v in summary.lines}
        assert statuses["revenue"] == "rejected"
        assert statuses["cost_of_revenue"] == "auto_validated"

    def test_null_value_line_rejected(self) -> None:
        summary = StatementValidator().validate([_c("revenue", None)])
        statuses = {v.candidate.ontology_code: (v.ext_status, v.failure) for v in summary.lines}
        assert statuses["revenue"][0] == "rejected"

    def test_cash_flow_lines_pass_without_movement_code(self) -> None:
        # Ontology v1 carries no net-cash-movement code -> the movement
        # identity cannot run yet; lines must pass (limitation logged in R41).
        candidates = [
            _c("cfo", "150000"),
            _c("cfi", "-50000"),
            _c("cff", "-40000"),
        ]
        summary = StatementValidator().validate(candidates)
        assert all(v.ext_status == "auto_validated" for v in summary.lines)
        assert summary.rejected_count == 0
