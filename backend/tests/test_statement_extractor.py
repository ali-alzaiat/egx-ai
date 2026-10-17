"""Fixture tests for StatementExtractor (Review Focus #1: ambiguity drops, never guesses)."""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

from app.statements.extractor import LineCandidate, StatementExtractor

FIXTURES = Path(__file__).parent / "fixtures" / "filings"


@pytest.fixture(scope="module")
def extractor() -> StatementExtractor:
    return StatementExtractor()


def _candidate_codes(extractor: StatementExtractor, path: Path) -> dict[str, Decimal]:
    result = extractor.extract(
        path.read_bytes(), "application/xml", "annual_report"
    )
    assert not result.drops or all(d.reason for d in result.drops)
    return {c.ontology_code: c.value for c in result.candidates if c.value is not None}


class TestXbrlPath:
    def test_english_xbrl_resolves_codes(self, extractor: StatementExtractor) -> None:
        codes = _candidate_codes(extractor, FIXTURES / "specimen_annual_en.xml")
        assert codes["revenue"] == Decimal("1200000.0")
        assert codes["net_income"] == Decimal("180000.0")
        assert codes["total_assets"] == Decimal("2500000.0")
        assert codes["total_equity"] == Decimal("1500000.0")
        assert codes["cfo"] == Decimal("220000.0")
        assert codes["capex"] == Decimal("60000.0")

    def test_arabic_xbrl_resolves_codes(self, extractor: StatementExtractor) -> None:
        codes = _candidate_codes(extractor, FIXTURES / "specimen_annual_ar.xml")
        assert codes["net_income"] == Decimal("90000.0")
        assert codes["total_assets"] == Decimal("1400000.0")

    def test_ambiguous_label_dropped_not_guessed(
        self, extractor: StatementExtractor
    ) -> None:
        codes = _candidate_codes(extractor, FIXTURES / "specimen_duplicate.xml")
        # "Total liabilities and equity" matches total_liabilities AND total_assets.
        assert "net_income" not in codes
        assert any(
            d.reason == "AMBIGUOUS_ALIAS" and d.label == "Total liabilities and equity"
            for d in extractor.extract(
                (FIXTURES / "specimen_duplicate.xml").read_bytes(),
                "application/xml",
                "annual_report",
            ).drops
        )

    def test_every_candidate_carries_provenance(
        self, extractor: StatementExtractor
    ) -> None:
        result = extractor.extract(
            (FIXTURES / "specimen_annual_en.xml").read_bytes(),
            "application/xml",
            "annual_report",
        )
        for candidate in result.candidates:
            assert isinstance(candidate, LineCandidate)
            assert candidate.source_label_reported.strip()
            assert candidate.extraction_method == "xbrl"
            assert candidate.source_page is None  # xbrl has no page

    def test_currency_is_carried(self, extractor: StatementExtractor) -> None:
        result = extractor.extract(
            (FIXTURES / "specimen_annual_ar.xml").read_bytes(),
            "application/xml",
            "annual_report",
        )
        assert all(c.currency == "EGP" for c in result.candidates)

    def test_unit_element_resolves_currency(self, extractor: StatementExtractor) -> None:
        xml = (
            b"<?xml version='1.0'?><xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance'>"
            b"<xbrli:unit id='u_usd'><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>"
            b"<line item='Total Assets' unitRef='u_usd' decimals='-2'>700000</line>"
            b"<line item='Total Assets' unitRef='nope' decimals='-2'>800000</line>"
            b"</xbrli:xbrl>"
        )
        result = extractor.extract(xml, "application/xml", "annual_report")
        assert result.candidates[0].value == Decimal("700000")
        assert result.candidates[0].currency == "USD"
        assert any(d.reason == "NO_CURRENCY" for d in result.drops)

    def test_undeclared_unit_shorthand_is_used(self, extractor: StatementExtractor) -> None:
        xml = (
            b"<?xml version='1.0'?><xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance'>"
            b"<line item='Total Assets' unitRef='EGP' decimals='-2'>700000</line>"
            b"</xbrli:xbrl>"
        )
        result = extractor.extract(xml, "application/xml", "annual_report")
        assert result.candidates[0].currency == "EGP"

    def test_long_unit_shorthand_not_guessed(self, extractor: StatementExtractor) -> None:
        xml = (
            b"<?xml version='1.0'?><xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance'>"
            b"<line item='Total Assets' unitRef='millions' decimals='-2'>700000</line>"
            b"</xbrli:xbrl>"
        )
        result = extractor.extract(xml, "application/xml", "annual_report")
        assert result.candidates == []
        assert [d.reason for d in result.drops] == ["NO_CURRENCY"]


class TestDuplicateCodes:
    def test_second_occurrence_dropped_not_crashing(self, extractor: StatementExtractor) -> None:
        xml = (
            b"<?xml version='1.0'?><xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance'>"
            b"<line item='Total Assets' unitRef='EGP' decimals='-2'>700</line>"
            b"<line item='Total Assets' unitRef='EGP' decimals='-2'>900</line>"
            b"</xbrli:xbrl>"
        )
        result = extractor.extract(xml, "application/xml", "annual_report")
        assert len(result.candidates) == 1
        assert result.candidates[0].value == Decimal("700")
        assert [d.reason for d in result.drops] == ["DUPLICATE_CODE"]


def _run_pytest() -> None:  # pragma: no cover - direct run convenience
    import subprocess

    subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"])


if __name__ == "__main__":
    _run_pytest()
