# Competitor feature scan: enhancement candidates for EGX AI

Researcher: Nadia. All fetch dates: **2026-10-30**. "(search)" = taken from a web-search summary because the direct fetch returned 403 or no detail; treat as weaker. Business models, pricing, GICS tables and the Mubasher feature list are in `phase-2-industry-competitive-landscape.md` and `mubasher-features-2026-10.md` and are not repeated. Mubasher: no new data this pass.

## 1. Competitor patterns (features only)

**Thndr (EGX broker)**
- ThndrX workspace: financials, valuation metrics, "financial health ratings", screeners, alerts, expert watchlists from its Rumble research arm: https://support.thndr.app/en/articles/799477-what-is-thndrx
- Jun 2026 redesign: one consolidated portfolio across stocks, funds, fixed income and gold; Discovery filters by category, objective and **Shariah compliance**; Rumble technical notes sold separately from fundamental research: https://enterpriseam.com/egypt/2026/06/07/thndr-is-layering-up-its-stock-trading-platform-and-integrating-wealth-management/
- "Alpha" AI assistant builds a plan from goals and risk, then **prepares buy/sell orders for one-click execution** (same URL). Conflicts with the no-execution rule; do not copy.
- Fair-value estimates in-app: no data (none found in search).

**Argaam**
- Screener, ratio pages (P/E, ROE, book value), alerts, comparison tools: https://www.argaam.com/en/subscription-packages
- Egypt coverage: no data. Both that page and https://developer.argaam.com/catalog name Saudi/GCC only. Not a direct EGX competitor.

**Investing.com Egypt**
- Egypt page: EGX 30 / EGX 70 / PIGI with advancers-decliners, sector indices, price/volume/earnings alerts, watchlists: https://www.investing.com/markets/egypt
- Site-wide: earnings, dividend, IPO and holiday calendars, heatmap, technical summary, pivot points (same URL).
- Fair Value and company health score appear locked behind a paywall on an EGX stock page (search): https://uk.investing.com/equities/saudi-egypt-in

**TradingView**
- Egypt screener with preset lists (oversold, unusual volume, 52-week high/low, high dividend, most volatile) and tabs (Performance, Technicals, Valuation, Dividends, Profitability, statements). Columns include Rel vol, RSI, analyst rating, sector: https://www.tradingview.com/markets/stocks-egypt/market-movers-oversold/
- Stock heatmap: size by market cap/volume/turnover, colour by change/performance/volatility, grouped by sector with drill-down, and selectable by index **or whole country**: https://www.tradingview.com/support/solutions/43000766446

**stockanalysis.com (EGX pages exist)**
- Tabs: Overview, Financials, Forecast, Statistics, Dividends, History, Profile; Compare and Alerts buttons. Header states "Currency is EGP", source S&P Global, "At close" date, "Last checked" date: https://stockanalysis.com/quote/egx/COMI/
- Statistics page shows Piotroski F-Score and Altman Z-Score, "Important Dates" (earnings, ex-dividend), and **shows "n/a" where EGX data is missing** (e.g. EV multiples, Altman Z): https://stockanalysis.com/quote/egx/COMI/statistics/
- Analyst price target and consensus shown on the overview (E£181.08 at fetch; vendor figure): same COMI URL.

**Simply Wall St** (direct fetch 403; support pages via search)
- Company report order: Valuation, Management, Ownership, Company Information; ownership checks insider buying over 3 months (buys > sells) and share dilution from historical share counts: https://support.simplywall.st/hc/en-us/articles/8787431138831-Understanding-The-Management-and-Ownership-Sections (search)
- Dividend section: yield, payout ratio, ex-date and a stability check (a drop over 20% in a year is flagged volatile): https://support.simplywall.st/hc/en-us/articles/8604726406159-Understanding-The-Dividend-Section (search)
- EGX list pages (growth, biggest losers by sector) exist: https://cap.simplywall.st/stocks/eg/software/growth
- Snowflake and peers are in the prior file; not repeated.

**Koyfin**
- Saved, reusable graph templates, watchlist column layouts, multi-panel custom dashboards, one-click sharing; alerts on price, technicals, valuation, news: https://koyfin.com/features/
- Earnings calendar can be filtered to a watchlist: https://www.koyfin.com/help/earnings-calendar-feature/
- EGX coverage: no data (not named on any page).

**TIKR**
- Valuation builder from templates; 30-year financials; ownership tracking: https://www.tikr.com/
- EGX coverage: no data.

