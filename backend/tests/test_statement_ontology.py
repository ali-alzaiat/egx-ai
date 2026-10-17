"""Tests for the statement ontology (stmt-ontology-1.0)."""

import pytest

from app.statements.ontology import (
    STATEMENT_LINES,
    STATEMENT_ONTOLOGY_VERSION,
    LineSection,
    StatementLine,
    line,
)

EXPECTED_INCOME = [
    "revenue",
    "cost_of_revenue",
    "gross_profit",
    "selling_expenses",
    "admin_expenses",
    "operating_expenses",
    "operating_profit",
    "finance_costs",
    "income_tax",
    "net_income",
    "eps",
]

EXPECTED_BALANCE = [
    "total_assets",
    "current_assets",
    "cash_and_equivalents",
    "interest_bearing_assets",
    "inventory",
    "non_current_assets",
    "total_liabilities",
    "current_liabilities",
    "interest_bearing_debt",
    "total_equity",
    "minority_interests",
]

EXPECTED_CASH = [
    "cfo",
    "cfi",
    "cff",
    "capex",
    "dividends_paid",
    "debt_repayment",
]


def test_ontology_version_constant() -> None:
    assert STATEMENT_ONTOLOGY_VERSION == "stmt-ontology-1.0"


def test_income_codes_present() -> None:
    assert [
        c for c, s in STATEMENT_LINES.items() if s.section is LineSection.INCOME
    ] == EXPECTED_INCOME


def test_balance_codes_present() -> None:
    assert [
        c for c, s in STATEMENT_LINES.items() if s.section is LineSection.BALANCE
    ] == EXPECTED_BALANCE


def test_cash_flow_codes_present() -> None:
    assert [
        c for c, s in STATEMENT_LINES.items() if s.section is LineSection.CASH_FLOW
    ] == EXPECTED_CASH


def test_all_codes_have_labels() -> None:
    for code, s in STATEMENT_LINES.items():
        assert isinstance(s, StatementLine)
        assert s.label_en.strip(), f"missing EN label for {code}"
        assert s.label_ar.strip(), f"missing AR label for {code}"


def test_line_lookup_sections() -> None:
    assert line("gross_profit").section is LineSection.INCOME
    assert line("total_assets").section is LineSection.BALANCE
    assert line("cfo").section is LineSection.CASH_FLOW


def test_unknown_code_raises() -> None:
    with pytest.raises(KeyError):
        line("no_such_line")
