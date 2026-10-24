# Long-run (terminal-stage) EGP cost of equity - 2026-10-24

Brief: `.workflow/inbox/researcher.md`. Purpose: R45 M5 (fade the discount rate; explicit stage = R44 28.36%, terminal value = a long-run Ke consistent with 5.4% terminal inflation). All fetches 2026-10-24 unless stated.

## Bottom line

Recommended terminal Ke: **17.51%** (Candidate B). Damodaran's full method gives 20.82% (Candidate A). Both start from a default-free long-run EGP rate of 7.34%, built by the inflation-differential method on the 5.4% IMF inflation. A longest-bond yield is not usable: no EGP bond at 5y or longer is available from an official source, and it would carry today's inflation, not 5.4%.

## Sourced inputs

| # | Input | Value | Source (URL) | Fetched | Notes |
|---|---|---|---|---|---|
| I1 | Egypt CPI inflation 2031 (terminal anchor) | 5.4% (2026-2031: 13.3, 14.8, 8.9, 6.5, 5.8, 5.4) | https://www.imf.org/external/datamapper/api/v1/PCPIPCH/EGY | 2026-10-24 | WEO edition not stated in the API response (`no data`). Matches R44. |
| I2 | US CPI inflation 2031 (IMF) | 1.9% (2026-2031: 3.6, 2.8, 2.1, 1.9, 1.9, 1.9) | https://www.imf.org/external/datamapper/api/v1/PCPIPCH/USA | 2026-10-24 | Used only in sensitivity S1. |
| I3 | Damodaran USD risk-free (US T-bond net of US default spread) | 4.23% | https://pages.stern.nyu.edu/~adamodar/pc/blog/DiffInflationRiskfree26.xlsx (cell B2) | 2026-10-24 | July 2026 blog workbook. |
| I4 | Damodaran expected US inflation (his own input) | 2.35% | same file, cell B1 | 2026-10-24 | Pairs with I3. |
| I5 | Damodaran's own EGP risk-free via inflation differential | 10.20% = (1+4.23%) x (1+8.2167%) / (1+2.35%) - 1, where 8.2167% is his average expected Egypt inflation 2026-2031 | same file, row 56 (Egypt), formula in D56 | 2026-10-24 | His Egypt average (8.22%) differs from the IMF 2026-2031 average I computed from I1 (9.12%). Vintage difference not explained (`no data`). It is a 6-year average, not the terminal rate; we substitute 5.4%. |
| I6 | Method statement | "If no liquid local bond exists, or you distrust the bond rate, you can build the rate from a base-currency rate plus the expected inflation differential" (his example: 4% USD, 2.5% US inflation, 10.5% Brazil inflation gives about 12%). Local-bond rates are adjusted "for the default risk of the government in question". | https://aswathdamodaran.blogspot.com/2026/07/country-risk-drivers-measures-and.html (post dated 2026-07-15) | 2026-10-24 | Page does not state the exact default-spread subtraction formula or say whether a CRP is added on top of a local rate (`no data` on that point). |
| I7 | Mature-market ERP, July 2026 | 4.20% = S&P 500 implied ERP 4.42% (1 Jul 2026) less 0.22% US Aa1 default spread | same blog post; workbook https://pages.stern.nyu.edu/~adamodar/pc/datasets/ctrypremJuly26.xlsx, sheet "ERPs by country", cell for mature premium = 0.042 | 2026-10-24 | **Newer than the 4.23% (5 Jan 2026) in R44.** Damodaran's homepage says the next update is January 2027 (search-result text, not fetched from the homepage). |
| I8 | Egypt, Moody's Caa1: rating-based default spread | 5.97% | ctrypremJuly26.xlsx, sheet "ERPs by country", row Egypt; sheet "Default Spreads for Ratings" Caa1 = 597.02 bp (30 Jun 2026) | 2026-10-24 | Workbook header: "Default spreads corrected on July 9, 2026". |
| I9 | Egypt country risk premium (default spread x 1.5545 relative equity volatility) | 9.28%; total ERP 13.48% | same sheet, Egypt row (13.48% = 4.20% + 9.28%) | 2026-10-24 | The Jan 2026 values in R44's file were 9.71% / 13.94%. |
| I10 | Egypt CDS-based alternative | CRP 5.32%, total ERP 9.52%; net CDS 3.42% | same sheet, Egypt row (CDS columns) | 2026-10-24 | Optional alternative to I8/I9. |
| I11 | Damodaran's rule on CRP | Total ERP = mature premium + country risk premium (step 4 of the workbook FAQ) | ctrypremJuly26.xlsx, sheet "Explanation and FAQ" | 2026-10-24 | In his framework the risk-free rate is default-free, so the CRP is added. In R44 the 24.128% yield already carries sovereign risk, so adding a CRP would double count. |
| I12 | Current EGP long yields (context, not used) | 3y T-bond 24.128% (auction 19/10/2026); 1y 25.912% | already in `.workflow/research/r43-sector-and-valuation-sources.md` rows 99-100 (CBE auction pages) | filed 2026-10-23 | Not re-fetched. No 5y/10y auction on the CBE page. |
| I13 | Cbonds "Egypt 10Y YTM" 23.06% on 2026-09-09 | 23.06% | https://cbonds.com/indexes/24229/ | **search-result snippet only** | Page returned HTTP 403 on fetch. Aggregator quote index, not official. Unverified; not used. |

