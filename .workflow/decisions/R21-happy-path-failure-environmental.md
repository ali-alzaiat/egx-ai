# R21 — Ruling: `test_full_refresh_happy_path` failure is environmental, not from the R20 diff

**From:** Mostafa (tech-lead) · 2026-10-10
**Inputs:** inbox brief; `backend/tests/test_ingestion_jobs.py:99-129`; `backend/app/ingestion/sync.py` working-tree diff; `backend/app/dataquality/service.py:369-407` (`_persist`); `backend/tests/conftest.py:16-33` (`db_session`); `backend/app/ingestion/jobs.py:229-244`; live `pytest` run output.

## Verification (ran and read, not remembered)

- **Reproduced the failure:** `.venv/bin/python -m pytest tests/test_ingestion_jobs.py::test_full_refresh_happy_path` → `assert 1374 == (229 * 3)` at line 129. Exactly 2× the expected 687.
- **The R20 diff cannot reach this failure.** The fix only adds an `else: failures.append(...)` branch for empty `bars` in `sync.py`. The happy path uses `_StubProvider()` with no `fail`/`empty` tickers, so every ticker takes the unchanged `if bars` branch. The failing line (129) is a global row count, downstream of none of the changed lines. Staff-backend's stash check (identical failure without the change) is consistent.
- **The assertion is fragile by construction.** Lines 125-129 count *global* `Company` and `DataQualityAssessment` rows. `conftest.py:16-33` binds `db_session` to the shared `engine` (the dev `egx_ai` DB) and rolls back only the test's own writes — pre-existing committed rows remain visible. Any history in the DB breaks `rows == companies×3` structurally.
- **No upsert-dedup defect (option (b) rejected).** `_persist` (`service.py:377-391`) is idempotent per (company, scope, as_of, methodology_version): delete-then-insert + flush. A same-day re-run replaces rows; it cannot accumulate. 6 rows/company = 2 distinct key-sets (prior dates/versions) = legitimate history, handled by `latest()` via `order_by(as_of desc, computed_at desc)`. Corroborating: the job's *own* counter assertion (`scores_written == assessed×3`, lines 120-123) **passed** — only the global-count line failed.

## Ruling — option (a): ENVIRONMENTAL

1. The R20 fix stands as landed (regression test green, ruff/mypy clean; diff minimal).
2. **qa-api** re-verifies the jobs file on a **clean test DB** (fresh database, or truncate `data_quality_assessments` + non-test companies first). On green, **Stream A ships per R20** without returning to tech-lead.
3. Ledger note (advisory): `test_full_refresh_happy_path:125-129` asserts a global census and will fail on any non-empty DB. If it bites again, scope it (filter to the run's `as_of`/companies, or assert the delta) — a later hardening pass, not a Stream A gate.
