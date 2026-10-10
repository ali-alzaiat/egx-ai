# Inbox: staff-backend

From: router (Phase 3 authorized) · 2026-10-10
Task: Implement Phase 3 backend per `.superpowers/sdd/2026-10-08-competitive-enhancement-roadmap/task-phase-3-brief.md` (R25 V1–V6 under R26: re-verify 013 chain first, extend `app/valuation/` in place, additive router change only). Research context: `.workflow/research/phase-3-valuation.md`. Backend only. End NEXT: qa-api | BLOCKED: <question> | DONE + files + pasted gate outputs.

---

From: router (R24 fix-list) · 2026-10-10
Task: R24 three-item fix-list, backend only: (F1) emit BOTH `reason` and `explanation` keys (same string) on industry percentile entries + test; (F2) wire real `display_name` via in-repo `get_metric()` with fallback + test; (F3) PUT-`[]` regression test pinning "explicit empty override" semantics (basis `override`, INSUFFICIENT_DATA floor). Details in `.workflow/decisions/R24-phase-2-backend-verdict.md`. No rework, nothing else. Run pytest on touched suites + ruff + mypy, paste outputs. Never touch frontend/** or .workflow/**. End NEXT: qa-api | BLOCKED: <question> | DONE + files + evidence.

---

From: router (Phase 2 authorized) · 2026-10-10
Task: Implement Phase 2 backend per `.superpowers/sdd/2026-10-08-competitive-enhancement-roadmap/task-phase-2-brief.md` (R22 scope + R23 migration 012; research Track A). Backend only. End NEXT: qa-api | BLOCKED: <question> | DONE + files + pasted gate outputs.

---

From: router (R20 fix-list) · 2026-10-10
Task: One fix in `backend/app/ingestion/sync.py::fetch_one` — treat empty `bars` (`[]`, the provider's real no-history signal per `egx/provider.py:145,158-160`) as a failure entry `failures.append((ticker, "Yahoo returned no history"))` so the job reports `partial` with the ticker in `failed_tickers` instead of lying `done`/`failed_count 0`. Add the R20 regression test to `backend/tests/test_ingestion_jobs.py` (stub returns `[]`: assert `partial`, `failed_count == 1`, exact `failed_tickers` entry, assessment still ran; keep raise-path test green). No contract change. Run pytest on the jobs file + ruff + mypy on touched files, paste outputs. Scope: backend only; never touch frontend/** or .workflow/**. End with NEXT: qa-ui | BLOCKED: <question> | DONE + files + evidence. (Prior Stream A brief kept below for context.)

---

From: router (direct dispatch, no tech-lead briefing hop) · 2026-10-09
Parallel stream A: implement the refresh + automatic assessment closeout for the two
reported data gaps.

## Reference contract (single source of truth)
- `.workflow/design/refresh-and-assess-contract.md` (architect Tarek) — accepted with R16 amendment: `POST /api/ingestion/sync` returns 409 **only while accepted/running**; terminal states start a new job. All interfaces, types, mocks, safety bounds and rejected alternatives are pinned.

## Bindings from rulings
- **R16:** in-process job, no job table; 202 + poll via `GET /api/ingestion/sync/status`; six statuses incl. `idle`; phase order `universe → prices → assessment`; one job at a time; job uses its own sessions (never the request session); `Settings.SYNC_JOB_TIMEOUT_SECONDS=1800` (wait_for); summary-returning core for `sync_prices` (CLI unchanged); assessment runs for every company × 3 scopes via `DataQualityService.assess` (idempotent upsert); `GET /api/data-quality/...` stays read-only.
- **R18:** fold Task 7 review into this work's review — verify R15 invariants: stamp in `write_prices` (not `ingest_prices`), `base_url` only, no `description`, `last_synced_at` not backfilled, test `backend/tests/test_sync_provenance.py` still meaningful and the sync path still works. Include Task 7's impl `6486ae7` in the diff-under-review.

## Deliverables / files to change
- `backend/app/ingestion/jobs.py` — new module (job state + runner + single-flight + timeout)
- `backend/app/api/ingestion.py` — new router, mount at `/api/ingestion`; two routes
- `backend/app/ingestion/sync.py` — extract summary-returning core from `sync_prices`; CLI unchanged
- `backend/app/core/config.py` — `SYNC_JOB_TIMEOUT_SECONDS: int = 1800`
- `backend/app/api/data_sources.py` — add `last_synced_at` to each item
- `backend/app/main.py` — `app.include_router(ingestion.router)`
- Tests: `backend/tests/test_ingestion_jobs.py` (happy path 202→done, 409 single-flight, partial, failed, timeout, assessment rows exist, GET status always 200, R16 409-while-running vs new job on terminal/idle). Extend `backend/tests/test_data_quality_api.py` lightly if needed, but do not weaken GET read-only contract. `test_sync_provenance.py` unchanged in spirit, still passes.

## Implementation notes
- Job holds a task reference to prevent GC; uses `asyncio.wait_for(settings.SYNC_JOB_TIMEOUT_SECONDS)`.
- Per-ticker price failures → `failed_tickers` capped at 20, `failed_count` full; job becomes `partial` (or `failed` only on uncaught exception/timeout).
- Assessment: sequential, one session, commit per company; `assessment.scores_written` counts upserted rows (company×3). Reuse `DataQualityService` exactly as-is (no signature changes).
- Do not add a job table. Do not add compute-if-missing to GET. Follow existing hand-serialization style (strings/isoformat).

## Verification gates
- `cd backend && .venv/bin/pytest -q` → green
- `cd backend && .venv/bin/ruff check app tests` → clean
- `cd backend && .venv/bin/mypy app` → 0 errors (no baseline deferral for new code)

## Handoff
End with exactly one contract string: NEXT: qa-api, BLOCKED: <question>, or DONE.
