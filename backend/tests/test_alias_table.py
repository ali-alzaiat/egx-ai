"""Fixture tests for the versioned alias table (spec Review Focus #1)."""


from app.statements.aliases import ALIAS_TABLE_VERSION, ALIASES, resolve_label


def test_alias_table_version() -> None:
    assert ALIAS_TABLE_VERSION == "stmt-extractor-alias-1.0"


def test_core_codes_have_aliases() -> None:
    required = {
        "revenue",
        "net_income",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "gross_profit",
        "cfo",
        "capex",
    }
    assert required.issubset(ALIASES.keys())


def test_resolve_english_variant() -> None:
    assert resolve_label("Net income") == ("net_income", "en")
    assert resolve_label("Profit for the period") == ("net_income", "en")


def test_resolve_arabic_variant() -> None:
    assert resolve_label("صافي الربح") == ("net_income", "ar")
    assert resolve_label("إجمالي الأصول") == ("total_assets", "ar")


def test_unknown_label_returns_none() -> None:
    assert resolve_label("Completely Made Up Label") is None


def test_case_and_whitespace_insensitive() -> None:
    assert resolve_label("  REVENUE  ") == ("revenue", "en")