**Finviz**
- Screener with switchable column views (Overview, Valuation, Financial, Ownership, Performance, Technical, Custom), "My Stock Presets", add-to-compare, alerts, CSV export: https://finviz.com/screener.ashx
- No EGX universe (see prior file).

**Seeking Alpha**
- Five factor grades (Value, Growth, Profitability, Momentum, EPS Revisions), A+ to F, **graded against the stock's sector** across 100+ metrics; updated daily; excludes stocks with no analyst coverage: https://help.seekingalpha.com/premium/quant-ratings-and-factor-grades-faq
- The overall rating is not an average of grades; a poor grade on one factor caps it (same URL).
- Rating history and track record: no data (the FAQ page does not describe one).

**Morningstar**
- Fair value plus **fair value uncertainty** (low to extreme). Uncertainty sets the margin of safety, so higher uncertainty needs a bigger discount before a buy call. Moat rating: none, narrow, wide. "Consider buying / selling" prices tied to the discount thresholds: https://morningstar.in/posts/9275/how-morningstar-calculates-stocks-fair-values.aspx
- Illustrative thresholds, about 20% discount at low uncertainty vs 40% at high (older material, search): https://morningstar.ca/ca/news/188241/how-morningstar-values-stocks.aspx
- Moat is an analyst judgement. Not reproducible deterministically.

**Shariah apps**
- Musaffa: grade C- to A+ with a green/orange/red colour; a report explaining each verdict by business activity and ratios; up to 3-year compliance history; alerts when status changes; filters by status, grade, debt limit: https://musaffa.com/pricing
- Zoya: free tier shows status only, paid shows the full report; several rulebooks to switch between; email alert on status change: https://help.zoya.finance/en/articles/8455907-what-is-included-in-a-zoya-pro-subscription
- Islamicly Egypt page: per-stock purification ratio and reason for status; screening updated daily, but no "last updated" date shown: https://www.islamicly.com/home/Country/Egypt
- Portfolio-level purification tracking (Zoya) is third-party described: https://www.halalwallet.us/providers/zoya

**EGX newcomers**
- EGX Bots: ML "AI score" (Random Forest, LightGBM) for odds of beating EGX 30, scanners, Telegram signals. Traction minimal, no date or pricing: https://www.hunted.space/product/egx-bots
- Official EGX app, beta 17 Aug 2025: real-time data, news, index summaries, gainers/losers. Arabic support not stated: https://techpoint.africa/news/egypts-egx-app-launches/
- No Arabic-first EGX fundamentals product found (search).

## 2. Ranked enhancement candidates

Effort: S under 1 week, M 1-3 weeks, L over 3 weeks. "Has data" is my inference from the brief, not verified against code.

