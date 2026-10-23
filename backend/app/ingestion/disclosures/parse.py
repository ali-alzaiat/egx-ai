"""Rule-based PDF parse v1: pdfplumber-first, Camelot behind one interface (R34 P0-2).

Both engines normalize to :class:`RawTable` (page + row/col grid + optional
Camelot ``parsing_report``); :func:`tables_to_cells` turns grids into located
cells. Every cell keeps ``{page, table_id, row, col, statement_name}``.
Scanned PDFs (no selectable text, no tables) return UNKNOWN
``{scanned-needs-OCR}`` — never a silent skip, never zero rows pretending to
be a parse. Engine imports are lazy (``importlib``) so a missing optional
dependency degrades to UNKNOWN ``{engine}-unavailable`` instead of breaking
the API process at import time.
"""

import importlib
import io
import logging
import os
import tempfile
from collections.abc import Collection, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import Any, NamedTuple

from app.core.config import settings
from app.ingestion.disclosures.constants import PARSE_ENGINES, PARSE_METHODS

logger = logging.getLogger(__name__)


class ParsingReport(NamedTuple):
    """Camelot-style per-table report: accuracy/whitespace 0-100, order, page."""

    accuracy: float | None
    whitespace: float | None
    order: int | None
    page: int | None


class RawTable(NamedTuple):
    """One engine-extracted table grid before metric mapping."""

    table_id: int
    page: int
    rows: list[list[str | None]]
    report: ParsingReport | None


class ParsedCell(NamedTuple):
    """One located metric reading; ``value`` None means missing numeral."""

    metric: str
    raw_text: str | None
    value: Decimal | None
    missing: bool
    page: int
    table_id: int
    row: int
    col: int
    statement_name: str


class ParseOutcome(NamedTuple):
    """Result of :func:`parse_filing_bytes`: OK cells or first-class UNKNOWN."""

    status: str  # "OK" | "UNKNOWN"
    reason: str | None
    cells: list[ParsedCell]
    engine: str | None
    engine_version: str | None
    method: str | None
    confidence: dict[str, Any]


def parse_numeral(text: str | None) -> Decimal | None:
    """ASCII financial numeral to Decimal; blank/unparseable stays None.

    Handles thousands separators, non-breaking spaces, parenthesised
    negatives, and trailing percent signs. Zero stays zero; anything that is
    not a plain numeral (dashes, Arabic-Indic digits, footnotes) returns None
    so the fact layer records UNKNOWN instead of inventing a number.
    """
    if text is None:
        return None
    cleaned = text.strip().replace(",", "")
    for sep in (" ", "\u00a0", "\u202f", "\t"):
        cleaned = cleaned.replace(sep, "")
    if not cleaned:
        return None
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    if negative:
        cleaned = cleaned[1:-1]
    if cleaned.endswith("%"):
        cleaned = cleaned[:-1]
    if not cleaned:
        return None
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return -value if negative else value


def _report_number(raw: Any) -> float | None:
    """Coerce a parsing_report field to float; anything odd stays None."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _report_int(raw: Any) -> int | None:
    """Coerce a parsing_report field to int; anything odd stays None."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def parsing_confidence(report: ParsingReport | None) -> dict[str, Any]:
    """Camelot ``parsing_report`` to a ``{"value", "status"}`` confidence payload.

    Accuracy is Camelot's 0-100 score, normalized to 0-1. A missing report or
    an out-of-range accuracy is INSUFFICIENT_DATA — never a guessed number.
    """
    if report is None or report.accuracy is None:
        return {
            "value": None,
            "status": "INSUFFICIENT_DATA",
            "reason": "no parsing accuracy reported",
        }
    accuracy = report.accuracy
    if not 0.0 <= accuracy <= 100.0:
        return {
            "value": None,
            "status": "INSUFFICIENT_DATA",
            "reason": f"parsing accuracy {accuracy} outside 0-100",
        }
    return {"value": round(accuracy / 100.0, 4), "status": "OK"}


