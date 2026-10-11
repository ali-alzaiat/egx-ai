# Frontend Catch-Up Contract — Phases 2–8 Backends → UI

**Date:** 2026-10-11 · **Author:** router (architect dispatch aborted; built from live-code verification) · **User directive:** full contract first, then batches
**Source of truth:** backend routers + schemas (verified 2026-10-11). Frontend inventory: 12 pages, `CompanyTabs` (7 views), 25 hooks in `client.ts` — none for industry/scores/theses/disclosures/watchlists/alerts/triggers/events.

## What exists vs what is missing

| Domain | Backend | Frontend today | Verdict |
|---|---|---|---|
| Industry/peers (Ph.2) | `GET /api/industry/companies/{id}` (peers + percentiles + profile version), `PUT …/peers` (override) | Nothing | MISSING |
| Valuation (Ph.3) | `GET …/companies/{id}`, `POST …/calculate`, `GET …/fair-value` (weighted FV, bull/base/bear, sensitivity, DQ-fed confidence) | `Valuation.tsx` on v1 shapes (`useValuations` + calculate) | STALE — upgrade to fair-value + scenarios + sensitivity |
| Investment score (Ph.4) | `GET /api/scores/companies/{id}` (`assessment: null` when unassessed), `POST …/assess` | Nothing | MISSING |
| Thesis (Ph.5) | `GET /api/theses/companies/{id}`, `POST …/assess`, `POST …/update` (rationale required) | Nothing | MISSING |
| Shariah v2 (Ph.6) | `GET …/companies/{id}` (per-rule breakdown), `GET/POST …/purification` (EGP), `GET/POST …/egx-membership` (side-by-side) | `Screening.tsx` + `ShariahScreening.tsx` on v1 shapes | STALE — upgrade to breakdown + purification + EGX33 |
| Disclosures (Ph.7) | `POST /register`, `POST /upload`, `GET /filings`, `POST /filings/{id}/parse`, `POST /facts`, `GET /facts`, `GET /comparison`, `GET /diffs` | Nothing | MISSING |
| Watchlists/alerts/events (Ph.8) | `POST/GET /api/watchlists`, `…/{id}/entries` CRUD, `POST/GET/PATCH/DELETE /api/alerts` + `/fired` + `/{id}/ack`, `POST /api/triggers/evaluate` (internal), `GET /api/events` + `/export` | Nothing | MISSING |

## Cross-cutting rules (every batch)

- **Hooks:** one `client.ts` hook per endpoint above (`useIndustrySnapshot`, `useScore`, `useThesis`, `usePurification`, `useEgxMembership`, `useFairValue`, `useFilings`, `useFacts`, `useComparison`, `useDiffs`, `useWatchlists`, `useWatchlistEntries`, `useAlertRules`, `useFiredAlerts`, `useEvents`), TanStack Query keyed by `(domain, companyId)`; mutations invalidate their domain key. Types in `types/index.ts`.
- **Honest states:** every data surface handles loading / error / empty / `null`-assessment (`assessment: null` → "Not yet assessed" + assess button, never a default); `INSUFFICIENT_DATA` badges stay visible; `data_as_of` shown; scores older than 90 days get a non-dismissable staleness banner (Phase 14 rule, build it now — cheap).
- **Copy:** rule 10 — "potentially … under these assumptions", never BUY/SELL; triggers "propose reassessment", never auto-advice.
- **Provenance:** every number shows methodology_version + source (fact ids / price as-of) via title tooltip or footnote; fair values always paired with assumptions + sensitivity table.
- **Perf:** Vercel skill client/rerender/bundle/rendering/js rules; no new deps unless named; colocated CSS like existing pages.

## Batch A — Company page upgrades (ship first; extends existing surfaces)

1. **Score card** — new `CompanyTabs` view `Score`: `GET /api/scores` → 4/5 components with weights, confidence separate from score, floors; `POST …/assess` button. Accept: unassessed company shows empty state + assess; assessed shows all components + confidence + methodology_version.
2. **Shariah v2** — upgrade `ShariahScreening.tsx`: per-rule breakdown (pass/fail/UNKNOWN + threshold + report_date), purification estimator (`POST …/purification` → EGP math + inputs), EGX33 side-by-side (`GET …/egx-membership`, reconcile-never-override copy). Accept: UNKNOWN rules render as unknown with reason; purification shows formula inputs.
3. **Valuation v2** — upgrade `Valuation.tsx`: `GET …/fair-value` (per-model values, weights, weighted FV, bull/base/bear, ±1% sensitivity, DQ confidence ladder); keep `POST …/calculate`. Accept: FV always paired with assumptions + sensitivity table; DEGRADED data shows widened range + caveat.
4. **Industry strip** — new `CompanyTabs` view `Peers`: sector/industry, peer chips, per-metric percentile bars with written explanation, editable peer override (`PUT …/peers`). Accept: override persists and changes percentiles.

## Batch B — Thesis page (new route `/companies/:ticker/thesis`)

Narrative skeleton + labelled-assumption scenarios + stored invalidation conditions (metric/threshold/period/source/action) + catalyst records + append-only ledger timeline; `POST …/update` with required rationale (disable submit without it). Accept: break-threshold proposal renders "potentially invalidated under these assumptions" + confirm path; ledger shows versions.

## Batch C — Disclosures page (new route `/disclosures`, analyst-facing)

Filing registry table (register/upload/parse actions) + facts table with provenance (page/bbox/engine/accuracy) + period comparison + "what changed" diffs (`GET /comparison`, `GET /diffs`, restatement flags). Accept: parsed fact links back to filing + locator; diff view shows old/new/delta.

## Batch D — Watchlists + alerts + events (new nav section, SWS-feed-first per research)

- `/watchlists`: multi-list CRUD, entries with group/note/thesis link, per-row badges (price/change/as-of/staleness, score, Shariah, thesis) or INSUFFICIENT_DATA.
- `/alerts`: 4-family rule builder (price crossing, valuation gap, document toggle per list, score-change ±5%), fired-alerts feed with ack.
- `/events`: append-only ledger feed (filter by symbol/type/date) + JSON export link; SWS-style validate-or-invalidate framing per item.
- Accept per R38 B1/B2/B6: entry badges populated or INSUFFICIENT_DATA; fired row carries inputs snapshot; alert→check→confirm yields three ordered filterable rows.

## Explicitly NOT in v1

Email/push delivery, list sharing, reusable column views, formula columns, Watchlist News, free-text multi-tags, CSV export (backend serves JSON), TA-indicator/screener alerts (no backend), LLM evaluation/chat surfaces, Confirmed-vs-Tentative catalyst dating.

## Batch order + QA

A → B → D → C (C last: smallest audience). Each batch: implement → `npm run build && npm run lint && npm test` → qa-ui (Playwright against running frontend, 0 console errors) → ux-expert review vs `app-wide-ux-patterns.md` + phase research → tech-lead verdict. Batches are independently shippable; A must land before B/D (thesis links, badges).
