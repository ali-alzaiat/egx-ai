# App-wide UX audit — EGX AI (live)

**Method:** Live walkthrough with Playwright MCP against `http://localhost:5173` (API `localhost:8000`), 2026-10-09. Routes walked: `/`, `/companies` (search, sector filter, back-navigation), `/companies/COMI` + all six sub-routes (financials, metrics, technical, ai, screening, valuation), `/companies/SWDY/financials`, `/companies/ACAP` (no-data company), `/companies/ZZZZ` (invalid ticker), `/rankings` (filter, re-run scoring, show excluded). Evidence is accessibility-snapshot YAML, network log and console log under `.playwright-mcp/`.

**Limitations:** This model cannot read images, so screenshots were not reviewable — no findings on pure visual styling (spacing, contrast, color). Findings below are all grounded in the accessibility tree, network requests, console output, or source greps. No console JS errors occurred; the only console errors are expected 404s (cited where relevant).

---

## P0 — blocks the core task

### F1. Shariah Screening and Valuation pages tell the user to call a REST API themselves
- **Screen:** `/companies/COMI/screening` and `/companies/COMI/valuation`.
- **Action:** User opens the screening page expecting to screen the company (the app is titled "Stock Analysis & **Shariah Screening**").
- **Friction:** The page ends in API documentation. There is no "Run screening" button; the only actionable element is a raw endpoint with a UUID.
- **Who it hurts:** Every non-developer user — the entire target audience of a research tool.
- **Evidence** (snapshot `page-2026-10-09T13-01-16-888Z.yml`, lines 44–45):
  ```
  - text: "To screen this company, use the API endpoint:"
  - code [ref=f6e41]: POST /api/screening/companies/b56a8e69-f490-474c-913b-92782a5ea401/screen
  ```
  Same pattern on valuation (`page-2026-10-09T13-01-44-540Z.yml`, lines 34–35):
  ```
  - text: "To calculate valuations, use the API endpoint:"
  - code [ref=f7e29]: POST /api/valuation/companies/b56a8e69-f490-474c-913b-92782a5ea401/calculate
  ```

### F2. Screening and Valuation are orphan routes — no link to them anywhere in the UI
- **Screen:** Company overview `/companies/COMI` and the whole app.
- **Action:** User tries to find the screening or valuation feature by clicking.
- **Friction:** The overview tab row offers only `Financial Data / Metrics / Technical / AI Insights`. Nothing links to `/screening` or `/valuation`; they exist only as typed URLs. Two headline features are undiscoverable.
- **Who it hurts:** First-time users and returning users who don't know the URL; anyone evaluating the product's main claim.
- **Evidence:** overview tab row (`page-2026-10-09T12-57-24-835Z.yml`, lines 18–25) shows exactly 4 links. Source grep of `frontend/src` for `/screening|/valuation` returns only the route definitions in `App.tsx:32,35` and the two page files' own `<code>` strings — zero `<Link>` targets.

### F3. Sub-tab pages have no tab bar and no back affordance — one-way trips
- **Screen:** `/companies/COMI/financials` (same for metrics, technical, ai, screening, valuation).
- **Action:** User clicks "Financial Data" from the overview, then wants to switch to "Metrics".
- **Friction:** The tab row present on the overview is absent on every sub-page; the heading is not a link; there is no breadcrumb. The only ways back are browser-back or re-searching the company from the list. Six sibling views cannot be traversed laterally.
- **Who it hurts:** Analysts comparing views of one company — the core research loop.
- **Evidence:** `page-2026-10-09T12-57-56-604Z.yml` / `page-2026-10-09T12-58-17-463Z.yml` contain only `heading "Financial Data - COMI"` and section headings. A `playwright_browser_find` for `/(Metrics|Technical|AI Insights|Overview)/` on that page returned `No matches found`.

### F4. Technical tab demands the user paste prices the app already has
- **Screen:** `/companies/COMI/technical`.
- **Action:** User wants RSI/MACD for COMI.
- **Friction:** The page is a manual form — "Enter comma-separated historical prices and volumes" — with `Calculate Indicators` **disabled** until the user types data. The app fetched COMI's full price history on the overview in the same session (`GET /api/companies/{id}/prices?start_date=2025-10-09&page_size=365 => [200]`), and `GET /api/technical/companies/{id}` returned `[]`. The user is asked to hand-transcribe hundreds of values the server holds.
- **Who it hurts:** Any user wanting technical analysis; the task is effectively impossible.
- **Evidence** (`page-2026-10-09T12-59-20-171Z.yml`, lines 18, 21, 49):
  ```
  - paragraph [ref=f4e17]: Enter comma-separated historical prices and volumes to calculate technical indicators.
  - textbox "e.g. 10.5, 11.2, 10.8, 11.5, 12.0" [ref=f4e20]
  - button "Calculate Indicators" [disabled] [ref=f4e41]
  ```