def fill_rate_confidence(tables: Sequence[RawTable]) -> dict[str, Any]:
    """Deterministic fallback confidence for engines without accuracy scores.

    pdfplumber reports no per-table accuracy, so confidence is the filled-cell
    fraction across extracted grids — labelled as such, never presented as an
    accuracy score. Empty input is INSUFFICIENT_DATA.
    """
    total = sum(len(row) for table in tables for row in table.rows)
    if total == 0:
        return {
            "value": None,
            "status": "INSUFFICIENT_DATA",
            "reason": "no cells extracted",
        }
    filled = sum(
        1 for table in tables for row in table.rows for cell in row if cell
    )
    return {
        "value": round(filled / total, 4),
        "status": "OK",
        "basis": "cell fill rate (no engine accuracy reported)",
    }


def detect_scanned(*, text_chars: int, table_count: int) -> bool:
    """A PDF with no selectable text and no tables is scanned (needs OCR)."""
    return text_chars == 0 and table_count == 0


def statement_for_page(
    page: int, statement_pages: Mapping[str, Sequence[int]] | None
) -> str:
    """Reverse-lookup which statement a page belongs to (P&L vs OCI split)."""
    if statement_pages:
        for statement, pages in statement_pages.items():
            if page in pages:
                return statement
    return "unknown_statement"


def tables_to_cells(
    tables: Sequence[RawTable],
    *,
    statement_pages: Mapping[str, Sequence[int]] | None = None,
    default_statement: str = "unknown_statement",
    value_col: int = 1,
    metrics: Collection[str] | None = None,
) -> list[ParsedCell]:
    """Grid rows to located cells. Blank labels are skipped; missing numerals
    stay missing (``missing=True``, ``value=None``) for UNKNOWN fact rows."""
    wanted = {m.strip().lower() for m in metrics} if metrics is not None else None
    cells: list[ParsedCell] = []
    for table in tables:
        statement = statement_for_page(table.page, statement_pages)
        if statement == "unknown_statement":
            statement = default_statement
        for row_idx, row in enumerate(table.rows):
            if not row or row[0] is None:
                continue
            metric = row[0].strip()
            if not metric:
                continue
            if wanted is not None and metric.lower() not in wanted:
                continue
            raw: str | None = None
            if 0 <= value_col < len(row):
                raw = row[value_col]
            value = parse_numeral(raw)
            cells.append(
                ParsedCell(
                    metric=metric,
                    raw_text=raw,
                    value=value,
                    missing=value is None,
                    page=table.page,
                    table_id=table.table_id,
                    row=row_idx,
                    col=value_col,
                    statement_name=statement,
                )
            )
    return cells


def engine_version(module_name: str) -> str | None:
    """Installed engine version, or None when the optional dep is absent."""
    try:
        module = importlib.import_module(module_name)
    except ImportError:
        return None
    version = getattr(module, "__version__", None)
    return str(version) if version is not None else "unknown"


def extract_with_pdfplumber(data: bytes) -> tuple[list[RawTable], int]:
    """pdfplumber text + bordered-table extraction; ImportError when absent."""
    pdfplumber = importlib.import_module("pdfplumber")
    tables: list[RawTable] = []
    text_chars = 0
    table_id = 0
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page_no, page in enumerate(pdf.pages, start=1):
            text_chars += len((page.extract_text() or "").strip())
            for grid in page.extract_tables() or []:
                rows = [
                    [cell.strip() if isinstance(cell, str) and cell.strip() else None
                     for cell in grid_row]
                    for grid_row in grid
                ]
                tables.append(
                    RawTable(table_id=table_id, page=page_no, rows=rows, report=None)
                )
                table_id += 1
    return tables, text_chars


def extract_with_camelot(
    pdf_path: str, *, flavor: str = "lattice", pages: str = "all"
) -> list[RawTable]:
    """Camelot ruled/whitespace-table extraction; ImportError when absent."""
    if flavor not in PARSE_METHODS:
        raise ValueError(f"Unknown Camelot flavor {flavor!r}; expected {PARSE_METHODS}")
    camelot = importlib.import_module("camelot")
    reader = camelot.read_pdf(pdf_path, flavor=flavor, pages=pages)
    tables: list[RawTable] = []
    for table_id, table in enumerate(reader):
        raw_report: Any = table.parsing_report or {}
        page_raw = getattr(table, "page", None)
        report = ParsingReport(
            accuracy=_report_number(raw_report.get("accuracy")),
            whitespace=_report_number(raw_report.get("whitespace")),
            order=_report_int(raw_report.get("order")),
            page=_report_int(page_raw),
        )
        page = report.page if report.page is not None else 0
        rows: list[list[str | None]] = []
        for grid_row in table.df.values.tolist():
            rows.append(
                [
                    str(cell).strip()
                    if str(cell).strip() not in ("", "nan", "NaN", "None")
                    else None
                    for cell in grid_row
                ]
            )
        tables.append(RawTable(table_id=table_id, page=page, rows=rows, report=report))
    return tables


