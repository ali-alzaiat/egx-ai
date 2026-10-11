# R37 — Phase 7 findings verdict (supplements R36; rules qa-api F1–F7)

**From:** Mostafa (tech-lead) · 2026-10-11
**Supplements:** R36 (SHIP stands; this ruling disposes of the 7 findings R36 did not address).
**Sources:** R34 scope, R35 authorization, live code + gates re-run 2026-10-11:
- `pytest tests/test_disclosures_phase7.py` → **67 passed**
- `ruff check` on Phase-7 files (`api/disclosures.py`, `ingestion/disclosures/`, `models/disclosure.py`, `repositories/disclosure.py`, `tests/test_disclosures_phase7.py`, `017_disclosure_phase7.py`) → **clean**. Tree-wide ruff shows 10 E501s, all in Phase-8 in-flight files (`api/companies.py`, `ingestion/financial_service.py`, `ingestion/fra/provider.py`) — out of Phase-7 scope.
- `mypy app` → **clean (147 source files)**.
- `.venv/bin/pip show`: `python-multipart` → `License-Expression: Apache-2.0`; `camelot-py` → `MIT`; `pdfplumber` metadata blank (upstream MIT, unchanged from R35).
- `app/api/disclosures.py` → **8 `@router` routes** (register, upload, filings GET, parse POST, facts POST, facts GET, comparison GET, diffs GET).
- `tests/test_disclosures_phase7.py:1096-1145` pins **404 + 422**; `test_full_round_trip` exists (`:1005`); no alembic upgrade/downgrade test; `UNKNOWN` pinned (`:248,277,345,350,451,1067,1126`).
- `DisclosureService.filing_payload` (`service.py:774-790`) carries **no** `methodology_version`; fact (`facts.py:142`), comparison (`service.py:697`), and diff (`service.py:759`, `diffs.py:95`) payloads do.
**Binding:** R34 P0-1–P0-6; R35 dep ruling (as corrected below); AGENTS.md 1/2/3/5/6/7/10.

## Rulings

- **F1 — python-multipart is Apache-2.0, not MIT as R36 declared: CORRECT THE RECORD, no code fix, no carry.** Verified via installed metadata (`License-Expression: Apache-2.0`). Apache-2.0 is permissive, MIT-compatible, no copyleft — the R35 intent (no AGPL; PyMuPDF stays rejected) is fully preserved. R36's "python-multipart (MIT)" line is amended to Apache-2.0 by this ruling. Nothing to change in `pyproject.toml` (version pins carry no license claim).
- **F2 — fact blocks emit UNKNOWN vs AGENTS.md INSUFFICIENT_DATA literal (TTM blocks use INSUFFICIENT_DATA): ACCEPT-AND-CARRY, no code fix.** The split is R34-scoped, not a defect: P0-4 makes UNKNOWN first-class for fact/provenance blocks ("missing numeral → UNKNOWN, never zero"), P0-5 mandates INSUFFICIENT_DATA for short TTM windows. Implementation follows scope exactly and UNKNOWN is pinned by 7+ test assertions — renaming now would churn scope plus the green suite for zero behavioral gain. Carry: surface the two-vocabulary note (`fact.value.status ∈ {OK,UNKNOWN}` vs `comparison.*.status ∈ {OK,INSUFFICIENT_DATA}`) to the frontend catch-up / next API-consumer touch; unify only if a cross-phase status enum is ever scoped.
- **F3 — validation errors 422 vs brief 404/400: ACCEPT, no code fix, no carry.** Code maps `LookupError→404`, `ValueError→422`, Pydantic→422 automatic; tests pin 404+422. 422 is correct HTTP semantics for semantic validation failures and matches the R33-O1 precedent (FastAPI-idiomatic, test-pinned). The brief's "404/400" wording is corrected by this ruling; no code change.
- **F4 — filing_payload lacks methodology_version: ACCEPT-AND-CARRY (next disclosures touch).** Genuine but minor: the cross-phase contract wants the version on records, and every *computed* output already echoes it (fact/comparison/diff). Filing rows are registry pointers (URL/hash/dates) with no methodology-dependent computation, so no consumer can misattribute methodology today. Fix is a one-line constant echo + assertion — scheduled as carry, not a fix-list, to avoid churning a shipped phase for metadata. (Router: add to STATUS carry-forward.)
- **F5 — 8 routes vs brief 7: ACCEPT, correct the record, no carry.** Count-only. The 8th route (`GET /filings` list) is the natural read side of the P0-1 registry P0-1's own accept criterion ("same PDF twice → single row") needs for verification. No scope breach; R36's "7 endpoints" is amended to 8 by this ruling.
- **F6 — no 017 round-trip test: ACCEPT, no fix-list; carry a migration smoke test as nice-to-have.** API round-trip IS covered (`test_full_round_trip`, `:1005`); the missing piece is an alembic upgrade/downgrade test. Chain integrity was verified at authorization (R35: `down_revision="016"`, 017 free) and is corroborated by the in-flight Phase-8 tree chaining on top without complaint. Carry: fold an 017 (or next-migration) upgrade/downgrade smoke test into the next backend migration touch.
- **F7 — stress unprobed: ACCEPT, no carry.** Disclosure endpoints are synchronous DB CRUD + sha256 hash; there is no background job or single-flight protocol (unlike the ingestion sync), and double-registration is covered by hash dedupe (tested). ASGI defaults stand per the R24 precedent; load probing belongs to pre-production hardening, not a phase gate.

## Verdict: SHIP (R36 stands, supplemented)

Phase 7 backend **ships**. No fix-list, no rework. Carries for the router to file: (1) F4 methodology_version echo on filing_payload at next disclosures touch; (2) F2 two-vocabulary note for frontend catch-up; (3) F6 migration smoke test at next migration touch.
