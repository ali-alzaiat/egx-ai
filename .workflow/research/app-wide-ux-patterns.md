# App-wide UX patterns — retail stock / investment-research apps

**Researcher:** Nadia · **Compiled:** 2026-10-09 · **All URLs fetched:** 2026-10-09 unless noted
**Method:** live page fetches for primary sources (marked ✅); search-result snippets with URL for the rest (marked 🔍); third-party reviews/case studies marked ⚠️ (secondary — verify before quoting as fact). Anything I could not verify is `no data`.

---

## 0. Sources at a glance

| App | Primary sources fetched ✅ | Secondary 🔍/⚠️ |
|---|---|---|
| Simply Wall St | — | Product pages, product-lead case study |
| TradingView | ✅ Official screener walkthrough | 🔍 2026 screener guides |
| Koyfin | — | 🔍 Official release notes, reviews |
| Finviz | — (theme page snippet only) | ⚠️ Redesign portfolio concepts (not shipped product) |
| Yahoo Finance | — | 🔍 Official 2023 redesign press release, NN/g analysis, app reviews |
| Stock Analysis | ✅ Screener tutorial + Data Sources page | 🔍 Changelog, reviews |
| Zoya | ✅ Help-center methodology article | 🔍 Public GraphQL schema, blog |
| Musaffa | — | 🔍 Methodology page, reviews |
| Islamicly | — | 🔍 Screening-process page, app-store reviews |
| States/colour/typography | — (design-system articles) | 🔍 NN/g, govt design system, Bloomberg UX |

---

## 1. Information architecture & navigation

### 1.1 What goes where

- **Global top nav = product areas, not data.** Stock Analysis's nav groups *destinations*: Watchlist, Stocks (→ Screener, Exchanges, By Country, Comparison, Earnings Calendar, By Industry, Lists), IPOs, ETFs, Analysts, News, Trending, Chart, Market Movers — with the screener nested one level under its asset class. ✅ https://stockanalysis.com/tutorials/screener/ (fetched 2026-10-09)
- **TradingView puts every screener behind one entry point:** `Products → Screeners → {Stock, ETF, Bond, Crypto, CEX, DEX, Pine}`; each screener also opens from the right-hand toolbar on any page. ✅ https://www.tradingview.com/support/solutions/43000718885-tradingview-screeners-walkthrough/ (fetched 2026-10-09)
- **Koyfin restructured its left nav around user-created artefacts:** a new "My Koyfin" section collects everything the user creates (watchlists, custom dashboards, templates), "Home" is the start page with favourites pinned on top, sections are collapsible and reorderable, and any feature can be starred into a favourites list. ✅-as-snippet 🔍 https://www.koyfin.com/help/release-notes/customizable-left-navigation/ (dated 2026-05-19; retrieved via search 2026-10-09)
- **A screener is framed as "presets + filters", not a blank query builder.** Stock Analysis ships a "Popular Screens" dropdown of preset screens you can start from; TradingView's screens menu offers "Open screen → popular preset screens tailored to related asset groups". ✅ Stock Analysis tutorial + ✅ TradingView walkthrough (both fetched 2026-10-09)
- **Lists feed into the screener rather than dead-ending:** Stock Analysis's market-movers pages have an "Open in Screener" action that carries the list's filters and sort into the full screener. ✅ https://stockanalysis.com/tutorials/screener/ (fetched 2026-10-09)

### 1.2 Tabs: use them, don't stack them

- **NN/g rule for company pages:** in-page tabs are for chunking one page's content and progressively disclosing it; navigation tabs that take the user elsewhere should not share the same control. High-use content should be first and default-selected. Mixed/stacked tab lists disorient users. 🔍 https://www.nngroup.com/articles/tabs-used-right/ (published 2024-08-02; retrieved 2026-10-09)
- **Yahoo Finance is the cautionary tale:** NN/g explicitly cited Yahoo Finance's "3 layers of navigation tabs" as exposing several tiers of IA at once. 🔍 same URL (retrieved 2026-10-09)
- **Stock Analysis removed chart tabs from stock pages** in favour of one "Full Chart" button to a dedicated full-screen chart page — fewer, deeper destinations instead of many shallow ones. 🔍 https://stockanalysis.com/changelog/ (retrieved 2026-10-09)

