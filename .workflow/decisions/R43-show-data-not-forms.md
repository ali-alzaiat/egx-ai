# R43 — Show company data and recommendations, not forms (PM: Sherif)

**Date:** 2026-10-23 · **Trigger:** user directive "show the company data and recommendation, not take it from the user." · **Gates:** data-first gate PASSED (203 companies); AGENTS rules 1, 2, 3, 5, 10; CONTRACT real-data check.

## Inventory findings (verified in code, beyond the router grep)

- Technical tab re-sends every stored close/volume to `POST /api/technical/.../calculate` as comma-separated query params; the server already has the prices.
- Valuation "Calculate valuation" asks for 12 hand-typed inputs; the weighted fair value (`GET /fair-value`) is already auto-computed from stored metrics on read, so the form duplicates it with invented numbers.
- Metrics, score, fair value and Shariah `/screen` read the legacy FinancialFact/CompanyMetric store. The 212 companies' vendor statement lines only reach `/statements/.../ratios`, stance freshness and `/screening/.../screen-statements` (two Shariah engines; the tab calls the legacy one).
- Nothing calls the trigger service (`/api/triggers/evaluate`, `on_facts_landed`, `on_price_crossing`): alerts never fire on their own (see OUT).
- AI Insights route `/companies/:ticker/ai` exists but no tab or link reaches it.

## Decision table

| # | Screen | Control | Decision | Trigger / replacement |
|---|---|---|---|---|
| 1 | Valuation | 12-field assumptions form + Calculate | REMOVE | Auto fair value only (FairValueCard + SensitivityTable); recompute after statement import and after price sync. Manual per-model table leaves user screens; endpoint fate is the architect's call. |
| 2 | Technical | Calculate indicators (client posts prices) | REMOVE | Server computes from stored prices after price sync, or on first view when no snapshot or snapshot older than latest price. |
| 3 | Financial Metrics | Calculate metrics | REMOVE | Auto after statement import (vendor CLI, manual filing, review approve) + on first view. Needs statement-lines → metrics bridge. |
| 4 | Investment Score | Assess | REMOVE | Auto after statement import and after price sync + on first view. |
| 5 | Shariah | Screen (legacy `/screen`) | REMOVE | Auto after statement import via the statement-lines engine + on first view; missing rules UNKNOWN; vendor-based verdicts labelled provisional. |
| 6 | Shariah | Purification form (8 fields) | REMOVE | Auto per-share purification estimate from stored DPS × non-permissible revenue ratio; INSUFFICIENT_DATA naming the missing input. "Shares held" calculator OUT. |
| 7 | Shariah | EGX33 membership entry | REMOVE (no admin UI) | CLI `python -m app.screening.egx33` (R42); read-only EGX33 block stays. |
| 8 | Thesis | Assess (horizon, shareholder) | REMOVE | Auto-assess with `DEFAULT_HORIZON_YEARS`, `is_shareholder=null`, after statement import / price sync + first view; tab shows "horizon: N years (methodology default)". Shareholder question OUT. |
| 9 | Thesis | Documented update form | MOVE to admin | Ledger timeline stays read-only on the tab. |
| 10 | Peers | Edit peer list (raw IDs) | MOVE to admin | Default peers + percentiles stay read-only. |
| 11 | Disclosures | Register / Upload / per-row Parse | MOVE to admin | Parse auto-runs after upload. Registry, provenance facts, comparison, "What changed" stay read-only. |
| 12 | Disclosures | Comparison metric picker | KEEP | View selector. |
| 13 | AI Insights | Prepare data + free-text LLM query | REMOVE route + page from UI | Backend `/api/ai/*` untouched; auto AI narrative OUT. |
| 14 | Company overview | Refresh market data | MOVE to admin | Same job via admin or `python -m app.ingestion.sync`; pages show price as-of date. |
| 15 | Rankings | Re-run scoring | REMOVE | Signals run as the final step of the price-sync job; filters stay. |
| 16 | Filings intake (`/intake`) | Manual filing entry | MOVE to admin | `/admin/intake`, off the main sidebar. |
| 17 | Watchlists | CRUD | KEEP | User feature. |
| 18 | Alerts | Rules CRUD, ack, filters | KEEP | User feature (delivery OUT). |
| 19 | Events | Filters + Export | KEEP | |
| 20 | Companies | Search, sector, sort, pagination | KEEP | |
| 21 | Recommendations | Search, stance, Shariah-only, sort | KEEP | |
| 22 | Dashboard, Screening list, Financial Data, Signals, Statements, Ratios | Retry links only | KEEP | |