1. **Freshness header on every page (S).** Currency, data source, "price as of", "fundamentals as of", provisional-vendor flag. Seen on stockanalysis COMI. Reuses data-quality tab. Has data: yes. No rule conflict. Reinforces the honesty positioning. No decision needed.
2. **Screener with preset lists and switchable column views (M).** Presets (oversold, unusual volume, 52-week range, high dividend) plus filters for Shariah verdict, investment score, stance and quality. Saved presets. TradingView, Finviz, Thndr (Shariah filter). Matters because the recommendations page is a fixed ranking and a retail user wants own cuts. Has data: mostly (prices, scores); relative volume needs volume history. **Needs UX decision** (new page vs extend Recommendations).
3. **Sector heatmap (S-M).** Size by market cap or turnover, colour by period change, grouped by EGX sector, drill-down. TradingView, Investing.com. Fast market read for retail. Has data: prices and sectors yes; market cap needs share counts (unverified). **Needs UX decision** (Markets dashboard placement).
4. **Shariah verdict history and change alerts (S-M).** Show verdict over time with the methodology version, and alert on a status flip or an EGX33 semi-annual review change. Musaffa, Zoya. Matters because Shariah investors must exit or purify when status flips. Has data: verdicts are versioned and the events ledger exists; history storage unknown. No conflict; alerts feed the existing ledger.
5. **Deterministic health scores: Piotroski F-Score and Altman Z (S).** Return INSUFFICIENT_DATA where inputs are missing, exactly as stockanalysis does (n/a). Altman Z is not meaningful for banks, so it needs a sector exclusion. Needs statements (vendor data present). Methodology constants must be versioned. Fits as extra checks in "health".
6. **Fair value uncertainty band and price-to-fair-value margin of safety (M).** Map the existing sensitivity range to low/medium/high uncertainty and show the discount needed. Morningstar. Matters because EGX earnings are volatile and a single point fair value overstates precision. Has data: sensitivity yes. **Needs a methodology/UX decision** (threshold choice, versioned). Avoid "Consider Buying" wording (certainty-wording rule); say "price at which discount reaches X%".
7. **Sector-relative letter grades per component (S-M).** Show past/health/growth/value/dividends as sector-relative grades or percentile chips with N peers. Seeking Alpha. Has data: peer percentiles exist. Must degrade to INSUFFICIENT_DATA when N is small. Do not adopt the "Strong Buy" labels. **UX decision** (overlaps the investment-score tab).
8. **Earnings, filings and ex-dividend calendar filtered to watchlist (M).** Koyfin, Investing.com, stockanalysis "Important Dates". Matters because results season drives EGX moves. Has data: filing dates in the ledger; forward dates unknown, **do not estimate**, show only published dates. Source of EGX forward calendars: no data found.
9. **Dividend safety checks and ex-date list (S-M).** Payout ratio, cash coverage, stability flag, with ex-dates. Simply Wall St, stockanalysis. Matters for income and Shariah purification timing. Has data: dividends component exists; ex-dates unverified.
10. **Vendor consensus price target beside own fair value (S-M).** Labelled provisional vendor data with fetch date, showing the gap. stockanalysis COMI. Has data: only if the saved vendor files contain forecasts (unverified). Conflict: vendor data is provisional; filings outrank it. Must not feed the stance score.
11. **Company compare view (S-M).** 2-4 tickers, rebased price and key metrics. stockanalysis Compare button, Finviz compare set. Has data: yes. Extends the peers tab. **UX decision.**
12. **Stance history and outcome tracking (M).** Store each stance with methodology version, show later price outcome. Mubasher signals lifecycle (prior file) as the pattern. Builds trust in a deterministic engine. Look-ahead rule is satisfied only if stances are stored at issue time, so it cannot be backfilled. **Needs architecture decision** (new table).
13. **Ownership and dilution checks (S for dilution, L for insiders).** Dilution derived from share-count history; insider trades need a source. Simply Wall St, TIKR. Mubasher lists insider trades for EGX (prior file), so a source exists, but it is a competitor's. Insider data: no data on a free EGX feed.
14. **Manual holdings tracker with purification roll-up (L).** Zoya, Thndr consolidated portfolio. Manual entry only, no broker link, no execution. Matters because purification depends on holdings. **Needs architecture decision** (EGX AI is single-user with no accounts model beyond watchlists).

## 3. Do not copy
- One-click order preparation (Thndr Alpha): trade-execution rule.
- ML "odds of beating the index" score (EGX Bots): not a deterministic, versioned formula.
- Analyst-set moat ratings: not reproducible in code.

## 4. Unverified (do not re-search blindly)
- Seeking Alpha rating history; SWS and Koyfin EGX coverage depth (SWS direct pages 403).
- Argaam Egypt coverage; Investing.com Fair Value method; Finviz heatmap mechanics (page returned no description).
- Zoya EGX coverage and purification method; Islamicly Egypt update timestamp.
- TIKR Guided Valuation and EGX coverage.

## 5. Router check against the app and dev DB (2026-10-30)
- #1 Freshness: the company hub already shows "Prices as of <date>" and a "Provisional (vendor data)" badge; missing piece is a "fundamentals as of FY…" line and the same header on non-hub pages.
- #2 Screener: volume, value_traded and trades are stored per day, so relative volume and turnover filters are feasible.
- #3 Heatmap and #7 sector-relative grades: **blocked** - `companies.sector` is null for all 234; needs the R44 sector loader first. A turnover-sized heatmap without sectors is possible.
- #4 Shariah history: `shariah_screening_results` holds one row per company (234) - no history yet; needs a history table (architecture decision).
- #5 Piotroski: every input line is imported (cfo, total_assets, current assets/liabilities, interest-bearing debt, shares, gross profit, revenue). Altman Z also needs retained earnings, which is in the vendor files (`retearn`) but not imported.
- #10 Consensus targets: **not possible** - the saved vendor files contain no forecast or price-target fields.
- #12 Stance history: momentum `signal_runs` are stored (2 runs, 464 rows), but Buy/Hold/Reduce stances are computed on read and not stored.
- #8 Calendar: no source for forward EGX dates; past filing dates only.