**Copyable rule for a small React app:** 4–6 global destinations max (Home / Search / Screener / Watchlist / Settings); company page = hero + one row of in-page tabs (Overview, Financials, Valuation, Shariah, News) with Overview default; never put a second tab strip inside a tab panel.

---

## 2. Dashboard & company-page layout

### 2.1 Dashboard = feed of updates, not a wall of numbers

- **Simply Wall St's dashboard is an event feed tied to the user's holdings** (earnings reported, key personnel change, insider buy/sell, analyst estimate change, valuation change, risk change), built because dropping users "into a complex app with minimal guidance" meant only ~5% of visitors became active users; the feed became "the largest single predictor of paid user retention". ⚠️ Author is Simply Wall St's Content Product Lead — first-party account but a case study, not a controlled study. 🔍 https://infinitenuance.com/2024/11/27/case-study-simply-wall-st-dashboard-feed/ (published 2024-11-27; retrieved 2026-10-09)
- **Dashboard widgets are aggregations you read before you click:** SWS shows portfolio tables replaced by a performance chart with time-horizon switches, portfolios as tiles showing snowflake/returns/risks without opening them, and a widget surfacing "new companies added to your saved screeners". 🔍 https://support.simplywall.st/hc/en-us/articles/7894830045199-What-s-New (retrieved 2026-10-09)
- **Koyfin's dashboard = drag-and-drop linked widgets** (watchlist + chart + benchmark + news) that can update together when a symbol is selected; layouts save across sessions. ⚠️ Reviews. 🔍 https://tradingtoolshub.com/blog/koyfin-pro-setup-guide-2026/ (dated 2026-06-11) and https://simplemarkets.io/blog/post/koyfin-review (dated 2026-05-31), both retrieved 2026-10-09
- **Crowding is the named failure mode:** repeated Koyfin review complaints — "the interface feels crowded when too many widgets are loaded", "dashboard setup can feel overwhelming at first". ⚠️ 🔍 https://www.techjockey.com/us/reviews/koyfin (dated 2025-03-28; retrieved 2026-10-09)

### 2.2 Company / quote page

- **Simply Wall St's company report is a fixed six-section visual report:** Past Performance · Risks & Rewards · Valuation & Comparison · Growth Forecast · Financial Health · Management Profile (plus dividend, insider transactions, growth-forecast panels). The pitch is explicitly "condense thousands of data points into one visual report". 🔍 https://simplywall.st/features/stock-research (retrieved 2026-10-09)
- **Stock Analysis quote page pattern:** price (real-time with pre/after-hours) → headline valuation metrics → analyst targets → peer comparison → quick links into deeper Financials / Statistics / Dividend pages; overview shows revenue, net-income and EPS growth. ⚠️ Review. 🔍 https://www.financialtechwiz.com/post/stockanalysis-review/ (dated 2025-12-23; retrieved 2026-10-09)
- **Yahoo's 2023 redesign brief:** "better organized our quote pages so you can easily find the financial data you need", plus compare mode for side-by-side stocks. 🔍 Official: https://www.yahooinc.com/press/yahoo-finance-debuts-new-design-and-features-to-empower-everyday-investors (dated 2023-11-07) and https://finance.yahoo.com/news/yahoo-finance-site-update-delivers-deeper-insights-richer-content-110006796.html (dated 2023-11-07), retrieved 2026-10-09
- **A one-line hierarchy principle worth stealing:** visual and logical hierarchy must agree, or the dashboard reads as clutter; group similar info together, label plainly, avoid abbreviations in labels. 🔍 GoodData, https://www.gooddata.ai/blog/six-principles-of-dashboard-information-architecture/ (dated 2023-01-17; retrieved 2026-10-09)

