# R43 data gaps D-8 + D-9: sector and valuation-assumption sources

**From:** Nadia (researcher) · 2026-10-24 · for pm (then architect / analyst)
**Brief:** `.workflow/inbox/researcher.md` top entry (2026-10-23). Context: `.workflow/design/r43-computed-company-data.md` §1.6, §6 D-8/D-9.
**Method:** EGX and CBE pages were read in the built-in browser at human pace, because WebFetch got `ECONNRESET` (EGX) or "Request Rejected" (CBE WAF). No CAPTCHA was hit and nothing was bypassed. Per-page reads only: 1 listed-stocks page, 1 company-details page, 16 sector-index dropdown views (one EGX error page on the first try, so I waited and retried once), 3 CBE pages and 1 EGX market-watch page. Dev-DB checks were read-only `SELECT`s.

---

## Task A (D-9): EGX sector per company

### A1. Sources found

| # | Source | What it gives | Fetched |
|---|---|---|---|
| S1 | https://www.egx.com.eg/en/listedstocks.aspx ("All Listed Stocks") | **Every listed stock**: company name, **ISIN**, **SECTOR**. 263 rows, 263 unique ISINs, 18 sectors. No ticker/Reuters column. Each row has hidden links `CompanyDetails.aspx?ISIN=…`, `StocksData.aspx?ISIN=…`, `NewsList.aspx?ISIN=…`. No as-of date on page. | 2026-10-23 |
| S2 | https://www.egx.com.eg/en/currentindexconstituntes.aspx?type=3&nav=3 ("Sectoral Indices → Index Constituents") | ISIN + **Reuters code** + name for each **sector index**. The sector is picked with an ASP.NET postback dropdown (`ctl00$C$I$DropDownList1`), **not** a URL parameter. Footer: "The index constituents may include companies with multiple lines". | 2026-10-23 |
| S3 | https://www.egx.com.eg/en/CompanyDetails.aspx?ISIN=EGS60121C018 (one page, CIB) | ISIN, **Reuters code (COMI.CA)**, sector (Banks), listed shares 3,405,139,100, listing date, par value, P/E 5.34, dividend yield 4.65, market cap (as of last trading date 21/10/2026) | 2026-10-23 |
| S4 | https://www.egx.com.eg/en/MarketWatchSectors.aspx | Per-sector traded value/volume and market cap for the day (18 sectors). **No P/E.** | 2026-10-23 |

**`type=` mapping:**
- `type=3`: sectoral-indices family. Verified this session.
- `type=1`: EGX30, from `phase-2-industry-competitive-landscape.md` (fetched 2026-10-10).
- `type=22`: EGX33 Shariah, already used in `backend/app/screening/egx33.py`.
- `type=2`: the page hung and rendered nothing (2026-10-23). `no data`.

The sector inside `type=3` comes from the dropdown values:

| Dropdown value | Sector index | Constituents read | All Listed Stocks (S1) count |
|---|---|---|---|
| 1 | Banks | 12 | 14 |
| 2 | Basic Resources | 13 | 18 |
| 7 | Health Care & Pharmaceuticals | 15 | 21 |
| 8 | Industrial Goods , Services and Automobiles | 7 | 9 |
| 11 | Real Estate | 29 | 35 |
| 16 | Travel & Leisure | 5 | 14 |
| 18 | IT , Media & Communication Services | 7 | 8 |
| 19 | Food, Beverages and Tobacco | 25 | 31 |
| 20 | Energy & Support Services | 3 | 6 |
| 21 | Trade & Distributors | 6 | 7 |
| 22 | Shipping & Transportation Services | 3 | 5 |
| 23 | Education Services | 4 | 6 |
| 24 | Non-bank financial services | 26 | 42 |
| 25 | Contracting & Construction Engineering | 9 | 16 |
| 26 | Textile & Durables | 8 | 9 |
| 27 | Building Materials | 10 | 14 |
| none | Utilities | no sector index | 2 |
| none | Paper & Packaging | no sector index | 6 |

The 18 S1 sector names match `EGX_SECTOR_NAMES` in `backend/app/industry/constants.py`, **except for spacing**. EGX writes `"Industrial Goods , Services and Automobiles"` and `"IT , Media & Communication Services"` (space before the comma). The repo writes them without the space.