def _unknown(
    reason: str,
    *,
    engine: str | None,
    engine_version_str: str | None,
    method: str | None,
) -> ParseOutcome:
    return ParseOutcome(
        status="UNKNOWN",
        reason=reason,
        cells=[],
        engine=engine,
        engine_version=engine_version_str,
        method=method,
        confidence={"value": None, "status": "INSUFFICIENT_DATA", "reason": reason},
    )


def parse_filing_bytes(
    data: bytes,
    *,
    engine: str = "pdfplumber",
    method: str = "lattice",
    statement_pages: Mapping[str, Sequence[int]] | None = None,
    metrics: Collection[str] | None = None,
) -> ParseOutcome:
    """Parse stored PDF bytes with the chosen engine (pdfplumber-first).

    Scanned PDFs surface as UNKNOWN ``{scanned-needs-OCR}``; a missing engine
    surfaces as UNKNOWN ``{engine}-unavailable``; corrupt bytes surface as
    UNKNOWN with the parse failure named. Nothing here invents numerals.
    """
    if engine not in PARSE_ENGINES:
        raise ValueError(f"Unknown parse engine {engine!r}; expected {PARSE_ENGINES}")
    if method not in PARSE_METHODS:
        raise ValueError(f"Unknown parse method {method!r}; expected {PARSE_METHODS}")
    if engine == "pdfplumber":
        version = engine_version("pdfplumber")
        if version is None:
            return _unknown(
                "pdfplumber-unavailable", engine=engine,
                engine_version_str=None, method=method,
            )
        try:
            tables, text_chars = extract_with_pdfplumber(data)
        except Exception as exc:
            logger.warning("pdfplumber parse failed", exc_info=exc)
            return _unknown(
                f"pdfplumber parse failed: {type(exc).__name__}", engine=engine,
                engine_version_str=version, method=method,
            )
        if detect_scanned(text_chars=text_chars, table_count=len(tables)):
            return _unknown(
                "scanned-needs-OCR", engine=engine,
                engine_version_str=version, method=method,
            )
        cells = tables_to_cells(
            tables, statement_pages=statement_pages, metrics=metrics
        )
        return ParseOutcome(
            status="OK",
            reason=None,
            cells=cells,
            engine=engine,
            engine_version=version,
            method=method,
            confidence=fill_rate_confidence(tables),
        )
    if not settings.CAMELOT_ENABLED:
        return _unknown(
            "camelot-disabled (set CAMELOT_ENABLED=true for trusted PDFs)",
            engine=engine, engine_version_str=None, method=method,
        )
    version = engine_version("camelot")
    if version is None:
        return _unknown(
            "camelot-unavailable", engine=engine,
            engine_version_str=None, method=method,
        )
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        tables = extract_with_camelot(tmp_path, flavor=method)
    except Exception as exc:
        logger.warning("camelot parse failed", exc_info=exc)
        return _unknown(
            f"camelot parse failed: {type(exc).__name__}", engine=engine,
            engine_version_str=version, method=method,
        )
    finally:
        if tmp_path:
            os.unlink(tmp_path)
    if not tables:
        return _unknown(
            "no-tables-extracted (scanned-needs-OCR or wrong method)",
            engine=engine, engine_version_str=version, method=method,
        )
    cells = tables_to_cells(tables, statement_pages=statement_pages, metrics=metrics)
    reports = [t.report for t in tables if t.report and t.report.accuracy is not None]
    accuracies = [r.accuracy for r in reports if r.accuracy is not None]
    confidence: dict[str, Any]
    if accuracies:
        confidence = parsing_confidence(
            ParsingReport(
                accuracy=sum(accuracies) / len(accuracies),
                whitespace=None, order=None, page=None,
            )
        )
    else:
        confidence = fill_rate_confidence(tables)
    return ParseOutcome(
        status="OK",
        reason=None,
        cells=cells,
        engine=engine,
        engine_version=version,
        method=method,
        confidence=confidence,
    )
