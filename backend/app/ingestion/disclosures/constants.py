"""Pinned constants for Phase-7 document intelligence (methodology version 1.0).

Sources (via `.workflow/research/phase-7-document-intelligence.md`):
- Intake mirror shape (content hash + bulletin id + download timestamp as the
  durability precedent): FoudaLens permanent disclosure mirror,
  https://foudalens.com/en/disclosures (research §1).
- Rule-based parse v1 (Camelot lattice/stream + pdfplumber bordered-table path,
  parsing_report accuracy/whitespace as confidence input): Camelot
  https://github.com/atlanhq/camelot and the pdfplumber-vs-PyMuPDF benchmark
  https://pdfmux.com/blog/pymupdf-vs-pdfplumber (research §2a).
- EAS gotcha tags + per-filing accounting_basis (never silently pool EAS with
  IFRS): IFRS Egypt jurisdiction profile,
  https://www.ifrs.org/content/dam/ifrs/publications/jurisdictions/pdf-profiles/egypt-ifrs-profile.pdf
  (research §2c).
- Period comparison (TTM + Q-vs-Q + TTM-margin-vs-prior-year) + own diff ledger
  with As-Restated detection: Simply Wall St past-performance + Koyfin
  Actuals-vs-Consensus + SEC XBRL restatement columns (research §3).
- Provenance record shape (page/cell locator + extraction report +
  methodology_version + first-class UNKNOWN): halal.sh compliance object +
  Docling page/bbox geometry (research §4).
Changing any value below requires bumping DISCLOSURE_METHODOLOGY_VERSION.
"""

DISCLOSURE_METHODOLOGY_VERSION = "1.0"

#: Filing types accepted at intake (R34 P0-1): periodic statements plus the
#: EGX continuing-obligation disclosure forms.
FILING_TYPES: tuple[str, ...] = ("Q", "H1", "9M", "FY", "BOARD", "AGM", "MATERIAL")

#: Accounting bases stored per filing (R34 P0-3). Banks filing under CBE
#: instructions on top of EAS use EAS+CBE.
ACCOUNTING_BASES: tuple[str, ...] = ("EAS", "EAS+CBE", "IFRS")

#: Bases that may be pooled without a comparator refusal.
EAS_FAMILY: tuple[str, ...] = ("EAS", "EAS+CBE")

#: The five EAS-vs-IFRS gotchas, stored per fact (R34 P0-3, research §2c).
EAS_GOTCHA_TAGS: tuple[str, ...] = (
    "profit-sharing-distribution",
    "fx-remeasurement-2016-2022-23",
    "pre2023-no-revaluation",
    "two-statement-format",
    "separate-no-equity-method",
)

#: Parse engines (R34 P0-2 + R35): pdfplumber-first, Camelot behind the same
#: interface. PyMuPDF stays REJECTED (AGPL); Tabula/Docling stay DEFERRED.
PARSE_ENGINES: tuple[str, ...] = ("pdfplumber", "camelot")

#: Table-structure modes shared by both engines (Camelot flavour names).
PARSE_METHODS: tuple[str, ...] = ("lattice", "stream")

#: Audit states stored per fact; the caller states what the filing says.
AUDIT_STATES: tuple[str, ...] = ("audited", "reviewed", "unaudited")

#: Provenance fact statuses (R34 P0-4). UNKNOWN is first-class: a missing
#: numeral is stored as UNKNOWN, never as zero.
FACT_STATUSES: tuple[str, ...] = ("OK", "UNKNOWN")

#: Diff-ledger row kinds (R34 P0-6).
DIFF_KINDS: tuple[str, ...] = ("period_diff", "restatement")

#: Beat/miss labels; only written where an estimate exists.
BEAT_MISS_LABELS: tuple[str, ...] = ("beat", "miss")

#: Quarterly period types used for TTM/YoY series (Phase-1 enum values).
QUARTER_PERIOD_TYPES: tuple[str, ...] = ("Q1", "Q2", "Q3", "Q4")

#: Intake trust boundary: uploads larger than this are rejected outright.
MAX_PDF_BYTES = 25_000_000

#: DataSource row auto-provisioned for disclosure documents (manual intake).
DISCLOSURE_DATA_SOURCE_NAME = "EGX Bulletin Mirror"

#: Default metrics for the TTM-margin-vs-prior-year block (R34 P0-5).
MARGIN_REVENUE_METRIC = "revenue"
MARGIN_INCOME_METRIC = "net_income"