**Full listed-companies-by-sector list: yes, it exists (S1).**

### A2. Coverage against the dev DB (read-only, 2026-10-23)

- The DB has 234 companies: 230 real and **4 junk rows `RT9ECFD0E`, `RT9144DDC`, `RT932D477`, `RT9E9C665`** ("RT9… Co", isin = ticker). These look like test-fixture leakage into the dev DB, so they should be flagged to QA.
- **`companies.isin` is null for all 230 real companies.** S1 is keyed by ISIN only, so `industry/backfill.py`'s ISIN join matches **0** companies today. Its fallback to the Reuters ticker needs a Reuters code, and S1 has none.
- Joining the 16 sector-index pages (S2) by Reuters code (minus `.CA`) gives **181 / 230 (79%)** matched with sector directly.
- One alias is needed: EGX `AIFI.CA` (Atlas For Investment and Food Industries, ISIN EGS071L1C018, Real Estate) is **`ALRA`** in our DB (stockanalysis ticker). With it, coverage is **182 / 230**.
- 48 companies remain without a match. All appear in S1 by name; I checked several by eye, e.g. SAIB, EGAS, TAQA, RAKT, UNIP, IRON, HALN→"MNT Tech Holding". They are mostly non-index names, plus the whole Utilities and Paper & Packaging sectors:
  ACAMD, AFDI, AMES, AMII, APSW, AREH, BIOC, SPMD, CAED, CCRS, COPR, CRST, DCCC, DEIN, DGTZ, EASB, EGAS, ELNA, ELWA, EOSB, EPPK, FCMD, GGRN, GMCI, GPPL, HALN, ICLE, IRON, KORA, KRDI, MEGM, MMAT, NAPR, NEDA, PHGC, POCO, PRMH, RAKT, ROTO, RREI, RTVC, SAIB, SPHT, TAQA, TWSA, TYCN, UEFM, UNIP.
  - **AREH** ("Real Estate Egyptian Consortium") had no obvious S1 name match, so it may be delisted or renamed. `no data`.
- **Estimated coverage:** 182 matched for certain via the official ISIN↔Reuters pairs, plus up to ~47 by reviewed name match against S1. That is ~229/230 (~99%), with 1 `no data` (AREH). These figures were **verified on 2026-10-23** and will drift with index reviews.

### A3. Recommended loading approach (snapshot module, mirrors `screening/egx33.py`)

1. **New module `backend/app/industry/egx_sectors.py`** with `SOURCE_URLS` (S1, S2), `FETCHED_ON = date(2026,10,23)`, a `SNAPSHOT_NOTE` saying the pages carry no effective date, and a literal tuple `SECTOR_ROWS: (ticker, isin, egx_sector_name, match_basis)`.
   - `match_basis` is one of:
     - `"sector_index_reuters"` for the 181 S2 rows,
     - `"alias"` for ALRA↔AIFI,
     - `"name_review"` for the S1 name matches, each checked by a human. It is not automatic fuzzy matching.
   - The CLI follows the EGX33 pattern: `python -m app.industry.egx_sectors` (idempotent). It calls the existing `backfill_egx_sectors` with `EgxListingRow`s, and also **writes `companies.isin`** from the snapshot, so later loads can join on ISIN.
2. **Normalise sector names** before `_ensure_egx_sector`: collapse `" ,"` → `","` and trim. Without this the backfill:
   - creates 2 duplicate `egx_sectors` rows, and
   - leaves "Industrial Goods…" companies unmatched by `METRIC_PROFILES`/`VALUATION_PROFILES` (`industrials` profile), so they fall to `default`.
3. **ISIN↔ticker bridge for the 48 names (PM/router call):**
   - (a) A human name review against S1, recorded in the snapshot with `match_basis="name_review"`. Recommended: no extra fetches.
   - (b) Reading `CompanyDetails.aspx?ISIN=…` (S3), which shows the Reuters code, for those 48 ISINs at human pace. That is 48 page views, which I did not do because it approaches bulk scraping.
   - Do **not** script S1/S2. S2 is postback-driven, and EGX returned an error page once under 3-second spacing.
4. The GICS mapping stays as is: `EGX_TO_GICS_SUB` maps only Banks, Real Estate, Industrial Goods and Contracting. Other sectors keep `gics_sub_industry_id = null`, which is honest. No new GICS mappings are proposed without a citable source.