**Admin area:** one route `/admin` grouping #9, #10, #11, #14, #16; a small "Admin" link in the sidebar footer. Convenience grouping, not a security boundary (one API token already guards the API). Roles/accounts OUT.

**Triggers:**
- *After statement import:* end of `python -m app.statements.vendor_import`, after `POST /statements/manual-filings`, after a review-queue approve → recompute metrics → Shariah → fair value → score → thesis for affected companies only.
- *After price sync:* end of `ingestion/jobs.py::_run_phases` and the sync CLI → technicals → signals run → score → fair value for synced tickers.
- *On first view:* GET on a company with inputs but no snapshot (or a snapshot older than its newest input) computes, snapshots, returns; never "unassessed" when inputs exist.

Mechanism (inline vs queued, caching) is the architect's; the behaviour is the requirement.

## Build order

1. M1 Bridge: metrics, score, fair value, Shariah read approved statement lines (filing outranks vendor, as `latest_approved`); provenance carries tier, period end, source; no zero-fill.
2. M2 Auto-compute: the three triggers, idempotent (one snapshot per company + methodology_version).
3. M3 Company tabs read-only: remove #1–8, #13, #15; empty states give the INSUFFICIENT_DATA reason (missing line), not "click Calculate".
4. M4 `/admin`: move #9, #10, #11, #14, #16 unchanged.
5. M5 Real-data check (AC-9).

## OUT (v1)

Scheduled daily price sync (prices may go stale until a sync); trigger-service wiring (alerts/thesis invalidation auto-fire, Phase 11 carry-forward); personal purification calculator and thesis shareholder question; user-adjustable valuation assumptions (only ever as a labelled sandbox); auto AI narrative; admin UI for EGX33 membership; auth/roles for `/admin`; retiring unused POST endpoints (optional); Rankings vs Recommendations v2 consolidation (separate ruling).

## Acceptance criteria

- **AC-1** No file under `frontend/src/pages/` or `frontend/src/components/` outside admin imports `calculateValuations`, `calculateIndicators`, `calculateMetrics`, `assessScore`, `assessThesis`, `updateThesis`, `screenCompany`, `estimatePurification`, `recordEgxMembership`, `putPeerOverride`, `registerFiling`, `uploadFiling`, `parseFiling`, `startMarketRefresh`, `runSignals`, `recordManualFiling`. A vitest render of each company tab with mocked data finds no `input`/`select`/`textarea` (except the Disclosures comparison selector) and no button except retry, pagination and view selectors.
- **AC-2** For a seeded company with approved lines (≥2 periods) and ≥200 price bars, GETs alone (metrics, fair value, score, screening, technical, thesis) return computed payloads (snapshot exists, `calculated_at`, `methodology_version`); no POST.
- **AC-3** A seeded company missing a required line returns `value: null`, INSUFFICIENT_DATA, reason naming the line; never 0; one test per engine.
- **AC-4** Every M1 number carries source tier, period end, source reference; UI shows "Provisional (vendor data)" when a vendor line was used (incl. Shariah verdict); filing beats vendor (test).
- **AC-5** Vendor import / manual filing / review approve for company X refresh X's metric, Shariah, fair value, score, thesis snapshots (`calculated_at` after the event) with no client POST; other companies unchanged.
- **AC-6** After the refresh job: synced tickers get new technical snapshots, a new signals run, recomputed score and fair value; job status reports per-step counts.
- **AC-7** First GET with inputs and no snapshot computes (never `assessment: null`); a second GET with no new inputs does not recompute.
- **AC-8** `/admin` renders intake, disclosure register/upload/parse, peer override, thesis update, market refresh; their tests pass there; Intake leaves the main sidebar; `/companies/:ticker/ai` no longer resolves.
- **AC-9** Dev-DB report: per-engine non-null coverage over companies with lines + prices; sanity stance distribution before/after; Shariah verdict distribution. 0% coverage where inputs exist is a defect; any outcome >80% must be explained.
- **AC-10** No new certainty copy; stance labels per R42; fair value worded "estimate under the stated methodology".
- **AC-11** pytest, ruff, mypy, tsc, eslint, vitest, build: zero errors, zero warnings; CI green; vercel-react-best-practices review of changed frontend files clean.

## Open notes for the architect

1. Valuation inputs with no source in our data (discount rate, terminal growth, target multiples) come from a versioned, sourced methodology record; with no sourced value the model is INSUFFICIENT_DATA, never a hard-coded constant (AGENTS rule 5).
2. Market-cap-denominated Shariah ratios need price × shares; without shares outstanding in statement lines those rules return UNKNOWN.

NEXT: architect