**Copyable rule:** hero (price + change + as-of + verdict badge) → key-stats strip (6–8 metrics) → tabbed detail; dashboard = 1 chart + 1 holdings table + 1 events feed, nothing more on v1.

---

## 3. Data-heavy screeners & tables

### 3.1 Anatomy of a good screener (TradingView, verified)

TradingView's official walkthrough defines exactly five components — a clean blueprint for a small app:

1. **Screener switch menu** (top-left): swap asset universe.
2. **Screens menu:** save / copy / rename / export CSV / create new / recently used (5) / open popular presets.
3. **Top filter panel:** apply a popular screen, add filter, add condition, edit ("Manual setup" for custom thresholds), reset/remove — and it can be **collapsed** to reclaim workspace.
4. **Table:** ready-made column sets or custom; add columns with `+`; sort by header click; right-click context menu to customize/move/remove columns; a **chart-view toggle** turns rows into a grid of mini-charts.
5. **Settings:** symbol descriptions on/off, **auto-refresh interval (10s / 1min / never)**, display currency.

✅ https://www.tradingview.com/support/solutions/43000718885-tradingview-screeners-walkthrough/ (fetched 2026-10-09)

### 3.2 Density, sorting, filtering, columns (Stock Analysis, verified)

- Filters added by **search-first** ("just start typing and the screener instantly suggests indicators") or a "+ Add Filters" button showing everything with checkboxes; numeric filters offer **Over / Under / Between / Exactly / Not Zero** operators and accept `K/M/B` suffixes; presets per filter; select, multi-select and date filter types. ✅ https://stockanalysis.com/tutorials/screener/ (fetched 2026-10-09)
- **7 saved "views"** (General, Filters, Performance, Analysts, Dividends, Financials, Valuation); per-view column choice persisted in the browser; sortable columns (click cycles desc → asc → none); rows-per-page with "Show All"; in-table search; pagination. ✅ same URL
- **Definitions at the point of confusion:** hover the "i" icon next to a filter name or table column header to see the indicator's definition and formula. ✅ same URL (also confirmed in changelog: "an 'i' icon next to the column headers … to easily find the indicator definition and formula"). 🔍 https://stockanalysis.com/changelog/ (retrieved 2026-10-09)
- **Sticky headers matter on tall tables:** screener and financials pages use a sticky column header (and sticky leftmost column) so you know which column you're reading when scrolling. 🔍 https://stockanalysis.com/changelog/ (retrieved 2026-10-09)
- Scale claim for context: 200+ indicators in the tutorial vs "299"/"317" filters in reviews — **the exact count differs by source; treat as "~300, and verify before quoting a number."** ✅ tutorial vs ⚠️ https://www.financialtechwiz.com/post/stockanalysis-review/ and https://tickernerd.com/resources/stockanalysis-review/ (retrieved 2026-10-09)

### 3.3 Mobile

- **Consensus: dense tables don't port.** "The mobile version feels cramped… I use it for checking alerts and quick reviews, not serious screening" (TradingView, third-party). ⚠️ 🔍 https://tokentrendtracker.com/tradingview-screener-latest-market-tools-update/ (dated 2025-12-05; retrieved 2026-10-09)
- **What Stock Analysis shipped for mobile instead:** compact view for small screens, sticky first column on financials, full-screen site search overlay instead of a narrow dropdown, cards instead of tables for analyst pages on mobile. 🔍 https://stockanalysis.com/changelog/ (retrieved 2026-10-09)
- Koyfin's mobile app is described by reviewers as a **companion, not a replacement** — dashboards "really need a desktop screen". ⚠️ 🔍 https://simplemarkets.io/blog/post/koyfin-review (retrieved 2026-10-09)
- Exact mobile table implementations of TradingView/Yahoo native apps: `no data` (no device testing performed).