### A4. Blocker for Shariah: EGX sector names must NOT go into `company.industry` as-is

`screening/rules.py::screen_industry` fails a company when any prohibited keyword is a **substring** of `company.industry`. The keywords come from the `ProhibitedIndustry` values in `screening/methodology.py`: `alcohol`, `gambling`, `pork`, `tobacco`, `adult_entertainment`, `weapons`, `conventional_banking`, `conventional_insurance`, `entertainment`. With raw EGX sector names:

- **"Food, Beverages and Tobacco" contains "tobacco".** All 31 names in that sector would FAIL, including EGX33 Shariah members JUFO, EFID and MPCO (see `egx33.py`). Only Eastern Company (EAST) is actually a tobacco business.
- **"Banks" does not contain "conventional_banking".** All 14 banks would PASS, including conventional CIB, QNB and Credit Agricole. EGX does not separate Islamic from conventional banks; ADIB, SAUD and FAIT are Islamic.
- **"Non-bank financial services" does not contain "conventional_insurance".** Delta Insurance, Mohandes Insurance and Misr Life Insurance would PASS.

So the EGX sector is a valid **valuation/peer** classification, but it is too coarse for the Shariah business-activity screen. That screen needs a per-company, versioned business-activity tag, e.g. bank = conventional/islamic and tobacco = EAST, with a cited source per tag. This is a **Shariah-methodology decision (pm / tech-lead / analyst)**. Until it is made, write the EGX sector to `companies.sector` / `egx_sector_id` only and keep `companies.industry` null, so the industry rule stays INSUFFICIENT rather than wrong.

---

## Task B (D-8): valuation assumptions for Egypt

All values are as published. Converting them into `discount_rate` / `terminal_growth_rate` (e.g. CoE = Rf + β·ERP, and whether to strip the default spread from a local-currency Rf) is a methodology choice for analyst/pm. I deliberately do **not** compute a discount rate here.

| Key it would feed | Value | Unit | As-of | Source (fetched) | Note |
|---|---|---|---|---|---|
| Risk-free, EGP, 1y | **25.912** | % weighted avg accepted yield, 364-day T-bill | auction 22/10/2026 | https://www.cbe.org.eg/en/auctions/egp-t-bills (2026-10-23) | 182-day: 25.166%. Submitted-bid avg 26.425% (364d). |
| Risk-free, EGP, 3y | **24.128** | % weighted avg accepted yield, fixed-coupon T-bond (coupon 23.981%) | auction 19/10/2026 | https://www.cbe.org.eg/en/auctions/egp-t-bonds-fixed-coupon (2026-10-23) | 1.5y: 24.429%. No 5y/10y auction on the page. A longer-tenor EGP yield is `no data`. |
| Policy rate (context) | overnight deposit **19.00**, lending 20.00, main op 19.50, discount 19.50 | % | MPC 24 Sep 2026 (unchanged) | https://www.cbe.org.eg/en/news-publications/news/2026/09/24/15/38/mpc-press-release-24-september-2026 (2026-10-23) | T-bill yields sit ~6–7 pp above the policy rate. Analyst should note this before choosing Rf. |
| Inflation outturn (context) | headline **14.5**, core 14.9 | % y/y | Aug 2026 | same CBE release | — |
| Inflation target (anchor) | **7 ± 2**, convergence "during H2 2027" | % | 24 Sep 2026 | same CBE release | The 5% ±2 for Q4 2028 target appears only in secondary reports of the Dec-2024 MPC: https://www.dailynewsegypt.com/2024/12/28/cbe-extends-inflation-target-horizon-to-q4-2026-at-7-%c2%b1-2-q4-2028-at-5-%c2%b1-2/ (search result, 2026-10-23). CBE primary for the 2028 target is `no data`. |
| Equity risk premium, Egypt (total) | **13.94** | % | Jan 5, 2026 | https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html (2026-10-23) | Moody's Caa1. |
| Country risk premium, Egypt | **9.71** | % | Jan 5, 2026 | same | Mature-market ERP implied **4.23%** (Aaa rows: CRP 0, ERP 4.23). |
| Default spread, Egypt | **6.37** | % (rating-based, adjusted) | Jan 5, 2026 | same | Sovereign CDS 3.41%. CDS-based ERP 9.41%. |
| Corporate tax rate, Egypt | 22.50 | % | Jan 5, 2026 | same | — |
| Long-run inflation (terminal anchor) | 2029 **6.5**, 2030 **5.8**, 2031 **5.4** (2026 13.3, 2027 14.8, 2028 8.9) | % avg CPI change | IMF WEO current DataMapper vintage | https://www.imf.org/external/datamapper/api/v1/PCPIPCH/EGY (2026-10-23) | **The WEO edition (Apr vs Oct 2026) is not stated in the API response** (`no data`). Record `as_of` = fetch date and the API URL. |
| Long-run real growth (terminal anchor) | 2029 5.5, 2030 **4.8**, 2031 **4.8** | % real GDP | same vintage | https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH/EGY (2026-10-23) | Egypt WEO data is on a fiscal-year basis (Jul–Jun). |
| `target_pe` / `target_pb` / `target_ps` per EGX sector | **`no data`** | — | — | — | See below. |

