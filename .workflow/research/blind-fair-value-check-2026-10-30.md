# Blind fair-value check vs the app (2026-10-30)

A fresh agent got only raw exports (24.5k approved statement lines, latest prices with trading currency, four sourced market rates) and no app code, results or method. It chose its own methods (banks and financials: residual income; operating companies: two-stage FCFF DCF, falling back to residual income when cash flow is weak), its own cost of equity (31.6% near term, fading to 22.4%; Damodaran Egypt spread and CRP), and terminal growth of 10.46% nominal. Script and outputs are kept in the session scratchpad (`blind/blind_valuation.py`, `blind_fair_values.csv`, `blind_method.md`).

## Agreement
- Both value most of the market below its price. On the 75 companies both value and have a price: median fair value / price is 0.39 in the app and 0.55 blind.
- Verdict direction agrees for 52 of 75 (45 both overvalued, 4 both undervalued, 3 both around fair value). Spearman rank correlation of fair value / price: 0.67.
- Both refuse or flag the same oddities: NIPH far above value in both; COPR, MEGM and RTVC get no app value, and the blind agent flagged their price and share count as inconsistent (implied P/E 0.75 for MEGM, 0.25 for RTVC).

## Where the app is lower (median app / blind = 0.64)
| Blind method | n | median app / blind |
|---|---|---|
| FCFF DCF | 26 | 0.52 |
| Residual income (fallback) | 29 | 0.64 |
| Residual income (bank) | 11 | 0.74 |
| Residual income | 16 | 0.98 |

Causes traced:
1. **Debt repayment projected forever.** The FCFE base includes the 3-year average net borrowing, so a company paying down debt carries that repayment into every future year, growing at up to 13.59%. 34 of the 105 companies with an FCFE base were net repayers over the 3 years. RACC repaid 159m-265m a year against total debt of 752m, so the projection repays several times the debt that exists; the app's base is 139m against the blind 424m FCFF.
2. **The bank model does not fade the discount rate.** Justified P/B uses 28.33% in a perpetuity, while the FCFE model fades to 17.51% after 5 years (owner ruling R45: 5-year fade in all models).
3. **Bank ROE is a single year.** FAIT: 2025 ROE 10.2% in the app vs a 3-year 20.4% blind (2024 net income was [removed] against [removed] and [removed] either side). The FCFE base is a 3-year average by ruling V1; bank ROE is not.

Not a cause: the terminal multiple. App 1 / (17.51% - 5.4%) = 8.3x; blind 1 / (22.4% - 10.46%) = 8.4x.

## Differences that are judgement, not error
- The blind agent converted USD prices at 56.17 EGP/USD; the app refuses the comparison (ruling C1).
- The blind agent used net income to common (after employee profit share); the app's ROE input should be checked for the same line.
