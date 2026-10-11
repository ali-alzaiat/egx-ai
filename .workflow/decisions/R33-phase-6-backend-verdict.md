# R33 — Phase 6 backend verdict (Shariah, R32 B1–B6)

**From:** Mostafa (tech-lead) · 2026-10-10
**Sources:** qa-api conformance (R32 B1–B6 PASS, gates green); live code
verified this session: `backend/alembic/versions/016_shariah_phase6.py:8-10`,
`backend/app/api/screening.py:140-207,366-423,449-503`,
`backend/app/repositories/screening.py:104-119,202-217`,
`backend/tests/test_screening_phase6.py:27,494-510`; gates re-run from
`backend/`: 46 screening tests passed, ruff 1 error (F1), mypy clean (134 files).
**Binding:** R32 scope B1–B6; AGENTS.md rules 1/2/3/5/6/7/10.

## Conformance — PASS (B1–B6)

B1 v2 identifier, B2 report_date + per-rule provenance, B3 purification
formula/doctrine/branches, B4 honest INSUFFICIENT_DATA degradation, B5 EGX33
side-by-side with flagged discrepancy and no override path, B6 one migration
(016) + contracts kept — all present per qa-api, no evidence to the contrary
in the files sampled. Gates re-verified: `pytest
tests/test_screening_phase6.py tests/test_screening.py` → **46 passed**;
`mypy app` → clean (134 files).

## F1 ruling — FIX-LIST (one-line ruff autofix, no discretion)

**Confirmed** via `.venv/bin/ruff check`: `016_shariah_phase6.py:8`
`I001 Import block is un-sorted` — `from alembic import op` before
`import sqlalchemy as sa`. Fix is the documented autofix (swap lines 8–9).
Gates require ruff clean; this is the only red. **Fix now:** apply
`ruff check --fix` on the file, nothing else.

## O1 ruling — ACCEPT AS-CORRECT (no change, test stays)

Bad `review_cycle` → **422** (`screening.py:419-423`) is FastAPI-idiomatic
(Pydantic validation errors are 422; manual 422 matches), and it is
**test-pinned** (`test_screening_phase6.py:502` asserts 422 for `2026-05`).
A 400 would break the pin and diverge from framework convention for zero
consumer gain. No brief demand for 400 (R32 B5 specifies Feb/Aug cycles,
not a status code). Rejected; test stands as the contract.

## O2 ruling — ACCEPT-AND-CARRY (single-GET version filter)

**Confirmed:** `list_screened_companies` exposes `?methodology_version`
(`screening.py:186,191-194`); single-GETs (`GET .../companies/{id}`,
`GET .../purification`) do not, though the repository already accepts the
parameter (`repositories/screening.py:104-108,202-206` — pass-through is
6 lines + test). R32 B1 ("old rows stay readable via version filter") is
satisfied in letter by the list filter + version echo on every record;
no evidence any consumer needs old-version full breakdown today (no
Phase-6 frontend in this verdict). Cost-of-delay is nil; expanding the GET
surface now buys nothing for the continuous run. **Carry (binding):**
the next touch of `app/api/screening.py` (Phase 7 filings or any screening
follow-up) adds `methodology_version: str | None = Query(None)` to both
single-GETs, passes it to the repo calls, and adds a pinned test
(old-version row readable via single-GET, latest still default).

## O3 ruling — ACCEPT-AND-CARRY (404-shape tests on new sub-resources)

**Confirmed:** no 404 assertions in `test_screening_phase6.py` (grep for
404/unknown returns zero in that file), while the code raises the standard
shapes (`screening.py:376-377` company, `:382` estimate-missing,
`:459-460` company on egx-membership) identical to already-tested routes.
Missing tests, not a functional defect — no wrong-shape evidence. Test-only
addition does not justify holding the phase. **Carry (binding):** fold
404-shape tests for POST/GET purification + POST/GET egx-membership
(unknown company → 404 `Company not found`; GET purification with no
estimate → 404) into the next screening QA pass; qa-api to confirm then.

## Verdict: FIX-LIST then ship (no rework, no second verdict)

Phase 6 backend **conforms to R32 (B1–B6)** and ships once the follow-up
lands; no return to tech-lead — qa-api re-verifies the fix-list green
and the phase ships per this ruling.

1. **F1:** `ruff check --fix` on `016_shariah_phase6.py` (import order only).
