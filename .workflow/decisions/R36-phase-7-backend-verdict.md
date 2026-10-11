# R36 — Phase 7 backend verdict (Document intelligence, R34 P0-1–P0-6 + R35)

**From:** Mostafa (tech-lead) · 2026-10-11
**Sources:** qa-api conformance review (R34 P0-1–P0-6 PASS, all gates green); live code verified:
`backend/app/ingestion/disclosures/` (`constants.py`, `intake.py`, `parse.py`, `facts.py`, `comparison.py`, `diffs.py`, `service.py`),
`backend/app/models/disclosure.py`, `backend/app/repositories/disclosure.py`, `backend/app/api/disclosures.py` (7 endpoints),
migration `017_disclosure_phase7.py`; gates verified:
`pytest tests/test_disclosures_phase7.py` → **67 passed**; `pytest tests/test_ingestion_jobs.py` → **11 passed**;
`ruff check app tests` → **clean**; `mypy app` → **clean (144 source files)**.
**Binding:** R34 scope P0-1–P0-6; R35 dependency ruling; AGENTS.md rules 1/2/3/5/6/7/10.

## Conformance — PASS (P0-1–P0-6)

- **P0-1 (Intake registry):** `FilingRegistry` table with `content_hash` sha256 + `url_hash` deduplication; manual URL registration + upload endpoints; no crawler/poller. Verified: re-registration of identical content returns existing record.
- **P0-2 (Rule-based parse):** `pdfplumber` + `Camelot` registry engines; cell locators (`page`, `table_id`, `row_idx`, `col_idx`, `statement_name`); scanned PDF detection explicitly returns `UNKNOWN` with `scanned-needs-OCR` reason, never silently skipped.
- **P0-3 (EAS gotchas):** `accounting_basis` (EAS / EAS+CBE / IFRS) + 5 EAS tags; pooling guard enforces that cross-basis comparison surfaces tags and refuses unflagged aggregation.
- **P0-4 (Provenance shape):** Full cell locator + extraction metadata attached to normalized facts; missing numerals persist as `UNKNOWN`, never zero.
- **P0-5 (Period comparison):** Deterministic TTM (trailing 4 quarters); single quarter or partial series honestly degrades to `INSUFFICIENT_DATA`; YoY deltas and margin comparisons quantised and preserved.
- **P0-6 (Diffs & restatements):** Diff ledger records changes; restatement detector creates a new fact linking `supersedes_fact_id` while keeping the original historical fact; `as_of` queries faithfully reconstruct pre-restatement state per AGENTS.md rule 4 (no look-ahead).

## Dependencies & Licenses — PASS

`pdfplumber` (MIT), `camelot-py` (MIT), `python-multipart` (MIT) conform to R35. No AGPL copyleft code introduced.

## Verdict: SHIP (no fix-list, no rework)

Phase 7 backend **conforms to R34 (P0-1–P0-6) and R35**; all gates green.
Phase 7 backend **SHIPS**. Continuous run advances.
