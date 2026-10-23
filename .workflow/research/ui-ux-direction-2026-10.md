# UI/UX direction for the EGX AI redesign (2026-10)

**Researcher:** Nadia · **Compiled:** 2026-10-23 · **All URLs fetched 2026-10-23** unless noted.
**Method:** live pages read; competitors' production CSS and font binaries downloaded; fonts inspected with fontTools; WCAG contrast computed in Python. No screenshots (text/CSS extraction gave hard values: hex codes, row heights, font stacks).
**Evidence labels:** ✅ primary source fetched/inspected · 🔍 secondary/search snippet · ⚠️ vendor or practitioner blog (low weight).
Builds on `.workflow/research/app-wide-ux-patterns.md` (2026-10-09); its findings still stand (screener anatomy, empty/loading/error triad, as-of timestamps, `i` popovers, never red/green alone).

## 0. Direction in one paragraph

A quiet, ledger-like research tool: light first with a matching dark theme that follows the OS; one family in two scripts (IBM Plex Sans + IBM Plex Sans Arabic); Western digits with tabular figures everywhere; one non-green brand accent, green/red reserved for gain/loss and never shown without a sign or shape; dense tables (32px rows, 28px compact) with hairline dividers instead of cards; no gradients, glass, glow, emoji or pills; a grouped sidebar plus a company hub with ~7 tabs (down from 13).

## 1. What the current UI does that reads as "AI slop" (repo evidence)

Sources: `frontend/src/index.css`, `components/Layout.tsx`, `components/CompanyTabs.tsx`, `pages/Companies.tsx`, `pages/Recommendations.tsx`.

| Current pattern | Why it is slop / a defect | Source |
|---|---|---|
| Two radial-gradient glows on `body`; gradient-text logo with `◈`; `.card::before` gradient overlay; `.coverage-banner::before` gradient left stripe | "Purple-to-indigo gradients have become the Times New Roman of AI-generated design"; a thick one-sided coloured border on a rounded card is "the single most recognizable signature of AI-generated UI" | ✅ https://www.thefountaininstitute.com/blog/signs-vibe-coded-ui ; ⚠️ https://noqta.tn/en/blog/ai-design-slop-overused-ui-patterns-fix-2026 |
| `backdrop-filter: blur()` on sidebar, pricing cards, statements tables (6 uses) | Glassmorphism "can pose significant accessibility and usability challenges"; text must meet contrast | ✅ https://www.nngroup.com/articles/glassmorphism/ (2024-06-07) |
| Dark navy "terminal" + glow as the only theme | "dark background plus glow equals premium" is a named tell | ✅ Fountain Institute |
| Inter as UI font | Default output "will almost always conform to Inter fonts, purple gradients on white backgrounds" | ✅ https://claude.com/blog/improving-frontend-design-through-skills (2025-11-12) |
| Glyph/emoji icons in data cells: `✓ ✕ ☪ ⚠ ↻ ▲ ● ▼ ◐ ○ ▶ ▸ ◂` | "The AI-generated interface has discovered emojis and will not stop using them" | ✅ Fountain Institute |
| `border-radius: 9999px` pills (11 uses); uppercase letter-spaced badges/headers (0.06–0.08em) | Oversized radius and wide tracking on uppercase labels are tells; tracking breaks Arabic joins (§4) | ⚠️ noqta; ✅ W3C alreq |
| Hover lift `translateY(-1/-2px)` + shadow on cards/buttons | Decoration that signals nothing | ✅ Fountain Institute |
| Brand accent is green (`--accent #449058`, active nav `--green`), same as the gain colour | Brand chrome and "price up" become one signal | Analysis (§5) |
| `--text-muted #71829a` on `--bg-card #0b1a30` = 4.45:1; `--accent` on card = 4.46:1 | Below WCAG AA 4.5:1 at 11–13px | Computed |
| Table cell padding 0.6875rem ×2 + 13px × line-height 1.65 | ~44px rows for one line; Finviz uses 24–28px | Computed |
| `th { text-align: left }` (physical) | In Arabic headers stay left while text cells go right: misaligned | Repo CSS |
| `@media (max-width:768px) .sidebar { display:none }` with no replacement | No navigation at all on phones | Repo |
| `Companies.tsx` hardcodes English ("Companies", "Search ticker or name...", "All Sectors", column labels, `stance.toUpperCase()` → "BUY") | Key screen doesn't translate; "BUY" in caps conflicts with AGENTS.md principle 10 | Repo; AGENTS.md |
| Three families with different metrics (Inter, JetBrains Mono, Cairo) | Arabic and Latin don't harmonise; mono numbers look like code | §4 |
| 9 flat sidebar items; 13 company tabs in one scrolling row | Too many same-level tabs | §6 |