**Copyable rule:** desktop screener = collapsible filter bar of chips + column views + sticky header + sortable headers + `i` popovers; mobile = card list with 4 key fields + "view full" drill-in; never ship a 12-column table to a phone.

---

## 4. States: empty, loading, error, missing data

(Generic design-system guidance — none of it finance-specific unless noted; all retrieved 2026-10-09.)

- **Never render a failure as an empty set.** "A request fails, the component renders nothing, the user sees an empty list… they conclude the data is gone." Failure must look visibly different from empty. 🔍 https://elvissautet.com/interface/loading-empty-and-error-states (dated 2026-07-08)
- **Three distinct empty states with different copy and actions:**

| Situation | Heading | Action |
|---|---|---|
| Nothing exists yet (new user) | "No watchlists yet" | Create/import button |
| Filters matched nothing | "No matching stocks" | "Clear filters" (secondary) |
| Search returned nothing | "No results for '{query}'" | adjust-search hint |

🔍 Once UI handbook, https://handbook.once-ui.com/common-patterns/empty-and-error-states (retrieved 2026-10-09); same split in 🇦🇺 agriculture design system, https://design-system.agriculture.gov.au/patterns/loading-error-empty-states (retrieved 2026-10-09)
- **Empty states are onboarding moments:** NN/g — a blank panel makes users wonder "is it loading? did I set the wrong filters?"; use the empty space to explain the feature and link directly to the first action (e.g. a "Create alert" button inside an empty alerts panel). In-context help shown on interaction beats forced tutorials at first use. 🔍 https://www.nngroup.com/articles/empty-state-interface-design/ (dated 2021-09-19)
- **Loading:** skeleton when the content shape is predictable (reserve exact space to avoid layout shift); spinner only for short/unknown-shape waits; no indicator at all under ~300ms; status copy after a few seconds; never show skeleton and empty state at once; skeletons must not be focusable. 🔍 https://uxpatternsguide.com/compare/loading-skeleton-vs-empty-state-vs-error-state/ and https://atekian.com/en/blog/designing-empty-loading-and-error-states (dated 2026-08-09), both retrieved 2026-10-09
- **Error:** specific plain-language cause + "whether anything was saved" + a retry button + optional error code; inline error inside the failed widget rather than a full-page error; preserve filter/input context across failures. 🔍 Once UI handbook (above); 🇦🇺 agriculture design system (above); WCAG 2.2 SC 4.1.3 wants status messages announced (`role="alert"`/`aria-live`). 🔍 https://uiuxatlas.com/lessons/interaction-design/system-states-loading-skeleton-empty-error-and-success/ (retrieved 2026-10-09)
- **Finance-specific: blank ≠ zero.** "Never blank the cell. An empty cell reads as a zero position… freeze the value at its last known number, mark it visibly stale with a badge and muted contrast, stamp the exact time it was last good." 🔍 https://pavle-design.com/blog/fintech-dashboard-design-patterns (dated 2026-07-15; retrieved 2026-10-09)
- **Market-closed is its own state**, distinct from feed-stale — "design an explicit market closed state instead of showing a flat line and letting the user guess". 🔍 same URL (retrieved 2026-10-09)

---

## 5. Colour, typography, chart discipline, dark mode

