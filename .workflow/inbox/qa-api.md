# Inbox: qa-api

From: router (R29 fix-list re-verify) · 2026-10-10
Task: Final re-verify of the R29 fix-list (uncommitted tree on main) — read-only: read-path reconstruction (reason/health_track/ticker on GET, no migration), headline number in both builders, round-trip test (`backend/app/scores/service.py`, `backend/app/repositories/scores.py`, `backend/tests/test_scores_api.py`). Re-run scores suites + ruff + mypy (.venv binaries), paste outputs. On green, Phase 4 SHIPS per R29 (no return to tech-lead) — end DONE. Anything red → NEXT: tech-lead with evidence. Never write under .workflow/ or append handoffs.log.

---

From: router (Phase 4 conformance) · 2026-10-10
Task: Contract-conformance review of the Phase 4 backend (uncommitted tree on main) — read-only. Source of truth: R28 (`.workflow/decisions/R28-phase-4-scope.md` P1–P6), brief `task-phase-4-brief.md`. Implementation: `app/scores/` (checks/constants/service/seed), `app/models/scores.py`, `app/repositories/scores.py`, `app/api/scores.py` (GET + assess POST), migration `014_scores.py`. Checks: 23-check determinism (pass/fail/not-run, missing never fail/zero); floors (≥3/6, ≥3/5, headline null+reason); equal weights only (no fitted); dual-track routing + profile echo; confidence ladder never moves score (margin-of-safety display-only); explanation completeness + hedged copy (never BUY); 014 chain + round-trip; 404 shapes; methodology_version everywhere; assess-POST gap-filling honesty (latest price/FV/metrics/DQ-None). Known pre-existing: happy-path census failure (R21). Re-run gates you doubt (.venv binaries), paste outputs. Never write under .workflow/ or append handoffs.log. End NEXT: <agent> | BLOCKED: <question> | DONE + findings with file:line evidence.

---

From: router (R27 fix-list re-verify) · 2026-10-10
Task: Final re-verify of the R27 fix-list (uncommitted tree) — read-only: corrected `get_fair_value` docstring, last-writer-wins notes, pinning test (`backend/app/api/valuation.py`, `backend/app/repositories/valuation.py`, `backend/tests/test_valuation_fair_value_api.py`). Re-run valuation suites + ruff + mypy (.venv binaries), paste outputs. On green, Phase 3 SHIPS per R27 (no return to tech-lead) — end DONE. Anything red → NEXT: tech-lead with evidence. Never write under .workflow/ or append handoffs.log.

---

From: router (Phase 3 conformance) · 2026-10-10
Task: Contract-conformance review of the Phase 3 backend (uncommitted tree) — read-only. Source of truth: R25 (`.workflow/decisions/R25-phase-3-scope.md` V1–V6), R26 constraints, brief `task-phase-3-brief.md`. Implementation: `app/valuation/{models,constants,fairvalue,seed,service}.py`, `app/models/valuation.py`, `app/repositories/valuation.py`, `app/api/valuation.py` (new GET `.../fair-value`, existing GET byte-identical), migration `013_valuation.py`. **Headline check:** implementer flags GET fair-value *flushes* (never commits) a deterministic snapshot cache — rule whether any DB write inside a GET violates the read-only-GET contract (R16) or is acceptable session hygiene; if the latter, say what test would pin it. Also: 4-model determinism (no fabricated growth/CoE), profile routing + exposed weights, bull/base/bear ordering + copy (never BUY), 1-D monotonicity, DQ ladder + MISSING degradation, 013 chain + round-trip, additive-router proof (existing GET shape test), methodology_version everywhere. Known pre-existing: happy-path census failure (R21). Re-run gates you doubt (.venv binaries), paste outputs. Never write under .workflow/ or append handoffs.log. End NEXT: <agent> | BLOCKED: <question> | DONE + findings with file:line evidence.

---

