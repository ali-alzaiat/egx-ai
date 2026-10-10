# Inbox: pm

From: router · 2026-10-10
Task: Phase 4 requirements (Investment score, roadmap §6: one explainable score, all components visible, confidence separate). Read `.workflow/research/phase-4-investment-score.md` in full (Snowflake 5×6 equal-weighted checks + thresholds; Morningstar 4-input star + widening ladder; Alpha Spread blend + solvency + assumption tables; EGX component support incl. thin-consensus + PDF-only constraints; req-3/req-4 mappings; non-binding steers). Cut scope ruthlessly into builds vs defers: component set v1 (which of value/growth/past/health/dividend survive EGX data), weighting (equal vs fitted — fitted needs justification against rule 2), confidence construction (DQ-fed ladder), INSUFFICIENT_DATA floors per component, what "explanation" each response carries. Bind AGENTS.md + cross-phase contracts (one migration, UUID PKs, `/api/<domain>/companies/{id}`, methodology_version on scores). No code, no file writes (return decision inline; router files with next R-number). End NEXT: tech-lead | BLOCKED: <question> | DONE.

---

From: router · 2026-10-10 (Phase 3 brief kept below for record)
Task: Phase 3 requirements (Valuation, roadmap §4–§5). Read `.workflow/research/phase-3-valuation.md` in full (SWS 4-model router + 6 checks; Morningstar uncertainty ladder; TIKR 3-input adjustability + bull/base/bear; InvestingPro 15-model weighting; Alpha Spread scenarios; EGX broker target-price practice; EGX filing inputs support 5-statement models but thin consensus + PDF-only; standing req 3 mapping; design steers §1–3 non-binding). Cut scope ruthlessly into builds vs defers against §4–§5 exit criteria (models per industry, weighted fair value, bull/base/bear, sensitivity, confidence fed by data quality): how many models v1 (research steers 4 SWS-parity, decide), adjustability depth, uncertainty-ladder calibration source, what happens under financial_statements MISSING (honest degradation per AGENTS rule 4). Bind AGENTS.md + cross-phase contracts (one migration, UUID PKs, `/api/<domain>/companies/{id}`, methodology_version on scores, INSUFFICIENT_DATA pattern). No code, no file writes (return decision inline; router files with next R-number). End NEXT: tech-lead | BLOCKED: <question> | DONE.

---

From: router · 2026-10-10 (Phase 2 brief kept below for record)
Task: Phase 2 requirements + business-model positioning. Read `.workflow/research/phase-2-industry-competitive-landscape.md` (Track A: GICS-dual taxonomy, EGX 18-sector backfill, editable peers, versioned per-industry metric profiles, honest percentiles; Track B: competitor price board, moats, EGX+Shariah weaknesses, 6 ownable gaps + don't-build list). Turn it into prioritized Phase 2 requirements with ruthless scope cuts: what Phase 2 builds (must fit roadmap §2–§3 exit criteria: sector/industry tables, peer groups, configurable industry metrics, peer percentiles with explanation) vs defers (with reasons), plus the product/business-model positioning to carry into Phases 3–10 (which of the 6 ownable gaps become standing requirements, pricing-lane note from the B0 price umbrella — no prices set, lanes only). Bind to AGENTS.md (no fabricated data, versioned methodology, INSUFFICIENT_DATA pattern) and cross-phase contracts (one migration, UUID PKs, `/api/<domain>/companies/{id}`, methodology_version on scores). Return the decision inline (router files it under `.workflow/decisions/` with the next R-number). End with exactly one contract string: NEXT: tech-lead | BLOCKED: <question> | DONE.

---

From: router (via researcher) · 2026-10-08 (superseded Task 5 brief, kept for record)
Task: Roadmap Phase 1, Task 5 — decide what we build for the assessment service + API.
Research: .workflow/research/task-5-data-quality-scoring.md
Prior plan context: docs/superpowers/plans/2026-10-08-competitive-enhancement-roadmap.md § Task 5 (lines 211-231)
Your job: read the research, decide what Task 5 should actually include (accept/reject/amend the plan's proposed interfaces in light of competitor data), write decision to .workflow/decisions/R12-...md (router files it if you return inline). End with: NEXT: tech-lead, BLOCKED: <question>, or DONE.
