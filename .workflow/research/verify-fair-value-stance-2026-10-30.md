# Verification: fair values and stances on real data (2026-10-30)

Scope: all 234 companies via the running API (valuation 1.2, signal-rules-2.0), dev DB after the 30 Oct restore, prices to 2026-10-28.

## Correct (verified)
- FCFE math: recomputed all 91 intrinsic values independently (float re-implementation of the 2-stage + faded-rate model). 91/91 match to 4 dp.
- Verdicts: 84 with fair value and price; label matches discount vs required margin in 84/84.
- Inputs: app FCF equals the vendor file `fcf` (ncfo + capex) for the same period in 91/91. Share counts are period-end common shares (e.g. CCAP 4.23bn after its 2025 capital increase), not weighted averages.

## Not reliable (methodology / coverage)
1. Single-year FCF base. Fair value / price median 0.37; 35 of 84 below 0.25 (AMES: one year's capex almost equalled its operating cash flow, leaving a near-zero FCF). One lumpy capex year sets the whole valuation.
2. "FCFE" is OCF - capex with no net borrowing; consolidated, so minority interests' share is included. Overstates indebted groups (CCAP 6.6x price).
3. One profile for everyone: all 234 on `default` (sector is null everywhere), so banks get FCFE (COMI INVALID: negative FCF).
4. Relative (P/E) leg: 234/234 INSUFFICIENT_DATA (no sourced target multiples). DDM: 234/234 (no DPS). Fair value = FCFE alone.
5. Negative 3y CAGR extrapolated for 5 years (no floor), e.g. AREH -17.8%.
6. Bull/base/bear scenarios: 234/234 INSUFFICIENT_DATA.

## Stances
- Engines feeding the stance: technical only 179, technical+volume 16, score+technical 4, none 35 (no prices).
- The fair-value verdict is not a stance input; valuation enters only via scenarios, which are always missing. 16 "undervalued" are all "reduce".
- Distribution: reduce 172, hold 50, buy 12. `app.signals.sanity`: 86% reduce in top 50; breadth -10% median over 20 sessions, 80% falling, so the skew matches the tape.
- Statement freshness unknown for 234/234: vendor lines carry no published_date.

## Not checked
- Vendor (S&P via stockanalysis) figures against official filings.
