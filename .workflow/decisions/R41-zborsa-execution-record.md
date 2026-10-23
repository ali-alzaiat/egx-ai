# R41 — ZBorsa upgrade execution record + deviations found

**Date:** 2026-10-23
**Scope:** Implementation record of `docs/superpowers/plans/2026-10-17-zborsa-upgrade.md` (spec `design/zborsa-inspired-upgrade-spec.md`).

## Ship record

Tasks 1–14 SHIPPED on main:

- Tasks 1–6: commits `216b46c`, `0570cff`, `ca8f13e`, `daf22e5`, `05ce6d8`, `0f6b2da` (+ review-gate fixes `f6a1fd5`).
- Task 7: `d82f76b`. Task 8–11 (screening re-feed, stance code, billing code, contract surface): `9e08e23` + parallel-session cleanups (`f667297`, `95e3e77`, `399fc7a`).
- Tasks 12–14 (frontend): lanes F1–F4 (`47123c3`) integrated with the parallel remote terminal-restyle (`3b7578d`, all tree gates green). Remote implementations won page conflicts; local structure (radar table, radarSort+tests, savings goldens) kept where remote had nothing.
- Task 9/10 tests (recovery pass, 2026-10-23): `test_stance_service.py` (24), `test_billing.py` (20), `test_entitlements.py` (5) — 49/49 green on gate DB; mypy 0/181; ruff clean app+tests.
- Full backend suite on gate DB: 770 passed / 5 failed (environmental, see below).

## Bugs found by the new Task 9/10 tests and FIXED

1. **`Subscription.tier` pg-enum binding bug** (`models/billing.py`): `Enum(PlanTier)` without `values_callable` binds member NAMES (`FREE`) while migration 020's pg enum stores lowercase values → every `Subscription` insert failed. Fixed with the same `values_callable` bridge already used for `Plan.tier`/`Subscription.status` (006–008 lesson).
2. **Canceled subscription kept paid quota** (`billing/service.py.assert_quota`): the quota tier read only `sub.tier`, ignoring `status=CANCELED`, so a canceled PRO user kept 10k/day. Fixed: canceled status ⇒ effective tier FREE immediately.
3. **Unknown checkout tier returned 500** (`api/billing.py`): `PlanTier(tier)` raised `ValueError` on user-supplied garbage. Fixed: `try/except → 404 "plan not found"` (matches the frontend's honest no-provider path; also carries the plan's Review-Focus-5 requirement that no entitlements state is touched without a verified flow).

Noted (accepted, carried): `api/billing.py` contains an unreachable `raise` after the `HTTPException` re-raise in the webhook handler (dead line, cosmetic).

## Rubric finding (unfixed, needs a ruling next pivot)

**BUY stance is unreachable under the fixed rubric.** Maximum achievable positive total = technical +20 + valuation +25 + score +10 = 55, strictly below the ≥60 BUY floor — stale_statementspenalty paths (Shariah −30, freshness −15) only pull down. Behavior is pinned at HOLD in `test_max_bullish_case_is_hold`. Either the BUY floor should be ≤55 or a positive-points source must be added; deliberate single-award decision, not a code change made under test pressure.

## Logged deviations (from plan §"Known deviations", confirmed at execution)

1. Real-PDF fixtures deferred until a real filing is fetched through FetchService; PDF path covered by the Task 6 integration once one lands.
2. Non-compliant income share remains an industry-rule input (ontology v1 has no income-breakdown code).
3. Review queue = line-status filter (no `PendingFinancialData` backend model exists; reason logged in the plan self-review).
4. Real PSP integration = open blocker (spec §non-goals; manual adapter is DEV/TEST ONLY, collects no funds).
5. **BATCH_1_TICKERS left empty `tuple()`** (plan Task 3 rule): `data/egx_universe.csv` is gitignored and absent on the executing machine, so the top-10 EGX30 list cannot be verified from the running system here. `fetch_company`/`fetch_batch` take explicit tickers in the interim; fill the constant + this record when a verified universe snapshot is available.

## Environmental failures on the gate DB (machine-local fixture data)

5 pre-existing tests fail on this machine only, all tracing to missing machine-local fixture data (`data/` dir is gitignored; snapshot `data/egx_universe.csv` and DB seeds from prior ingestion runs are absent here):

- `test_universe.py::test_committed_snapshot_is_marked_as_fallback` and `test_signals_api.py` ×2 — `UniverseDiscoveryError: no universe snapshot at ...\data\egx_universe.csv` (ingest/freshness + re-run scoring).
- `test_ingestion_jobs.py::test_data_sources_exposes_last_synced_at` — asserts "the dev/test database always has at least one source"; empty gate DB has none.
- `test_screening_phase6.py::test_bank_carve_out_never_silent_zero` — depends on a seeded data source row.

Carry-forward: make these tests skip cleanly (pytest.skip) when their fixture data is absent, or ship a committed fixture snapshot, so the zero-fail gate is portable across machines.

## Data warning (carried)

`DATA WARNING: outputs computed on synthetic data — not for real-money use until Phase 13 ships` (standing pre-phase gate; 0 real financial facts in DB).
