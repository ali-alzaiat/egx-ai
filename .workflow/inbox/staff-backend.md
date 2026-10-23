# Staff-Backend brief — ZBorsa Task 9/10 test recovery + gate fixes (2026-10-22)

Read first: docs/superpowers/plans/2026-10-17-zborsa-upgrade.md (Tasks 9, 10, and Global Constraints / Review Focus #5). Scope: `backend/**` only. Do NOT touch `frontend/**` or `.workflow/**`.

## Context
Commit `9e08e23` shipped Task 9 (`app/signals/stance.py`, `app/api/stance.py`) and Task 10 (`app/billing/*`, `app/api/billing.py`, `app/models/billing.py`, migration `020_billing.py`) as CODE WITHOUT their plan-required tests. Your job: write the missing tests, fix the code to satisfy both the plan interfaces and your own tests, and leave the backend gate-clean.

## Current known gate state (baseline 2026-10-22)
- **Environment FIXED and ready:** Docker/WSL2 was repaired and Postgres is up (docker compose). A FRESH GATE DB exists at `postgresql://postgres:postgres@localhost:5432/egx_ai_gate` with `alembic upgrade head` already applied (head = 020, all statement/billing tables created and seeded). Run ALL your gates with `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/egx_ai_gate` (env var) set in the same shell as pytest/alembic. Do NOT touch the `egx_ai` dev DB.
- `mypy app`: 5 errors — `app/statements/service.py:149` (Invalid index type `UUID | None`), `app/api/screening.py:331` (JSONResponse vs dict), `app/api/stance.py:118` and `:119` (dict-item int|str vs None). Fix ALL five in whatever way is correct per the plan's error-handling shape.
- `ruff check .`: 113 repo errors. Zero NEW errors allowed in your touched files (F401/I001/W292/E501 appear in the new statements/billing/stance code — clean `app/` and `tests/` files you touch; pre-existing alembic debt is explicitly OUT of scope).
- 2026-10-22 note: two earlier full-suite runs hit an env outage (dead DB), not a code hang — treat any E-on-setup errors as stale. Run the full suite; if any test exceeds ~60s/individual, record it and continue past it via deselect, never assume.

## Work list
1. **Task 9 tests → `backend/tests/test_stance_service.py`** per plan Task 9 "Tests" line: deterministic rubric golden cases (each rule triggered: technical, valuation gap, score tier, Shariah, freshness), cap-on-insufficient (confidence ≤ 40, missing-input limitation first), scenario-order guard (bear ≥ entry ≥ bull→ targets INSUFFICIENT_DATA/SCENARIO_ORDER), stop from entry vs range-low, limitations invariant (non-CS empty limitations), valuation INSUFFICIENT → TargetLevel(status INSUFFICIENT_DATA, value None). Endpoint tests: `stop_pct` validation 422 beyond (0, 90], radar page_size ≤ 50. Constants must match the code's `SIGNAL_RULES_VERSION = "signal-rules-1.0"` and the compliance copy.
2. **Task 10 tests → `backend/tests/test_billing.py` + `backend/tests/test_entitlements.py`** per plan: plan seeds exact entitlement numbers (FREE=3 stance/day, FREE=1 radar); 429 shape `{"error":"QUOTA_EXCEEDED","quota":n,"tier":t}` on 4th stance; radar quota; forged webhook (bad/missing signature → PaymentProviderSignatureError, subscription ROW UNCHANGED — Review Focus #5); replay (same event_id twice → second rejected); canceled sub drops to FREE immediately (quota re-check); checkout for Free returns `{"provider":"manual","url":None}`.
3. **Fix code where interfaces/tests disagree** — the code is authoritative ONLY if it matches plan interfaces; where it does not (spec-fixed rubric points, checkpoint values, response shapes), prefer the plan. File-gate: `ruff check <touched files>`, `mypy app` (0 errors overall — the 5 listed must also be fixed), full pytest (with hang workaround noted above).
4. **Migration 020 sanity:** run upgrade/downgrade roundtrip on the gate DB if reachable (`DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/egx_ai_gate`); if DB is unreachable, note it — do not fabricate a pass.

## Rules
- Versioned methodologies stay versioned; deterministic math in code; `{"value": null, "status": "INSUFFICIENT_DATA", "reason": ...}` shape exact; no zero-fill.
- Follow existing test conventions in tests/ (fixtures, client( ) pattern used by test_statement_review_api.py etc.).
- Do NOT commit; leave changes in the working tree (router commits after QA).

## Result contract
End with exactly ONE of: `DONE` (with gate evidence: pytest counts, ruff, mypy output tails), `BLOCKED: <question>`, `ASK USER: <precise question>`, or `NEXT: <agent>`.
