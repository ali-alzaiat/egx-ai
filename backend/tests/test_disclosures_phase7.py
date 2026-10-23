"""Phase-7 document intelligence tests (R34 P0-1–P0-6).

Pure-engine tests (hash, numerals, confidence, TTM/YoY, diffs, restatement
detection, provenance shape) run without a database; service/API tests use the
rolled-back ``db_session`` fixture. Every financial formula covers zero,
negative, and missing inputs per AGENTS.md rule 7.
"""

import sys
import types
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.disclosures import methodology_version
from app.core.config import settings
from app.ingestion.disclosures import parse as parse_mod
from app.ingestion.disclosures.comparison import (
    compute_ttm,
    margin_vs_prior_year,
    quantize4,
    ttm_margin,
    yoy_delta,
)
from app.ingestion.disclosures.constants import (
    DISCLOSURE_METHODOLOGY_VERSION,
    MAX_PDF_BYTES,
)
from app.ingestion.disclosures.diffs import (
    FactVersion,
    beat_or_miss,
    build_diff_row,
    restatement_decision,
    select_as_of,
)
from app.ingestion.disclosures.facts import (
    BasisMixError,
    ensure_comparable_basis,
    fact_payload,
    validate_eas_tags,
)
from app.ingestion.disclosures.intake import (
    MAX_PDF_BYTES as INTAKE_MAX,
)
from app.ingestion.disclosures.intake import (
    check_upload_bytes,
    compute_content_hash,
    filing_period_bounds,
    registration_hash_for_url,
    validate_accounting_basis,
    validate_filing_type,
)
from app.ingestion.disclosures.parse import (
    ParsingReport,
    RawTable,
    detect_scanned,
    fill_rate_confidence,
    parse_filing_bytes,
    parse_numeral,
    parsing_confidence,
    tables_to_cells,
)
from app.ingestion.disclosures.service import DisclosureService
from app.models.disclosure import DisclosureFiling
from app.models.financial import FinancialFact
from app.models.market import Company

REPORT_Q1_2024 = date(2024, 3, 31)
REPORT_Q2_2024 = date(2024, 6, 30)
REPORT_Q3_2024 = date(2024, 9, 30)
REPORT_Q4_2024 = date(2024, 12, 31)
REPORT_Q1_2025 = date(2025, 3, 31)
REPORT_Q2_2025 = date(2025, 6, 30)
REPORT_Q3_2025 = date(2025, 9, 30)
REPORT_Q4_2025 = date(2025, 12, 31)

T1 = datetime(2025, 1, 10, tzinfo=UTC)
T2 = datetime(2025, 4, 10, tzinfo=UTC)


# ---------------------------------------------------------------------------
# P0-1 intake: hashing, validation, period keys (pure)
# ---------------------------------------------------------------------------


class TestIntakePure:
    def test_content_hash_deterministic(self) -> None:
        assert compute_content_hash(b"pdf-bytes") == compute_content_hash(b"pdf-bytes")
        assert len(compute_content_hash(b"pdf-bytes")) == 64

    def test_content_hash_distinguishes_bytes(self) -> None:
        assert compute_content_hash(b"a") != compute_content_hash(b"b")

    def test_url_hash_deterministic(self) -> None:
        url = "https://www.egx.com.eg/downloads/Bulletins/310486_2.pdf"
        assert registration_hash_for_url(url) == registration_hash_for_url(url)
        assert registration_hash_for_url(url) != registration_hash_for_url(url + "?x=1")

    def test_validate_filing_type(self) -> None:
        assert validate_filing_type("Q") == "Q"
        with pytest.raises(ValueError):
            validate_filing_type("10-K")

    def test_validate_accounting_basis(self) -> None:
        assert validate_accounting_basis("EAS+CBE") == "EAS+CBE"
        with pytest.raises(ValueError):
            validate_accounting_basis("US-GAAP")

    def test_check_upload_bytes(self) -> None:
        assert check_upload_bytes(b"%PDF-1.4", filename="a.pdf") == b"%PDF-1.4"
        with pytest.raises(ValueError):
            check_upload_bytes(b"", filename="empty.pdf")
        with pytest.raises(ValueError):
            check_upload_bytes(b"x" * (INTAKE_MAX + 1), filename="huge.pdf")
        with pytest.raises(ValueError):
            check_upload_bytes(b"<html>", filename="not-a.pdf")
        assert INTAKE_MAX == MAX_PDF_BYTES

    def test_period_bounds_quarters(self) -> None:
        assert filing_period_bounds(date(2026, 2, 15), "Q") == (
            "Q1", 2026, 1, date(2026, 1, 1), date(2026, 3, 31),
        )
        assert filing_period_bounds(date(2026, 8, 15), "Q")[0] == "Q3"
        assert filing_period_bounds(date(2026, 11, 15), "Q")[0] == "Q4"

    def test_period_bounds_year_shapes(self) -> None:
        assert filing_period_bounds(date(2026, 5, 1), "FY")[0] == "ANNUAL"
        assert filing_period_bounds(date(2026, 5, 1), "H1")[0] == "SEMI_ANNUAL"
        assert filing_period_bounds(date(2026, 5, 1), "9M")[0] == "INTERIM"
        kind, year, quarter, start, end = filing_period_bounds(date(2026, 5, 1), "BOARD")
        assert (kind, quarter, start, end) == (
            "INTERIM", None, date(2026, 5, 1), date(2026, 5, 1),
        )
        assert year == 2026


# ---------------------------------------------------------------------------
# P0-2 parse: numerals, confidence, scanned detection, cell mapping (pure)
# ---------------------------------------------------------------------------


