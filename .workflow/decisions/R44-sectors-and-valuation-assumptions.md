# R44 Decision: sector loading (D-9), valuation assumptions v1 (D-8), DPS/purification (D-6)

**From:** Sherif (pm) · 2026-10-24 · for staff-backend (then analyst gate at QA)
**Inputs:** `.workflow/research/r43-sector-and-valuation-sources.md` (S1-S4, Task B table), `.workflow/design/r43-computed-company-data.md` §6, `backend/app/screening/rules.py::screen_industry`, `purification.py::ISLAMIC_BANK_TICKERS`.

## (a) D-9 Sector loading and Shariah category

**Two separate things.** EGX sector = peer/valuation classification (`companies.sector`, `egx_sector_id`). Shariah business activity = a per-company tag. `companies.industry` stays null and the raw sector name is never passed to `screen_industry` (substring match: "Food, Beverages and Tobacco" would fail all 31 names; "Banks" would pass conventional banks).

**Sources, priority order (no scripting of S1/S2, no extra page fetches):**
1. S2 sector-index pages joined on Reuters code (181) + alias ALRA to AIFI (182). `match_basis="sector_index_reuters"` / `"alias"`.
2. S1 "All Listed Stocks" by human-reviewed name match for the other 48. `match_basis="name_review"`. No fuzzy auto-matching.
3. AREH and the 4 junk `RT9...` rows: no sector (UNKNOWN). Junk rows are excluded from the snapshot and flagged to QA.

Snapshot module `app/industry/egx_sectors.py` (pattern of `egx33.py`: source URLs, `FETCHED_ON=2026-10-23`, literal rows, idempotent CLI). It also writes `companies.isin`. Sector names are normalised (`" ,"` to `","`).

**Shariah activity tag.** New versioned snapshot `app/screening/activity_tags.py` (`tag_set_version="1.0"`, tied to Shariah methodology v2; each row has `source`/`basis`). `screen_industry` receives the tag only: a prohibited tag value (existing `ProhibitedIndustry` strings), or `permitted`, or null for UNKNOWN. Tags map to sectors as follows:

| EGX sector | Tag rule |
|---|---|
| Banks (14) | `conventional_banking` (FAIL) except the Islamic carve-out FAIT, FAITA, ADIB, SAUD, which get `islamic_bank` (PASS, existing carve-out; add FAITA to `ISLAMIC_BANK_TICKERS` if it is in the DB) |
| Basic Resources, Industrial Goods, Real Estate, Contracting, Building Materials, Textile & Durables, Energy & Support, Trade & Distributors, Shipping, Education, Utilities, Paper & Packaging, Health Care & Pharma | `permitted`, basis `sector_default`, overridable per company |
| **Food, Beverages and Tobacco (31)**, Travel & Leisure (14), IT/Media/Communication (8), Non-bank financial (42) | **No sector default.** Each company is reviewed and listed in the override list. Unreviewed means UNKNOWN. Never a sector-wide fail |

- Override list: EAST gets `tobacco`. Insurers (name states insurance and is not takaful) get `conventional_insurance` by name review. Any `permitted` in the four review sectors needs a cited activity source (EGX CompanyDetails or filing); a name alone gives UNKNOWN. A FAIL tag from a name alone is limited to the insurer case.
- Leasing, factoring, microfinance, mortgage finance, holdings: UNKNOWN. A "conventional financing" category is a methodology change and is out of v1 (analyst to decide later; needs a version bump).
- Stays UNKNOWN: AREH, unreviewed review-sector names, financing firms. UNKNOWN keeps `industry_screen` INSUFFICIENT_DATA, so no COMPLIANT verdict.

## (b) D-8 Valuation assumptions v1

`methodology_version="1.0"` (matches valuation 1.0 per D-7, no bump). EGP nominal throughout: nominal EGP cash flows, EGP nominal rate. Input keys added to `valuation_assumptions` (researcher's recommendation); `discount_rate` and `terminal_growth_rate` are **computed in code**, not stored by hand.

| Key | Value | Source / as_of |
|---|---|---|
| `risk_free_rate` | 0.24128 (3y fixed T-bond, weighted avg accepted yield) | CBE, auction 19/10/2026. Longest sourced EGP tenor |
| `equity_risk_premium` | 0.0423 (mature-market ERP) | Damodaran ctryprem, 2026-01-05 |
| `long_run_inflation` | 0.054 (IMF WEO 2031) | IMF DataMapper API; as_of = fetch date, edition `no data` |

- `discount_rate` = `risk_free_rate + equity_risk_premium` = 28.36% (market beta 1 by construction; no sourced EGX betas). **No CRP and no default spread added**: the EGP yield already carries sovereign risk, adding CRP double counts.
- `terminal_growth_rate` = `stable_growth` = `long_run_inflation` (zero real growth, conservative). Real growth 4.8% is not used in v1. Cost: lower fair values, fewer "potentially undervalued" outputs.
- Not stored (cut): 1y T-bill, CRP, default spread, policy rate, inflation outturn. They remain in the research file.
- Staleness: yield rows older than 120 days, ERP/IMF rows older than 400 days give INSUFFICIENT_DATA with reason "stale assumption".
- **Stay INSUFFICIENT_DATA:** `target_pe`/`target_pb`/`target_ps` (relative legs; no sourced Egypt multiples). Damodaran emerging-markets multiples are rejected (not Egypt, USD-era, different basis). Peer-median of our own computed multiples is deferred to a separate methodology version, not v1.
- DCF and DDM can run; relative legs report the missing assumption by name. Models already excluded by profile (e.g. banks on FCF) stay excluded. Outputs say "under these assumptions".

## (c) D-6: ACCEPT, with conditions

- DPS = `abs(dividends_paid) / shares_outstanding` is accepted, labelled **"cash dividends paid per share (derived)"**, never "declared DPS". It uses period-end `shares_outstanding` from the same statement set. Missing shares or dividends gives INSUFFICIENT_DATA (never 0, no fallback to weighted-average shares). Bonus-share/split years are flagged as "share count may not be comparable".
- Interest income alone for purification is accepted as a **partial lower-bound estimate** (status `ESTIMATE_PARTIAL`, shown as "at least"). The other 13 lines of the Islamicly checklist are listed as not covered. It is never presented as the final purification amount. Missing interest income gives INSUFFICIENT_DATA, not 0. Islamic-bank carve-out branch unchanged.
- Analyst confirms at QA. If rejected, fall back as per design D-6.

## Acceptance criteria
1. Every sector-assigned company has a `match_basis`; no name-only match without a review record; 229/230 real companies assigned (AREH null); 0 duplicate `egx_sectors` rows; companies.isin filled for matched rows.
2. Unit tests: "Food, Beverages and Tobacco" company without an override is UNKNOWN (not FAIL, not PASS); EAST fails; CIB fails; FAIT/ADIB/SAUD pass by carve-out; an insurer fails; a sector-default company passes with basis shown.
3. Raw EGX sector names never reach `screen_industry` (test).
4. `valuation_assumptions` holds exactly the 3 rows above with source_url/title/as_of; `discount_rate` = 0.28358 and `terminal_growth_rate` = 0.054 from code, tested incl. missing/stale row to INSUFFICIENT_DATA; relative legs INSUFFICIENT with named reason.
5. DPS/purification tests for zero, negative, missing, bonus-share flag; partial status never rendered as final.
6. Coverage report (AC-9) states fair-value coverage by leg and Shariah distribution including UNKNOWN count.

NEXT: staff-backend