From: router (R24 fix-list re-verify) · 2026-10-10
Task: Final re-verify of the R24 fix-list (uncommitted tree) — read-only: F1 dual reason/explanation keys + test, F2 display_name via get_metric() + test, F3 PUT-[] regression test (`backend/app/industry/service.py`, `backend/tests/test_industry_api.py`). Re-run industry suites + ruff + mypy (.venv binaries), paste outputs. On green, Phase 2 backend SHIPS per R24 (no return to tech-lead) — end DONE. Anything red → NEXT: tech-lead with evidence. Never write under .workflow/ or append handoffs.log.

---

From: router (Phase 2 conformance) · 2026-10-10
Task: Contract-conformance review of the Phase 2 backend (uncommitted tree) — read-only. Source of truth: R22 (`.workflow/decisions/R22-phase-2-scope.md` R1–R6 + acceptance lines), R23 (migration 012), brief `task-phase-2-brief.md`. Implementation: `backend/app/models/industry.py`, `backend/app/industry/` (constants/percentiles/backfill/seed/service), `backend/app/repositories/industry.py`, `backend/app/api/industry.py` (GET peers+percentiles, PUT override), migration `012_industry.py`. Checks: GICS 4-level chain + EGX-18 mapping with provenance (only 4 EGX→GICS mappings seeded — verify claimed-verified-only); ISIN backfill honesty (no fabrication); override versioning; profile scoping + default fallback; INSUFFICIENT_DATA floor (minimum-N=3, target included) + explanation strings; methodology_version everywhere; 404/400 shapes; migration up/down. Known pre-existing failure (not this diff): `test_full_refresh_happy_path` census (R21). Re-run gates you doubt (pytest/ruff/mypy, .venv binaries), paste outputs. Never write under .workflow/ or append handoffs.log. End NEXT: <agent> | BLOCKED: <question> | DONE + findings with file:line evidence.

---

From: router (R21 re-verify) · 2026-10-10
Task: Re-verify `backend/tests/test_ingestion_jobs.py` on a CLEAN test DB per R21 (`.workflow/decisions/R21-happy-path-failure-environmental.md`): fresh database, or truncate `data_quality_assessments` + non-test companies first — the shared dev DB's history breaks the global-census assertion at lines 125-129. Then run the jobs file + ruff + mypy, paste outputs. R20 fix (empty-bars failure entry) + its regression test must be green along with the happy path. Read-only except test-DB hygiene (document exactly what you truncated). On green, Stream A ships per R20 — end DONE. If anything else fails, end NEXT: tech-lead with evidence. Never write under .workflow/ or append handoffs.log.

---

From: router · 2026-10-09 (prior conformance brief kept for record)
Task: Contract-conformance review of Stream A (refresh+assess) backend — read-only, change nothing. Source of truth: `.workflow/design/refresh-and-assess-contract.md` as amended by `.workflow/decisions/R16-refresh-assess-contract.md` (A1: 409 only while a job is live accepted/running; terminal POST starts a new job. C1: history_days clamps). Implementation: `backend/app/api/ingestion.py` (POST /api/ingestion/sync → 202/409; GET /api/ingestion/sync/status), `backend/app/ingestion/jobs.py`, `sync.py` core extraction, `config.py` timeout, `data_sources.py` last_synced_at, read-only `GET /api/data-quality/`. This review also covers R18.1's folded Task 7 scope (`write_prices` stamp inheritance per R15, `36f5c8e..HEAD`).

Checks: endpoint shapes/status codes vs contract §Types/shapes; six job statuses; phase order universe→prices→assessment; assessment rows = companies×3 scopes; DQ GET read-only (no writes); error-shape conformance; stress behavior (double-POST single-flight, restart-after-terminal). Router-verified gates (paste-trusted, re-run if you doubt): pytest 345 passed, ruff clean, mypy 0 errors/106 files. Relevant tests: `backend/tests/test_ingestion_jobs.py`, `test_sync_provenance.py`. Never write under .workflow/ or append handoffs.log. End with exactly one contract string: NEXT: <agent> | BLOCKED: <question> | DONE + findings list with file:line evidence.