class TestParsePure:
    def test_numerals(self) -> None:
        assert parse_numeral("1,234.50") == Decimal("1234.50")
        assert parse_numeral("(1,000)") == Decimal("-1000")
        assert parse_numeral("12%") == Decimal("12")
        assert parse_numeral("-5") == Decimal("-5")

    def test_numeral_zero_stays_zero(self) -> None:
        assert parse_numeral("0") == Decimal("0")
        assert parse_numeral("0.00") == Decimal("0.00")

    def test_numeral_missing_stays_missing(self) -> None:
        assert parse_numeral(None) is None
        assert parse_numeral("") is None
        assert parse_numeral("   ") is None
        assert parse_numeral("—") is None
        assert parse_numeral("n/a") is None

    def test_parsing_confidence(self) -> None:
        assert parsing_confidence(None)["status"] == "INSUFFICIENT_DATA"
        assert parsing_confidence(
            ParsingReport(accuracy=None, whitespace=1.0, order=1, page=1)
        )["status"] == "INSUFFICIENT_DATA"
        assert parsing_confidence(
            ParsingReport(accuracy=-5.0, whitespace=1.0, order=1, page=1)
        )["status"] == "INSUFFICIENT_DATA"
        assert parsing_confidence(
            ParsingReport(accuracy=150.0, whitespace=1.0, order=1, page=1)
        )["status"] == "INSUFFICIENT_DATA"
        good = parsing_confidence(
            ParsingReport(accuracy=87.5, whitespace=10.0, order=1, page=2)
        )
        assert good == {"value": 0.875, "status": "OK"}

    def test_parsing_confidence_zero_is_valid(self) -> None:
        assert parsing_confidence(
            ParsingReport(accuracy=0.0, whitespace=99.0, order=1, page=1)
        ) == {"value": 0.0, "status": "OK"}

    def test_fill_rate_confidence(self) -> None:
        assert fill_rate_confidence([])["status"] == "INSUFFICIENT_DATA"
        tables = [
            RawTable(table_id=0, page=1, rows=[["a", "1"], ["b", None]], report=None)
        ]
        assert fill_rate_confidence(tables) == {
            "value": 0.75,
            "status": "OK",
            "basis": "cell fill rate (no engine accuracy reported)",
        }

    def test_detect_scanned(self) -> None:
        assert detect_scanned(text_chars=0, table_count=0) is True
        assert detect_scanned(text_chars=10, table_count=0) is False
        assert detect_scanned(text_chars=0, table_count=2) is False

    def test_tables_to_cells_locators(self) -> None:
        tables = [
            RawTable(
                table_id=3, page=5,
                rows=[["Revenue", "1,000"], ["Costs", None], ["", "9"], [" ", "8"]],
                report=None,
            )
        ]
        cells = tables_to_cells(
            tables, statement_pages={"income_statement": [5]}, metrics=None
        )
        assert len(cells) == 2  # blank labels skipped
        revenue = cells[0]
        assert revenue.metric == "Revenue"
        assert revenue.value == Decimal("1000")
        assert revenue.missing is False
        assert (revenue.page, revenue.table_id, revenue.row, revenue.col) == (5, 3, 0, 1)
        assert revenue.statement_name == "income_statement"
        assert cells[1].missing is True
        assert cells[1].value is None

    def test_tables_to_cells_allowlist(self) -> None:
        tables = [
            RawTable(
                table_id=0, page=1,
                rows=[["Revenue", "10"], ["Header 2026", "x"], ["Net income", "3"]],
                report=None,
            )
        ]
        cells = tables_to_cells(tables, metrics=["revenue", "net income"])
        assert [cell.metric for cell in cells] == ["Revenue", "Net income"]

    def test_tables_to_cells_default_statement(self) -> None:
        tables = [RawTable(table_id=0, page=9, rows=[["Revenue", "10"]], report=None)]
        cells = tables_to_cells(tables)
        assert cells[0].statement_name == "unknown_statement"

    def test_parse_rejects_unknown_engine_and_method(self) -> None:
        with pytest.raises(ValueError):
            parse_filing_bytes(b"%PDF", engine="pymupdf")
        with pytest.raises(ValueError):
            parse_filing_bytes(b"%PDF", method="guess")

    def test_parse_engine_unavailable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "pdfplumber", None)
        outcome = parse_filing_bytes(b"%PDF-1.4", engine="pdfplumber")
        assert outcome.status == "UNKNOWN"
        assert outcome.reason == "pdfplumber-unavailable"
        assert outcome.cells == []

    def test_parse_scanned_pdfplumber_stub(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = types.ModuleType("pdfplumber")
        module.__version__ = "stub"

        class _Page:
            def extract_text(self) -> str:
                return ""

            def extract_tables(self) -> list[list[list[str]]]:
                return []

        class _Pdf:
            pages = [_Page()]

            def __enter__(self) -> "_Pdf":
                return self

            def __exit__(self, *args: object) -> None:
                return None

        module.open = lambda _bio: _Pdf()  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "pdfplumber", module)
        outcome = parse_filing_bytes(b"fake-scanned", engine="pdfplumber")
        assert outcome.status == "UNKNOWN"
        assert outcome.reason == "scanned-needs-OCR"

    def test_parse_pdfplumber_stub_ok(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = types.ModuleType("pdfplumber")
        module.__version__ = "stub"

        class _Page:
            def extract_text(self) -> str:
                return "Income statement"

            def extract_tables(self) -> list[list[list[str | None]]]:
                return [[["Revenue", "2,500"], ["Costs", None]]]

        class _Pdf:
            pages = [_Page()]

            def __enter__(self) -> "_Pdf":
                return self

            def __exit__(self, *args: object) -> None:
                return None

        module.open = lambda _bio: _Pdf()  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "pdfplumber", module)
        outcome = parse_filing_bytes(
            b"fake-digital",
            engine="pdfplumber",
            statement_pages={"income_statement": [1]},
        )
        assert outcome.status == "OK"
        assert outcome.engine_version == "stub"
        assert len(outcome.cells) == 2
        assert outcome.cells[0].value == Decimal("2500")
        assert outcome.cells[1].missing is True
        assert outcome.confidence["status"] == "OK"

    def test_parse_camelot_stub_ok(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = types.ModuleType("camelot")
        module.__version__ = "stub-cv"
        grid = SimpleNamespace(
            values=SimpleNamespace(tolist=lambda: [["Revenue", "100"], ["EPS", "1.5"]])
        )
        table = SimpleNamespace(
            parsing_report={"accuracy": 92.0, "whitespace": 8.0, "order": 1},
            page=2,
            df=grid,
        )
        module.read_pdf = lambda _path, **_kwargs: [table]  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "camelot", module)
        monkeypatch.setattr(settings, "CAMELOT_ENABLED", True)
        outcome = parse_filing_bytes(b"whatever", engine="camelot", method="lattice")
        assert outcome.status == "OK"
        assert outcome.confidence == {"value": 0.92, "status": "OK"}
        assert [cell.metric for cell in outcome.cells] == ["Revenue", "EPS"]
        assert outcome.cells[0].page == 2

    def test_parse_camelot_no_tables_is_unknown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = types.ModuleType("camelot")
        module.__version__ = "stub"
        module.read_pdf = lambda _path, **_kwargs: []  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "camelot", module)
        monkeypatch.setattr(settings, "CAMELOT_ENABLED", True)
        outcome = parse_filing_bytes(b"whatever", engine="camelot")
        assert outcome.status == "UNKNOWN"
        assert "scanned-needs-OCR" in (outcome.reason or "")

    def test_parse_camelot_disabled_by_default(self) -> None:
        outcome = parse_filing_bytes(b"whatever", engine="camelot")
        assert outcome.status == "UNKNOWN"
        assert "camelot-disabled" in (outcome.reason or "")

    def test_parse_real_garbage_is_unknown(self) -> None:
        outcome = parse_filing_bytes(b"definitely-not-a-pdf", engine="pdfplumber")
        assert outcome.status == "UNKNOWN"
        assert outcome.cells == []