## Candidates (all EGP nominal; beta 1 as in R44)

Common step: default-free long-run EGP rate
`rf_LR = (1 + USD rf) x (1 + Egypt inflation) / (1 + US inflation) - 1 = 1.0423 x 1.054 / 1.0235 - 1 = 7.34%` (I3, I1, I4; method I6).

| Cand. | Formula | Calculation | Terminal Ke |
|---|---|---|---|
| **A: Damodaran full** | rf_LR + mature ERP + scaled CRP (= total Egypt ERP) | 7.34% + 13.48% (I9) | **20.82%** |
| **B: R44-consistent (recommended)** | rf_LR + sovereign default spread + mature ERP, no CRP | 7.34% + 5.97% (I8) + 4.20% (I7) | **17.51%** |
| C: Lower bound, sovereign risk fades to zero | rf_LR + mature ERP | 7.34% + 4.20% | 11.54% |

Variants (not separate options):
- Sensitivity S1: swap Damodaran's US inflation (2.35%) for IMF's 1.9% (I2). rf_LR becomes 7.81%, so A = 21.29%, B = 17.98%.
- Sensitivity S2: CDS instead of rating (I10). B with net CDS 3.42% gives 14.96%; A with CDS-based total ERP gives 16.85%.
- Rejected: "longest EGP bond + mature ERP" (e.g. I13 23.06% + 4.20% = 27.26%). It embeds today's inflation, so it does not fade and contradicts the 5.4% terminal growth. Also unverified (I13).
- Rejected: Fisher with a real rate. No sourced long-run Egypt real yield exists (no inflation-linked EGP bond found; nothing from CBE or IMF). `no data`.

## Why B over A

