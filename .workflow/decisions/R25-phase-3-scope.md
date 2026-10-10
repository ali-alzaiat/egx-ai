# R25 — Phase 3 scope (Valuation, roadmap §4–§5)

**From:** Sherif (pm) · 2026-10-10
**Sources:** `.workflow/research/phase-3-valuation.md` + roadmap §4–§5 exit criteria; R22 standing reqs 3+4.
**Binding:** AGENTS.md rules 1/2/3/5/6/7/9/10 + INSUFFICIENT_DATA (never zero); cross-phase contracts (one migration, UUID PKs, `/api/<domain>/companies/{id}`, `methodology_version` on every score, hand-serialized Decimal/date).

## Decisions

1. **v1 model count: ACCEPT 4 SWS-parity, amended.** `FCFE-2stage` (general) + `DDM` (fallback/dividend payers) + `Excess-Returns` (banks/insurers, FCFE-at-CoE) + `AFFO-2stage` (REITs + Egyptian developers v1). Full project-level SOTP CUT — needs per-project PDF inputs with no structured feed.
2. **Adjustability: TIKR-3-input only** (`revenue_growth, operating_margin, exit_multiple`; discount visible but fixed v1). Pre-fill from historical extrapolation, NOT consensus (EGX thin). Advanced grid deferred.
3. **Uncertainty ladder: Morningstar widening-margin ladder calibrated from our DataQualityScore.** Single disclosed CoE/WACC + terminal-g, versioned, never fabricated per-ticker (EGP curve: `no data`).
4. **MISSING degradation: honest.** `financial_statements=MISSING` → intrinsics `INSUFFICIENT_DATA`, weighted FV `null`; relative leg only if prices OK; confidence capped POOR/MISSING.
5. **Standing-req-3 concrete form:** new table `industry_valuation_profiles` (FK to GICS sub_industry, primary/fallback/preferred_multiple, methodology_version) reusing Phase-2 taxonomy; one outputs table, same single migration; one router `GET /api/valuation/companies/{id}` echoing profile/version/values/weights/counts.

## BUILD (in order)

**V1. Deterministic 4-model engine** (pure + tests; zero/negative/missing per formula; value or INSUFFICIENT_DATA, no fabricated growth/CoE).
**V2. Profile router + weighted fair value** (fixed versioned weights, exposed; bank→Excess-Returns+P/B, general→FCFE+P/E-or-P/S).
**V3. Bull/base/bear** from same 3 inputs, side-by-side, range-not-guess copy, never BUY.
**V4. Minimal 1-D sensitivity** (±discount, ±growth, monotonic); 2-D grid deferred.
**V5. Confidence from data quality** (QualityScore→Low/Medium/High/VeryHigh ladder; MISSING→null FV + capped confidence).
**V6. One migration `013` + one domain API** (up/down round-trip; 404 unknown; payload carries methodology_version).

## CUT / DEFER

- Project-level SOTP/NAV → Phase 5+; 15-model kitchen sink/EPV/CAPM/Fair-Ratio → cut; advanced adjustability + shareable/export → Phase 10; reverse-DCF/analyst-target/consensus pre-fill → defer; per-ticker EGP curve → cut; custom templates/real-time/chatbot → never (rules 6/9/10).