# ---------------------------------------------------------------------------
# P0-3/P0-4: EAS tags, basis guard, provenance payload (pure)
# ---------------------------------------------------------------------------


class TestFactsPure:
    def test_validate_eas_tags(self) -> None:
        assert validate_eas_tags(None) == []
        assert validate_eas_tags(["two-statement-format"]) == ["two-statement-format"]
        with pytest.raises(ValueError):
            validate_eas_tags(["made-up-tag"])

    def test_basis_guard(self) -> None:
        ensure_comparable_basis(set())
        ensure_comparable_basis({None})
        ensure_comparable_basis({"EAS", "EAS+CBE", None})
        with pytest.raises(BasisMixError):
            ensure_comparable_basis({"EAS", "IFRS"})
        with pytest.raises(BasisMixError):
            ensure_comparable_basis({"EAS+CBE", "IFRS"})
        with pytest.raises(BasisMixError):
            ensure_comparable_basis({"US-GAAP"})

    def test_fact_payload_ok_shape(self) -> None:
        filing = DisclosureFiling(
            id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            filing_url="https://www.egx.com.eg/x.pdf",
            bulletin_id="B-1",
            report_date=date(2026, 6, 30),
            filing_type="Q",
            accounting_basis="EAS",
            content_hash="h",
            downloaded_at=datetime.now(UTC),
        )
        fact = FinancialFact(
            id=uuid.uuid4(),
            period_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            company_id=filing.company_id,
            fact_type="INCOME_STATEMENT",
            reported_label="revenue",
            normalized_label="revenue",
            reported_value=Decimal("123.4"),
            currency="EGP",
            status="REPORTED",
            filing_id=filing.id,
            accounting_basis="EAS",
            eas_tags=["two-statement-format"],
            locator={"page": 3, "table_id": 0, "row": 5, "col": 1,
                      "statement_name": "income_statement"},
            extraction={"engine": "pdfplumber", "method": "lattice"},
            audit_state="reviewed",
            methodology_version="1.0",
            is_restated=False,
            created_at=datetime.now(UTC),
        )
        payload = fact_payload(
            fact, company_ticker="TICK", filing=filing,
            period_end=date(2026, 6, 30), period_label="Q2-2026",
        )
        assert payload["metric"] == "revenue"
        assert payload["value"] == {"value": "123.4", "status": "OK", "reason": None}
        assert payload["currency_unit"] == "EGP"
        assert payload["period"] == {
            "end": "2026-06-30", "type": "Q2-2026", "audit_state": "reviewed",
        }
        assert payload["source"]["bulletin_id"] == "B-1"
        assert payload["source"]["company"] == "TICK"
        assert payload["locator"]["page"] == 3
        assert payload["extraction"]["engine"] == "pdfplumber"
        assert payload["accounting_basis"] == "EAS"
        assert payload["eas_tags"] == ["two-statement-format"]
        assert payload["methodology_version"] == "1.0"
        assert payload["status"] == "OK"
        assert payload["supersedes"] is None
        assert payload["is_restated"] is False

    def test_fact_payload_unknown(self) -> None:
        fact = FinancialFact(
            id=uuid.uuid4(),
            period_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            company_id=uuid.uuid4(),
            fact_type="INCOME_STATEMENT",
            reported_label="revenue",
            reported_value=None,
            currency="EGP",
            status="INSUFFICIENT_DATA",
            unknown_reason="missing numeral for revenue",
            is_restated=False,
            created_at=datetime.now(UTC),
        )
        payload = fact_payload(
            fact, company_ticker="TICK", filing=None,
            period_end=None, period_label=None,
        )
        assert payload["status"] == "UNKNOWN"
        assert payload["value"]["value"] is None
        assert payload["value"]["reason"] == "missing numeral for revenue"
        assert payload["source"]["filing_url"] is None


