# Status
- **Current phase:** Phase 8 — Continuous Intelligence (kickoff per continuous run)
- **Current task:** Batches B–D SHIPPED per R40 (thesis, disclosures, watchlists, alerts, events; all gates zero-errors-zero-warnings). Frontend covers all 20 backend routers — never-behind rule in effect going forward.
- **Shipped:** Phase 1 (data quality), Phase 2 (industry intelligence), Phase 3 (valuation), Phase 4 (investment score), Phase 5 (investment thesis), Phase 6 (Shariah v2), Phase 7 (document intelligence backend per R36, findings verdict R37 — ship, no fix-list), Phase 8 backend (B1–B6 per R38/R39, 650/650) + full frontend catch-up (Batch A company upgrades; Batches B–D per R40). All on `feature/phase8-continuous-intelligence`, committed as `f64c39d`.
- **Next actor:** router → merge/commit decision (phase branch holds backend + frontend; Phase-13 stashes still parked)
- **Open escalations:** none.
- **Carry-forward (address on next relevant touch):**
  - Drop unused `useHealthCheck` on next `client.ts` touch
  - 004→005 migration enum bug (pre-existing)
  - ~~R21 fragile census test~~ — **FIXED 2026-10-11:** resilient assertion (`>= stub_companies * 3`), jobs suite 11/11 green
  - Repo-wide alembic ruff debt (33 pre-existing errors; F1 fixed in Phase 6)
  - Frontend pipeline stalled after Phase 1 — Phases 2–7 backend-only; schedule frontend catch-up
  - Phase 0 import hotfix (`TYPE_CHECKING` in `models/financial.py`) — verified in working tree, clean pytest collection
- **Decisions ledger:** R9–R40 filed. Next ruling: R41.
- **Standing pre-phase data gate (2026-10-11):** 0 real financial facts in DB (`DATA WARNING: outputs computed on synthetic data — not for real-money use until Phase 13 ships`).
- **Subagent models (2026-10-16, per user directive):** all eleven agents on parent model `opencode/muse-spark-1.3-contributor-free`; no tier split.

- **Update 2026-10-17:** Phase 8 alert scope-matching fixed in backend (unscoped/list-scoped rules fire; 3 tests, 653/653, ruff/mypy clean, uncommitted); Alerts/Watchlists ticker-dropdown UX shipped; Watchlist/Alerts/Events UX overhaul implemented per `.workflow/design/watchlist-alerts-events-ux.md` (W1/W3, A1–A4, E1–E3; gates green tsc 0/eslint 0/build 0 warn/vitest 10/10). **Backend scope fix + UX overhaul still UNCOMMITTED on `feature/phase8-continuous-intelligence`.**
- **Subagent models (2026-10-17, per user directive):** all eleven agents switched to parent model `opencode/glm-5.3-flash-free` (effective after opencode restart).
- **Carry-forward added:** W2 — watchlist numeric-metric model rename/delete endpoints (PATCH/DELETE on `/api/watchlists/{id}`) are absent in `backend/app/api/watchlists.py`; no UI built. See `.workflow/design/watchlist-alerts-events-ux.md`.
