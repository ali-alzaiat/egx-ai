# R28 — Phase 4 scope (Investment score, roadmap §6)

**From:** Sherif (pm) · 2026-10-10
**Sources:** `.workflow/research/phase-4-investment-score.md` + roadmap §6 exit criteria + R22 standing reqs + R25 (Phase 3 engine).
**Binding:** AGENTS.md rules 1/2/3/5/6/7/9/10 + INSUFFICIENT_DATA (never zero, never fail-on-missing); cross-phase contracts (one migration `014`, UUID PKs, `/api/<domain>/companies/{id}`, `methodology_version` on every score, hand-serialized Decimal/date).

## Verdict: 4 of 5 components survive v1; future-growth ships degraded-or-absent, never fabricated

| Component | v1 fate | Why (EGX reality) |
|---|---|---|
| Value | BUILD (degraded) | Needs Phase-3 FV + PE/PB vs market/industry; PEG + analyst-target legs CUT (thin consensus). |
| Past performance | BUILD (full) | 5-yr EPS/ROE/ROCE/ROA from 5 statements + notes. |
| Financial health | BUILD (dual track) | Non-financials 6-check track fully computable; banks separate track, each check individually gated (NPL/allowance/deposit vary per pack). |
| Dividend | BUILD (narrowed) | Stability + earnings-coverage + history; cash-payout-%/yield thresholds CUT (`no data`). |
| Future growth | BUILD as honest-degrade only | All 6 SWS checks need consensus; v1 = historical-extrapolation fallback or component INSUFFICIENT_DATA. No synthetic consensus. |

## Weighting: equal-weighted v1; fitted CUT

Fitted weights need return-history regression (look-ahead risk, rule 4) with PDF-only thin inputs (rule 2). v1 = SWS-parity equal weight: every check 1 pt, component = passes/run, headline = mean of components-with-data. Fitted defers to Phase 9 with published hit-rate discipline.

## Confidence: DQ-fed Morningstar-style ladder, never moves the score

Confidence = function of `DataQualityScore` + freshness/lag + N-with-data → Low/Medium/High/VeryHigh; widens buy/sell bands only. `MISSING` scope → score `null` + confidence capped POOR/MISSING. Failed ≠ missing — missing listed as checks-not-run.

## BUILD (in order)

**P1. Deterministic check engine** (~20 checks, 4 full + degraded value/growth; pass/fail/not-run + threshold + cited inputs; zero/negative/missing per formula).
**P2. Floors + INSUFFICIENT_DATA rules** (component needs ≥3/6 checks run; headline needs ≥3/5 valid else `null` + reason; dividend-growing fails-open to not-run when pay-history <10y).
**P3. Equal-weight aggregation + dual-track routing** (`industry_score_profile` reusing Phase-2 GICS taxonomy + Phase-3 profile pattern; banks → financial-health track; profile id+version echoed).
**P4. Confidence ladder from data quality** (published bands; margin-of-safety selector default 20% drives display-only Buy-Zone).
**P5. Explanation payload** (headline + components + per-check detail + confidence + scale + checks-not-run + versions + N-with-data + as_of/timestamps/filing citations; hedged copy per rule 10).
**P6. One migration `014` + one domain API** (`investment_scores` + components/checks JSONB; `GET /api/scores/companies/{id}` + assess POST; 404 unknown; reads filter by methodology_version).

## CUT / DEFER

- Fitted/learned weights, 12-multiple aggregation, 0–100 solvency formula → CUT v1 (all `no data`; paid back in Phase 9).
- PEG, analyst-target, cash-payout-%/yield thresholds, per-ticker EGP CoE → CUT (thin/gated/`no data`).
- Bank NPL/allowance/deposit beyond available line items → gate per-ticker.
- Letter grades, star-forcing, distribution targets → CUT (no forced distribution).
- Backtest-hit-rate page, 5-yr history chart, shareable/export → Phase 9/10.
- Shariah/social 0–100 as score component → Phase 6 (MISRI weights `no data`).