# ---------------------------------------------------------------------------
# P0-5 comparison (pure)
# ---------------------------------------------------------------------------


class TestComparisonPure:
    def test_quantize4(self) -> None:
        assert quantize4(Decimal("1.23456")) == Decimal("1.2346")
        assert quantize4(Decimal("-1.23454")) == Decimal("-1.2345")
        assert quantize4(Decimal("0")) == Decimal("0.0000")
        assert quantize4(Decimal("2.5")) == Decimal("2.5000")

    def test_ttm_exact_four(self) -> None:
        result = compute_ttm(
            [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")], metric="revenue"
        )
        assert result == {"value": "10", "status": "OK"}

    def test_ttm_negative_and_zero(self) -> None:
        result = compute_ttm(
            [Decimal("0"), Decimal("-5"), Decimal("5"), Decimal("10")], metric="revenue"
        )
        assert result == {"value": "10", "status": "OK"}

    def test_ttm_refuses_partial(self) -> None:
        assert compute_ttm(
            [Decimal("1"), Decimal("2"), Decimal("3")], metric="revenue"
        )["status"] == "INSUFFICIENT_DATA"
        assert compute_ttm([], metric="revenue")["status"] == "INSUFFICIENT_DATA"

    def test_ttm_refuses_missing_leg(self) -> None:
        result = compute_ttm(
            [Decimal("1"), None, Decimal("3"), Decimal("4")], metric="revenue"
        )
        assert result["status"] == "INSUFFICIENT_DATA"
        assert result["value"] is None

    def test_yoy(self) -> None:
        result = yoy_delta(
            current=Decimal("120"), prior=Decimal("100"), metric="revenue",
            current_label="Q2-2026", prior_label="Q2-2025",
        )
        assert result["delta"] == "20"
        assert result["delta_pct"] == "0.2000"
        assert result["status"] == "OK"

    def test_yoy_negative(self) -> None:
        result = yoy_delta(
            current=Decimal("-10"), prior=Decimal("100"), metric="net_income",
            current_label="Q2-2026", prior_label="Q2-2025",
        )
        assert result["delta"] == "-110"
        assert result["delta_pct"] == "-1.1000"

    def test_yoy_zero_prior(self) -> None:
        result = yoy_delta(
            current=Decimal("50"), prior=Decimal("0"), metric="revenue",
            current_label="Q2-2026", prior_label="Q2-2025",
        )
        assert result["status"] == "OK"
        assert result["delta"] == "50"
        assert result["delta_pct"] is None

    def test_yoy_missing(self) -> None:
        assert yoy_delta(
            current=None, prior=Decimal("1"), metric="m",
            current_label="a", prior_label="b",
        )["status"] == "INSUFFICIENT_DATA"
        assert yoy_delta(
            current=Decimal("1"), prior=None, metric="m",
            current_label="a", prior_label="b",
        )["status"] == "INSUFFICIENT_DATA"

    def test_margin(self) -> None:
        assert ttm_margin(
            ttm_net_income=Decimal("30"), ttm_revenue=Decimal("200")
        ) == {"value": "0.1500", "status": "OK"}

    def test_margin_zero_revenue(self) -> None:
        result = ttm_margin(ttm_net_income=Decimal("5"), ttm_revenue=Decimal("0"))
        assert result["status"] == "INSUFFICIENT_DATA"
        assert result["value"] is None

    def test_margin_missing(self) -> None:
        assert ttm_margin(ttm_net_income=None, ttm_revenue=Decimal("1"))["status"] == (
            "INSUFFICIENT_DATA"
        )

    def test_margin_vs_prior(self) -> None:
        block = margin_vs_prior_year(
            current_margin={"value": "0.1500", "status": "OK"},
            prior_margin={"value": "0.1000", "status": "OK"},
        )
        assert block["status"] == "OK"
        assert block["delta"] == "0.0500"
        block = margin_vs_prior_year(
            current_margin={"value": None, "status": "INSUFFICIENT_DATA"},
            prior_margin={"value": "0.1000", "status": "OK"},
        )
        assert block["status"] == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# P0-6 diffs + restatement detector (pure)
# ---------------------------------------------------------------------------


class TestDiffsPure:
    def test_restatement_decision(self) -> None:
        assert restatement_decision(
            new_value=Decimal("1"), latest_value=None, latest_id=None
        ).action == "insert"
        assert restatement_decision(
            new_value=Decimal("1"), latest_value=Decimal("1"),
            latest_id=uuid.uuid4(),
        ).action == "duplicate"
        assert restatement_decision(
            new_value=None, latest_value=None, latest_id=uuid.uuid4()
        ).action == "duplicate"
        latest_id = uuid.uuid4()
        decision = restatement_decision(
            new_value=Decimal("2"), latest_value=Decimal("1"), latest_id=latest_id
        )
        assert decision.action == "restate"
        assert decision.supersedes_id == latest_id

    def test_beat_or_miss(self) -> None:
        assert beat_or_miss(Decimal("150"), Decimal("140")) == "beat"
        assert beat_or_miss(Decimal("140"), Decimal("140")) == "beat"
        assert beat_or_miss(Decimal("130"), Decimal("140")) == "miss"
        assert beat_or_miss(Decimal("130"), None) is None
        assert beat_or_miss(None, Decimal("140")) is None

    def test_build_diff_row(self) -> None:
        row = build_diff_row(
            metric="revenue", prior_value=Decimal("100"), current_value=Decimal("150"),
            prior_period="Q1-2026", current_period="Q2-2026", kind="period_diff",
            estimate=Decimal("140"),
        )
        assert row["delta"] == "50"
        assert row["delta_pct"] == "0.5000"
        assert row["beat_miss"] == "beat"

    def test_build_diff_row_negative_and_zero_prior(self) -> None:
        row = build_diff_row(
            metric="m", prior_value=Decimal("-10"), current_value=Decimal("-30"),
            prior_period="a", current_period="b", kind="period_diff",
        )
        assert row["delta"] == "-20"
        assert row["delta_pct"] == "2.0000"
        assert row["beat_miss"] is None
        row = build_diff_row(
            metric="m", prior_value=Decimal("0"), current_value=Decimal("5"),
            prior_period="a", current_period="b", kind="restatement",
        )
        assert row["delta"] == "5"
        assert row["delta_pct"] is None

    def test_build_diff_row_missing(self) -> None:
        row = build_diff_row(
            metric="m", prior_value=None, current_value=Decimal("5"),
            prior_period="a", current_period="b", kind="period_diff",
        )
        assert row["delta"] is None
        assert row["delta_pct"] is None

    def test_select_as_of(self) -> None:
        old_id, new_id = uuid.uuid4(), uuid.uuid4()
        versions = [
            FactVersion(id=old_id, value=Decimal("100"), created_at=T1,
                        supersedes_id=None),
            FactVersion(id=new_id, value=Decimal("120"), created_at=T2,
                        supersedes_id=old_id),
        ]
        assert select_as_of(versions, as_of=datetime(2025, 1, 1, tzinfo=UTC)) is None
        assert select_as_of(versions, as_of=T1) is not None
        assert select_as_of(versions, as_of=T1).id == old_id  # pre-restatement
        assert select_as_of(versions, as_of=T2).id == new_id


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def _register(
    service: DisclosureService,
    company: Company,
    report_date: date,
    *,
    filing_type: str = "Q",
    accounting_basis: str = "EAS",
    bulletin_id: str | None = None,
    content_hash: str | None = None,
    pdf: bytes | None = None,
) -> DisclosureFiling:
    if pdf is not None:
        filing, _ = await service.upload(
            company_id=company.id,
            filename="pack.pdf",
            data=pdf,
            bulletin_id=bulletin_id,
            report_date=report_date,
            filing_type=filing_type,
            accounting_basis=accounting_basis,
        )
    else:
        filing, _ = await service.register_url(
            company_id=company.id,
            filing_url=f"https://www.egx.com.eg/{company.ticker}/{report_date.isoformat()}.pdf",
            bulletin_id=bulletin_id,
            report_date=report_date,
            filing_type=filing_type,
            accounting_basis=accounting_basis,
            content_hash=content_hash,
        )
    return filing


# ---------------------------------------------------------------------------
# P0-1 service: registry + hash dedupe
# ---------------------------------------------------------------------------


class TestIntakeService:
    async def test_register_then_reregister_is_single_row(
        self, db_session: AsyncSession, test_company: Company
    ) -> None:
        service = DisclosureService(db_session)
        first, created_first = await service.register_url(
            company_id=test_company.id,
            filing_url="https://www.egx.com.eg/bulletin/1.pdf",
            bulletin_id="B-1",
            report_date=REPORT_Q1_2024,
            filing_type="Q",
        )
        second, created_second = await service.register_url(
            company_id=test_company.id,
            filing_url="https://www.egx.com.eg/bulletin/1.pdf",
            bulletin_id="B-1",
            report_date=REPORT_Q1_2024,
            filing_type="Q",
        )
        assert created_first is True
        assert created_second is False
        assert first.id == second.id
        count = await db_session.scalar(
            select(func.count(DisclosureFiling.id)).where(
                DisclosureFiling.content_hash == first.content_hash
            )
        )
        assert count == 1

    async def test_upload_bytes_dedupe(
        self, db_session: AsyncSession, test_company: Company
    ) -> None:
        service = DisclosureService(db_session)
        blob = b"%PDF-1.4 same-bytes"
        first, created_first = await service.upload(
            company_id=test_company.id, filename="a.pdf", data=blob,
            bulletin_id=None, report_date=REPORT_Q1_2024, filing_type="Q",
        )
        second, created_second = await service.upload(
            company_id=test_company.id, filename="renamed.pdf", data=blob,
            bulletin_id=None, report_date=REPORT_Q1_2024, filing_type="Q",
        )
        assert (created_first, created_second) == (True, False)
        assert first.id == second.id
        assert first.byte_size == len(blob)
        assert first.pdf_bytes == blob

    async def test_register_rejects(
        self, db_session: AsyncSession, test_company: Company
    ) -> None:
        service = DisclosureService(db_session)
        with pytest.raises(LookupError):
            await service.register_url(
                company_id=uuid.uuid4(), filing_url="https://x/y.pdf",
                bulletin_id=None, report_date=REPORT_Q1_2024, filing_type="Q",
            )
        with pytest.raises(ValueError):
            await service.register_url(
                company_id=test_company.id, filing_url="https://x/y.pdf",
                bulletin_id=None, report_date=REPORT_Q1_2024, filing_type="10-K",
            )
        with pytest.raises(ValueError):
            await service.register_url(
                company_id=test_company.id, filing_url="   ",
                bulletin_id=None, report_date=REPORT_Q1_2024, filing_type="Q",
            )
        for bad_url in ("javascript:alert(1)", "file:///etc/passwd", "/relative.pdf"):
            with pytest.raises(ValueError):
                await service.register_url(
                    company_id=test_company.id, filing_url=bad_url,
                    bulletin_id=None, report_date=REPORT_Q1_2024, filing_type="Q",
                )
        with pytest.raises(ValueError):
            await service.upload(
                company_id=test_company.id, filename="e.pdf", data=b"",
                bulletin_id=None, report_date=REPORT_Q1_2024, filing_type="Q",
            )
        with pytest.raises(ValueError):
            await service.upload(
                company_id=test_company.id, filename="n.pdf", data=b"<html>not a pdf",
                bulletin_id=None, report_date=REPORT_Q1_2024, filing_type="Q",
            )


# ---------------------------------------------------------------------------
# P0-3/P0-4 service: provenance facts, UNKNOWN rows, restatement chain
# ---------------------------------------------------------------------------


class TestRecordFacts:
    async def test_record_ok_fact_with_provenance(
        self, db_session: AsyncSession, test_company: Company
    ) -> None:
        service = DisclosureService(db_session)
        filing = await _register(service, test_company, REPORT_Q1_2024)
        fact, created, diff = await service.record_fact(
            filing_id=filing.id,
            metric="revenue",
            value=Decimal("2500"),
            statement_name="income_statement",
            page=3, table_id=0, row=5, col=1,
            audit_state="reviewed",
            eas_tags=["two-statement-format"],
            extraction={"engine": "pdfplumber", "method": "lattice"},
        )
        assert created is True
        assert diff is None  # first period: nothing to diff against
        assert fact.reported_value == Decimal("2500")
        assert fact.accounting_basis == "EAS"
        assert fact.eas_tags == ["two-statement-format"]
        assert fact.locator == {
            "statement_name": "income_statement", "page": 3,
            "table_id": 0, "row": 5, "col": 1,
        }
        assert fact.extraction == {"engine": "pdfplumber", "method": "lattice"}
        assert fact.audit_state == "reviewed"
        assert fact.methodology_version == "1.0"
        assert fact.is_restated is False
        assert fact.supersedes_id is None

    async def test_missing_numeral_persists_unknown(
        self, db_session: AsyncSession, test_company: Company
    ) -> None:
        service = DisclosureService(db_session)
        filing = await _register(service, test_company, REPORT_Q1_2024)
        fact, created, _ = await service.record_fact(
            filing_id=filing.id, metric="revenue", value=None,
            statement_name="income_statement",
        )
        assert created is True
        assert fact.status.value == "INSUFFICIENT_DATA"
        assert fact.reported_value is None
        assert fact.unknown_reason == "missing numeral for revenue"

    async def test_record_rejects(
        self, db_session: AsyncSession, test_company: Company
    ) -> None:
        service = DisclosureService(db_session)
        with pytest.raises(LookupError):
            await service.record_fact(
                filing_id=uuid.uuid4(), metric="revenue", value=Decimal("1"),
                statement_name="income_statement",
            )
        filing = await _register(service, test_company, REPORT_Q1_2024)
        with pytest.raises(ValueError):
            await service.record_fact(
                filing_id=filing.id, metric="  ", value=Decimal("1"),
                statement_name="income_statement",
            )
        with pytest.raises(ValueError):
            await service.record_fact(
                filing_id=filing.id, metric="revenue", value=Decimal("1"),
                statement_name="income_statement", eas_tags=["bogus-tag"],
            )
        with pytest.raises(ValueError):
            await service.record_fact(
                filing_id=filing.id, metric="revenue", value=Decimal("1"),
                statement_name="income_statement", audit_state="maybe",
            )

    async def test_restatement_supersedes_and_keeps_prior(
        self, db_session: AsyncSession, test_company: Company
    ) -> None:
        service = DisclosureService(db_session)
        original_filing = await _register(
            service, test_company, REPORT_Q1_2024, bulletin_id="B-1"
        )
        restated_filing = await _register(
            service, test_company, REPORT_Q1_2024, bulletin_id="B-1R"
        )
        original, _, _ = await service.record_fact(
            filing_id=original_filing.id, metric="revenue", value=Decimal("100"),
            statement_name="income_statement", created_at=T1,
        )
        revised, created, diff = await service.record_fact(
            filing_id=restated_filing.id, metric="revenue", value=Decimal("120"),
            statement_name="income_statement", created_at=T2,
        )
        assert created is True
        assert revised.is_restated is True
        assert revised.supersedes_id == original.id
        assert diff is not None
        assert diff.kind == "restatement"
        assert diff.prior_value == Decimal("100")
        assert diff.current_value == Decimal("120")
        # Prior kept: two rows on disk.
        count = await db_session.scalar(
            select(func.count(FinancialFact.id)).where(
                FinancialFact.company_id == test_company.id
            )
        )
        assert count == 2
        # Live read shows the restated value; as_of T1 shows pre-restatement.
        live = await service.list_fact_payloads(test_company.id, metric="revenue")
        assert len(live) == 1
        assert live[0]["value"]["value"] == "120.0000"
        assert live[0]["is_restated"] is True
        early = await service.list_fact_payloads(
            test_company.id, metric="revenue", as_of=T1
        )
        assert len(early) == 1
        assert early[0]["value"]["value"] == "100.0000"
        assert early[0]["is_restated"] is False

    async def test_duplicate_republish_returns_existing(
        self, db_session: AsyncSession, test_company: Company
    ) -> None:
        service = DisclosureService(db_session)
        filing = await _register(service, test_company, REPORT_Q1_2024)
        first, _, _ = await service.record_fact(
            filing_id=filing.id, metric="revenue", value=Decimal("100"),
            statement_name="income_statement",
        )
        second, created, diff = await service.record_fact(
            filing_id=filing.id, metric="revenue", value=Decimal("100"),
            statement_name="income_statement",
        )
        assert created is False
        assert second.id == first.id
        assert diff is None

    async def test_period_diff_with_beat(
        self, db_session: AsyncSession, test_company: Company
    ) -> None:
        service = DisclosureService(db_session)
        q1 = await _register(service, test_company, REPORT_Q1_2024)
        q2 = await _register(service, test_company, REPORT_Q2_2024)
        await service.record_fact(
            filing_id=q1.id, metric="revenue", value=Decimal("100"),
            statement_name="income_statement", created_at=T1,
        )
        _, _, diff = await service.record_fact(
            filing_id=q2.id, metric="revenue", value=Decimal("150"),
            statement_name="income_statement", estimate=Decimal("140"),
            created_at=T2,
        )
        assert diff is not None
        assert diff.kind == "period_diff"
        assert diff.delta == Decimal("50")
        assert diff.delta_pct == Decimal("0.50000000")
        assert diff.beat_miss == "beat"
        assert diff.prior_period == "Q1-2024"
        assert diff.current_period == "Q2-2024"


# ---------------------------------------------------------------------------
# P0-5 service: TTM + YoY + margin
# ---------------------------------------------------------------------------


class TestComparisonService:
    async def _eight_quarters(
        self, service: DisclosureService, company: Company
    ) -> None:
        revenues = [10, 20, 30, 40, 50, 60, 70, 80]
        incomes = [1, 2, 3, 4, 5, 6, 7, 8]
        dates = [
            date(2024, 3, 31), date(2024, 6, 30), date(2024, 9, 30),
            date(2024, 12, 31), date(2025, 3, 31), date(2025, 6, 30),
            date(2025, 9, 30), date(2025, 12, 31),
        ]
        for idx, report_date in enumerate(dates):
            filing = await _register(service, company, report_date)
            await service.record_fact(
                filing_id=filing.id, metric="revenue",
                value=Decimal(str(revenues[idx])),
                statement_name="income_statement",
            )
            await service.record_fact(
                filing_id=filing.id, metric="net_income",
                value=Decimal(str(incomes[idx])),
                statement_name="income_statement",
            )

    async def test_ttm_yoy_margin(
        self, db_session: AsyncSession, test_company: Company
    ) -> None:
        service = DisclosureService(db_session)
        await self._eight_quarters(service, test_company)
        comparison = await service.compare(test_company.id, "revenue")
        assert comparison["ttm"] == {"value": "260.0000", "status": "OK"}  # 50+60+70+80
        yoy = comparison["yoy"]
        assert yoy["status"] == "OK"
        assert yoy["current_label"] == "Q4-2025"
        assert yoy["prior_label"] == "Q4-2024"
        assert yoy["delta"] == "40.0000"  # 80 - 40
        assert yoy["delta_pct"] == "1.0000"
        assert comparison["methodology_version"] == "1.0"
        margin = await service.margin_block(test_company.id)
        assert margin["status"] == "OK"
        assert margin["current"]["value"] == "0.1000"  # 26/260
        assert margin["prior"]["value"] == "0.1000"  # 10/100
        assert margin["delta"] == "0.0000"

    async def test_single_quarter_refuses_ttm(
        self, db_session: AsyncSession, test_company: Company
    ) -> None:
        service = DisclosureService(db_session)
        filing = await _register(service, test_company, REPORT_Q1_2024)
        await service.record_fact(
            filing_id=filing.id, metric="revenue", value=Decimal("100"),
            statement_name="income_statement",
        )
        comparison = await service.compare(test_company.id, "revenue")
        assert comparison["ttm"]["status"] == "INSUFFICIENT_DATA"
        assert comparison["yoy"]["status"] == "INSUFFICIENT_DATA"
        margin = await service.margin_block(test_company.id)
        assert margin["status"] == "INSUFFICIENT_DATA"

    async def test_mixed_bases_refused(
        self, db_session: AsyncSession, test_company: Company
    ) -> None:
        service = DisclosureService(db_session)
        for idx, report_date in enumerate(
            [REPORT_Q1_2024, REPORT_Q2_2024, REPORT_Q3_2024, REPORT_Q4_2024]
        ):
            filing = await _register(
                service, test_company, report_date,
                accounting_basis="IFRS" if idx == 3 else "EAS",
            )
            await service.record_fact(
                filing_id=filing.id, metric="revenue",
                value=Decimal(str((idx + 1) * 10)),
                statement_name="income_statement",
            )
        with pytest.raises(BasisMixError):
            await service.compare(test_company.id, "revenue")


# ---------------------------------------------------------------------------
# API round-trips
# ---------------------------------------------------------------------------


class TestDisclosuresApi:
    async def test_full_round_trip(
        self, client: AsyncClient, test_company: Company
    ) -> None:
        register = {
            "company_id": str(test_company.id),
            "filing_url": "https://www.egx.com.eg/bulletin/rt.pdf",
            "bulletin_id": "RT-1",
            "report_date": "2025-03-31",
            "filing_type": "Q",
            "accounting_basis": "EAS",
        }
        first = await client.post("/api/disclosures/register", json=register)
        assert first.status_code == 200
        assert first.json()["created"] is True
        filing_id = first.json()["filing"]["content_hash"]
        assert filing_id
        again = await client.post("/api/disclosures/register", json=register)
        assert again.json()["created"] is False

        upload_files = {"file": ("pack.pdf", b"%PDF-1.4 bytes", "application/pdf")}
        upload_data = {
            "company_id": str(test_company.id),
            "report_date": "2025-06-30",
            "filing_type": "Q",
            "accounting_basis": "EAS",
        }
        uploaded = await client.post(
            "/api/disclosures/upload", data=upload_data, files=upload_files
        )
        assert uploaded.status_code == 200
        upload_filing_id = uploaded.json()["filing"]["id"]
        redup = await client.post(
            "/api/disclosures/upload", data=upload_data, files=upload_files
        )
        assert redup.json()["created"] is False

        fact_body = {
            "filing_id": upload_filing_id,
            "metric": "revenue",
            "value": 150.0,
            "statement_name": "income_statement",
            "page": 2,
            "eas_tags": ["two-statement-format"],
            "estimate": 140.0,
        }
        recorded = await client.post("/api/disclosures/facts", json=fact_body)
        assert recorded.status_code == 200
        assert recorded.json()["created"] is True

        unknown_body = dict(fact_body, metric="costs", value=None)
        unknown = await client.post("/api/disclosures/facts", json=unknown_body)
        assert unknown.status_code == 200

        facts = await client.get(
            "/api/disclosures/facts", params={"company_id": str(test_company.id)}
        )
        assert facts.status_code == 200
        by_metric = {row["metric"]: row for row in facts.json()}
        assert by_metric["revenue"]["value"] == {
            "value": "150.0000", "status": "OK", "reason": None,
        }
        assert by_metric["revenue"]["methodology_version"] == "1.0"
        assert by_metric["costs"]["status"] == "UNKNOWN"
        assert by_metric["costs"]["value"]["value"] is None

        comparison = await client.get(
            "/api/disclosures/comparison",
            params={"company_id": str(test_company.id), "metric": "revenue"},
        )
        assert comparison.status_code == 200
        assert comparison.json()["comparison"]["ttm"]["status"] == "INSUFFICIENT_DATA"

        diffs = await client.get(
            "/api/disclosures/diffs", params={"company_id": str(test_company.id)}
        )
        assert diffs.status_code == 200
        assert isinstance(diffs.json(), list)

        filings = await client.get(
            "/api/disclosures/filings", params={"company_id": str(test_company.id)}
        )
        assert filings.status_code == 200
        assert len(filings.json()) == 2

    async def test_api_errors(
        self, client: AsyncClient, test_company: Company
    ) -> None:
        missing = uuid.uuid4()
        response = await client.get(
            "/api/disclosures/facts", params={"company_id": str(missing)}
        )
        assert response.status_code == 404
        bad_type = {
            "company_id": str(test_company.id),
            "filing_url": "https://x/y.pdf",
            "report_date": "2025-03-31",
            "filing_type": "10-K",
        }
        response = await client.post("/api/disclosures/register", json=bad_type)
        assert response.status_code == 422
        bad_fact = {"filing_id": str(uuid.uuid4()), "metric": "revenue", "value": 1.0}
        response = await client.post("/api/disclosures/facts", json=bad_fact)
        assert response.status_code == 404

    async def test_parse_garbage_bytes_is_unknown(
        self, client: AsyncClient, test_company: Company
    ) -> None:
        uploaded = await client.post(
            "/api/disclosures/upload",
            data={
                "company_id": str(test_company.id),
                "report_date": "2025-03-31",
                "filing_type": "Q",
            },
            files={"file": ("g.pdf", b"%PDF-1.4 garbage-body", "application/pdf")},
        )
        filing_id = uploaded.json()["filing"]["id"]
        parsed = await client.post(
            f"/api/disclosures/filings/{filing_id}/parse", json={}
        )
        assert parsed.status_code == 200
        assert parsed.json()["status"] == "UNKNOWN"
        assert parsed.json()["facts"] == []

    async def test_parse_url_only_has_no_bytes(
        self, client: AsyncClient, test_company: Company
    ) -> None:
        registered = await client.post(
            "/api/disclosures/register",
            json={
                "company_id": str(test_company.id),
                "filing_url": "https://www.egx.com.eg/nobytes.pdf",
                "report_date": "2025-03-31",
                "filing_type": "Q",
            },
        )
        filing_id = registered.json()["filing"]["id"]
        parsed = await client.post(
            f"/api/disclosures/filings/{filing_id}/parse", json={}
        )
        assert parsed.status_code == 422

    async def test_parse_persists_cells(
        self,
        client: AsyncClient,
        test_company: Company,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        uploaded = await client.post(
            "/api/disclosures/upload",
            data={
                "company_id": str(test_company.id),
                "report_date": "2025-03-31",
                "filing_type": "Q",
            },
            files={"file": ("p.pdf", b"%PDF-1.4", "application/pdf")},
        )
        filing_id = uploaded.json()["filing"]["id"]

        def _fake_parse(*args: object, **kwargs: object) -> parse_mod.ParseOutcome:
            return parse_mod.ParseOutcome(
                status="OK",
                reason=None,
                cells=[
                    parse_mod.ParsedCell(
                        metric="revenue", raw_text="1,000", value=Decimal("1000"),
                        missing=False, page=1, table_id=0, row=0, col=1,
                        statement_name="income_statement",
                    )
                ],
                engine="pdfplumber",
                engine_version="stub",
                method="lattice",
                confidence={"value": 1.0, "status": "OK"},
            )

        monkeypatch.setattr(parse_mod, "parse_filing_bytes", _fake_parse)
        parsed = await client.post(
            f"/api/disclosures/filings/{filing_id}/parse",
            json={"metrics": ["revenue"]},
        )
        assert parsed.status_code == 200
        body = parsed.json()
        assert body["status"] == "OK"
        assert len(body["facts"]) == 1
        facts = await client.get(
            "/api/disclosures/facts",
            params={"company_id": str(test_company.id), "metric": "revenue"},
        )
        assert facts.json()[0]["locator"]["page"] == 1

    async def test_diff_ledger_lists_restatement(
        self, db_session: AsyncSession, test_company: Company
    ) -> None:
        service = DisclosureService(db_session)
        original_filing = await _register(
            service, test_company, REPORT_Q1_2024, bulletin_id="B-1"
        )
        restated_filing = await _register(
            service, test_company, REPORT_Q1_2024, bulletin_id="B-1R"
        )
        await service.record_fact(
            filing_id=original_filing.id, metric="revenue", value=Decimal("100"),
            statement_name="income_statement", created_at=T1,
        )
        await service.record_fact(
            filing_id=restated_filing.id, metric="revenue", value=Decimal("120"),
            statement_name="income_statement", created_at=T2,
        )
        diffs = await service.list_diffs(test_company.id)
        assert len(diffs) == 1
        assert diffs[0]["kind"] == "restatement"
        assert diffs[0]["delta"] == "20.0000"
        assert diffs[0]["methodology_version"] == "1.0"


def test_methodology_version_echo() -> None:
    assert methodology_version() == "1.0"
    assert DISCLOSURE_METHODOLOGY_VERSION == "1.0"
