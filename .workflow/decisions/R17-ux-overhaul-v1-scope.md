# R17 — App-wide UX overhaul: v1 scope and cut line

**From:** Mostafa (tech-lead) · 2026-10-09
**Subject:** what the first UX overhaul fixes vs defers — Stream B
**Inputs ruled on:** `.workflow/design/app-ux-audit.md` (Salma, F1–F17, live), `.workflow/research/app-wide-ux-patterns.md` (Nadia, cited), `.workflow/decisions/R16-refresh-assess-contract.md`

## Binding constraints for v1 (these generate most of the cuts)

1. **Design only.** The ux-expert produces a spec; **one** staff-frontend task implements it,
   together with R16's frontend surface. No code in this stream.
2. **Frontend only.** v1 ships **no backend changes**. A finding whose fix needs a new/changed
   endpoint is deferred and named as such in the spec, with the missing endpoint listed.
   Everything available is listed in the brief (screening/valuation/metrics/technical calculate
   POSTs, prices/signals/coverage/financial/AI GETs, `/api/data-sources` — which gains
   `last_synced_at` from R16).
3. **Zero new dependencies.** No chart library, no UI kit, no `jsdom` in v1 (see R18). Existing
   tokens/CSS only.
4. **Honest data only** (AGENTS rules 2/4/10): no fabricated numbers, no "BUY", empty ≠ zero,
   staleness never shown as freshness.

## Findings — disposition

| Finding | v1 | How (frontend-only, existing endpoints) |
|---|---|---|
| F1 screening/valuation dead-end "call the API" | **IN** | "Run screening" / "Calculate valuation" buttons calling the existing POSTs; results rendered in-page |
| F2 orphan routes | **IN** | every company sub-view reachable from one tab row; nav gains a honest global path to screening |
| F3 sub-pages are one-way trips | **IN** | shared tab bar rendered on **every** company sub-page (F2+F3 are one component) |
| F4 technical tab = paste 365 prices | **IN** | fetch stored prices (`GET /api/companies/{id}/prices`, bounded window ≤ 200 bars) → call existing `POST /api/technical/companies/{id}/calculate` → render `GET` results; manual form removed |
| F5 dashboard hardcodes "Phase 2/4/5 will populate" while 229 companies exist | **IN** | dashboard fetches real numbers (companies, signals coverage, `/api/data-sources` → "Last refresh" from R16) |
| F6 metrics = developer instruction | **IN** | "Calculate metrics" button on the existing calculate endpoint + honest empty state |
| F7 AI: RAG jargon, `alert()`, unavoidable failure | **IN** | rename heading, `alert()` → inline status, copy names what data exists |
| F8 financials = four bare strings | **IN** | reason + next-step copy per the rankings pattern (naming *why* data is absent) |
| F9 filter change wipes table with false "Scoring the market…" | **IN** | keep results during refetch (stale-while-revalidate / skeleton), truthful copy |
| F10 re-run scoring: no state, no confirmation | **IN** | disable while running + success line with refreshed as-of timestamp |
| F11 365-row raw price dump | **PARTIAL** | cap/paginate + consistent number formatting + hide no-information rows; **no chart** (needs a dep → deferred) |
| F12 sector filter drops 222/229 silently; dead columns | **PARTIAL** | drop Currency/Status columns; explicit "N of 229 shown — sector not recorded for M" note; **sector backfill deferred** (Phase 2 data work) |
| F13 Back destroys list filters | **IN** | sector/search/page live in URL search params |
| F14 three names for one screen, "Screener" doesn't screen | **IN** | nav labels renamed; spec picks exact labels and must not promise what a screen doesn't do |
| F15 invalid ticker = four words + double 404 | **IN** | not-found state echoes the ticker, links back to the list, single fetch |
| F16 DQ card in prime space, always "–" | **IN** | card placement/weight per the new layout (UX owns placement); R16 owns its strings, incl. the pinned empty-state line |
| F17 no-data company: stats vanish, console 404 ×2 | **IN** | explicit "no price data from the configured source" states instead of absent stats; single fetch |

**v1 = all 17 findings touched, two of them (F11, F12) at copy/layout level only.**

## Research additions in scope (cheap, cited, they make it feel like a different app)

- **As-of / freshness everywhere:** "Last refresh" on the dashboard and an as-of line under
  prices (Nadia §6.1; data from R16's `last_synced_at`).
- **Empty/loading/error triad** on every async view the spec touches — failure never renders as
  empty, three distinct empty states (nothing yet / no match / no results) (Nadia §4).
- **Colour never alone** on components the spec touches — sign/arrow/label always paired
  (Nadia §5, WCAG 1.4.1). No global palette rewrite.
- **Verdicts stay honest** — tri-state/`INSUFFICIENT_DATA` never collapsed to pass/fail, report
  date shown with any verdict (Nadia §6.3, §8).

## Explicitly deferred out of v1 (do not design, do not spec)

| Deferred | Why |
|---|---|
| Charts / sparklines / price chart | needs a chart dependency; no new deps in v1 |
| Dark mode toggle | global theme work; cheap-looking, expensive to do honestly (contrast per mode) |
| Global `i` definition popovers on every metric/column | sweep across untouched screens; add per-screen when that screen is redesigned later |
| Mobile card-list / responsive overhaul | separate pass; desktop-first v1 |
| Watchlist, alerts, saved screens, presets, onboarding tour | belong to roadmap Phases 8/10, not this fix-the-gaps stream |
| Sector/industry data backfill (root cause of F12) | backend/data work, Phase 2 |
| Drag-and-drop dashboards, chart-grid screener, 100+ filters | Nadia §9 names these as *not* recommended for a small app |
| Any backend endpoint change | see constraint 2 |

## Relationship to Stream A (pinned so the two never fight)

- R16 owns: endpoint payloads, TS types, status semantics, the exact strings
  `Refresh market data`, the phase/status lines, the DQ empty-state line, the invalidation list.
- R17/the UX spec owns: **where** those surfaces live, the surrounding layout, all other copy,
  navigation and state handling.
- Conflict rule for the staff-frontend task: contract text wins on behaviour and pinned strings;
  the UX spec wins on placement and everything the contract does not pin.
- The DQ card empty state gains R16's one-line amendment to
  `.workflow/design/data-quality-card-ux.md` §5/§6 — ux-expert notes it at UX-review time.

**Ledger:** this ruling authorises the ux-expert brief at
`.superpowers/sdd/2026-10-08-competitive-enhancement-roadmap/task-ux-redesign-brief.md`.