### F5. Dashboard tells users the app is empty while the app holds 229 companies
- **Screen:** `/` (Dashboard) — the first screen every user sees.
- **Action:** User lands and reads system status.
- **Friction:** All three stat cards show `--` with "Phase 2/4/5 will populate" and the table says "No data yet. Ingestion layer coming in Phase 2." — yet `/companies` lists 229 companies and `/rankings` scores 199. The dashboard is hardcoded (`frontend/src/pages/Dashboard.tsx:29,58` — no fetch; network shows only `GET /api/health`). A first-time user concludes the product doesn't work and leaves; a returning user distrusts every other number.
- **Who it hurts:** First-time visitors most — it is the landing screen.
- **Evidence** (`page-2026-10-09T12-56-07-001Z.yml`, lines 23–32, 42):
  ```
  - generic [ref=e21]: EGX Companies
  - generic [ref=e22]: "--"
  - generic [ref=e23]: Phase 2 will populate
  ...
  - cell "No data yet. Ingestion layer coming in Phase 2." [ref=e42]
  ```
  vs `page-2026-10-09T12-56-37-648Z.yml` line 223: `Page 1 of 12 (229 companies)`.

---

## P1 — repeated friction and misleading states

### F6. Metrics tab shows a developer instruction instead of an action
- **Screen:** `/companies/COMI/metrics`.
- **Action:** User opens Metrics expecting ratios.
- **Friction:** The whole page is one line of API instruction with no button, no explanation of what a metric is, and no path forward. Dead end.
- **Who it hurts:** Non-developer users; also sets a bad expectation for every empty tab.
- **Evidence** (`page-2026-10-09T12-58-57-532Z.yml`, line 15):
  ```
  - generic [ref=f3e14]: No metrics calculated yet. Use the calculate endpoint to generate metrics.
  ```
  Same string in source: `frontend/src/pages/FinancialMetrics.tsx:80`.

### F7. AI Insights: internal jargon, a native browser alert, and an unavoidable failure
- **Screen:** `/companies/COMI/ai`.
- **Action:** (a) click "Index Company Data"; (b) type a query and click "Run Analysis".
- **Friction:** (a) The heading is `Index Data for RAG` — retrieval-pipeline jargon exposed as UI — and the result arrives as a **blocking native `alert()`**: `Indexed 0 chunks for COMI`, which neither says success nor failure nor what a "chunk" is. (b) Analysis then always lands on `Insufficient data available for analysis.` plus `Please ensure financial statements and metrics have been ingested` — instructions addressed to an ingestion engineer, not the analyst clicking the button. No link to what data does exist (prices do).
- **Who it hurts:** Any user trying the AI feature — the tab's only two actions both end in confusion or failure.
- **Evidence:** modal state after click: `["alert" dialog with message "Indexed 0 chunks for COMI"]`; result (`page-2026-10-09T13-00-43-457Z.yml`, lines 18, 37, 41):
  ```
  - heading "Index Data for RAG" [level=3]
  - generic [ref=f5e31]: Insufficient data available for analysis.
  - generic [ref=f5e35]: No relevant financial data was found for this company. Please ensure financial statements and metrics have been ingested.
  ```
  Network: `POST /api/ai/companies/.../index => [200]`, `POST .../analyze => [200]` — both "succeeded" from the server's view.

### F8. Financials is four stacked empty strings with no reason or next step (app-wide)
- **Screen:** `/companies/COMI/financials`, `/companies/SWDY/financials`.
- **Action:** User opens the flagship financial-statements view for two major issuers.
- **Friction:** Four bare messages ("No financial periods available", "No income statement data available", "No balance sheet data available", "No cash flow data available") — no explanation of why, no source status, no "what to do", no distinction between "not ingested yet" and "doesn't exist". Identical for COMI and SWDY, so the tab reads as broken to every user who tries it. Contrast with `/rankings`, which does this well ("30 excluded: 30 lack price history from the configured source") — the pattern exists, it just isn't used here.
- **Who it hurts:** Users doing fundamental analysis — the tab's entire audience.
- **Evidence** (`page-2026-10-09T13-08-08-301Z.yml`, lines 17–26): the four messages above, after `GET /api/financial/periods/... => [200]` and three `financial/facts` calls all `[200]`.