## 2. How best-in-class products lay out dense financial data

**Finviz** — ✅ https://finviz.com/quote.ashx?t=AAPL ; ✅ https://finviz.com/assets/dist/main.649fc629.css ; ✅ https://finviz.com/assets/dist/redesign.6515f6da.css (hashed names will change)
- `--font-sans: "IBM Plex Sans", …` — direct evidence Plex works in a very dense financial product.
- Rows: `.styled-table-new.is-medium td { height: 24px; padding-block: 4px }`, `.is-large td { height: 28px; padding-block: 6px }`, plus `.is-condensed`.
- Most common sizes 13/12/11px. Headers weight 400, grey `#4c5263` (dark `#c3c6d0`).
- Gain/loss `--color-green-500 #19803d`, `--color-red-500 #d91e2b` (~5.0:1 on white); lighter tints for borders, darker for text. Light + Dark themes (🔍 https://finviz.com/theme).

**Stock Analysis** — ✅ https://stockanalysis.com/stocks/aapl/ ; ✅ `/_app/immutable/assets/0.DSiATJVl.css` ; ✅ https://stockanalysis.com/stocks/aapl/financials/
- System font stack; `text-sm` (14px) dominant (123 uses vs 34 `text-base`); `whitespace-nowrap`, `py-px` mobile / 8px from `sm`.
- Tabs: Overview, Financials, Forecast, Statistics, Metrics, Dividends, History, Profile, Chart. Financials sub-tabs (Income, Balance, Cash Flow, Ratios, KPIs), period toggles (Annual/Quarterly/TTM), units stated once ("in millions of USD"); first column row labels, other columns periods.

**TradingView** — ✅ https://www.tradingview.com/symbols/NASDAQ-AAPL/ : system stack (`-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif`); gain/loss hex `no data`.
**Morningstar** — ✅ https://www.morningstar.com/stocks/xnas/aapl/quote : proprietary MorningstarIntrinsic / IntrinsicDisplay; tokens `no data`.
**Yahoo Finance** — ✅ https://finance.yahoo.com/quote/AAPL/ : separate data typography tokens (`--data-sm-reg-family`); values `no data`.
**Koyfin, Simply Wall St** — tab/token details `no data` (🔍 https://thecfoclub.com/tools/koyfin-review/); prior-file findings stand.

**Egyptian conventions**
- **Mubasher** — ✅ https://www.mubasher.info/countries/eg/stock-prices ; ✅ https://www.mubasher.info/assets/ui/main.rtl.min.css : body `"Noto Kufi Arabic","Helvetica Neue LT","Arial"` (114 uses), Noto Naskh secondary; `.up{color:#458d37}` / `.down{color:#dc0a0a}` + caret icons (green = up, red = down); `.number, .up, .down {direction:ltr; white-space:nowrap}` right-aligned in RTL; charts `direction:ltr` (not mirrored); numeric headers share the cell class; 1,092 Western vs 2 Eastern digits; `#458d37` is 4.10:1 on white (fails AA).
- **Thndr** — ✅ https://thndr.app/ar/ : `dir="rtl" lang="ar"`, 30 Western / 0 Eastern digits; in-app UI `no data` (🔍 App Store listing).
- **Al Borsa News** — ✅ https://www.alborsaanews.com/ : Cairo; 988 Western / 0 Eastern.
- **Youm7 economy** — ✅ https://www.youm7.com/Section/البورصة-والاقتصاد/297/1 : 833 Western / 0 Eastern.
- **EGX** — https://www.egx.com.eg/ar/homepage.aspx returned a bot challenge/CAPTCHA; not bypassed; conventions `no data`.

## 3. What reads as "AI slop" (critiques)

- **Anthropic (primary):** overused fonts (Inter, Roboto, Arial, system fonts), clichéd schemes (purple gradients on white), predictable layouts; remedy: "Commit to a cohesive aesthetic. Use CSS variables for consistency"; "Dominant colors with sharp accents outperform timid, evenly-distributed palettes." ✅ https://claude.com/blog/improving-frontend-design-through-skills
- **Fountain Institute (7 signs):** neon palettes with no priority; decorative glow on dark mode; emoji icons; purple gradients; cards inside cards; multicoloured side tabs on every block; status dots that signal nothing. ✅ https://www.thefountaininstitute.com/blog/signs-vibe-coded-ui
- **Superdesign:** Inter/Roboto, purple/indigo, centred hero, three rounded icon cards, uniform shadows, glassmorphism, badge above headline, coloured left-border cards; fix: name exact typefaces/hex values, keep a design-system file. ⚠️ https://www.superdesign.dev/blog/why-ai-design-looks-generic (2026-06-15)
- **Noqta:** oversized radius, glow, generic "Live" badges ("decoration cosplaying as information"), vague copy. ⚠️ https://noqta.tn/en/blog/ai-design-slop-overused-ui-patterns-fix-2026 (bot byline, low weight)
- Controlled study on density and trust: `no data`.

## 4. Arabic and RTL

### 4.1 Fonts (fontTools on google/fonts binaries; ✅ https://raw.githubusercontent.com/google/fonts/main/ofl/{ibmplexsansarabic,ibmplexsans,cairo,notosansarabic,tajawal,almarai}/…)

| Family | Western digits tabular | Eastern tabular | x-height / cap-height | Typo asc + desc | Verdict |
|---|---|---|---|---|---|
| **IBM Plex Sans Arabic** | Yes (600 units, same as Plex Sans) | No | 516 / 698 (identical to Plex Sans) | 1085 + 415 | **Recommended** — metrics and digits match the Latin face; contains Latin A–z |
| IBM Plex Sans | Yes | n/a | 516 / 698 | 1025 + 275 | Recommended Latin face (Finviz) |
| Noto Sans Arabic | Yes | Yes | 536 / 714 | 1374 + 738 | Good fallback; has `tnum` |
| Cairo (current) | Yes | No | 500 / 700 | 1303 + 571 | Kufi display face; Latin side is Titillium Web |
| Tajawal | No (proportional, no `tnum`) | No | 454 / 633 | — | Reject for tables |
| Almarai | No (proportional, no `tnum`) | No | 514 / 716 | — | Reject for tables |

IBM Plex Arabic: D&AD 2020 Typography archive (🔍 https://dandad.org/awards/professional/2020/232950/ibm-plex-arabic); OFL, npm `@ibm/plex-sans-arabic` (✅ https://github.com/IBM/plex); Google Fonts serves both split by `unicode-range` (✅ https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Sans+Arabic:wght@400;500;600); static weights 100–700.

### 4.2 Digits

- W3C alreq: Arabic-Indic digits "are used in Eastern Arabic-speaking countries such as Egypt"; digits always LTR. ✅ https://www.w3.org/TR/alreq/ (2025-10-02 draft)
- Both systems used in Egypt, Western increasingly favoured. 🔍 https://en.wikipedia.org/wiki/Eastern_Arabic_numerals
- Egyptian financial media use Western digits (counts in §2).
- Node 22.14 Intl: `ar-EG` → Eastern digits + U+061C; `ar-EG-u-nu-latn` → `‎-1,234,567.89`, `+4.23%`. The app already uses `ar-EG-u-nu-latn` (`frontend/src/i18n/useLang.tsx:54`, tested) — keep it. Plex Sans Arabic has no U+061C glyph (matters only for plain `ar-EG`).

### 4.3 Mirroring

Material bidirectionality (✅ https://m1.material.io/usability/bidirectionality.html): mirror layout, nav order, directional icons, text-field icons, linear progress, linear time sequences; do not mirror numbers, phone numbers, clocks, charts/graphs, media controls, non-directional icons, circular-time icons.
W3C (✅ https://www.w3.org/International/articles/inline-bidi-markup/): wrap opposite-direction runs in `dir="ltr"`; `dir="auto"`/`<bdi>` for unknown-direction runtime text; markup over control characters.
Numeric alignment: right-align numeric columns (✅ https://design.alberta.ca/examples/display-numbers-in-a-table-so-they-can-be-scanned-easily/); Mubasher keeps numbers right-aligned in RTL → numeric cells use physical `text-align: right` in both directions; column order still mirrors.

### 4.4 Size and spacing

- alreq: moving joined characters apart "creates undesirable results" → Arabic `letter-spacing: 0`, no uppercase transforms.
- alreq §7.4: Arabic ascenders/descenders extend further; Plex Arabic descender 415 vs Latin 275 → taller Arabic line-heights.
- UAE design system: Noto Kufi Arabic, ≥16px content, line-height ≥1.5. ✅ https://designsystem.gov.ae/guidelines/typography
- Arabic needing a larger px size than Latin: `no data` → same px sizes, taller line-heights.

## 5. Gains/losses, accessibility, dark vs light

- Egypt: green = up, red = down (Mubasher, Finviz same).
- Proposed gain-vs-loss contrast 1.08:1 (light) / 1.17:1 (dark): colour alone fails → every directional value carries a sign plus a shape (▲/▼) or a word.
- NN/g: light mode performs better for normal vision, especially at small sizes; offer user-selectable dark following the OS. ✅ https://www.nngroup.com/articles/dark-mode/ → light designed first, dark matches, default follows `prefers-color-scheme` with manual override.

## 6. Navigation

- NN/g: vertical left nav is excellent where nav grows; always-visible text labels; don't hide desktop nav in a hamburger. ✅ https://www.nngroup.com/articles/vertical-nav/ ; don't stack tab strips, default tab = high-use one (🔍 https://www.nngroup.com/articles/tabs-used-right/).
- Stock Analysis: ~9 main tabs, sub-tabs only under Financials.

**Proposed IA (for ux-expert):**
- Sidebar, grouped, labels, no icons — Markets: Dashboard, Recommendations, Rankings · Research: Companies, Shariah screening · Tracking: Watchlists, Alerts, Events · Data: Filings intake (now `/admin` per R43). Persistent ticker search at the top (`/` or Ctrl-K).
- Company hub: sticky header (ticker, name, last close + as-of, change with sign and arrow, Shariah verdict, stance + confidence), 7 tabs: Overview · Price & signals (Signals + Technical) · Financials (segmented: Statements · Ratios · Metrics · Pending data) · Valuation (Valuation + Score) · Shariah · Peers · Thesis & filings (Thesis + Disclosures).
- Mobile (<768px): top bar with search + menu opening the same grouped list (fixes "no nav"); wide tables → card lists of 4 key fields.

## 7. Concrete direction

### 7.1 Type

`--font-ui: "IBM Plex Sans", "IBM Plex Sans Arabic", system-ui, sans-serif` (Arabic mode puts "IBM Plex Sans Arabic" first). Optional `--font-code: "IBM Plex Mono"` only for methodology versions/IDs. Drop Inter, JetBrains Mono, Cairo. Weights 400/500/600 only. `font-variant-numeric: tabular-nums lining-nums` on tables, hero numbers, stat strips.

| Token | Size | LTR lh | RTL lh | Use |
|---|---|---|---|---|
| `--fs-micro` | 11px | 14px | 16px | axis ticks, footnotes |
| `--fs-meta` | 12px | 16px | 18px | table headers, as-of, captions |
| `--fs-table` | 13px | 18px | 20px | table cells |
| `--fs-ui` | 14px | 20px | 22px | controls, body UI |
| `--fs-read` | 16px | 24px | 26px | prose |
| `--fs-h3` | 16px/600 | 22px | 26px | section titles |
| `--fs-h2` | 20px/600 | 28px | 32px | page title |
| `--fs-h1` | 24px/600 | 32px | 36px | company name |
| `--fs-figure` | 28px/500 | 32px | 32px | hero price |

Sentence case everywhere; no uppercase, no positive letter-spacing; headings ≤ −0.01em in LTR only.

### 7.2 Palette (WCAG ratios vs `--surface`)

Light (default):
```
--bg #F6F6F3   --surface #FFFFFF   --surface-2 #EFEFEB   --border #DCDCD5
--border-strong #878A83 (3.50:1)   --text #16181B (17.79)   --text-2 #474B52 (8.76)
--text-3 #62666E (5.76; 5.00 on surface-2)   --accent #2A4A7F (8.81, ink blue)
--gain #0A7A3E (5.43; 4.71 on surface-2)   --gain-bg #E8F3EC (gain on it 4.78)
--loss #C1272D (5.84)   --loss-bg #FBEAEA (loss on it 5.02)
--warn #8A5300 (6.33)   --neutral #5B6068 (6.33)
```
Dark (follows OS, manual override):
```
--bg #0F1012   --surface #16171A   --surface-2 #1E2024   --border #2B2D32
--border-strong #666A73 (3.31)   --text #E7E8EA (14.62)   --text-2 #B3B6BC (8.82)
--text-3 #8E929A (5.74)   --accent #9DB7E6 (8.83)
--gain #45C07A (7.74) --gain-bg #14261C (6.85)   --loss #F07A72 (6.60) --loss-bg #2A1716 (6.27)
--warn #E3A64A (8.38)   --neutral #A3A7AE (7.42)
```
Categorical series: Okabe–Ito; never red/green as categories. Hex values are a proposal; ux-expert may tune but must keep the ratios.

### 7.3 Density, spacing, shape

4px grid; gutters 24px desktop / 16px mobile; tables use full content width. Radius 4px controls/badges, 6px panels/popovers; no 9999px. No elevation except popovers/menus/dialogs. Motion: colour/opacity ≤120ms, no transforms, respect `prefers-reduced-motion`.

### 7.4 Tables

1. 32px default rows, compact 28px toggle. 2. 6px inline padding; single-line cells; ticker + name (`--fs-meta`/`--text-3`) on one line where width allows. 3. Header `--surface-2`, `--fs-meta`, 500, `--text-2`, sentence case, sticky; identifier column sticky on horizontal scroll. 4. Hairline dividers only, no zebra, no card shadow, ≤6px outer radius. 5. Numeric cells + headers: physical `text-align: right`, `dir="ltr"`, nowrap, tabular. 6. Text cells + headers: `text-align: start`. 7. Units once in the header ("Revenue (EGP m)"); consistent decimals per column. 8. Missing: "—" in `--text-3` with the INSUFFICIENT_DATA reason as tooltip; never 0 or blank. 9. Whole header is the sort button with ▲/▼ and `aria-sort`; hover row tint `--surface-2`. 10. Direction: `+2.31%` gain, `−1.80%` loss; shape optional in cells, mandatory where no sign (stance). 11. Meta line above each table (count, filter, as-of, source); methodology/version footnote below.

### 7.5 Charts

Never mirror in RTL (wrap in `dir="ltr"`). 1.5px lines, no area gradients, no 3D, no pies for >5 parts or time series. Horizontal gridlines only (`--border`); axis `--fs-micro` `--text-3` tabular. Direct end-of-line labels over legends. Estimates/reference levels dashed and muted; actuals solid. Up/down bars `--gain`/`--loss`; multi-series Okabe–Ito. As-of + source caption on every chart.

### 7.6 Components

- Hero/key stats: label-over-value strip with hairline dividers (6–8 stats), not hover-lift card grids.
- Badges: text-first, 4px radius, `--surface-2` or semantic `-bg` tint. Stance = shape + localised word + confidence; no certainty words (AGENTS.md 10). Shariah: our verdict and EGX33 as two labelled items, no ☪/✓/✕.
- Icons: one SVG set, one stroke width, actions only (search, sort, external link, info, menu), with text in nav; library choice for architect/staff-frontend.
- Notices: one neutral style, 1px border + icon; severity via icon and wording, no coloured stripe or gradient.
- Language toggle: plain segmented control "English | عربي" in the sidebar footer.
- States: table-shaped skeletons; distinct empty / no-match / error copy; retry inside the failed widget.

### 7.7 Do-not rules

1. No gradients, glow, `backdrop-filter`, gradient text or decorative glyphs (◈ ▸ ◂).
2. No emoji or pictographs as icons (✓ ✕ ☪ ⚠ ↻); one SVG set with text labels.
3. Brand accent is never green or red.
4. Gain, loss and verdicts never by colour alone.
5. No cards for tabular data, no cards in cards, no hover-lift KPI card grids.
6. No uppercase or letter-spacing on labels in either language.
7. No pill radius, nothing above 6px; no hover translate/shadow animations.
8. Never mirror numbers or charts; never `text-align: end` on numbers; never mix Eastern and Western digits (Western via `ar-EG-u-nu-latn`).
9. No status dots, "Live" or "AI" badges unless mapped to real computed state; no vague copy.
10. Never blank or zero a missing value — "—" plus the INSUFFICIENT_DATA reason.

### 7.8 Arabic pairing and RTL summary

Plex Sans + Plex Sans Arabic (identical metrics and digit widths); fallback Noto Sans Arabic, system-ui. Same px sizes; Arabic line-heights +2–4px; `letter-spacing: 0`. `<html lang dir>` switch together; logical properties for layout, physical `right` only for numeric columns. Wrap tickers, Latin names, numbers, dates, versions in `dir="ltr"`; `dir="auto"`/`<bdi>` for database text. Mirror nav order, back/forward chevrons, progress, drawer side; don't mirror charts, ▲/▼, refresh, search, media controls. Every string through `t()` (`Companies.tsx` is English-only today).

## 8. Gaps (`no data`)

EGX official site conventions (CAPTCHA, not bypassed); Thndr in-app UI; Koyfin tab names/density; TradingView/Yahoo/Morningstar/SWS gain-loss hex and spacing tokens; whether Arabic needs larger px; Noto Kufi Arabic digit metrics; controlled studies on density/slop effects (slop sources are practitioner/vendor blogs except Anthropic and NN/g); hashed CSS URLs will rot (values captured 2026-10-23).

## 9. Open points (not blocking)

Stance copy wording (Buy/Hold/Reduce vs "lean") — PM/UX under AGENTS.md 10; icon and charting library choice — architect/staff-frontend; optional Eastern-digit setting (evidence favours Western default).

NEXT: ux-expert