- **Red/green may stay, but never alone.** WCAG 2.2 SC 1.4.1 requires colour not be the sole carrier of meaning; red-green deficiency affects roughly 1 in 12 men, and default red/green pairs are near-identical in lightness (WCAG contrast ~1.2:1). Always add sign (`+4.2% / −1.8%`), arrow, or label. 🔍 https://colourwise.app/data-visualisation/semantic-colour-in-charts (retrieved 2026-10-09); 🔍 https://data.europa.eu/apps/data-visualisation-guide/accessible-colour-palettes (retrieved 2026-10-09)
- **Bloomberg does this at scale:** dedicated UX work on colour accessibility for the Terminal because ~20,000 users have colour vision deficiency. 🔍 https://www.bloomberg.com/ux/2021/10/14/designing-the-terminal-for-color-accessibility/ (dated 2021-10-14; retrieved 2026-10-09)
- **Categorical palettes:** use Okabe–Ito for multi-series charts; keep red/green *out* of categorical palettes so semantic gain/loss colour isn't diluted; estimates = muted **dashed** line, actuals = solid bold; never colour a "miss" green. 🔍 https://colorarchive.org/guides/financial-ui-color-guide/ (retrieved 2026-10-09); 🔍 analyst-kit charting reference, https://github.com/mohitjandwani/analyst-kit/blob/main/plugins/analyst-kit/skills/charting/references/aesthetics.md (retrieved 2026-10-09)
- **Hierarchy through weight, not more colour:** top-line numbers full contrast; detail rows lower saturation/smaller type — "the most important numbers are visually heaviest". 🔍 ColorArchive guide (above)
- **Chart restraint rules worth copying:** no raw 12-digit dollar axes; don't mix `$` and `%` on one axis; no pie charts for time series or >5 slices; rebase unequal companies to 100; ≤ ~6 competing colours. 🔍 analyst-kit reference (above)
- **Dark mode is table stakes for this category:** Finviz ships a "Modern" theme in Light **and** Dark (classic theme in use since 2007, still supported); Stock Analysis lists Dark theme as a Pro feature with a site-wide Light/Dark toggle. 🔍 https://finviz.com/theme (retrieved 2026-10-09); ✅ https://stockanalysis.com/tutorials/screener/ footer (fetched 2026-10-09). Practical notes: off-white on near-black rather than pure #FFF/#000; check contrast per mode. 🔍 https://tradecn.dev/docs/color/ (retrieved 2026-10-09)
- **Simply Wall St's 2026 rebrand** moved to "a warmer colour palette, contemporary typography… a focused environment where you can do your best thinking" — evidence that even data-heavy brands are softening away from cold blue-black. 🔍 https://www.morningstar.com/news/business-wire/20260219970491/... (dated 2026-02-24; retrieved 2026-10-09) and 🔍 https://simplywall.st/ (retrieved 2026-10-09)
- Exact typefaces / font sizes / hex palettes used by TradingView, Yahoo, Koyfin, Finviz: `no data` (I did not inspect their stylesheets).

---

## 6. Communicating data quality, confidence & coverage

This is the strongest differentiator available to a small, honest app.

### 6.1 Freshness & delay

- **Regulatory floor:** Nasdaq requires a *prominent delay message* ("Data Delayed 15 minutes") at or near the top of every display of delayed data, and a prominent attribution message ("Source: Nasdaq Last Sale") for real-time quotes. ✅ https://www.nasdaqtrader.com/content/AdministrationSupport/Policy/DISPLAYREQUIREMENTSPOLICY.pdf (retrieved 2026-10-09)
- **Stock Analysis does the retail version well:** a per-stock **"last updated" timestamp under the price**, in exchange-local time; and a full Data Sources page naming every provider per data type (S&P Global & Fiscal AI for fundamentals, CBOE for real-time prices, Nasdaq UTP for delayed consensus, TipRanks for analysts, Quartr for transcripts), including *limitations* ("S&P does not allow downloads…"; "each provider uses different methods… information may be slightly different than what other sites show"). It closes with an honest "impossible to maintain 100% accuracy… contact us" and a page-last-updated date. ✅ https://stockanalysis.com/data-sources/ (fetched 2026-10-09)
- **TradingView footer attribution:** "Select market data provided by ICE Data Services. Select reference data provided by FactSet." ✅ https://www.tradingview.com/support/solutions/43000718885-tradingview-screeners-walkthrough/ (fetched 2026-10-09)
- **Stale-feed pattern:** status dot "Live" → "Data delayed" banner with last-update time → "As of · market closed"; downgrade never silent; when one data lens is unavailable the UI says which lens is dark and withholds the derived call rather than guessing. 🔍 StrikeGEX docs, https://strikegex.com/docs/data-freshness (retrieved 2026-10-09)
- **Delay disclosure belongs next to the number, at readable weight** — "not tucked into a tooltip"; treat the delay label with the same seriousness as the number. 🔍 https://pavle-design.com/blog/fintech-dashboard-design-patterns (retrieved 2026-10-09)