### F9. Screener: changing a filter claims "Scoring the market…" and erases the results
- **Screen:** `/rankings` (nav "Screener", H1 "Market Rankings").
- **Action:** User selects Tier = STRONGEST.
- **Friction:** During the fetch the entire results region — table, coverage block, status line — is replaced by `Scoring the market…`. Nothing is being scored; a GET was in flight (`GET /api/signals?limit=50&tier=STRONGEST => [200]`). The copy is wrong and the wipe causes a visible layout collapse/reflow on every filter keystroke-change.
- **Who it hurts:** Users refining the ranking — the main interaction on the screen.
- **Evidence** (`page-2026-10-09T13-04-32-281Z.yml`, line 41; table and coverage block absent):
  ```
  - generic [ref=f8e733]: Scoring the market…
  ```

### F10. "Re-run scoring" gives no in-flight state and no confirmation
- **Screen:** `/rankings`.
- **Action:** User clicks `Re-run scoring`.
- **Friction:** The button never disables (snapshot taken immediately after click still shows it clickable → double-fire possible), and afterwards nothing confirms the run happened: no toast, no timestamp change (still `as of 2026-09-24`), table visually identical. The network proves it worked (`POST /api/signals/run => [200]`, then three GETs) — the user sees none of that. Users will click repeatedly, unsure.
- **Who it hurts:** Users refreshing scores after new price data.
- **Evidence:** `page-2026-10-09T13-03-09-014Z.yml` line 17: `button "Re-run scoring" [ref=f8e16] [cursor=pointer]` (no `[disabled]`) right after the click; network log entries 37–40.

### F11. Company overview: a 365-row raw price dump replaces analysis
- **Screen:** `/companies/COMI` (overview/landing for a company).
- **Action:** User opens a company to get oriented.
- **Friction:** Below the stats sits an unbounded `Historical Prices` table — the request is `page_size=365`, the snapshot exceeded 50 KB / 1,166 lines inside one table, with prices printed to four decimals (`128.2000`) while volume is human-formatted (`4,385,761`), and non-trading days rendered as flat rows with `Volume 0`. There is no chart, no date range, no pagination, no sort. Key content (the tabs) is fine above it, but the page reads as a database dump and any scroll-to-bottom task is over.
- **Who it hurts:** Users trying to read a price history quickly; anyone scanning for recent context.
- **Evidence:** network `GET /api/companies/{id}/prices?start_date=2025-10-09&page_size=365 => [200]`; snapshot rows e.g. `- cell "128.2000" [ref=f1e308]`, `- cell "0" [ref=f1e449]`; Read output: `Output capped at 50 KB. Showing lines 1-1166`.

### F12. Companies list: filters and search silently drop most of the universe
- **Screen:** `/companies`.
- **Action:** (a) scan the table; (b) pick a sector in the filter.
- **Friction:** 19 of the first 20 rows show `Sector "--"` and `Industry "--"`, so selecting **Financials** returns just 7 of 229 companies (ADIB, COMI, EFIH, FWRY, HDBK, HRHO, PHAR) with no message that the other 222 were excluded for having no sector recorded. Compounding it, two of the six columns carry zero information in practice: `Currency` is `EGP` on every row and `Status` is `ACTIVE` on every row — columns that look like data but never discriminate. The filter is also the only indication of data completeness anywhere on the screen.
- **Who it hurts:** Users filtering/browsing the universe; they get wrong-sized result sets and silently miss companies.
- **Evidence:** `page-2026-10-09T12-56-37-648Z.yml` lines 46–47 (`cell "--"`, `cell "--"`), lines 49/56 (`ACTIVE`, `EGP` throughout); filtered snapshot `page-2026-10-09T13-09-44-624Z.yml` contains exactly 7 data rows, no pagination footer.

