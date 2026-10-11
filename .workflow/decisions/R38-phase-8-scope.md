# R38 — Phase 8 Scope (Continuous Intelligence: §17 + §23 + §24)

**Date:** 2026-10-11 · **From:** pm → tech-lead · **Research:** `.workflow/research/phase-8-continuous-intelligence.md`
**Verified before scoping:** migration `018` is free (`backend/alembic/versions/` ends at `017_disclosure_phase7.py`). `006_valuation.py` / `013_valuation.py` share a descriptive name but are filesystem-unique — no renumber needed. Surfaces confirmed: Phase 5 `models/thesis.py` + `repositories/thesis.py`; Phase 7 provenance fields; Phase 1 `dataquality/service.assess()`.
**Exit criteria:** thesis versioning on new data · watchlist · alerts.

## BUILD

**B1 — Watchlist v1 (§17).** Multi-list per user; entry `{company_id, group (single string, groups-as-tags), note (inline journal), thesis_link}`. Fixed per-row columns v1: price/change/as-of/staleness (Phase 1), score (Phase 4), Shariah state (Phase 6), thesis link (Phase 5). Accept: create → add → group+note → read back with badges populated or INSUFFICIENT_DATA, never blank.

**B2 — Alert families v1 (§23).** Four families only: (a) price crossing (threshold × Phase 1 closes); (b) valuation-vs-price gap (Phase 3/4); (c) documents — toggle-only per watchlist, fires on new Phase 7 parsed batch; (d) score-change beyond ±5% neutral band on versioned Phase 4 history. Per-symbol setup for numerics, per-list toggle for documents. Single flat quota v1. Delivery v1 = persisted fired-alerts queryable in-app with ack; email/push deferred. Accept: set price alert → land crossing → fired row with inputs snapshot; ack clears.

**B3 — Arrival-only trigger evaluation, warn/break + human-review gate (§24 core).** Evaluates ONLY on (a) new Phase 7 fact batch or (b) Phase 1 price crossing — never timer alone; quiet days write "checked, nothing new", no LLM run. Warn → `watch` + next-proof-point; break → reassessment proposal as new thesis version via compare-and-swap (`version_conflict` on stale approve); warnings notify immediately, `broken`/KC-fired waits for user confirm. Deterministic code only (rule 6); no LLM evaluation in v1. Accept: filing breaching stored break → `possibly_invalidated` proposal with page-cited provenance, thesis unchanged until confirm.

**B4 — Restatement detector v1 (§24).** Same-period-different-value across two bulletin PDFs = revision candidate → version-not-overwrite, old/new/delta, re-evaluate affected checks, `restatement.detected` event; EAS-gotcha tags excluded before firing; as-reported vs as-knowable kept separate. Single materiality constant v1. Accept: corrected filing → revision candidate with old/new/delta, original untouched.

**B5 — Fail-closed + evidence-quality gate (rules 2/3).** Break on low-confidence parse (below-floor accuracy, OCR path, EAS-ambiguous) yields `unknown`/needs-review, never `broken`; confidence + methodology_version stored per check; missing inputs → persisted `unknown` with reason, never silent pass. Accept: break math on low-confidence fact → `unknown` citing confidence.

**B6 — Ledger schema v1 (event-bus substrate).** ONE append-only table: `event {id UUID, ts, actor (user/system + rule version), type ENUM, symbols, inputs_snapshot (fact ids + price as-of + methodology_version), reason, supersedes FK-nullable}`; types: `watchlist.add/remove, alert.created/fired/acked, fact.landed, check.evaluated {pass/warn/break/unknown}, restatement.detected, thesis.updated, rule.changed, note.added`. Corrections are new rows. Filters by symbol/type/date + JSON export. Accept: alert → check → thesis-confirm yields three ordered rows, filterable, JSON-exportable.

## DEFER

- **D1** — Reusable column views, formula columns, sharing, dashboard embedding, summary rows, Watchlist News. (No rows yet; decoration.)
- **D2** — Free-text multi-tags. (Groups-as-tags covers v1.)
- **D3** — TA-indicator alerts, screener alerts, filed-account guardrails, email/push, tiered quotas. (Needs indicator history + tiers.)
- **D4** — LLM evaluation, Midas-style tripwire, SWS editorial feed + sell-checklist UX. (Deterministic-first; editorial surface later with real data.)
- **D5** — CSV export, cold-storage/WORM, hash-chaining/Merkle, rejected-evaluation gate logs. (Compliance-grade immutability premature pre-Phase 13.)
- **D6** — Confirmed-vs-Tentative catalyst dating, impact-scored feed. (Carried `no data`.)

## Binding constraints

- AGENTS.md #2/#3/#5/#6/#9/#10: no fabrication; source everything (fact ids + price as-of in inputs_snapshot); methodology_version on every record; deterministic checks; no execution; reassessment-never-auto-sell ("potentially invalidated under these assumptions").
- Cross-phase: single migration **018** · UUID PKs · `/api/<domain>/companies/{id}` · hand-serialized `str(Decimal)`/ISO dates · Phase 5 ledger becomes one B6 stream, not parallel.
