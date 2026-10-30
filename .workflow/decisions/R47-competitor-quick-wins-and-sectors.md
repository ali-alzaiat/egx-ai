# R47: competitor quick wins and the sector loader (owner rulings 2026-10-30)

Source: `.workflow/research/competitor-enhancements-2026-10-30.md` (ranked list plus the router's data check, section 5).

Build list chosen by the owner: the quick wins below, and the R44 sector loader first among the sector features. Not chosen for now: screener, Shariah history and alerts, stance track record.

| # | Item | Ruling |
|---|---|---|
| Q1 | Piotroski F-Score | **Shown beside the score**, its own card on the Score tab (9 checks with their inputs, "N of 9 pass", INSUFFICIENT_DATA per check when inputs are missing). Not part of the investment score; no score methodology bump. Banks: not meaningful, so not run, with the reason. |
| Q2 | Dividend safety | **Shown only**: payout ratio (dividends paid / net income to common) and cash coverage (operating cash flow - capex) / dividends paid, labelled "from dividends paid (derived)", per R44 D-6. Score dividend checks stay NOT_RUN (earlier ruling). |
| Q3 | Freshness line | **Company header + page tops**: hub header adds "Fundamentals: FY<year> (vendor, provisional)" beside "Prices as of"; Markets, Recommendations and Shariah screening pages get "Prices as of <date>" under the title. |
| S1 | Sectors | Build the R44 D-9 sector loader as specified there (EGX 18 sectors, match_basis, Shariah activity tags). Heatmap and sector-relative grades come after, each with its own design decision. |

## Price history chart (owner request 2026-10-30)

Ranges Day, Week, Month, YTD, 1 year, 5 years, plus a forecast button.

| # | Ruling |
|---|---|
| P1 | **Day** = last session summary (open, high, low, close, change, volume); no intraday line. Daily closes only, no intraday ingestion. |
| P2 | **Backfill 5 years** of daily prices from Yahoo (the existing source), one-off CLI; stored history today starts 2025-09-18. |
| P3 | **Forecast = volatility cone**: bands where the price would land 50% and 90% of the time over the next 1, 3 and 6 months if it keeps its past volatility, centred on today's price (zero drift). Deterministic and versioned; labelled "range of typical moves, not a prediction". No point forecast, no trend line. |
| P4 | **Chart patterns: detect + measured EGX odds, display only.** Deterministic, versioned detection of head and shoulders (and inverse), double top/bottom and triangles (ascending, descending, symmetrical), counted only once confirmed (breakout close), drawn on the chart. Each pattern type shows its backtest on the stored EGX history: number of cases, how often the price moved the expected way after 20 and 60 sessions, the base rate for an ordinary day, and a confidence interval; too few cases says so. Does not feed Buy/Hold/Reduce. No look-ahead: detection at a date uses only prices up to that date. |

Proposed, not yet approved: test the volatility cone against history (share of past cases that ended inside the 50% / 90% bands, per stock) and show the measured hit rate beside the cone.
| P6 | **Forming patterns shown with their own measured odds** (owner, 2026-10-30). A shape whose confirmation window is still open and that has not broken out is shown as forming, with the close that would confirm it. Its odds are measured from the forming stage on EGX history: how often such shapes went on to confirm, and how the price moved after 20 and 60 sessions from the forming date (not from a breakout). Confirmed-pattern odds stay as they are. Display only. Version patterns-1.1. |
| P7 | **Forming-pattern filter on the Companies page** (owner, 2026-10-30): a filter beside the search with the choices any forming shape / expected to break up / expected to break down (a symmetrical triangle counts under "any" only). When on, the list shows only those companies and a column with the shape, the confirming close and the sessions left; a row opens the chart with Patterns on. |
| P5 | **Cone calibration approved** (owner, 2026-10-30): the cone is tested on each stock's own history and the chart shows the measured share of past cases that ended inside the 50% / 90% bands. |

## Follow-up rulings (2026-10-30)

| # | Ruling |
|---|---|
| S2 | **Sector rows by owner review.** An agent reads EGX "All Listed Stocks" (S1) once and proposes ticker -> ISIN -> sector for every company, flagging uncertain matches; the owner approves or fixes the table; only approved rows load (`match_basis` "name_review"). No per-company page fetching (R44 stands). |
| S3 | **Sector table approved** (owner, 2026-10-30). Source: S1 read once in a browser on 2026-10-30 (robots.txt 404), saved as `.workflow/research/egx-s1-listed-stocks-2026-10-30.tsv`; proposal in `egx-sectors-proposed-2026-10-30.csv`. Rulings: all 14 translated/renamed name matches load, MAAL included; EGX's published sector is kept even where it looks odd (ALRA Real Estate, ICFC and SMFR Trade & Distributors, MEGM Paper & Packaging, OIH IT/Media, SCTS Education); of the two-listing pairs only FAIT/FAITA loads (confirmed by our EGP/USD records); SEIG/SEIGA and VLMR/VLMRA stay blank until the listing is confirmed; AREH stays blank (R44 D-9). 225 rows loaded. |
| Q4 | **Piotroski leverage** = interest-bearing debt / total assets (stated in the check); a missing debt line makes only that check INSUFFICIENT_DATA. |
