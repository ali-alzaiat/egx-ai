# R35 — Phase 7 authorization (Document intelligence, R34 scope verified current)

**From:** tech-lead · 2026-10-11
**Inputs:** R34 scope (`.workflow/decisions/R34-phase-7-scope.md`, P0-1–P0-6 + defers),
research (`.workflow/research/phase-7-document-intelligence.md`),
plan cross-phase contracts (`docs/superpowers/plans/2026-10-08-competitive-enhancement-roadmap.md:71-94`).
**Type:** routine authorization per CONTRACT step 26 (no code disagreement → no scope amendment).

## Verification against live code (all commands run 2026-10-11)

1. **Migration head — 016 landed, 017 free.** `backend/alembic/versions/` lists
   `001`–`016_shariah_phase6.py`; `016` declares `down_revision = "015"` and no
   file takes `016` as `down_revision`. Next revision is `017` — no renumber needed
   (unlike R23).
2. **Intake skeleton confirmed empty.** `backend/app/ingestion/disclosures/__init__.py`
   and `backend/app/ingestion/documents/__init__.py` are both 0 bytes. P0-1 builds
   into `disclosures/`; `documents/` stays out of Phase 7 scope.
3. **New-dep ruling (explicit, as briefed).** `pdfplumber` and `Camelot` are both
   ABSENT from `backend/pyproject.toml` dependencies (verified by reading the file:
   httpx/bs4/yfinance only — no PDF libs). **APPROVED to add both**, license
   justification carried from R34 + research §2a: pdfplumber MIT, Camelot MIT —
   permissive, no copyleft, compatible with project MIT license. PyMuPDF stays
   REJECTED (AGPL, per R34). Tabula stays DEFERRED (Java runtime, per R34).
   Implementation note for the brief: `python:3.12-slim` Dockerfile currently
   installs only `build-essential` — Camelot needs Ghostscript (+ OpenCV for the
   `cv` flavour) via apt. Staff-backend must add the apt packages in the same
   diff or scope parse v1 pdfplumber-first with Camelot behind the same interface.
4. **Collision scan — clean.** No `filing`/`disclosure`/`parsed_fact`/`fact_diff`/
   `restatement`/`ttm` tables in `backend/app/models/` or `backend/alembic/versions/`.
   Existing `financial_documents` / `financial_periods` / `financial_facts`
   (`backend/app/models/financial.py:61-151`) are the Phase-1 surfaces P0-1/P0-4
   extend or reference — no parallel implementation. One router per domain under
   `backend/app/api/` (no `routers/` dir — brief must use `app/api/`). Working tree
   holds only `.workflow/` doc changes; no backend code in flight.
5. **Exit-criteria mapping.** Plan line 81 pins Phase 7 exit as "Disclosure → parse
   → facts with provenance, period comparison, 'what changed?'" = R34 P0-1–P0-6.
   Cross-phase contracts hold: one migration (`017`), UUID PKs, `/api/<domain>/…`,
   `methodology_version` on persisted records.

## Authorization

R34 is current. **staff-backend is authorized** to implement P0-1–P0-6 per R34,
one `017` migration (`down_revision = "016"`), intake registry in
`backend/app/ingestion/disclosures/`, parse v1 (pdfplumber + Camelot, both new MIT
deps approved above), EAS gotcha tags, provenance shape, TTM/YoY comparison, diff
ledger + restatement detector. All R34 defers stand (no crawler, no OCR, no XBRL).

Skipped: re-reading the full Phase-1 financial models (table names verified by grep only).
Risk: Camelot Ghostscript/OpenCV system deps must land in Dockerfile in the same diff,
or first CI run on slim will fail at import.
