# Inbox: researcher

From: router (Phase 6 kickoff, on main) · 2026-10-10
Task: Phase 6 (Shariah) research for roadmap §11–§12 — per-rule breakdown exposed, UNKNOWN when data missing, methodology + freshness on every result, estimated purification — plus standing req 1 (versioned verdict: methodology_version + report_date + per-rule UNKNOWN) and req 5 (EGX dividend purification math in EGP tied to cited filings). Study Zoya/Musaffa/Islamicly purification calculators (formulas, dividend handling), AAOIFI purification doctrine (citable sources only), EGX33 membership as catalyst input (reconcile with our verdicts), and how competitors display per-rule breakdowns. Existing engine: `backend/app/screening/` (extend in place per roadmap architecture — verify what exists before proposing). Reuse prior `.workflow/research/` files, don't redo them. Every claim cited with URL; `no data` where unverifiable. Return inline (router files as `.workflow/research/phase-6-shariah.md`). End NEXT: pm | BLOCKED: <question> | DONE.

---

From: router (Phase 5 kickoff, on main) · 2026-10-10
Task: Phase 5 (Investment thesis) research for roadmap §7, §8, §9 + §16 (part) — structured thesis referencing real metrics, scenarios with labelled assumptions, structurally stored invalidation conditions, catalyst records. Study how SWS Community Narratives / Morningstar analyst reports / Alpha Spread scenarios structure theses (assumption labelling, scenario ranges, what triggers invalidation), how catalyst/scenario tracking products do it (if any citable), and what EGX data supports per element. Reuse prior `.workflow/research/` files, don't redo them. Every claim cited with URL; `no data` where unverifiable. Return inline (router files as `.workflow/research/phase-5-investment-thesis.md`). End NEXT: pm | BLOCKED: <question> | DONE.

---

From: router (Phase 4 kickoff, on main) · 2026-10-10
Task: Phase 4 (Investment score) research for roadmap §6 — one explainable score with all components visible, confidence separate from score — plus standing req 3 (industry profiles feed score confidence) and req 4 (data-quality as product). Study how SWS Snowflake / Morningstar star-rating / Alpha Spread grades compose multi-factor scores (weights, thresholds, how components stay visible), how they separate score from confidence/uncertainty, and what EGX data supports per component. Reuse prior `.workflow/research/` files, don't redo them. Every claim cited with URL; `no data` where unverifiable. Return inline (router files as `.workflow/research/phase-4-investment-score.md`). End NEXT: pm | BLOCKED: <question> | DONE.

---

From: router (Phase 3 kickoff) · 2026-10-10
Task: Phase 3 (Valuation) research for roadmap §4–§5 (multiple models chosen per industry, weighted fair value, bull/base/bear, sensitivity, confidence score fed by data quality) + standing req 3 (per-industry metric profiles feed valuation model choice). Study how SWS/Koyfin/Yahoo/Morningstar do per-company valuation (methods, adjustable inputs, how they show uncertainty), what EGX-specific valuation practice looks like (broker research multiples by sector — EFG/CI reports), and which inputs EGX filings actually support (ties to financial_statements MISSING reality). Every claim cited with URL; `no data` where unverifiable. Reuse prior research files, don't redo them. Return inline (router files as `.workflow/research/phase-3-valuation.md`). End NEXT: pm | BLOCKED: <question> | DONE.

---

From: router (user directive: implement phases 2–10 + winning business model) · 2026-10-10
Task: Phase 2 (Industry intelligence) + competitive business-model landscape. Two tracks, one deliverable (router files it as `.workflow/research/phase-2-industry-competitive-landscape.md`).

Track A — Phase 2 product research (roadmap §2, §3; exit criteria: sector/industry tables, peer groups, configurable industry metrics, peer percentile comparison with written explanation). Also cover the R17-deferred sector backfill (`.workflow/decisions/R17-ux-overhaul-v1-scope.md`): how peers source/maintain sector-industry mappings for EGX/MENA listings. Reuse `.workflow/research/mubasher-features-2026-10.md`, don't redo it.

Track B — business model that wins. For the same competitor set (Simply Wall St, TradingView, Koyfin, Finviz, Yahoo Finance, Zoya, Musaffa, Islamicly, plus EGX brokers' research arms): how they monetize (tiers, prices, what sits behind paywalls), what their moat is (data, tooling, community, brand), where they are weak on EGX + Shariah coverage specifically, and which gaps this app (EGX-native + versioned Shariah screening + honest data-quality) can own. Frame findings as ownable advantages, not feature copying.

Every claim cited with a URL; unverifiable = `no data`. Return findings inline (router files them). End with exactly one contract string: NEXT: pm | BLOCKED: <question> | DONE.

---

From: router (user directive) · 2026-10-09 (superseded UX brief, kept for record)
Task: Whole-app UX research. The user dislikes the app's current UX and wants it
enhanced based on how comparable apps do it.

Focus: best-in-class UX for retail-facing stock / investment-research / screener apps.
Study a spread, e.g. Simply Wall St, TradingView, Koyfin, Finviz, Yahoo Finance,
Stock Analysis, Wisesheets, and Shariah-screening apps (Zoya, Musaffa, Islamicly).
Cover:
- Information architecture and navigation (what belongs in the top nav vs a company
  page; how a "screener" is framed).
- Dashboard and company-page layout (hero, key stats, tabs vs scroll, progressive
  disclosure).
- Data-heavy tables/screeners: density, sorting, filtering, column choice, mobile.
- States: empty, loading, error, missing data — what good apps do.
- Colour, typography and chart discipline; dark mode.
- How confidence / data-quality / coverage is communicated honestly.
- Onboarding: how a first-timer finds their first answer.

Every claim cited with a URL. Mark anything you cannot verify as `no data`. Prefer
patterns a small React app can realistically copy.

Deliverable: `.workflow/research/app-wide-ux-patterns.md`
End with exactly one contract string: NEXT: ux-expert, BLOCKED: <question>, or DONE.