### What I tried for EGX sector multiples, so the next researcher does not repeat it

- **EGX MarketWatchSectors (S4):** value, volume and market cap only, no P/E.
- **EGX CompanyDetails (S3):** has a **per-company P/E and dividend yield published by EGX** (CIB P/E 5.34 on 21/10/2026). A sector median would need ~230 page reads. Not done.
- **Damodaran PE by sector** (https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/pedata.html, fetched 2026-10-24): US-only, Jan 2026. The datasets page (https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datacurrent.html, fetched 2026-10-24) offers PE and EV/EBITDA for Emerging Markets (`peemerg.xls`, `vebitdaemerg.xls`; last full update Jan 9, 2026), but no Egypt or MENA cut. It is usable only as an "emerging-markets industry" proxy, which is a pm call. Not downloaded.
- **Web search** for an EGX monthly report with sector P/E: nothing found.
  - CEIC shows an EGX average dividend yield of 7.8% (Jan 2026) only: https://www.ceicdata.com/en/egypt/the-egyptian-exchange-dividend-yield (search result, 2026-10-23).
  - The phase-3 research already logged EFG/CI broker multiples as login-gated.

**Option for pm:** derive target multiples in code as a **peer median of our own computed P/E / P/B per EGX sector**. That is a deterministic methodology, not a sourced assumption, so it would need its own methodology version and is not a `valuation_assumptions` row. Otherwise the relative leg stays INSUFFICIENT_DATA.

### How to store the values (per design §1.6, `valuation_assumptions`)

- One row per `(methodology_version="1.0", key, scope="market", as_of)`.
  - `value` is a fraction, e.g. 0.25912.
  - `source_url` is the exact page above.
  - `source_title` is, e.g., "CBE EGP T-Bill auction results, 364-day, 22/10/2026".
  - `as_of` is the **publication/auction date**, not the fetch date (fetch date when no publication date exists, e.g. the IMF API).
  - `note` carries the tenor, "weighted avg accepted yield", and the fetch date.
- **Schema gap:** §1.6 keys are only `discount_rate`, `terminal_growth_rate`, `stable_growth` and `target_*`. The raw inputs (Rf, ERP, CRP, default spread, inflation anchor) have no key.
  - Either the analyst computes `discount_rate` from them with the arithmetic written in `note`,
  - or the architect adds input keys (`risk_free_rate`, `equity_risk_premium`, `country_risk_premium`, `default_spread`, `long_run_inflation`, `long_run_real_growth`) so that the derivation runs in code (AGENTS rule 1). **Recommended: the input keys.**
- **Staleness:** T-bill yields move weekly, Damodaran updates annually (January), and IMF WEO twice a year (Apr/Oct). The router should re-source on those cadences.

---

## Gaps (`no data`)

- EGX sector-index page `type=2` content and any other `type=` values (page hung).
- Effective dates of the EGX listing and sector-index snapshots (not shown on the pages).
- Sector for AREH (no S1 match).
- EGP yield beyond 3 years from current CBE auctions.
- The IMF WEO edition behind the DataMapper API.
- A CBE primary source for the 5% / Q4-2028 target.
- Any free EGX sector P/E, P/B or EV/EBITDA median.
- Betas for EGX names (not searched; out of brief scope).

NEXT: pm
