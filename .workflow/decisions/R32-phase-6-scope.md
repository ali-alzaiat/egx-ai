# R32 — Phase 6 scope (Shariah, roadmap §11–§12 + standing req 1 + req 5)

**From:** Karim (pm) · 2026-10-10
**Sources:** `.workflow/research/phase-6-shariah.md` + roadmap §11–§12 + standing reqs 1/5. Engine fields verified against `backend/app/screening/` live code this pass.
**Binding:** AGENTS.md 2/3/5/6/10 + INSUFFICIENT_DATA; cross-phase contracts (one migration, UUID PKs, `/api/<domain>/companies/{id}`, `methodology_version` on records).

## Engine verification (pm did it — researcher had not)

- **Exists:** 4 tri-state rules (`debt_ratio`, `interest_income_ratio`, `cash_securities_ratio`, `industry_screen`) returning PASS/FAIL/INSUFFICIENT_DATA with value/threshold/reason; overall `is_compliant: bool | None`; `methodology_version` + `methodology_name` + `screened_at` persisted; unique `(company_id, methodology_version)`; GET already exposes per-rule breakdown + version + `data_quality`.
- **Gaps driving builds:** version strings `"1.0"`/`"1.1"` pin no denominator/window — engine computes over spot total_assets + total_revenue (MSCI/FTSE-style, mislabeled "AAOIFI-based"); no `report_date`; no per-rule source/freshness; no purification storage/endpoint; no EGX33 field.

## BUILD (in order)

**B1 — Methodology v2 identifier** pinning denominator + window + thresholds (e.g. `aaoifi-assets-spot/33-33-5`); old rows stay readable via version filter. "AAOIFI" alone never ships again.
**B2 — `report_date` + per-rule freshness/source** on every verdict; INSUFFICIENT_DATA stays first-class with `{reason, missing_input}`.
**B3 — Purification v1: dividend-method estimate in EGP, labelled** (`dividend × non_permissible/total_revenue`; Zoya=Islamicly=MSCI-complement); every estimate carries `{amount_EGP, ratio, doctrine, ratio_provenance, DPS_source}` + not-zakat copy + edge branches (FAIL holding → whole dividend; FAIT/ADIB/SAUD carve-out branch).
**B4 — Honest degradation without parsed filings** (expected default): ratio-gated purification → INSUFFICIENT_DATA citing the 14-line checklist vocabulary; DPS stored with source+date, never invents ratio.
**B5 — EGX33 side-by-side, never override**: dated membership catalyst records (Feb/Aug reviews); surface shows both verdicts with the 10%-vs-5% discrepancy flagged unverified.
**B6 — One migration, contracts kept** (B2/B3/B5 columns; purification under `/api/screening/companies/{id}`; methodology_version everywhere).

## DEFERS (with cost)

- **D1 second rulebook (market-cap AAOIFI / switcher)** → revisit with Phase-7 filings.
- **D2 AAOIFI per-share purification** → advanced option deferred.
- **D3 capital-gains purification → OUT** (doctrinal disagreement, no advisor).
- **D4 buffer/Near-Limit flags** → value/threshold/reason suffices v1.
- **D5 full EGX33 reconciliation** → displays as unverified press summary until official PDF retrieved.
