# R30 — Phase 5 scope (Investment thesis, roadmap §7 + §8 + §9 + §16-part)

**From:** Sherif (pm) · 2026-10-10
**Sources:** `.workflow/research/phase-5-investment-thesis.md` + roadmap §7–§9 + §16-part exit criteria + R22 standing reqs + R25 + R28.
**Binding:** AGENTS.md rules 1/2/3/5/6/7/9/10 + INSUFFICIENT_DATA (never zero, never fail-on-missing); rules 6/9/10 strict — no LLM-invented facts, no execution, trigger forces reassessment never auto-sell, hedged copy only; cross-phase contracts (one migration `015`, UUID PKs, `/api/<domain>/companies/{id}`, `methodology_version` on every persisted record, hand-serialized Decimal/date).

## Verdict: SWS skeleton + Alpha display + ThesisCheck storage, history-anchored for EGX, everything consensus-dependent degrades honestly

No incumbent stores structured falsification — that gap is the v1 moat. Consensus-prefilled scenarios, impact scoring, and alerts are CUT: EGX inputs support filing-cited theses, history-extrapolated scenarios, and mandate-anchored catalysts only.

## BUILD (in build order, each with acceptance check)

**P1. Structured thesis v1 (SWS skeleton + Morningstar authority, filing-cited).**
Sections: header (own fair value + horizon + shareholder-disclosure toggle) / business evolution / Bulls×3 + Bears×3 as assumption-shifters / revenue-margin-earning-power impact / risks + capital allocation. Every assumption a labelled row (metric, value, horizon, source filing PDF, author). Thesis text is deterministic template from stored rows, never LLM-generated facts (rule 6).
*Accept: every number in a thesis resolves to a filing PDF citation or renders INSUFFICIENT_DATA.*

**P2. Scenarios Bear/Base/Bull, history-anchored (Alpha display, Phase-3 inputs).**
Same 3 TIKR inputs as Phase 3 (`revenue_growth, operating_margin, exit_multiple`), per-scenario assumption table + range-not-guess copy + margin-of-safety selector reused from Phase 4. Pre-fill from historical extrapolation with decaying rate; consensus pre-fill CUT (COMI 10 / ETEL 4–5 vs 40–88 US = thin). No probability weighting (`no data`).
*Accept: thin-consensus ticker renders 3 labelled scenarios from history or explicit nulls, never synthetic consensus.*

**P3. Minimal 1-D sensitivity on scenarios.**
Reuse Phase-3 sensitivity (±discount, ±growth, monotonic) per scenario; 2-D grid CUT.
*Accept: moving one input moves FV monotonically or returns INSUFFICIENT_DATA.*

**P4. Stored invalidation (ThesisCheck/Synoptiv rules, 2–4 per thesis).**
Shape per condition: metric + numeric threshold + period + evidence source (one of the 6 mandated EGX disclosures) + pre-committed action (= documented reassessment) + status (Active / Triggered / Reassessed) + extraction-confidence + version. Append-only ledger (timestamp, evidence, classification Confirmed/Pending/Challenged/Invalidated, variable, action, rationale). Trigger forces reassessment, never auto-sells (rules 9/10); price stop-loss explicitly excluded.
*Accept: firing a threshold marks Triggered + appends a ledger row and never emits a sell order.*

**P5. Catalyst records (mandated skeleton + third-party rows, labelled).**
Shape per row: event, date/window, variable tested, base-case expectation, outcome (Hit/Miss/Pushed), provenance, Confirmed-vs-Tentative label. Seed skeleton from EGX continuing-obligations cadence + Decypha / egypt-stocks / AskBorsa rows. Shariah33 in/out allowed as Tentative only (methodology PDF `no data`).
*Accept: every catalyst carries a source URL + Confirmed/Tentative label; skeleton exists even with zero third-party rows.*

**P6. Honest degradation + confidence.**
`financial_statements=MISSING` → FV null, scenarios history-only-or-null, invalidation checks stay Pending with lag/confidence noted, catalysts skeleton-only. Confidence = DataQualityScore-fed ladder (reuse R28), caps at POOR/MISSING; copy hedged per rule 10.
*Accept: MISSING-scope company renders skeleton + nulls + capped confidence, never a fabricated FV.*

**P7. One migration `015` + one domain API.**
Tables `investment_theses + thesis_invalidations + thesis_ledger + thesis_catalysts` (or JSONB equivalent — architect decides) in a single migration, UUID PKs, `methodology_version` on each record; `GET /api/theses/companies/{company_id}` (+ assess/update POSTs), 404 unknown, reads filter by version.
*Accept: round-trip thesis→invalidations→ledger→catalysts on one company with version echo.*

## CUT / DEFER (with cost)

- Consensus-prefilled bull/base/bear, PEG/analyst-target legs, per-ticker EGP CoE/ERP → CUT v1 (thin/gated/`no data`).
- SWS competing-narratives marketplace, FV-history chart, popular/undervalued filters → Phase 10.
- Morningstar full sections (Moat deep-dive, ESG risk, analyst-notes archive) → CUT.
- Alpha backtest discipline → Phase 9.
- FinMonkeys impact + sentiment, ICS/alert subscription, Catacal alerts, guidance calendars → Phase 8.
- Seeking Alpha crowd theses → never as authority.
- Project-level SOTP catalyst detail, EFG/CI login-gated notes → CUT (gated).
- Shareable/export, auto-reversioning → Phase 8/10.
- Stop-loss-as-invalidation, BUY/SELL copy, auto-sell on trigger → never (rules 9/10).
