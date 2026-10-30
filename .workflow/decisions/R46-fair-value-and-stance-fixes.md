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

## Round 3 (after the blind check, 2026-10-30)

Evidence: `.workflow/research/blind-fair-value-check-2026-10-30.md`. An independent agent with raw data only agreed on direction (52 of 75) and ranking (Spearman 0.67), but the app was a median 0.64x its values, traced to the two causes below.

| # | Ruling |
|---|---|
| V7 | **Debt grows with the firm.** The cash-flow base is the 3-year mean of pre-financing cash flow (operating cash flow - capex) x parent share. Projected FCFE each year = that flow grown at the stage's rate + the change in debt, where debt (interest-bearing debt, latest year) grows at the same rate, so the debt ratio stays stable. Past net borrowing no longer enters the base. Replaces V2's use of historical net borrowing. |
| V8 | **Banks: two-stage residual income with the fade.** 5 years at the near-term cost of equity, then the long-run rate (R45 fade ruling); ROE is the 3-year average. Replaces the single-rate justified P/B of V3. |

Version: valuation methodology 1.4.

## Round 4 (after re-running the blind comparison on 1.4, 2026-10-30)

Evidence: banks now agree with the blind values (median app / blind 1.18, all 11 within 2x; FAIT 64.0 vs 63.5); rank correlation 0.75 on 66 companies. But removing past borrowing from the base left 58 companies INVALID (was 26), e.g. SWDY: 3-year operating cash flow minus capex is negative.

| # | Ruling |
|---|---|
| V9 | **Residual income fallback.** When the cash-flow model is INVALID for a non-bank, value it with the same two-stage residual income model banks use (3-year ROE, 5-year fade), labelled as the fallback. |
