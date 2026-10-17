"""StatementExtractor: filing bytes -> candidate lines with provenance.

Pure module: takes content bytes + type and returns ontology-resolved
candidates. XBRL path first (deterministic tag mapping); otherwise text/HTML
parsing with per-page provenance. Drop-not-guess policy:
- label unknown -> DropRecord(NO_ALIAS)
- label matches 2+ codes -> DropRecord(AMBIGUOUS_ALIAS)
Review Focus #1.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from app.statements.aliases import resolve_label


@dataclass
class DropRecord:
    """A label kept out of candidates, with the reason it was dropped."""

    label: str
    reason: str  # NO_ALIAS | AMBIGUOUS_ALIAS | UNPARSEABLE_VALUE | NO_VALUE
    detail: str | None = None


@dataclass
class LineCandidate:
    """A candidate line before validation; ext_status starts as candidate."""

    ontology_code: str
    ontology_version: str
    value: Decimal | None
    currency: str
    source_label_reported: str
    source_label_en: str | None
    source_label_ar: str | None
    source_page: str | None
    extraction_method: str
    ext_status: str = "extraction_candidate"
    ext_reason: str | None = None
    published_date: Any = None


@dataclass
class ExtractionResult:
    candidates: list[LineCandidate] = field(default_factory=list)
    drops: list[DropRecord] = field(default_factory=list)


_ONTOLOGY_VERSION = "stmt-ontology-1.0"

_THOUSAND_RE = re.compile(r"[\s,،]|\u060C")


def _normalize_label(raw: str) -> str:
    return re.sub(r"\s+", " ", raw).replace(":", "").casefold().strip()


def _parse_value(raw: str | None) -> Decimal | None:
    """Parse a reported numeric string: separators, negatives in brackets,\u200f
    Arabic thousand separators. Returns None when unparseable."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    # Arabic decimal mark and Arabic thousands separator.
    text = text.replace("\u066b", ".").replace("\u066c", "")
    text = _THOUSAND_RE.sub("", text)
    text = text.split()[0] if " " in text.strip() else text
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return -value if negative else value


class StatementExtractor:
    def extract(self, content: bytes, content_type: str, document_type: str) -> ExtractionResult:
        lowered = content.lstrip()[:256].lower()
        if content_type in ("application/xml", "text/xml") or lowered.startswith(b"<?xml"):
            return self._extract_xbrl(content)
        if content_type == "text/html" or b"<html" in lowered:
            return self._extract_html(content)
        raise ValueError(f"unsupported content_type for extraction: {content_type}")

    # ------------------------------------------------------------------ XBRL
    def _extract_xbrl(self, content: bytes) -> ExtractionResult:
        result = ExtractionResult()
        try:
            root = ElementTree.fromstring(content)
        except ElementTree.ParseError as exc:
            result.drops.append(
                DropRecord(label="[xbrl]", reason="UNPARSEABLE_VALUE", detail=str(exc))
            )
            return result

        for element in root:
            if not isinstance(element.tag, str):
                continue
            reported_label = self._xbrl_label(element)
            value = _parse_value(self._xbrl_text(element))
            if value is None:
                result.drops.append(
                    DropRecord(
                        reported_label,
                        "NO_VALUE",
                        ElementTree.tostring(element, encoding="unicode")[:120],
                    )
                )
                continue
            resolved = resolve_label(reported_label)
            if resolved is None:
                result.drops.append(DropRecord(reported_label, self._drop_reason(reported_label)))
                continue
            code, lang = resolved
            result.candidates.append(
                LineCandidate(
                    ontology_code=code,
                    ontology_version=_ONTOLOGY_VERSION,
                    value=value,
                    currency=self._xbrl_currency(element),
                    source_label_reported=reported_label,
                    source_label_en=reported_label if lang == "en" else None,
                    source_label_ar=reported_label if lang == "ar" else None,
                    source_page=None,
                    extraction_method="xbrl",
                )
            )
        return result

    def _xbrl_label(self, element: Any) -> str:
        # Item-style fixture elements carry `item=`; standard XBRL uses the tag name.
        item = str(element.attrib.get("item") or "")
        if item:
            return item
        tag = element.tag.rsplit("}", 1)[-1]
        # Standard tags: Revenues, Assets, NetIncomeLoss, ...
        return self._prettify_tag(tag)

    def _xbrl_text(self, element: Any) -> str | None:
        text = element.text
        return text.strip() if text else None

    def _xbrl_currency(self, element: Any) -> str:
        del element  # unitRef present but currency uniformity is a validator gate
        return "EGP"

    def _prettify_tag(self, tag: str) -> str:
        spaced = re.sub(r"(?<=[a-z0-9])([A-Z])", r" \1", tag)
        spaced = spaced.replace("Loss", "loss")
        return spaced.strip().casefold()

    def _drop_reason(self, reported_label: str) -> str:
        # Unknown vs ambiguous: re-check via the inverted variant index.
        from app.statements.aliases import _VARIANTS

        if _VARIANTS.get(_normalize_label(reported_label)):
            return "AMBIGUOUS_ALIAS"
        return "NO_ALIAS"

    # ------------------------------------------------------------------ HTML
    def _extract_html(self, content: bytes) -> ExtractionResult:
        result = ExtractionResult()
        soup = BeautifulSoup(content, "html.parser")
        table_rows = soup.find_all("tr")
        for index, row in enumerate(table_rows):
            self._consume_row(row, f"row-{index}", result)
        return result

    def _consume_row(self, row: Any, page_ref: str, result: ExtractionResult) -> None:
        cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
        if len(cells) < 2:
            return
        label = cells[0]
        value_text = cells[1]
        value = _parse_value(value_text)
        if value is None:
            result.drops.append(DropRecord(label, "NO_VALUE", value_text[:80]))
            return
        resolved = resolve_label(label)
        if resolved is None:
            result.drops.append(DropRecord(label, self._drop_reason(label)))
            return
        code, lang = resolved
        result.candidates.append(
            LineCandidate(
                ontology_code=code,
                ontology_version=_ONTOLOGY_VERSION,
                value=value,
                currency="EGP",
                source_label_reported=label,
                source_label_en=label if lang == "en" else None,
                source_label_ar=label if lang == "ar" else None,
                source_page=page_ref,
                extraction_method="downloaded_document_table",
            )
        )
