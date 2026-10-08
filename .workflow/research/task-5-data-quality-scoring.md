# Research: Task 5 — Data-quality scoring for EGX stocks

**Question:** How do competitors score/communicate financial data quality to users — granularity, UI patterns, disclaimers?
**Researcher:** nadia (via router) · 2026-10-08 · All URLs fetched same date.

[FULL RESEARCH CONTENT PASTED BELOW — see researcher's inline output; this file is the filed copy]

---

## Summary of findings

### Five communication shapes in the market
| Shape | Who uses it |
|---|---|
| Composite 0–100 score | Soda (health score), Morningstar (coverage %), small platforms |
| Per-component score, no single headline | Bloomberg ESG (field→sub-issue→issue roll-up) |
| Binary / enumerated flags | Morningstar readiness (Yes/No ×4), S&P Research Type, DataScope grade |
| Pass/warn/fail per check | Soda, Great Expectations |
| Ordinal 1–5 per datapoint | PCAF scores surfaced by Bloomberg |

No vendor publishes a lone unexplained number. Every composite score found is accompanied by component breakdown, per-check detail, or a stated scale definition.

### Key precedents
- **Morningstar**: Data Coverage % shown per pillar + weight-scaled overall; 67% AUM threshold gates whether a score is shown at all (withheld, not low-scored). Readiness flags (Yes/No ×4) but NOT for Stocks database.
- **Bloomberg PCAF**: 1 (highest) to 5 (lowest) per field per scope, separate Data Type enum (Reported / Smart Estimate / Industry Implied) — provenance enum and ordinal score as separate queryable fields.
- **S&P**: "As Reported" vs "Fully Researched/Modeled" Research Type flag; dual-view + click-through audit trail to source documents; QA analyst not involved in collection.
- **DataScope**: grade field per pricing fact; grade > 0 = suspect, under analyst review; correction surfaces as U (Update) — explicit "under review" state.
- **Soda (OSS)**: DQ Health Score = % checks passed; three states pass/warn/fail; failed checks vs execution errors distinguished; public REST API for aggregate scores. Documented bug: two surfaces counting unevaluated checks differently give two "correct" scores (84% vs 73%) — pin one definition per surface.
- **Great Expectations**: no canonical score; maintainer quote: "different teams have different preferences for how to score." Community de-facto: successful/total × 100.
- **Mubasher (EGX-local)**: scope + freshness disclaimer in page header ("ratios for commercial companies only… updated quarterly") — closest local precedent to disclosing coverage limits.
- **FoudaLens (EGX-local)**: 0–100 "Fouda Score" with methodology page — but investment score, not data-quality score. Marks competitors' EGX coverage as "⚠️ Unverified."
- **SteadyShares**: 0–100 score = share of model inputs actually available; "we display filing dates so the lag is never hidden."

### Standards (wording the score definition)
- **DAMA/GOV.UK six dimensions**: accuracy, completeness, consistency, timeliness (among others). Completeness = "what data is critical vs optional," not 100% of fields.
- **ISO 8000-8**: (a) state the scale used; (b) let receiver know confidence — especially if any rule was not applied or data was not checked. Thresholds are business-set.
- **DAMA-NL catalogue**: 60 dimensions, 12 "common" — use this vocabulary, don't invent.

### EGX-local landscape
- No EGX-local vendor publishes a data-quality score (based on these searches; not an exhaustive audit).
- Mubasher discloses scope + update cadence.
- FoudaLens marks others' coverage as unverified rather than scoring its own data quality.
- EGX itself: no data on self-published data-quality scores.

### Gaps (`no data`)
Bloomberg FLDS per-datapoint provenance in Terminal UI; Refinitiv user-facing per-security DQ score for equities (appears not to exist); Morningstar "Investment Data Quality" product detail (bot interstitial); Deequ scoring API; primary-source disclaimer text; EGX/FRA official guidance.

### Implications for Task 5 (implications, not decisions)
1. Composite headline + component scores + per-check detail is convergent. `overall_score` alone is weaker than every precedent.
2. Return `scale` and `checks_not_run` in payload — ISO 8000-8 asks for both.
3. Distinguish INSUFFICIENT_DATA from a low score — Morningstar withholds below a gate; our AGENTS.md already mandates `{"value": null, "status": "INSUFFICIENT_DATA"}`.
4. Expose provenance/freshness as fields, not just inside the score.
5. Warn/fail thresholds per check map onto bar-count vs expected-trading-days.
6. Open lane: no EGX-local vendor publishes data-quality scoring.

NEXT: pm
