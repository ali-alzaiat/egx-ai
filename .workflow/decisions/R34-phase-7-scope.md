# R34 — Phase 7 scope (Document intelligence, roadmap §13–§16)

**From:** pm · 2026-10-11
**Sources:** `.workflow/research/phase-7-document-intelligence.md` + roadmap §13–§16 exit criteria.
**Binding:** AGENTS.md 2/3/5 + INSUFFICIENT_DATA; cross-phase contracts (one migration, UUID PKs, `/api/<domain>/...`, `methodology_version` on records).

## BUILD (in order)

**P0-1 — Disclosure intake registry v1 (manual/registered, mirrored).** One table: `filing_url, bulletin_id, company, report_date, filing_type (Q/H1/9M/FY + board/AGM/material), content_hash (sha256), downloaded_at` + stored PDF bytes/path (own mirror, not a scrape). Intake = explicit URL registration + file upload only. Sources v1: EGX bulletin PDFs + IR packs + CBE bank packs. No crawler, no scheduler.
*Accept: same PDF twice → single row (hash dedupe).*

**P0-2 — Rule-based parse v1: pdfplumber + Camelot only, every cell located.** Lattice vs Stream modes; `parsing_report {accuracy, whitespace, order, page}` as confidence input; locator `{page, table_id+row+col, statement_name}` per cell; separate P&L + OCI pages expected; scanned PDFs → `UNKNOWN {scanned-needs-OCR}`, never silent skip.
*License ruling: PyMuPDF REJECTED (AGPL copyleft); Tabula DEFERRED (Java runtime); Docling/VLM DEFERRED (compute cost, versioned upgrade path; schema already carries engine fields).*

**P0-3 — EAS gotcha tags (all 5, stored per fact).** `accounting_basis: EAS | EAS+CBE | IFRS` + tags (profit-sharing-distribution, fx-remeasurement-2016/2022-23, pre2023-no-revaluation, two-statement-format, separate-no-equity-method). Comparator refuses EAS/IFRS pooling without surfaced tags.

**P0-4 — Provenance record shape v1.** Full fact shape (metric/value/currency/period/source/locator/extraction/basis/methodology_version/status/supersedes); UNKNOWN first-class; missing numeral → UNKNOWN, never zero.

**P0-5 — Period comparison v1: history + TTM + YoY deltas.** Deterministic TTM (trailing-4-quarter sum) + `Q2-2026 vs Q2-2025` framing + TTM-margin-vs-prior-year; 1-yr + TTM only, 5/3-yr deferred. Single quarter → TTM INSUFFICIENT_DATA, not partial sum.

**P0-6 — "What changed?" v1: own diff ledger + minimal restatement detector.** Diff rows (metric, prior/current, delta, delta_pct, period pair) + beat/miss only where estimates exist + restatement detector (same company+metric+period republished → new fact with `supersedes` + As-Restated flag, prior kept for backtest rule 4).
*Accept: `as_of` query returns pre-restatement value.*

## DEFERS (with cost)

1. Auto-crawler/poller/scheduler → Phase 8 (manual intake; zero robots risk).
2. Third-party mirror ingestion → deferred (ToS/scraping risk avoided).
3. Tabula/PyMuPDF/Docling → deferred with stated reasons.
4. OCR + Arabic-Indic numerals → deferred (`no data`); scanned stays UNKNOWN.
5. Koyfin full Actuals-vs-Consensus row → deferred (thin consensus; schema reserves E slots).
6. 5/3-yr best-fit, assumption anchoring, sensitivity/reverse-DCF → deferred.
7. Non-reliance feed/taxonomy → deferred (value-diff detection only).
8. XBRL ingest → deferred (no EGX feed exists).