### 6.2 Definitions & methodology

- **Per-metric `i` popovers** with definition + formula (Stock Analysis, verified above). ✅
- **Selection-criteria disclosure:** Stock Analysis added "a popover explanation on market movers pages that explain the selection criteria and update frequency". 🔍 https://stockanalysis.com/changelog/ (retrieved 2026-10-09)
- **Named, versioned methodology with a disclaimer of interpretation:** Zoya — "The default standard is AAOIFI, but Zoya Pro subscribers can choose… S&P Shariah, MSCI Islamic, Dow Jones Islamic, and FTSE Russell Shariah… our compliance assessments are based on **our independent interpretation** of these publicly available methodologies… our results may vary from their official determinations." Every stock's "See Full Report" shows exact ratios, thresholds and underlying data. ✅ https://help.zoya.finance/en/articles/4189798-how-does-zoya-screen-stocks-for-shariah-compliance (fetched 2026-10-09)
- **Machine-readable honesty:** Zoya's public schema carries `status: COMPLIANT | NON_COMPLIANT | QUESTIONABLE | UNRATED`, `reportDate`, separate `businessScreen`/`financialScreen` verdicts, exact revenue splits and ratios — i.e. a first-class "questionable" and "unrated" state rather than forcing binary. 🔍 https://developer.zoya.finance/schema.graphql (retrieved 2026-10-09)
- **"Why do apps disagree?" articles as trust furniture:** Zoya publishes an explainer that different screeners legitimately disagree (different denominators, data schedules), and tells users to check the ratios and as-of date when a stock is borderline. 🔍 https://help.zoya.finance/en/articles/5666086-why-does-a-stock-s-compliance-status-differ-between-zoya-and-another-screener (dated 2026-04-14; retrieved 2026-10-09)
- **Update cadence stated in plain words:** Zoya — dataset refreshed daily; compliance reports refreshed per company reporting cycle (quarterly for US, semi-annual/annual elsewhere). 🔍 https://zoya.finance/ (retrieved 2026-10-09). Musaffa — "Halal rating updated every quarter by our Analysts team"; methodology page shows each ratio formula with its threshold. 🔍 https://musaffa.com/screening-methodology/ and https://musaffa.com/halal-investing-platform/ (retrieved 2026-10-09)
- **Coverage numbers stated up front:** SWS "120,000 stocks in 129 [exchanges] in 66 countries"; Zoya "60,000 stocks"; Musaffa "135,030 stocks and 8,241 ETFs across 150+ markets"; Stock Analysis "130,000+ tradable symbols". 🔍 respective homepages/methodology pages (retrieved 2026-10-09); Stock Analysis count ✅ from its Data Sources page.

### 6.3 Graded confidence instead of binary verdicts

- **Musaffa's Halal Score / C− to A+ grade** — "a detailed multi-factor compliance rating that goes beyond simple pass/fail"; historical compliance trend (when did it flip?) is a paid feature. ⚠️ 🔍 https://islamicfinancecalculator.com/reviews/musaffa-app-review (dated 2026-03-05) and https://www.halalwallet.us/providers/musaffa (retrieved 2026-10-09)
- **Islamicly's 1–5 "Moons" rating** — communicates *how comfortably* a stock passes, so users can prefer 4–5 moon names near a threshold. ⚠️ 🔍 https://islamicfinancecalculator.com/reviews/islamicly-app-review (dated 2026-03-05; retrieved 2026-10-09)
- **The gap both expose:** users complain when an app shows a verdict without the reasoning — "I want to know *why*" (App Store review of Islamicly). ⚠️ 🔍 https://apps.apple.com/us/app/islamicly-halal-stocks-gold/id1484332448 (retrieved 2026-10-09)

