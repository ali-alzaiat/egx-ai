# R46: fair value and stance fixes (owner rulings 2026-10-30)

Source: `.workflow/research/verify-fair-value-stance-2026-10-30.md`. All options were put to the owner with a recommendation; the owner picked the recommended option every time.

| # | Problem | Ruling |
|---|---|---|
| V1 | Fair value starts from one year of FCF | Base = **3-year average FCFE** (last 3 fiscal years). Fewer than 3 years -> INSUFFICIENT_DATA. Average <= 0 -> INVALID (as today). |
| V2 | "FCFE" ignores borrowing and minorities | **True FCFE** = operating cash flow - capex + net borrowing, times the parent share (net income to common / net income incl. minorities; 1 when no minorities). Cost-of-equity model unchanged. |
| V3 | Banks get the cash-flow model | Banks use **justified P/B**: fair value = BVPS x (ROE - g) / (ke - g). Banks are identified from statement lines (net loans + customer deposits), not sector. |
| V4 | Negative growth extrapolated | Stage-1 growth **floored at 0%** (cap 13.59% unchanged). |
| V5 | P/E leg never runs | **Leave it off**; fair value is the intrinsic leg alone and the page says so. Revisit with sector data (R44). |
| S1 | Stance ignores fair value | When fair-value confidence is Medium or High, the **fair-value discount becomes the valuation sub-score**. Scenarios stay optional. New signal-rules version. |

Bank inputs: the 12 vendor files in bank format (ADIB, CANA, CIEB, COMI, EGBE, EXPA, FAIT, HDBK, QNBE, SAIB, SAUD, UBEE) carry `netLoans` and `totalDeposits`, which are not imported today (27 ontology codes, none bank-specific).

Versions: valuation methodology 1.2 -> 1.3; signal rules 2.0 -> 2.1.

## Round 2 (after recompute on real data, 2026-10-30)

Evidence: with V1-V5 live, 85 companies have a fair value; median fair value / price is still 0.37 (63 overvalued, 8 undervalued). Not a defect: at ke 28.33% (5 years) then 17.51%, growth capped at 13.59%, the model's fair price is 8.25x FCFE at the cap (5.0x at 0% growth); the market's median P/E is 13.5.

| # | Ruling |
|---|---|
| V6 | **Show implied growth**: keep the model and verdict; add a reverse calculation - the stage-1 growth that makes the model value equal the price (banks: the ROE the price implies) - shown beside the 13.59% economy cap. No new assumptions. |
| S2 | Stance valuation sub-score is **relative to the market**: the company's fair-value discount minus the median discount of companies with Medium+ confidence, on the same 0.5 full scale. Replaces the absolute gap from S1. |
| C1 | **Trading currency**: record each listing's trading currency; when it differs from the statements' currency, the price comparison is INSUFFICIENT_DATA ("price in USD, statements in EGP"). Never converted. Case: EGBE (price 0.51 vs BVPS 25.84 EGP). |

Build defaults, not yet confirmed by the owner: 0.5 full-scale discount; "Medium or High" includes VeryHigh. Fixed in review: a negative parent share (parent loss, minorities profit) is now INSUFFICIENT_DATA instead of flipping the sign of FCFE (MIPH FY2023 was -2.47).