### F13. Company list state is destroyed by Back
- **Screen:** `/companies`.
- **Action:** User filters to Financials, opens COMI, presses Back to continue down the filtered list.
- **Friction:** The list resets to `All Sectors` / `Page 1 of 12 (229 companies)` — filter and any search text are gone (state lives in component memory, not the URL). The user must rebuild the result set after every company they inspect.
- **Who it hurts:** Analysts comparing several companies in one sector — the most common list workflow.
- **Evidence:** before navigation, `page-2026-10-09T13-09-44-624Z.yml` line 25: `option "Financials" [selected]`; after Back, `page-2026-10-09T13-10-31-565Z.yml` lines 19, 24, 223: `option "All Sectors" [selected]` … `Page 1 of 12 (229 companies)`.

### F14. Three names for one screen, and "Screener" doesn't screen
- **Screen:** nav → `/rankings`.
- **Action:** User looks for Shariah screening and clicks the nav item literally labelled **Screener**.
- **Friction:** The nav says `Screener`, the URL is `/rankings`, the page heading says `Market Rankings` — and it's a price-momentum ranking, not Shariah screening (which is the orphaned route in F1/F2). With only 3 nav links total, this one mislabel does most of the app's discovery damage: the feature the product is named after is neither where its name suggests nor reachable from it.
- **Who it hurts:** First-time users orienting from the nav; anyone hunting for the screening feature.
- **Evidence:** every snapshot, e.g. `page-2026-10-09T13-02-22-700Z.yml`: `link "Screener" … /url: /rankings` and `heading "Market Rankings" [level=1]`; document title `EGX AI - Stock Analysis & Shariah Screening`.

---

## P2 — dead ends, edge states, copy

### F15. Invalid ticker → four words and a dead end (404 fetched twice)
- **Screen:** `/companies/ZZZZ`.
- **Action:** User mistypes a ticker or follows a bad link.
- **Friction:** Main area is only `Company not found` — no echo of what was typed, no "did you mean", no search box, no link back to the list (the sidebar nav is the sole recovery). Console also logs the 404 **twice** (`255ms` and `1311ms`), a duplicate request on mount.
- **Who it hurts:** Anyone on a shared/bookmarked link or typing tickers manually.
- **Evidence:** `page-2026-10-09T13-06-16-227Z.yml` line 12: `- generic [ref=f9e11]: Company not found`; `console-2026-10-09T13-06-02-728Z.log` lines 2–3: `[ERROR] … 404 (Not Found) @ http://localhost:5173/api/companies/ticker/ZZZZ` (twice).

### F16. "Data quality" card occupies the top of every overview while always showing "–"
- **Screen:** `/companies/COMI`, `/companies/ACAP`.
- **Action:** User opens a company and reads the first card.
- **Friction:** Both companies tested show `–` + "No data-quality assessment has been run for this company yet." — a 0–100 scale, band legend and methodology line that never display a value. Two screens' worth of prime space explaining a metric that isn't there; users learn to ignore the most prominent card on the page.
- **Who it hurts:** Every company-page visitor; worse, it crowds out the price/stat content below.
- **Evidence:** `page-2026-10-09T12-57-24-835Z.yml` lines 30–34 and `page-2026-10-09T13-06-53-268Z.yml` lines 28–32 (`generic [aria-hidden]: –`).

### F17. No-data company: stats vanish silently, empty state gives no "why", 404 in console
- **Screen:** `/companies/ACAP` (real company, no prices).
- **Action:** User opens a listed company with no price feed.
- **Friction:** The OHLC/price stat cards that COMI shows are simply absent (not "no data"), `Historical Prices` says only `No price data available` — whereas the screener has the good version of this copy ("no price data from the configured source") and doesn't share it here. Meanwhile console logs `404 …/prices/latest` twice, which will mask real errors for developers.
- **Who it hurts:** Users of the 30 unscorable companies; they can't tell whether the app is broken or the data is missing.
- **Evidence:** `page-2026-10-09T13-06-53-268Z.yml` line 54: `- generic [ref=f10e50]: No price data available` (no stat block above it); `console-2026-10-09T13-06-46-945Z.log` lines 2–3 (404 ×2).

---

**Summary for prioritization:** F1–F5 mean the four advertised capabilities (screening, valuation, technical analysis, financial statements) each either cannot be started from the UI or actively misinform the user; F6–F14 are the friction that makes daily use tiring; F15–F17 are the edge states. Any redesign spec should treat F1+F2 (unreachable features), F3 (no lateral nav), F5 (lying dashboard) and F9/F13 (state destroyed by interaction) as the spine.

*Filed by the router from ux-expert Salma's inline result, 2026-10-09. Live walkthrough via Playwright MCP.*