**Copyable rule:** every number gets (a) an as-of timestamp, (b) a source name, (c) a formula popover; every verdict gets a grade or threshold-proximity bar, plus a "methodology" link. Show `INSUFFICIENT_DATA`/`UNRATED` as its own state — never silently pass/fail.

---

## 7. Onboarding: first-timer finds their first answer

- **Open the product before the wall.** Stock Analysis's homepage is search-a-ticker-get-data with no login wall (per review: "The homepage: search a ticker, get the data. No login wall."). ⚠️ 🔍 https://tickernerd.com/resources/stockanalysis-review/ (dated 2026-08-19; retrieved 2026-10-09) — corroborated by the site structure I fetched (anonymous access to tutorial/screener pages). ✅
- **Yahoo's opposite lesson:** third-party teardown — "The onboarding flow is quite long and requires a full account sign-up before a user can even see the app's main interface. Allowing a guest mode to explore public market data first could reduce initial friction." Yahoo *does* use small targeted contextual tooltips after sign-up (edit watchlist, follow a stock). ⚠️ 🔍 https://screensdesign.com/showcase/yahoo-finance-stocks-news (retrieved 2026-10-09)
- **Simply Wall St's quantified failure:** dropping users into a complex app with minimal guidance → only ~5% of visitors became active; the fix was a dashboard feed giving a "hook" ("I can see the history of events at XYZ stock"). ⚠️ (same case study as §2.1) 🔍 https://infinitenuance.com/2024/11/27/case-study-simply-wall-st-dashboard-feed/ (retrieved 2026-10-09)
- **Finviz redesign concept (not confirmed shipped):** replace the blank screener with a 3-step wizard — pick an investment goal → curated filters applied → preview a tailored screener = "a clear first success moment"; left-side progress tracker; explanations in a **sidebar** rather than hover tooltips; pre-built screens ("Top Growth Stocks") so users learn by doing. ⚠️ Portfolio concept study of Finviz; treat as a pattern, not as Finviz's product. 🔍 https://cherylalice.co.uk/financial-stock-screener-light and https://www.linkedin.com/pulse/financial-screener-uxui-case-study-yuliia-zhukova-kxyre (dated 2023-12-22), both retrieved 2026-10-09
- **Starter templates beat empty boxes:** Screenwich redesign — "Dense Layout → Intuitive Screener with Starter Templates", "Static Landing View → Personalized Starter Dashboard". ⚠️ 🔍 https://purvachawan.com/project/simplifying-flows-for-task-success/ (retrieved 2026-10-09)
- **In-context beats tours:** NN/g — in-context learning cues shown when the user starts a task are generally more successful than forced tutorials at initial use, because they can be applied immediately. 🔍 https://www.nngroup.com/articles/empty-state-interface-design/ (retrieved 2026-10-09)
- **Stock Analysis also ships a screener tutorial page** (with video, screenshots, TOC) linked from the product — documentation as onboarding. ✅ https://stockanalysis.com/tutorials/screener/ (fetched 2026-10-09)

**Copyable rule for v1:** no signup required to search and open a company; first screener visit pre-loaded with one friendly preset + a dismissible 3-step strip; empty watchlist shows a "Add a stock" search box and a "load demo list" link; tooltips on the three things users actually ask about (delay badge, `i` definitions, verdict grade).

---

## 8. Shariah-screening-specific patterns (relevant to this project)