- B has the same structure as R44 (sovereign-yield-equivalent rate + mature ERP, no separate CRP, no double count). Only the inflation embedded in the rate changes (today's to 5.4%). The fade from 28.36% to 17.51% is therefore attributable to inflation convergence plus the default spread being a constant 5.97% spread rather than a 24% yield.
- A is Damodaran's published procedure. It is 3.3 pp higher because the CRP is scaled by 1.5545 for equity-vs-bond volatility. It is the more conservative option and the more defensible if the owner wants to cite the method one-for-one.
- C is shown only as a bound. It assumes Egypt's sovereign risk vanishes in perpetuity, which no source supports.
- All three are above the 5.4% terminal growth, so Gordon growth is defined. Implied terminal multiple 1/(Ke - g): A 6.5x, B 8.3x, C 16.3x (arithmetic, not sourced). R44's 28.36% would give 4.4x.

## Caveats for the methodology note

1. The mature ERP differs between stages if R44 stays at 4.23% (Jan 2026) while the terminal uses 4.20% (July 2026). Recommend refreshing R44's ERP row to 4.20% (pm/architect call) so both stages use one vintage.
2. Default spread and CRP are held constant in perpetuity. Damodaran does not state a fade in the sources read (`no data`); a sovereign-risk fade is a methodology choice, not sourced.
3. I3/I4 (4.23%, 2.35%) are Damodaran's inputs from a workbook, not a primary market series. Primary US Treasury yield not fetched.
4. The new inputs would be stored with `source_url` and `as_of` per R44's pattern; the terminal Ke is computed in code (formula above), not entered by hand. Suggested keys: `usd_riskfree_rate` 0.0423, `us_long_run_inflation` 0.0235, `sovereign_default_spread` 0.0597 (new), with `equity_risk_premium` refreshed to 0.0420. Schema and staleness choices are the architect's.
5. Damodaran's page labels conflict (the ctryprem.html page header says 5 Jan 2026 while listing Apr and Jul 2026 updates). The July numbers above come from the July workbook directly.

## Not found

- Official CBE or MoF yield for a 5y+ EGP bond: no data (CBE auction page lists up to 3y; one search for 5y/10y October 2026 auctions returned nothing relevant).
- Long-run Egypt real interest rate from IMF/CBE: no data.
- Damodaran text stating explicitly whether a CRP is added on top of a local-currency government bond rate: no data in the blog post; the workbook FAQ gives only "total ERP = mature + CRP".

ASK USER: Which terminal-stage cost of equity should the fair-value model use: A 20.82% (Damodaran full, with scaled CRP), B 17.51% (R44-consistent, no CRP; recommended), or C 11.54% (lower bound, not recommended)? And should R44's ERP row be refreshed from 4.23% (Jan 2026) to 4.20% (Jul 2026)?

## Nominal GDP growth cap

Request: one citable nominal GDP growth rate for Egypt to cap fair-value stage-1 revenue growth (R45 F13). Fetched 2026-10-24.

### Inputs

| # | Input | Values | Source (URL) | Fetched | Notes |
|---|---|---|---|---|---|
| N1 | Real GDP growth, % | 2026 5.1, 2027 4.7, 2028 5.0, 2029 5.5, 2030 4.8, 2031 4.8 | https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH/EGY | 2026-10-24 | Same DataMapper vintage as I1 (2029 5.5 / 2030-31 4.8 match the R43 file). Edition not stated in the response (`no data`). Egypt data are fiscal-year (Jul-Jun) per the R43 file note. |
| N2 | CPI inflation, % (proxy for the GDP deflator) | 2026 13.3, 2027 14.8, 2028 8.9, 2029 6.5, 2030 5.8, 2031 5.4 | https://www.imf.org/external/datamapper/api/v1/PCPIPCH/EGY | 2026-10-24 | = I1. |
| N3 | Nominal GDP in EGP | `no data` | https://www.imf.org/external/datamapper/api/v1/NGDP/EGY returned only country labels; a web search found only USD aggregator figures, which conflict (e.g. $429.6bn vs $399.5bn for 2026) | 2026-10-24 | Not usable: USD, and mixes exchange-rate moves into growth. The IMF WEO database (local-currency "GDP, current prices") would be the primary source; not reachable via the DataMapper API. |

### Formula

`nominal_growth(year) = (1 + real_growth) x (1 + inflation) - 1`. CPI substitutes for the GDP deflator (no deflator series sourced), so this is an approximation.

| Year | 2026 | 2027 | 2028 | 2029 | 2030 | 2031 |
|---|---|---|---|---|---|---|
| Nominal % | 19.08 | 20.20 | 14.35 | 12.36 | 10.88 | 10.46 |

### Candidates

| Cand. | Definition | Value |
|---|---|---|
| **G1 (recommended)** | Geometric average 2027-2031 (5 years, a typical stage-1 horizon; 2026 is already ~10 months elapsed) | **13.59%** |
| G2 | 2031 value, (1.048 x 1.054) - 1; the long-run value consistent with the 5.4% terminal inflation | 10.46% |

For reference: 2026-2031 geometric average 14.49%; 2029-2031 geometric average 11.23%. Arithmetic 2027-2031 average is 13.65%.

### Recommendation and caveats

- G1 caps stage-1 growth at a level that does not fall below the inflation-driven decline; G2 is the stricter cap and matches the terminal anchor (stage-1 revenue growth would converge to 10.46%, still above terminal g of 5.4%, so a fade from the cap to g is still a methodology step for the architect/pm).
- If the stage-1 horizon is not 5 years, use the geometric average of the matching years from the table above.
- Because the cap is the geometric mean of a path that is front-loaded by 2027's 20%, G1 is generous in early years; the owner may prefer a per-year cap (the table row) over a single number. That is a methodology choice, not sourced.

ASK USER: Which nominal GDP growth cap: G1 13.59% (2027-2031 geometric average, recommended), G2 10.46% (2031 value), or a per-year cap from the table?
