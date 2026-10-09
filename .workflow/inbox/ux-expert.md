# Inbox: ux-expert

From: router (direct dispatch, no tech-lead briefing hop) · 2026-10-09
Parallel stream B: produce the v1 app-wide UX enhancement spec (design only) from the live
audit + competitor patterns.

## Inputs
- `.workflow/design/app-ux-audit.md` — live Playwright walkthrough, 17 findings F1–F17 (P0/P1/P2). Evidence: snapshots/logs under `.playwright-mcp/`.
- `.workflow/research/app-wide-ux-patterns.md` — Nadia's cited patterns (every claim cited).

## Rulings
- **R17:** v1 includes F1–F10, F13–F17; F11 partial (cap/paginate + formatting, no chart); F12 partial (drop Currency/Status, explicit "N of 229 shown, sector not recorded", backfill deferred); F16 amended per R16 (DQ card empty-state gets the pinned line). No backend changes; frontend-only, zero new deps.
- **R16:** adds `last_synced_at` to `GET /api/data-sources` → expose "Last refresh: …" in the screener/rankings or header as specified (use the format shown in contract mock).
- **R18:** Task 8 minor findings will be re-raised at v1 frontend review (do not chase them now).

## What to return
Write `.workflow/design/app-ux-enhancement-spec.md` with this structure:
1. **Goal** (1–2 lines)
2. **Constraints**: frontend-only, no new deps, design-only, respect existing API, no chart (F11), do not backfill sector, etc.
3. **IA & navigation** (fix F2/F3/F14): new tab row for company sub-pages, breadcrumb, add Screening and Valuation links, correct Screener name
4. **Per-screen fixes** (all in v1): Dashboard (F5), Companies list (F12/F13), CompanyDetail + tabs (F3/F11/F16), Financials (F8), Metrics (F6), Technical (F4), AI Insights (F7), Shariah Screening (F1/F2), Valuation (F1/F2), Rankings/Screener (F9/F10/F14), Not found (F15), No-data (F17)
5. **States & copy tables**: three-state empties (no data / no matches / error), loading/skeletons, error with retry, stale data (market-closed, last-updated, delay badge, `last_synced_at`), colour+sign never alone
6. **F1–F17 ledger**: for each, FIXED/AMENDED/DEFERRED + one-line rationale
7. **Deferred**: charts, dark mode, global `i` popovers, mobile layouts, watchlist/alerts/presets/onboarding, sector backfill, per R17
8. **Integration notes**: point to `DataQualityCard.tsx` empty line (`Refresh market data to compute assessments for every company.`), `refresh-and-assess-contract.md` for button placement (CompanyDetail header), and that backend won't add endpoints for F1/F6/F4 — fix by driving existing endpoints (screening/valuation/metrics/technical already expose calculate endpoints; the UI must call them, not show cURL).
9. **Do-not-touch**: backend files, API contracts

## Do
- Design minimal UI changes. For F1: replace the cURL line with a "Run screening" button that calls `POST /api/screening/companies/{id}/screen` (existing route per backend), show its result. Same for valuation (call existing calculate). For F4: auto-load prices into the form or call `/api/technical/companies/{id}` and/or pre-populate from prices endpoint; do not ask the user to paste hundreds of numbers. For F6: add a button to calculate metrics via existing endpoint. F7: replace `alert()` with inline toast, remove RAG jargon, show a sensible error.
- Be explicit with copy strings (exact text the staff-frontend should write).

## Don't
- Propose charts, dark mode, tooltips library, new packages.
- Propose backend endpoints or model changes.

## Handoff
End with exactly one contract string: NEXT: staff-frontend, BLOCKED: <question>, or DONE.