- **Two-part verdict, shown separately:** business-activity screen + financial-ratio screen, each with its own status, plus overall status. ✅ Zoya help article + 🔍 Zoya schema (fetched 2026-10-09)
- **Show the ratio vs the threshold, per criterion:** Musaffa's methodology page renders each test as *formula → threshold (e.g. 30% of trailing 36-month avg market value) → pass/fail*, including "why a limited tolerance exists". 🔍 https://musaffa.com/screening-methodology/ (retrieved 2026-10-09)
- **Methodology switcher at the top of the report** (AAOIFI / MSCI / S&P / DJIM / FTSE) so one stock's disagreement across apps becomes a feature, not a bug. 🔍 https://blog.zoya.finance/introducing-more-ways-to-screen-for-shariah-compliance-in-zoya/ (dated 2025-02-20; retrieved 2026-10-09)
- **Questionable / borderline is a first-class status** (Zoya `QUESTIONABLE`; Islamicly "Borderline — close to failing"; Musaffa "Doubtful"). Do not collapse to binary. 🔍 schema + reviews (above)
- **Report date on every verdict** — "last updated" per stock, tied to the company's filing cycle; staleness of a compliance badge is a real risk. ✅ Zoya schema fields (`reportDate`) via 🔍 developer.zoya.finance (retrieved 2026-10-09); staleness caution ⚠️ 🔍 https://faithscreener.com/blog/islamicly-app-review-halal-screening-compared (dated 2026-04-07; retrieved 2026-10-09)
- **What users punish:** Islamicly's top complaints are verdicts without reasoning, disagreement with stricter apps, and dated UI — i.e. exactly the trust gaps §6 addresses. ⚠️ 🔍 App Store reviews (above) and faithscreener review (above).

---

## 9. Pattern shortlist for a small React app (what to actually build)

Ranked by value ÷ effort; every item is evidenced above.

1. **Skeleton → data | empty | error triad on every async view** (table-shaped skeletons; distinct copy for no-data vs no-match vs failure; retry inside the failed widget). §4
2. **As-of timestamp + delay badge + source line** under every price; market-closed as its own state; grey, never blank, stale values. §6.1
3. **`i` definition popovers on every metric/column** (definition + formula + source). §6.2
4. **Screener = collapsible filter chips + 3–4 column views + preset "Popular screens" + sortable sticky-header table + clear-filters empty state.** §3
5. **Company page = hero → key-stats strip → 4–5 in-page tabs** (no nested tabs). §1.2, §2.2
6. **Verdicts graded, not binary** + "Show full report" exposing ratio vs threshold, with methodology name/version and report date. §6.3, §8
7. **Colour discipline:** red/green always paired with sign + arrow; Okabe–Ito for categorical; muted dashed lines for estimates; dark mode as a toggle, off-white on near-black. §5
8. **Search-first, no signup wall; preset starter screen; empty states as onboarding with one primary action.** §7
9. **Mobile: card list instead of wide tables; sticky first column where tables remain.** §3.3
10. **Footer data-sources page** naming provider per data type and admitting limits — cheap, and it is the trust asset competitors lean on hardest. §6.1

Explicitly **not** recommended for a small app (named as scope cuts for PM): drag-and-drop multi-widget dashboards (Koyfin; crowd risk flagged in its own reviews), chart-grid screener view, autosave/undo of screens, community feeds, 100+ filters.

---

## 10. Gaps — `no data`

- **Wisesheets** (named in inbox): not researched this pass — it is a spreadsheet tool, not a consumer app; no UX findings gathered. `no data`
- **Exact design tokens (fonts, hex palettes, spacing)** of any competitor: `no data` — I read pages and docs, not stylesheets.
- **Live/native mobile behaviour** of TradingView, Yahoo, Zoya, Musaffa apps: `no data` — no device or emulator testing; mobile claims are from reviews/changelogs only.
- **Whether Finviz has shipped the onboarding wizard** in the redesign case studies: `no data` — the sources are designer portfolio projects, not Finviz announcements; only Finviz's Light/Dark "Modern" theme page is first-party.
- **Screeners' real row counts / performance at scale:** `no data` beyond marketing claims.
- **Effect sizes of any pattern on conversion/retention** other than SWS's single first-party case study: `no data` — treat all "this improves activation" claims as design folklore until tested.
- **The user's own app:** not audited in this pass (out of scope for competitor research).

---

*Filed by the router from researcher Nadia's inline result, 2026-10-09.*
