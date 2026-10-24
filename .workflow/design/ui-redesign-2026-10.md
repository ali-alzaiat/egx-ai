# UI redesign spec, 2026-10 (ux-expert: Salma)

**Inputs:** `research/ui-ux-direction-2026-10.md` (Nadia), `decisions/R43-show-data-not-forms.md`, `decisions/R42-signal-rules-2-and-egx33-shariah.md`, the previous `design/watchlist-alerts-events-ux.md` (W1–W3, A1–A4 and E1–E3 still apply), and the source under `frontend/src`.

**Live walk:** done on 2026-10-23 in the built-in browser against `http://localhost:5173` with the backend on :8000.
- Desktop (1280 and 1024 px) and mobile (375 px), in English and Arabic.
- Only GETs through the Vite proxy; nothing was written to the database.
- Language switched back to English and viewport reset to desktop afterwards.

---

## 0. What the live walk found (this is why the spec is shaped this way)

| # | Screen / action | Friction (evidence) | Fixed by |
|---|---|---|---|
| F1 | Any page at 1024–1280 px | The page scrolls sideways. `scrollWidth` was 1450 on a 1280 viewport and 1380 on 1024. Cause: `.main-content { flex:1 }` has no `min-width:0`, so wide tables push the sidebar margin off screen. | §3.1 |
| F2 | Phone (375 px) | There is no navigation at all: `.sidebar` is `display:none` and nothing replaces it. The radar table is cut off after the Stance column. | §1.3 |
| F3 | Arabic mode | 18 of 24 pages and all 5 shared components never call `useLang`: Companies, Dashboard, Rankings, all hub tabs except Signals/Statements/Ratios, Watchlists, Alerts. In Arabic, Companies shows English headers and "REDUCE ▼" in an RTL frame. | §4, §6 |
| F4 | Arabic tables (Recommendations) | `th` is computed `text-align:left` while `td` is `start`, so the headers sit on the opposite side from their cells. Latin names are cut off at the wrong end ("…rcial International Bank Egypt (CIB) S.A.E") and trailing punctuation jumps to the front (".Orascom Development Egypt S.A.E"). | §6 |
| F5 | Companies, ACAP row | ACAP has no price and no inputs, but its stance shows "● HOLD". The API returns `confidence:0, reasons:[]`, and the limitation reads "No engine produced an input: stance defaults to hold". This presents a non-assessment as a stance. | §5.1 "Not assessed" |
| F6 | Companies, Shariah column | It shows "—" on every row, including EGX33 members (ADIB, AMOC). The overview endpoint carries no Shariah block, so a reader takes "—" to mean "not compliant". | §4.3 |
| F7 | Companies, sector filter | All six options return 0 rows. The options are hard-coded, and `sector` is null on 200 of 200 companies in the API. The filter is dead. | §4.3 (remove it) |
| F8 | Company hub, ETEL | The **Financial Data** tab says "No income statement facts recorded for ETEL yet". The **Statements** tab shows full 2021–2025 income, balance and cash-flow lines. **Signals** says "Technical-only stance: no fundamentals available yet". Three tabs disagree with each other. | §1.4 (one Financials tab), R43 M1 |
| F9 | Company hub, Overview | The first full screen is a meta "Data quality" card with progress bars. Price, change, stance and Shariah are not visible without scrolling. There is no daily change, no chart, and 50 raw OHLC rows. | §4.4.1 |
| F10 | Hub tab strip | 13 tabs in one row. Tab pages have three different headers: none (Signals, Statements, Ratios), "Financial Data - ETEL" and "Technical Analysis — ETEL". | §1.4 header |
| F11 | Two meanings of "score" | Companies "Score 75.8 · STRONGEST" for ABUK is the price-momentum rank (0–100). Recommendations "Composite score 80.0" for ABUK is the stance composite (−100..+100). Both columns are labelled "score". | §4.2, §4.3, §4.5 naming |
| F12 | Rankings | Max drawdown renders as "▲ +10.1%" in the gain colour; a 10% drawdown is a loss (`factors.py::_max_drawdown` returns a positive fraction). Trend alignment, an index from −1 to 1, renders as "▲ +100.0%" on every leader. `SociÃ©tÃ© Arabe…` is mojibake (a data defect). | §4.5 |
| F13 | Ratios | Mixed precision: "42%" next to "27.7%", current ratio "0.5075" next to leverage "1.18". The raw reason "(missing:eps)" is shown. The earlier 100× scaling bug (4,203.4%) is already fixed in the uncommitted working tree (`pages/Ratios.tsx`). | §2.6, §4.4.3 |
| F14 | Statements | Each year is stacked as three separate tables, so one line cannot be compared across years. Values are in full units ("106,672,946,000"). "Provisional" is repeated on every row. | §4.4.3 |
| F15 | Valuation, Disclosures | Internals are shown as content: `resolved_affo_source=fcf (unknown source)`, `fcfe_two_stage`, weight "0.6", "MISSING". Disclosures prints `metric / revenue / ttm / status / INSUFFICIENT_DATA / delta_pct` as a key/value dump. | §4.4.4, §4.4.7 |
| F16 | Signals | The disclaimer appears in both languages at once ("Research calculation — not investment advice · حساب بحثي…") and appears twice. Reasons and limitations are English free text even in Arabic. Dictionary strings use Eastern digits ("٢٠ جلسة", "٥٠٠ ألف", "١٫٥×") next to Western digits. | §5, §6, §8 |
| F17 | Shariah screening list | The only row's ticker is a raw UUID (`22805785-2b6e-…`, a company missing from the 234-company universe). | §4.6 |
| F18 | Alerts, Events | The company picker is a native `<select>` with 234 options. Alerts never fire on their own (R43 OUT: no trigger wiring), and the page does not say so. | §4.8, §4.9 |
| F19 | Recommendations | The subtitle says "ranked by value traded", but no value-traded column exists. Prices have mixed decimals ("87", "24.5", "1.14"). The composite uses a hyphen ("-20.0"). Rows are 66 px tall. | §4.2 |
| F20 | Every page | Body font is Inter, Arabic is Cairo. The theme is a dark navy glow with gradients and `backdrop-filter`. The `<title>` is the same on every route. | §2, §3 |

---

## 1. Information architecture

### 1.1 Routes (old → new)

| New route | Content | Old route(s) → behaviour |
|---|---|---|
| `/` | Dashboard | same |
| `/recommendations` | Recommendations radar | same |
| `/rankings` | Momentum rankings | same |
| `/companies` | Companies list | same |
| `/screening` | Shariah screening list | same |
| `/watchlists`, `/alerts`, `/events` | same pages | same |
| `/companies/:ticker` | Hub › Overview | same |
| `/companies/:ticker/price` | Hub › Price & signals | `/signals`, `/technical` → `<Navigate replace>` |
| `/companies/:ticker/financials` | Hub › Financials › Statements | `/statements` → redirect. The old Financial Data page is retired (F8). |
| `/companies/:ticker/financials/ratios` | › Ratios | `/ratios` → redirect |
| `/companies/:ticker/financials/metrics` | › Metrics | `/metrics` → redirect |
| `/companies/:ticker/financials/quality` | › Data quality | new (DataQualityCard moves here) |
| `/companies/:ticker/valuation` | Hub › Valuation (fair value and investment score) | `/score` → `/valuation#score` |
| `/companies/:ticker/shariah` | Hub › Shariah | `/screening` (company level) → redirect |
| `/companies/:ticker/peers` | Hub › Peers | same |
| `/companies/:ticker/thesis` | Hub › Thesis & filings | `/disclosures` → `/thesis#filings` |
| `/companies/:ticker/ai` | **removed**, no redirect; falls to Not found (R43 AC-8) | |
| `/admin` → `/admin/market` | Admin | |
| `/admin/market`, `/admin/intake`, `/admin/disclosures`, `/admin/peers`, `/admin/thesis` | Admin sections | `/intake` → `/admin/intake` |
| `*` | Not found page | new |

Two files are deleted:
- `pages/AIInsights.tsx` and `.css`.
- `pages/PendingFinancialData.tsx`. It is unused and its copy ("ingestion layer is not built yet") is false.

`pages/FinancialData.tsx` leaves the hub. If the architect's M1 contract keeps legacy facts that are not in statement lines, those facts surface in Thesis & filings › "Facts with provenance". They do not get their own tab.

### 1.2 Sidebar (≥1024 px, 224 px wide, sticky on the inline-start edge)

From top to bottom:
1. **Wordmark:** "EGX AI" in plain text, `--fs-h3` 600, `--text`. No glyph, no gradient. It links to `/`.
2. **Company search:** combobox, full width, 32 px tall. Placeholder "Search ticker or company" / "ابحث بالرمز أو اسم الشركة". The shortcut hint "Ctrl K" is shown as plain `--text-3` text at the inline-end edge. Spec in §3.3.
3. **Groups.** Each group label is `--fs-meta`, 500, `--text-3`, sentence case, 16 px above and 4 px below. Each item is 32 px tall, `--fs-ui`, with 12 px inline padding.
   - **Markets / السوق:** Dashboard / لوحة المعلومات · Recommendations / الترشيحات · Momentum rankings / ترتيب الزخم
   - **Research / البحث:** Companies / الشركات · Shariah screening / التصفية الشرعية
   - **Tracking / المتابعة:** Watchlists / قوائم المتابعة · Alerts / التنبيهات · Events / سجل الأحداث
4. **Active item:** `--accent-bg` background, `--accent` text, 600 weight, `aria-current="page"`. No stripe, no green. Hover: `--surface-2`. Hub routes keep "Companies" active.
5. **Footer,** pinned to the bottom:
   - Language segmented control "English | عربي". Each option carries its own `lang`. Aria label "Language" / "اللغة".
   - Theme segmented control "System | Light | Dark" / "النظام | فاتح | داكن".
   - Text link "Admin" / "الإدارة" in `--fs-meta`, `--text-2`.

### 1.3 Narrow screens

- **Below 1024 px:** the sidebar is hidden and replaced by a top bar.
- **Top bar:** 48 px tall, sticky, `--surface`, with a 1 px bottom border `--border`.
  - Inline-start: menu button (icon plus visually hidden "Menu" / "القائمة"), 40×40 px.
  - Then "EGX AI".
  - Inline-end: search button (icon, 40×40). It opens the search as a full-width overlay field under the bar, with autofocus.
- **Menu:** opens a drawer from the inline-start edge, 280 px wide, with the same groups and footer as the sidebar, over a scrim (`--scrim`).
  - It closes on Esc, a scrim click, route change, or the "Close" / "إغلاق" button.
  - Focus is trapped while open and returns to the menu button on close.
  - The body does not scroll while open.
- **Below 768 px:** wide tables switch to card lists (§3.4). Gutters are 16 px.

### 1.4 Company hub

**Header.** Not sticky; scrolls away. One component, `CompanyHeader`, rendered once by a hub layout route (`/companies/:ticker/*` with `<Outlet/>`). No tab page renders its own title any more.

- **Line 1:**
  - Ticker: `--fs-h2` 600, `dir="ltr"`, `--text-2`.
  - Then the company name as `<h1>` at `--fs-h1`. In Arabic, use `name_ar` when it is non-null. Today it is null on 200 of 200 rows, so the Latin name is shown in `<bdi dir="ltr" lang="en">`.
- **Line 2,** a stat strip (§3.5) with 4 items:
  1. **Last close:** "133.90" `--fs-figure`, then "EGP" `--fs-meta`.
  2. **Change:** "▼ −7.05 (−5.00%)" in `--loss` (or ▲ "+…" in `--gain`; "0.00 (0.00%)" in `--neutral`), with sub-line "vs previous close · 22 Oct 2026".
     - Computed client-side from the two most recent non-placeholder bars of the prices query already loaded for the chart.
     - Placeholder bars (O=H=L=C, volume 0) are skipped, the same filter as `CompanyDetail.tsx`.
     - With fewer than 2 bars, show "—" plus a tooltip "Not enough price history" / "سجل الأسعار غير كافٍ".
  3. **Stance:** StanceBadge (§5.1), then "Confidence 28/100".
  4. **Shariah:** ShariahPair, compact form (§5.2).
- **As-of line** (`--fs-meta`, `--text-3`): "Prices as of 22 Oct 2026 (end of day) · stance rules signal-rules-2.0".
- **Removed:** the "Refresh market data" button (moved to Admin).

**Tab strip.** Sticky at `top:0` (`top:48px` under the mobile top bar), `--surface` background, 1 px bottom border. Tabs are route links: `<nav aria-label>` with `aria-current`, not ARIA tablist. Each is 40 px tall, `--fs-ui`. The active tab has 600 weight, `--text`, and a 2 px bottom border in `--accent` (an underline, not a card stripe). Inactive tabs use `--text-2`.

On narrow screens the strip scrolls horizontally, with no wrapping, no scrollbar and no arrows, and the active tab is scrolled into view on mount.

| # | Tab EN / AR | Path | Built from (current files) |
|---|---|---|---|
| 1 | Overview / نظرة عامة | `` | parts of `CompanyDetail.tsx` plus summary blocks |
| 2 | Price & signals / السعر والإشارات | `/price` | `Signals.tsx` + `TechnicalAnalysis.tsx` (read-only) + price table from `CompanyDetail.tsx` |
| 3 | Financials / البيانات المالية | `/financials[/ratios\|/metrics\|/quality]` | `Statements.tsx`, `Ratios.tsx`, `FinancialMetrics.tsx` (read-only), `DataQualityCard.tsx` |
| 4 | Valuation / التقييم | `/valuation` | `Valuation.tsx` minus the form + `FairValueCard` + `SensitivityTable` + `InvestmentScore.tsx` (read-only) |
| 5 | Shariah / الشرعية | `/shariah` | `ShariahScreening.tsx` minus the three forms |
| 6 | Peers / الشركات المماثلة | `/peers` | `PeersTab.tsx` minus the edit form |
| 7 | Thesis & filings / الفرضية والإفصاحات | `/thesis` | `Thesis.tsx` minus assess and update forms + `Disclosures.tsx` minus register, upload and parse |

### 1.5 Admin (`/admin`)

- **Header:** "Admin" / "الإدارة". Notice (§3.8): "Maintenance and data-entry tools. Actions here write to the database." / "أدوات الصيانة وإدخال البيانات. الإجراءات هنا تكتب في قاعدة البيانات."
- **Sub-navigation:** a route-based tab strip with the same style as the hub:
  - Market data / بيانات السوق (`/admin/market`, the default)
  - Filings intake / إدخال القوائم الرسمية
  - Disclosures / الإفصاحات
  - Peer lists / قوائم الشركات المماثلة
  - Thesis updates / تحديثات الفرضية
- **Per-company sections** (disclosures, peers, thesis) start with a CompanyPicker (§3.3). The picked ticker goes in `?ticker=`, and the section form renders only after a pick.
- **Not shown in the main sidebar groups;** reachable only from the footer link.

---

## 2. Token sheet

Replace the whole `:root` block in `index.css`. Drop the Inter, JetBrains Mono and Cairo `@import`.

### 2.1 Fonts

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Sans+Arabic:wght@400;500;600&family=IBM+Plex+Mono:wght@400&display=swap">
```

Put this in `index.html` `<head>`, not as a CSS `@import`, which blocks rendering.

### 2.2 Light theme (default) plus shared tokens

```css
:root {
  color-scheme: light;
  /* surfaces */
  --bg:#F6F6F3; --surface:#FFFFFF; --surface-2:#EFEFEB;
  --border:#DCDCD5; --border-strong:#878A83;
  /* text */
  --text:#16181B; --text-2:#474B52; --text-3:#62666E;
  /* brand + state */
  --accent:#2A4A7F; --accent-bg:#E9EEF6;
  --gain:#0A7A3E; --gain-bg:#E8F3EC;
  --loss:#C1272D; --loss-bg:#FBEAEA;
  --warn:#8A5300; --warn-bg:#FBF1E1;
  --neutral:#5B6068;
  --focus:var(--accent);
  --scrim:rgba(22,24,27,.40);
  --shadow-pop:0 4px 16px rgba(22,24,27,.12);
  /* chart series (Okabe–Ito, darkened for ≥3:1 on white) */
  --series-1:#0072B2; --series-2:#9A5B00; --series-3:#8E4A75; --series-4:#6B6F76;
  --chart-grid:var(--border); --chart-axis:var(--text-3); --chart-ref:var(--text-3);

  /* type */
  --font-ui:"IBM Plex Sans","IBM Plex Sans Arabic","Noto Sans Arabic",system-ui,sans-serif;
  --font-code:"IBM Plex Mono",ui-monospace,monospace; /* methodology versions/IDs only */
  --fs-micro:11px; --lh-micro:14px;
  --fs-meta:12px;  --lh-meta:16px;
  --fs-table:13px; --lh-table:18px;
  --fs-ui:14px;    --lh-ui:20px;
  --fs-read:16px;  --lh-read:24px;
  --fs-h3:16px;    --lh-h3:22px;
  --fs-h2:20px;    --lh-h2:28px;
  --fs-h1:24px;    --lh-h1:32px;
  --fs-figure:28px;--lh-figure:32px;
  --tracking-heading:-0.01em;

  /* space (4px grid) */
  --space-1:4px; --space-2:8px; --space-3:12px; --space-4:16px; --space-5:20px;
  --space-6:24px; --space-8:32px; --space-10:40px; --space-12:48px;
  --gutter:24px;

  /* shape + size */
  --radius-sm:4px;   /* controls, badges, inputs */
  --radius-md:6px;   /* panels, table frame, popovers, drawer */
  --control-h:32px; --row-h:32px; --row-h-compact:28px;
  --sidebar-w:224px; --topbar-h:48px; --content-max:1440px;

  /* motion + layers */
  --dur:120ms; --ease:ease-out;
  --z-sticky:10; --z-drawer:40; --z-popover:50; --z-toast:60;
}
@media (max-width: 767px) { :root { --gutter:16px; --control-h:40px; } }
```

### 2.3 Dark theme (follows the OS; manual override wins)

```css
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { /* same block as below */ } }
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg:#0F1012; --surface:#16171A; --surface-2:#1E2024;
  --border:#2B2D32; --border-strong:#666A73;
  --text:#E7E8EA; --text-2:#B3B6BC; --text-3:#8E929A;
  --accent:#9DB7E6; --accent-bg:#1C2433;
  --gain:#45C07A; --gain-bg:#14261C;
  --loss:#F07A72; --loss-bg:#2A1716;
  --warn:#E3A64A; --warn-bg:#2A2112;
  --neutral:#A3A7AE;
  --scrim:rgba(0,0,0,.60);
  --shadow-pop:0 4px 16px rgba(0,0,0,.50);
  --series-1:#56B4E9; --series-2:#E69F00; --series-3:#CC79A7; --series-4:#9AA0A8;
}
```

**Theme state:** `localStorage["egx-theme"]` holds `"system" | "light" | "dark"`, read inside try/catch like `egx-lang`. `system` removes `data-theme`. Light and dark set `<html data-theme>`. Set it before React mounts (a 3-line inline script in `index.html`) so the page does not flash the wrong theme.

### 2.4 Arabic overrides

```css
html[lang="ar"] {
  --font-ui:"IBM Plex Sans Arabic","IBM Plex Sans","Noto Sans Arabic",system-ui,sans-serif;
  --lh-micro:16px; --lh-meta:18px; --lh-table:20px; --lh-ui:22px; --lh-read:26px;
  --lh-h3:26px; --lh-h2:32px; --lh-h1:36px; --lh-figure:32px;
  --tracking-heading:0;
}
```

### 2.5 Contrast (WCAG, computed 2026-10-23)

These are the research values, which I kept unchanged. The tokens I added were checked:

| Pair | Light | Dark |
|---|---|---|
| `--text-3` on `--bg` | 5.32 | 6.10 |
| `--text-3` on `--surface-2` | 5.00 | 5.23 |
| `--text-2` on `--surface-2` | 7.60 | 8.03 |
| `--accent` on `--accent-bg` (active nav, Shariah "passes") | 7.56 | 7.67 |
| `--text-3` on `--accent-bg` | 4.95 | 4.99 |
| `--warn` on `--warn-bg` | 5.66 | 7.41 |
| `--neutral` on `--surface-2` | 5.49 | 6.76 |
| `--border-strong` on `--bg` / `--surface` (control edges, ≥3:1) | 3.24 / 3.50 | 3.51 / 3.31 |
| `--focus` ring on `--bg` | 8.13 | 9.38 |
| series 1–4 on `--surface` (≥3:1 graphics) | 5.19 / 5.43 / 6.20 / 5.05 | 7.77 / 7.96 / 5.86 / 6.80 |

### 2.6 Global type and number rules

- **Base:** `body { font: 400 var(--fs-ui)/var(--lh-ui) var(--font-ui); background: var(--bg); color: var(--text); }`. No gradient and no `background-attachment`.
- **Weights:** 400, 500 and 600 only. Headings h1–h3 use 600 with `letter-spacing: var(--tracking-heading)`.
- **No uppercase transforms anywhere.** Remove every `text-transform: uppercase` and every positive `letter-spacing` (F20).
- **Focus:** `:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }`. Never removed.
- **Motion:** colour and opacity only, `var(--dur) var(--ease)`, no transforms. Under `prefers-reduced-motion: reduce`, transitions and animations are 0 ms.
- **Tabular digits:** `.num, .figure, td.num, th.num, .stat-value { font-variant-numeric: tabular-nums lining-nums; }`.
- **Formatting:** one module, `src/lib/format.ts`, merged with `i18n/format.ts`. Every helper takes `locale` from `useLang()`:

| Helper | Rule | Example EN | Example AR |
|---|---|---|---|
| `fmtPrice(v)` | 2 dp always | 133.90 | 133.90 |
| `fmtChange(abs, pct)` | sign always, U+2212 minus, 2 dp abs, 2 dp % | −7.05 (−5.00%) | same digits |
| `fmtPct(v)` (decimal input) | 1 dp fixed (`minimumFractionDigits:1`) | 42.0% | 42.0% |
| `fmtSignedPct(v)` | sign always, U+2212 | +63.1% / −14.3% | same |
| `fmtRatio(v)` (x-multiples) | 2 dp | 1.18 / 0.51 | same |
| `fmtInt(v)` | grouping, 0 dp | 4,461,086 | 4,461,086 |
| `fmtEgpMillions(v)` | full units ÷ 1e6, 1 dp, grouping | 106,672.9 | same |
| `fmtEgpCompact(v)` | ≥1e9 "bn" 2 dp, ≥1e6 "m" 1 dp, else K | EGP 237.9m | 237.9 مليون ج.م |
| `fmtScore(v)` (composite) | signed integer | +40 / −20 | same |
| `fmtDate(iso)` | `Intl.DateTimeFormat(locale,{day:"numeric",month:"short",year:"numeric",timeZone:"UTC"})`; date-only strings parsed as UTC | 22 Oct 2026 | 22 أكتوبر 2026 |
| `fmtCycle("2026-08")` | month and year | Aug 2026 | أغسطس 2026 |

- **Missing values:** any helper given `null`, `undefined`, `""` or a non-finite number returns `null`. The caller renders `<Missing reason=…/>` (§3.6). Never "0", "NaN" or "Never". `formatAsOf`'s English "Never" goes away.
- **Locale:** stays `ar-EG-u-nu-latn` for Arabic, so digits are Western.

---

## 3. Shared components (`src/components/ui/`, so pages stop restyling basics)

### 3.1 AppShell

- **Root:** `.layout` uses `display:grid; grid-template-columns: var(--sidebar-w) minmax(0,1fr)` at ≥1024 px. Below 1024 px it is one column with the top bar.
- **Main:** `main { min-width:0; padding: var(--space-6) var(--gutter); max-width: var(--content-max); }`. This fixes F1. Every table is wrapped in `.table-wrap { overflow-x:auto; }`, so only the table scrolls, never the page.
- **Sidebar:** `position: sticky; top:0; height:100dvh; overflow-y:auto`, placed in the grid. No `position:fixed` and no margin hacks, so RTL works without overrides.
- **Document title:** set per route as "{Page} · EGX AI", and "{TICKER} {Name} · {Tab} · EGX AI" in the hub (F20). Use React 19 `<title>` in the page component.

### 3.2 PageHeader

- **Content:** `<h1>` at `--fs-h2`, plus an optional one-sentence subtitle at `--fs-ui` in `--text-2`, plus an optional actions slot at inline-end.
- **Spacing:** 24 px below.
- **Not allowed:** cards, gradient or logo glyph.

### 3.3 CompanySearch and CompanyPicker (one combobox, two modes)

**Data:** `useCompanies({search:q, page_size:8})`, debounced 150 ms, starting from 1 character. Exact ticker match is sorted first.

**Row layout:** ticker (500, `dir=ltr`), then the name in `--text-3`. In Arabic, the name is `name_ar` when present, otherwise `<bdi>`.

**Keyboard and ARIA:** Up/Down moves, Enter selects, Esc clears and closes. Follow the ARIA 1.2 combobox pattern (`role=combobox`, `aria-expanded`, `aria-activedescendant`, listbox options).

**Global shortcuts:** `/` and `Ctrl/⌘+K` focus the search, unless focus is already in an input or textarea.

**Modes:**
- Search mode (sidebar): Enter navigates to `/companies/:ticker`.
- Picker mode (Alerts, Events, Watchlists add, Admin): calls `onSelect(company)`, shows the chosen "TICKER — Name" as the value, and has a clear button.

**Result states:**
- No results: "No company matches "{q}"" / "لا توجد شركة تطابق "{q}"".
- Error: "Search is unavailable. Retry" / "البحث غير متاح. إعادة المحاولة".

**Replaces:** the 234-option native selects in Alerts and Events (F18), and the raw-UUID peer field.

### 3.4 DataTable

**Column definition:** `{ id, header, type: "text"|"num", align?, sortable?, width?, sticky? }`.

**Cells:**
- Rows are `--row-h` (32 px). A compact toggle sets `--row-h-compact` (28 px) and is remembered in `localStorage["egx-density"]`.
- Cells have 6 px inline padding, `--fs-table`, are single-line with `white-space:nowrap`, and use `text-overflow:ellipsis` on text cells with the full text in `title`.
- A stock cell is "TICKER" (500, `--text`) and "Name" (`--fs-meta`, `--text-3`) **on one line**. Below 1280 px the name truncates. This replaces the stacked 66 px rows (F19).

**Headers:**
- Background `--surface-2`, text `--fs-meta` 500 `--text-2`, sentence case.
- Sticky at the top of `.table-wrap`. The first column is sticky on horizontal scroll (`inset-inline-start:0`, with a `--surface` background).

**Alignment and borders:**
- Numeric `th` and `td` use physical `text-align:right`, `dir="ltr"` and tabular digits.
- Text `th` and `td` use `text-align:start`, and must be set explicitly on `th` to override the browser default (F4).
- 1 px `--border` row dividers. No zebra striping. The outer frame is 1 px `--border` with `--radius-md`. No shadow. Hover row is `--surface-2`.

**Sorting:**
- The entire header cell is a `<button>` with a sort icon, and the `th` carries `aria-sort`.
- Clicking cycles descending, then ascending, then the default order.
- Sort state is mirrored in the URL (`?sort=col&dir=desc`).

**Meta and footer:**
- Meta line above the table: `--fs-meta` `--text-3`, e.g. "50 stocks · prices as of 22 Oct 2026 · rules signal-rules-2.0".
- Footnote below: methodology and version.

**Mobile (<768 px):** when the page passes `cardFields` (exactly 4 fields), each row renders as a `<li>` card instead of a table.
- Line 1: the stock cell.
- Lines 2–3: two label/value pairs per line.
- Line 4: the fourth field.
- Cards are separated by a 1 px divider (not boxed), and the whole card is a link when the row has one.

**Loading:** a skeleton of 8 rows at the real row height, with `--surface-2` bars and no shimmer animation when `prefers-reduced-motion` is set. Add an `aria-busy` and visually-hidden "Loading {thing}…" / "جارٍ تحميل {thing}…".

### 3.5 StatStrip

- **Item:** label (`--fs-meta` `--text-3`) over value (`--fs-table` or `--fs-figure` for the hero, tabular).
- **Layout:** items separated by 1 px `--border` inline dividers, 6–8 items per row, wrapping on small screens to a 2-column grid.
- **Not allowed:** cards, hover lift or icons.

### 3.6 Missing

- Renders "—" in `--text-3` with `title` = the localized reason, plus a visually-hidden reason for screen readers.
- Reason mapping: `missing:<line>` → "Missing line: {line label}" / "بند غير متوفر: {line label}". Unknown free-text reasons pass through (see §8).

### 3.7 Badges

- `--radius-sm`, padding 0 6 px, height 20 px, `--fs-meta` 500. Text always comes first.
- Variants: StanceBadge (§5.1), ShariahBadge (§5.2), and `Tag`, which is neutral: `--surface-2` with `--text-2`. Tags are used for "Provisional", "Low liquidity", "EGX33 member" and tiers.
- No pills and no uppercase.

### 3.8 Notice

- Style: 1 px `--border` (or `--warn` border for warnings), `--surface` background, `--radius-md`, a 16 px SVG icon at inline-start (info or warning), `--fs-ui` text.
- One style only. No coloured stripe, no gradient, no "!" or "⚠" glyphs.

### 3.9 Empty, NoMatch and Error states (inside the widget that failed, never full page)

- **Empty:** one sentence saying why the area is empty and what makes it fill. No buttons.
- **NoMatch:** "No {things} match these filters." plus a "Clear filters" / "مسح الفلاتر" text button.
- **Error:** "Couldn't load {thing}." / "تعذّر تحميل {thing}." plus a "Retry" / "إعادة المحاولة" button calling `refetch()`. Use `role="alert"`.

### 3.10 Other components

- **Segmented control:** 32 px tall, 1 px `--border-strong` frame, `--radius-sm`. The selected option uses `--accent-bg` with `--accent` text. It is a radio group (`role=radiogroup`).
- **Disclosure:** "Technical details" / "تفاصيل فنية" `<details>` for raw keys, versions and assumption strings. It is collapsed by default and is the only place raw codes may appear.
- **Info popover:** an `i` icon button that opens a popover (`--shadow-pop`, `--radius-md`, max 320 px) with the definition. Used beside the composite, confidence, momentum score, ATR band and purification.
- **PriceChart:** hand-written SVG, no new dependency.
  - Props: `bars` (date, close), optional `refLines:[{value,label}]`, height 240 desktop / 180 mobile.
  - Drawing: a 1.5 px `--series-1` close line, 4 horizontal gridlines in `--chart-grid`, y-axis labels at the inline-end side in `--fs-micro` `--chart-axis` tabular, x-axis month ticks.
  - Reference lines are dashed `--chart-ref` with a text label at the line end.
  - Hover crosshair shows a tooltip "22 Oct 2026 · 133.90". On keyboard focus, Left/Right steps through days.
  - Caption: "Daily close, EGP · source: {data source} · as of {date}".
  - Range segmented control 3M · 6M · 1Y. One query: `useCompanyPrices(id,{start_date: 1y ago, page_size: 300})` (the backend allows up to 1000). The client slices the 3M and 6M ranges.
  - Wrapped in `dir="ltr"` and never mirrored.
- **Icons:** about 10 inline SVG components in `components/ui/icons.tsx`: search, menu, close, sort, external-link, info, warning, chevron, triangle-up, triangle-down and bar. All 16 px with a 1.5 px stroke and `currentColor`. No icon library; that is one less dependency. Icons are for actions only; navigation stays text-only.
- **Pagination:** "Previous" and "Next" buttons plus "Page 1 of 12 (234 companies)" / "صفحة 1 من 12 (234 شركة)". The previous/next labels swap semantic direction in RTL, and the chevrons mirror.

---

## 4. Per-screen layout

Copy is given as "EN" / "AR". Every string goes into `i18n/dict.ts`. The test that both languages exist for every key stays.

### 4.1 Dashboard `/`

- **Header:** "Market overview" / "نظرة على السوق". Subtitle: "Prices, model stances and momentum leaders for EGX-listed companies." / "الأسعار ومواقف النموذج وأقوى الأسهم زخماً في البورصة المصرية."
- **Stat strip** (data: `useSignalCoverage`, `useDataSources`, `useStanceRadar(50)`):
  - Latest close date / تاريخ آخر إغلاق: "22 Oct 2026"
  - Companies with prices / شركات لها أسعار: "199 of 234"
  - Most-traded 50: stances / مواقف أكثر 50 سهماً تداولاً: "▲ 4 · ▬ 4 · ▼ 42" (aria label "4 lean buy, 4 neutral, 42 lean reduce"). Counts come from the radar items. A null stance or zero coverage counts as "not assessed" and is shown only if more than 0.
  - Tracked companies / الشركات المتابَعة: "234"
- **Two tables side by side** at ≥1280 px, stacked below that:
  - **"Most-traded stocks"** / "الأسهم الأكثر تداولاً": the first 10 radar items.
    - Columns: Stock · Stance · Confidence · Last close (EGP) · Shariah (compact).
    - Footer link: "All 50 in Recommendations" / "الخمسون كاملةً في الترشيحات".
  - **"Momentum leaders"** / "الأعلى زخماً": `useSignals({limit:10})`.
    - Columns: # · Stock · Momentum score · Tier · 3M return.
    - Footer link: "Full momentum rankings" / "ترتيب الزخم كاملاً".
- **"Your tracking"** / "متابعتك": one line with links. "2 watchlists · 3 unacknowledged alerts" / "قائمتا متابعة · 3 تنبيهات غير مُقرّة". When empty: "No watchlists yet. Create one in Watchlists." / "لا توجد قوائم متابعة بعد. أنشئ واحدة من قوائم المتابعة." The counts come from `useWatchlists` and `useFiredAlerts({acked:false})`. Use proper Arabic dual and plural forms via a `plural(n, forms)` helper (§6.12).
- **Removed:** the four hover cards and the "STRONGEST" uppercase tiers.
- **States:** each block owns its skeleton, empty and error state.
  - Radar empty: "No stances yet. Stances are computed after the next price sync." / "لا توجد مواقف بعد. تُحتسب المواقف بعد مزامنة الأسعار التالية."
  - Signals empty: "No momentum scores yet. Scores are computed after the next price sync." / "لا توجد درجات زخم بعد. تُحتسب الدرجات بعد مزامنة الأسعار التالية."

### 4.2 Recommendations `/recommendations`

- **Header:** "Recommendations" / "الترشيحات". Subtitle: "Model stances for the 50 most-traded EGX stocks, ordered by 30-day average value traded. Research calculations under signal-rules-2.0, not advice." / "مواقف النموذج لأكثر 50 سهماً تداولاً في البورصة المصرية، مرتبة حسب متوسط قيمة التداول خلال 30 يوماً. حسابات بحثية وفق signal-rules-2.0، وليست نصيحة استثمارية."
- **Controls row:**
  - Stance segmented: All · Leans buy · Neutral · Leans reduce, each with a count ("Leans buy 4").
  - Checkbox "EGX33 Shariah members only" / "أعضاء مؤشر EGX33 الشرعي فقط".
  - Filter input "Filter by ticker or name" / "تصفية بالرمز أو الاسم", client-side.
  - Density toggle at inline-end.
  - All state goes in URL params.
- **Meta line:** "{n} stocks · prices as of {date} · rules signal-rules-2.0".
- **Columns:**

| Column | Notes |
|---|---|
| # / الترتيب | traded rank (server order) |
| Stock | ticker plus name, then `Tag` "Low liquidity" / "سيولة منخفضة" when `low_liquidity` is true (tooltip: "Average value traded below EGP 500K over 20 sessions" / "متوسط قيمة التداول أقل من 500 ألف ج.م خلال 20 جلسة") |
| Stance | StanceBadge |
| Confidence (0–100) / الثقة (0–100) | integer |
| Composite (−100 to +100) / المؤشر المركب (−100 إلى +100) | `fmtScore`, with an `i` popover |
| Last close (EGP) / آخر إغلاق (ج.م) | `fmtPrice`, 2 dp fixed (F19) |
| Upside ref. / مرجع الصعود | `fmtPrice` |
| Downside ref. / مرجع الهبوط | `fmtPrice` |
| Shariah / الشرعية | ShariahPair compact |

- **Sorting:** all columns sortable client-side (reuse `pages/companies/radarSort.ts`). The default is #.
- **Rows:** clicking a ticker goes to `/companies/:ticker/price`.
- **Mobile card fields:** Stock · Stance + confidence · Last close · Shariah.
- **Footnotes:**
  - "Upside and downside references are a volatility band (+2 / −1.5 × ATR14) around the last close, not a forecast." / "مرجعا الصعود والهبوط نطاق تذبذب (+2 / −1.5 × ATR14) حول آخر إغلاق، وليسا توقعاً."
  - "Confidence is capped at 50 when only price data is available." / "الثقة محدودة بحد أقصى 50 عندما تتوفر بيانات الأسعار فقط."
- **States:**
  - Empty: "No stances yet. Stances are computed after the next price sync."
  - NoMatch: "No stocks match these filters." + Clear filters.
  - Error: standard.

### 4.3 Companies `/companies`

- **Header:** "Companies" / "الشركات". Subtitle: "All {n} EGX-listed companies we track." / "جميع الشركات المدرجة التي نتابعها ({n})." Second line: "For ranked views see Momentum rankings and Recommendations." with both as links.
- **Controls:** a search input (URL `q`, 250 ms debounce) and nothing else.
  - **Remove the sector select (F7).** Re-add it only when `sector` is populated (NEEDS-BACKEND B6).
- **Meta line:**
  - Normal: "Showing 1–50 of 234 · prices as of 22 Oct 2026".
  - With search: "12 matches for "bank"" / "12 نتيجة لـ "bank"".
- **Page size:** 50, which is the overview cap.
- **Columns:**
  - Stock
  - Last close (EGP)
  - As of: `fmtDate`. When older than the market's latest price date, show it in `--warn` with tooltip "Older than the latest market close" / "أقدم من آخر إغلاق للسوق".
  - Stance + confidence (one cell, "▲ Leans buy · 28")
  - Momentum score (0–100) / درجة الزخم (0–100)
  - Momentum tier / فئة الزخم: sentence-case Tag
  - Gross margin, latest FY / هامش الربح الإجمالي (آخر سنة): `fmtPct`, missing → `<Missing>`
  - Shariah, **only once** `/companies/overview` returns a Shariah block (NEEDS-BACKEND B2). Until then the column is not rendered at all; a column of "—" reads as "fails" (F6).
- **Coverage column removed.** Its status dots meant nothing; data quality lives in the hub.
- **Sorting:** only Ticker is sortable (server order).
- **Mobile card fields:** Stock · Last close + as-of · Stance · Momentum tier.
- **States:**
  - Empty (no companies): "No companies yet. The company list loads with the first market sync."
  - NoMatch: "No company matches "{q}"." + Clear.
  - Error: standard.

### 4.4 Company hub

#### 4.4.1 Overview

1. StatStrip from the latest bar: Open · High · Low · Volume · Value traded (EGP compact) · 52-week range (low–high from the 1Y prices) · Avg value traded, 20 sessions (from stance `liquidity`).
2. PriceChart, 1Y by default.
3. **"At a glance"** / "لمحة سريعة": a 3-column grid of plain sections, not cards. Each is a heading, two lines, and a text link. Below 1024 px they stack.
   - **Model stance:** badge, confidence and the first reason sentence. Link "Price & signals →".
   - **Shariah:** ShariahPair (full). Link "Shariah →".
   - **Fair value:** "Estimated fair value: EGP X under the stated methodology", or `<Missing>` with its reason. Link "Valuation →".
4. **"Data quality"** / "جودة البيانات": one line, "Prices 94/100 · Profile 70/100 · Statements not scored", linking to Financials › Data quality.
5. **"Profile"** / "الملف التعريفي": ISIN · Sector · Listing date · Shares outstanding · Free float as a definition list. Each null shows `<Missing reason="Not in our data yet">`. If all five are null (true for ETEL today), show one line instead: "ISIN, sector and share count are not in our data yet." / "رقم ISIN والقطاع وعدد الأسهم غير متوفرة في بياناتنا بعد."

The 50-row price table moves to Price & signals.

**Not-found state:** keep `CompanyNotFound`, with copy "No company with ticker "{t}"." / "لا توجد شركة بالرمز "{t}"." plus a CompanySearch.

#### 4.4.2 Price & signals

1. **Stance block:**
   - StanceBadge (large, 24 px).
   - "Confidence 28/100", with an `i` popover listing the caps: technical-only 50, low liquidity 30, statements older than 400 days 40.
   - "Composite +40 (−100 to +100)".
   - "Inputs: technical (40% of model weight). Missing: valuation, investment score." / "المدخلات: الفني (40% من وزن النموذج). غير متوفر: التقييم، درجة الاستثمار."
2. **"Why"** / "الأسباب": a bullet list from `reasons[].text`.
3. **"Limitations"** / "القيود": a bullet list from `limitations`. Drop any string that starts with "Research calculation", because the localized footer carries it (F16). Drop exact duplicates.
4. **"Reference levels"** / "المستويات المرجعية":
   - A 2-column table: Last close · Upside reference (+2 ATR) · Downside reference (−1.5 ATR) · ATR(14) · Horizon "Swing, 1–3 weeks" / "متأرجح، 1–3 أسابيع".
   - Beside it (below it on mobile), PriceChart 3M with dashed refLines for upside and downside.
   - Caption: "A volatility band around the last close, not a forecast or a price target." / "نطاق تذبذب حول آخر إغلاق، وليس توقعاً أو سعراً مستهدفاً."
5. **"Liquidity"** / "السيولة": "Avg value traded, 20 sessions: EGP 237.9m", plus the low-liquidity Tag when it applies.
6. **"Technical indicators"** / "المؤشرات الفنية": read-only table Indicator · Value · As of, from `useTechnicalIndicators` (computed on GET per R43).
   - Empty: "Indicators are computed after each price sync. None are stored for {TICKER} yet." / "تُحتسب المؤشرات بعد كل مزامنة أسعار. لا توجد مؤشرات مخزنة لـ {TICKER} بعد."
   - Remove the Calculate button.
7. **"Scenario values"** / "قيم السيناريوهات": a table Bear · Base · Bull. Each shows a value or `<Missing>` with its reason; when all three are missing, show one row with the reason.
   - Remove the "Price targets" wording (§5.3).
   - The risk reference row: "Risk reference level 124.81 (ATR-based)" / "مستوى مرجعي للمخاطر 124.81 (مبني على ATR)".
8. **"Daily prices"** / "الأسعار اليومية": DataTable Date · Open · High · Low · Close · Volume · Value traded, 20 rows per page. Note "Non-trading days are hidden." / "أيام عدم التداول مخفية."
9. **Footer:** "signal-rules-2.0 · as of 23 Oct 2026 · Research calculation, not investment advice." / "… · حساب بحثي، وليس نصيحة استثمارية." This appears **once**, in the current language only.

#### 4.4.3 Financials

A segmented control at the top: Statements / القوائم · Ratios / النسب · Metrics / المؤشرات · Data quality / جودة البيانات. These are route-based so they are linkable.

**Statements:**
- **Second segmented control:** Income statement · Balance sheet · Cash flows.
- **Meta line:** "Annual · EGP millions · newest first". When any period is vendor-sourced, add a Notice: "Provisional: vendor data (S&P Global via stockanalysis.com) until an official filing replaces it." / "مؤقت: بيانات مزوّد (S&P Global عبر stockanalysis.com) إلى أن تحل محلها القوائم الرسمية."
- **Table:**
  - Rows are lines in statement order (the first column is sticky).
  - Columns are fiscal years, up to 5, newest at inline-start. In RTL they mirror, so the newest is at the right.
  - Under each year header, a second header row shows the source per period: `Tag` "Provisional" / "مؤقت", or "Filing" / "قوائم رسمية" with an external link to the filing.
  - Cells use `fmtEgpMillions`, with U+2212 for negatives. Missing cells use `<Missing reason="Not reported in this source">`. The per-cell page reference goes in `title` ("Filing p. 12").
- **Fixes F14.**
- **Empty:** "No statements yet. Statements appear after an official filing is entered or vendor data is imported." / "لا توجد قوائم بعد. تظهر القوائم بعد إدخال قوائم رسمية أو استيراد بيانات المزوّد."

**Ratios:**
- **Meta line:** "Fiscal year 2025 · computed from statement lines · stmt-ratios-1.0".
- **Table:** Ratio · Value · Note.
  - Percent ratios use `fmtPct` (42.0%). Leverage and current ratio use `fmtRatio` with an "×" suffix ("1.18×", "0.51×").
  - Note is empty when available, otherwise the mapped reason ("Missing line: Earnings per share").
  - The Status column is removed; the "—" plus note says it.

**Metrics:**
- Read-only table Metric · Value · Period · Source, from `useCompanyMetrics`. Remove "Calculate metrics".
- **Empty:** "Metrics are computed automatically once statement lines exist. None are stored for {TICKER} yet." / "تُحتسب المؤشرات تلقائياً عند توفر بنود القوائم. لا توجد مؤشرات مخزنة لـ {TICKER} بعد." Append the INSUFFICIENT_DATA reason when the API provides one.

**Data quality:**
- DataQualityCard is restyled as one table per scope (Price history, Company profile, Financial statements).
  - Rows: Completeness · Freshness · Validation · Historical depth · Source reliability.
  - Columns: Weight · Score (/100) · Detail.
  - The score sits in the scope heading: "Price history: 94/100, Good".
- No progress bars and no "✓".
- An Issues list per scope uses the Notice style.
- Footnote: "Bands: 70+ good · 40–69 partial · below 40 poor · methodology v1.0. Data quality describes the inputs, not the company." Translate it.

#### 4.4.4 Valuation

1. **"Fair value estimate"** / "تقدير القيمة العادلة":
   - The headline value, or `<Missing>` with its reason, then "Price 133.90 as of 22 Oct 2026".
   - The verdict sentence (§5.3).
   - A scenario range table Bear · Base · Bull.
   - The confidence line "Confidence: {level} · required margin of safety {x}%", in words, not "MISSING".
2. **"Model legs"** / "مكونات النموذج": table Model · Value · Weight (%) · Status · Reason. Translate the model names (codes go to Technical details):

| Code | EN | AR |
|---|---|---|
| `fcfe_two_stage` | Two-stage free cash flow to equity | التدفق النقدي الحر لحملة الأسهم على مرحلتين |
| `price_to_earnings` | Price-to-earnings multiple | مضاعف السعر إلى الربحية |
| `dividend_discount` | Dividend discount | خصم التوزيعات |

   Weight 0.6 becomes "60%".
3. **"Sensitivity"** / "الحساسية": SensitivityTable restyled as a DataTable. The empty copy is unchanged in meaning but translated.
4. **"Investment score"** / "درجة الاستثمار" (`id="score"`): the total "/100" plus a table of the five components: Component · Score · Weight · Reason. Remove "Assess score".
   - **Empty:** "The investment score is computed automatically once statements and prices exist. Not available for {TICKER} yet: {reason}."
5. **Footer:** methodology version, profile and as-of. Raw assumption strings (`resolved_affo_source=fcf …`) go inside the "Technical details" disclosure only (F15).

**Remove the 12-field assumptions form** (R43 #1).

#### 4.4.5 Shariah

1. **Verdict pair:** two side-by-side definition blocks (stacked on mobile).
   - **Our screen:** verdict badge, then Methodology `<code>` (Plex Mono `--fs-meta`), Screened (date), and a "Provisional (vendor data)" Tag when the backend marks a vendor tier (R43 AC-4).
   - **EGX33 Shariah index:** member or not, review cycle, source (external link "EGX constituents page"), and the note text under the "Technical details" disclosure when it is longer than one line (the CLHO/GOUR reconciliation note).
2. **"Ratio checks"** / "اختبارات النسب": table Rule · Value · Threshold · Result (Passes / Fails / Unknown, as words, §5.2). Thresholds are read from the methodology record and never hard-coded in the UI.
3. **"Purification estimate"** / "تقدير التطهير":
   - "Estimated purification per share: EGP {x} (dividend per share × non-permissible revenue share)", or `<Missing>` naming the missing input.
   - Remove the 8-field form and the "Shares held" field (R43 #6).
4. **Footer:** "A screening result, not a fatwa or certification. Verify with a qualified Shariah scholar." / "نتيجة فحص، وليست فتوى أو شهادة. تحقّق مع عالم شرعي مؤهل."

Remove Run screening, the purification form and Record membership (R43 #5–7).

#### 4.4.6 Peers

- **Basis line:** "Peer basis: {basis} · {n} peers · as of {date}".
- **When sector is null:** "No peer basis: the sector for {TICKER} is not in our data yet." / "لا يوجد أساس للمقارنة: قطاع {TICKER} غير متوفر في بياناتنا بعد."
- **Tables:** a peers table (Stock plus the profile metrics) and a percentiles table (Metric · Value · Percentile vs peers).
- **Footer:** text link "Change the peer list in Admin" / "تعديل قائمة الشركات المماثلة من الإدارة" → `/admin/peers?ticker=X`.
- **Remove** the UUID edit form.

#### 4.4.7 Thesis & filings

1. **"Thesis"** / "فرضية الاستثمار" (auto-assessed per R43):
   - "Horizon: {N} years (methodology default)" / "الأفق: {N} سنوات (افتراضي المنهجية)".
   - Then the narrative skeleton (prose, `--fs-read`, max 72 characters per line), a scenarios table, a bulleted list of invalidation conditions, a catalysts table (Date · Catalyst · Source), and the ledger as a timeline list (date at inline-start, entry text, "Documented update" Tag when it applies).
   - **Empty:** "The thesis is assessed automatically once statements and prices exist. Not available for {TICKER} yet: {reason}."
   - **Remove** the assess form and the update form.
2. **"Filings"** / "الإفصاحات" (`id="filings"`):
   - A registry table: Report date · Type · Bulletin · Basis · Parsed (Yes / No / Failed) · Link.
   - **Empty:** "No filings registered for {TICKER} yet. Filings are added in Admin."
3. **"Facts with provenance":** a table Metric · Value · Period · Filing · Page.
4. **"Period comparison":** a metric selector (KEEP, R43 #12) with **localized labels** (Revenue / الإيرادات, Net income / صافي الربح, Total assets / إجمالي الأصول, Total equity / إجمالي حقوق الملكية, EPS / ربحية السهم), never the snake_case codes.
   - Below it, a designed table: Measure · Current · Prior · Change · Change %, with rows TTM, YoY and TTM margin.
   - Missing cells use `<Missing>` with the reason ("TTM needs four reported quarters; 0 available").
   - **Replaces the key/value dump (F15).**
5. **"What changed":** a list. Empty: "No changes recorded yet." / "لم تُسجَّل تغييرات بعد."

### 4.5 Momentum rankings `/rankings`

- **Header:** "Momentum rankings" / "ترتيب الزخم". Subtitle: "Companies with price history, scored 0–100 against each other on momentum, trend, drawdown, volatility and liquidity. Prices only, no fundamentals." / "الشركات التي لها سجل أسعار، مُقيّمة من 0 إلى 100 مقارنةً ببعضها في الزخم والاتجاه والتراجع والتذبذب والسيولة. أسعار فقط، دون بيانات مالية."
- **Meta line:** "199 of 234 companies scored · 35 without price history (show) · as of 22 Oct 2026 · model egx_price_momentum 1.1.0". The model code is in `--font-code`. "Show" expands the excluded list (ticker plus reason).
- **Controls:** Tier segmented (All · Strongest · Strong · Neutral · Weak · Weakest; AR: الكل · الأقوى · قوي · محايد · ضعيف · الأضعف) · "Min score" number input (0–100, step 5), replacing the imprecise slider · Show (25 · 50 · 100 · All).
- **Remove "Re-run scoring"** (R43 #15).
- **Columns:**

| Column | Format |
|---|---|
| # | rank |
| Stock | ticker plus name |
| Momentum score (0–100) | 1 dp |
| Tier | Tag, sentence case |
| 3M return | `fmtSignedPct` in gain/loss colour |
| 6M return | `fmtSignedPct` in gain/loss colour |
| Trend (−1 to +1) | signed 2 dp in `--text`, **no %, no colour, no arrow** (F12) |
| Max drawdown | "−10.1%" in `--text-2`, **no colour, no arrow**, because it is always a decline (F12) |
| Top factors | "3M momentum: 98th pctl · 6M momentum: 96th pctl" / "زخم 3 أشهر: المئين 98 · …"; "(1 factor missing)" becomes "1 factor missing" / "عامل واحد غير متوفر" |

- **Mobile card fields:** Stock · Momentum score + tier · 3M return · Max drawdown.
- **States:**
  - Empty: "No momentum scores yet. Scores are computed after the next price sync."
  - NoMatch: "No companies match these filters." + Clear.

### 4.6 Shariah screening list `/screening`

- **Header:** "Shariah screening" / "التصفية الشرعية". Subtitle: "Our ratio screen beside the official EGX33 Shariah index. A screening result is research input, not a certification." / "فحص النسب الخاص بنا بجانب مؤشر EGX33 الشرعي الرسمي. نتيجة الفحص مدخل بحثي، وليست شهادة."
- **Target table** (needs NEEDS-BACKEND B3: one list endpoint covering all companies):
  - Columns: Stock · Our screen · Methodology · Screened · EGX33 · Review cycle.
  - Filters: "Our screen" segmented (All · Passes · Fails · Not enough data · Not screened) and "EGX33" segmented (All · Members · Not members).
- **Interim, until B3 lands:** two sections.
  1. **"EGX33 Shariah index members (Aug 2026 review)":** from `useStanceRadar(50,"egx33")`, with columns Stock · Our screen · EGX33 cycle.
  2. **"Screened by our methodology":** the current list, ticker-resolved.
     - **Never print a UUID (F17).** Rows whose company cannot be resolved are omitted, and the meta line says "1 result for a company no longer in the universe is hidden" / "نتيجة واحدة لشركة لم تعد ضمن القائمة مخفية".
- **States:**
  - Empty: "No screening results yet. Screens run automatically after statements are imported."
  - Error: standard.

### 4.7 Watchlists `/watchlists`

- Keep W1 and W3 from the earlier design (7 columns, linked rows, price plus as-of, staleness Tag) and restyle to the tokens.
- **List selector:**
  - Wide screens: a list of watchlist names on the inline-start side, 240 px.
  - Below 1024 px: a select above the table.
  - "New list" / "قائمة جديدة" is an inline form (name plus Create).
- **Add company:** CompanyPicker plus an optional note plus "Add" / "إضافة". No UUID inputs.
- **Badge hints change (R43):** missing Score, Shariah or Thesis shows `<Missing>` with the INSUFFICIENT_DATA reason. **No "Assess on …" hints**, because those actions no longer exist.
- **Copy:**
  - Empty, no lists: "No watchlists yet. Create a list, then add companies by ticker." / "لا توجد قوائم متابعة بعد. أنشئ قائمة ثم أضف الشركات بالرمز."
  - Empty list: "This list is empty. Add a company by ticker above."
  - Footnote: "Badges are computed on the server for each row. A stale row's inputs are old; check the company page before relying on it. Research context only, not advice."
- **Mobile card fields:** Stock · Price + as-of · Score · Shariah.
- **Not in scope:** list rename and delete (W2, still NEEDS-BACKEND).

### 4.8 Alerts `/alerts`

- Keep A1–A4 (Build / Rules / Fired in-page tabs, scope radio, designed firing summaries, technical-details fold).
- **Top Notice** (honesty, R43 OUT, F18): "Alerts are not evaluated automatically yet, so rules will not fire on their own." / "لا يتم تقييم التنبيهات تلقائياً بعد، لذا لن تُطلق القواعد من تلقاء نفسها." Remove the notice when trigger wiring ships.
- **Replace** the company `<select>` with CompanyPicker.
- **Family labels:** Price crossing / تجاوز السعر · Valuation gap / فجوة التقييم · New document / مستند جديد · Score change / تغيّر الدرجة.
- **Fired tab:**
  - Empty: "Nothing has fired yet." / "لم يُطلق أي تنبيه بعد."
  - Unacknowledged rows use 600 weight; the "Acknowledge" / "إقرار" button stays.

### 4.9 Events `/events`

- Keep E1–E3. The symbol filter becomes CompanyPicker (with "All companies" as the cleared state). Type select labels are translated. "Export JSON" / "تصدير JSON" stays.
- **New empty copy** (the old one tells users to "assess a company", which no longer exists): "No events recorded yet. Events appear when watchlists change, alerts fire or new statement data lands." / "لم تُسجَّل أحداث بعد. تظهر الأحداث عند تغيّر قوائم المتابعة أو إطلاق التنبيهات أو وصول بيانات قوائم جديدة."
- Filtered empty: "No events match these filters." + Clear.

### 4.10 Admin

| Section | Content | Notes |
|---|---|---|
| Market data | Last sync summary (status, finished at, price records written, failed tickers count); "Refresh market data" / "تحديث بيانات السوق" primary button; live progress line using today's phase copy ("Fetching prices 120/234…" / "جارٍ جلب الأسعار 120/234…"); failure list in a disclosure, not the console | Moves from the Overview (R43 #14); keep the 409-adopts-job behaviour |
| Filings intake | Today's `FilingsIntake.tsx` unchanged in behaviour, restyled; the reason tags EGX33 / Most traded become Tags | R43 #16 |
| Disclosures | CompanyPicker → registry table → "Register a filing" form → "Upload a filing" form. Parse runs automatically after upload (R43 #11); show "Parse again" only on rows with status Failed | Optional fields grouped under "More details" |
| Peer lists | CompanyPicker → current peers as removable chips (ticker) → CompanyPicker "Add peer" → "Save peer list". Resolve tickers to ids client-side; never show ids | R43 #10 |
| Thesis updates | CompanyPicker → the existing documented-update form → read-only ledger preview below | R43 #9 |

Every write shows inline success ("Saved." / "تم الحفظ.") or a 422 detail in the form, and never a toast-only error.

---

## 5. Stance, Shariah and valuation copy (AGENTS.md principle 10)

### 5.1 Stance

Internal codes (`buy`, `hold`, `reduce`) and the R42 thresholds are unchanged. Only the displayed labels change, so that no label reads as an instruction.

| Code | Shape (SVG) | EN label | AR label | Colours |
|---|---|---|---|---|
| `buy` | triangle-up | Leans buy | يميل للشراء | `--gain` on `--gain-bg` |
| `hold` | bar | Neutral | محايد | `--neutral` on `--surface-2` |
| `reduce` | triangle-down | Leans reduce | يميل للتخفيض | `--loss` on `--loss-bg` |
| `null`, or coverage 0, or (`confidence===0 && reasons.length===0`) | none | Not assessed | لم يُقيَّم | `--text-3`, 1 px `--border`, transparent |

- **Not assessed fixes F5:** ACAP must render "Not assessed", never "Neutral".
- **Badge tooltip:** "Model stance under signal-rules-2.0, confidence {c}/100. A research calculation, not a recommendation to trade." / "موقف النموذج وفق signal-rules-2.0، الثقة {c}/100. حساب بحثي، وليس توصية بالتداول."
- **Confidence** always appears next to the stance on the hub and the radar. Display "28/100", never a bare "28".
- **Banned in UI copy:** "BUY", "SELL", "Strong buy", "target price", "will rise", "guaranteed", "safe", and any uppercase stance.

**This replaces the R42 dictionary labels "Buy/Hold/Reduce" (شراء/انتظار/تخفيض).** If tech-lead reads AC-10's "stance labels per R42" as fixing the words themselves, reverting is a three-key dictionary change. The rest of this spec does not depend on it.

### 5.2 Shariah

| Value | EN | AR | Style |
|---|---|---|---|
| `COMPLIANT` | Passes our screen | يجتاز فحصنا | `--accent` on `--accent-bg` |
| `NON_COMPLIANT` | Fails our screen | لا يجتاز فحصنا | `--warn` on `--warn-bg` |
| `INSUFFICIENT_DATA` | Not enough data | بيانات غير كافية | `--text-3` on `--surface-2` |
| `NOT_SCREENED` | Not screened yet | لم يُفحص بعد | `--text-3`, border only |
| vendor-tier suffix | · provisional (vendor data) | · مؤقت (بيانات مزوّد) | Tag |
| `egx33: member` | EGX33 Shariah index: member ({cycle}) | مؤشر EGX33 الشرعي: عضو ({cycle}) | Tag |
| `egx33: not_member` | EGX33: not a member (not a non-compliance verdict) | EGX33: ليس عضواً (وهذا ليس حكماً بعدم التوافق) | text-3 |
| `egx33: unknown` | EGX33: unknown | EGX33: غير معروف | text-3 |

- **Rule results:** Passes / يجتاز · Fails / لا يجتاز · Unknown / غير معروف.
- **Colour choice:** Shariah never uses `--gain` or `--loss`, so a pass is not read as a price gain. Verdicts are carried by the words.
- **No "☪", "✓" or "✕".**
- **Compact ShariahPair** (for tables): "{our verdict} · EGX33 {member|—}". The EGX33 "—" carries a tooltip with the not-member sentence above.

### 5.3 Valuation and levels

| Case | EN | AR |
|---|---|---|
| Headline | Estimated fair value under the stated methodology | القيمة العادلة المقدّرة وفق المنهجية المعلنة |
| Price below the estimate by more than the margin | Price is below the estimate: potentially undervalued under these assumptions. | السعر أقل من التقدير: قد يكون مقوّماً بأقل من قيمته وفق هذه الافتراضات. |
| Price above the estimate by more than the margin | Price is above the estimate: potentially overvalued under these assumptions. | السعر أعلى من التقدير: قد يكون مقوّماً بأعلى من قيمته وفق هذه الافتراضات. |
| Within the margin | Price is near the estimate under these assumptions. | السعر قريب من التقدير وفق هذه الافتراضات. |
| No estimate | No comparison: the fair value is not available ({reason}). | لا مقارنة: القيمة العادلة غير متاحة ({reason}). |
| Scenario values | Bear / Base / Bull: what each scenario implies, not what the price will do. | متحفظ / أساسي / متفائل: ما يعنيه كل سيناريو، وليس ما سيفعله السعر. |
| Reference levels | A volatility band around the last close, not a forecast or a price target. | نطاق تذبذب حول آخر إغلاق، وليس توقعاً أو سعراً مستهدفاً. |
| Global footer | Research calculation, not investment advice. | حساب بحثي، وليس نصيحة استثمارية. |

The over/under/near verdict uses the backend's own verdict field and margin. The UI never recomputes it.

---

## 6. RTL rules for the implementer

1. `<html lang dir>` switch together. This already happens in `useLang`; keep it.
2. Use logical properties for all layout: `margin-inline-*`, `padding-inline-*`, `inset-inline-*`, `border-inline-*`, `text-align:start/end`. Physical `left`/`right` is allowed **only** for `text-align:right` on numeric cells and headers.
3. Numeric cells and headers use `text-align:right` + `dir="ltr"` + `white-space:nowrap` + tabular digits, in both languages. Never `text-align:end` on numbers.
4. Text `th` must set `text-align:start` explicitly. The browser default is physical `left` (F4, measured `th` = left in RTL).
5. Wrap opposite-direction runs in `dir="ltr"` (static) or `<bdi>` (database text): tickers, Latin company names, numbers, dates, methodology versions, URLs, ATR/RSI/SMA abbreviations. In Arabic, Latin names get `<bdi dir="ltr" lang="en">`, which fixes the leading-dot and wrong-end truncation (F4).
6. **Mirrored in RTL:** column order, sidebar and drawer side, tab order, stat-strip order, pagination direction and chevrons, the "→" in "Price & signals →" links (use the chevron icon with `transform: scaleX(-1)` under `[dir=rtl]`), the combobox clear-button side, and the progress direction.
7. **Not mirrored:** charts (`dir="ltr"` wrapper), the ▲/▼ triangles and the bar, search, info, external-link, sort and refresh icons, numbers, dates and times, and code or version strings.
8. Western digits only: locale `ar-EG-u-nu-latn`. **Replace the Eastern digits in `dict.ts`:** `signals_liquidity` "٢٠" → "20", `low_liquidity_title` "٥٠٠" → "500", and `reco_levels_note` "٢× / ١٫٥×" → "2× / 1.5×". Add a vitest that fails if any `ar` string contains `[٠-٩۰-۹]`.
9. Arabic text uses `letter-spacing:0` and no `text-transform`. Use the Arabic line-heights from §2.4.
10. Use one language per screen. Never render EN and AR side by side, except in the language toggle (F16).
11. Backend free text that is not localized yet (reasons, limitations, INSUFFICIENT_DATA reasons, methodology descriptions) goes in `<span lang="en" dir="ltr">` in Arabic mode. Map known reason codes (`missing:<line>`) to localized strings; everything else waits for B5.
12. Plural forms come from a `plural(n, {zero, one, two, few, many, other})` helper built on `Intl.PluralRules(locale)`. No "companies (234)" workarounds.
13. Form controls: a `<select>` arrow follows the direction automatically. Number inputs get `dir="ltr"` with `text-align:right`, and date inputs get `dir="ltr"`.
14. Test both directions: every new page test renders once with `lang="ar"` and asserts `dir="rtl"` on `<html>`, no Latin-only page title, and that numeric cells carry `dir="ltr"`.

---

## 7. Removal checklist (do-not rules applied to the current code)

- **`index.css`:**
  - Remove the body radial gradients, every `backdrop-filter` (6 uses), `.card::before`, the `.coverage-banner::before` stripe, the `◈` logo, `translateY` hover lifts, `--shadow`/`--shadow-lg` on cards, all `9999px` radii (11 uses), and all uppercase/letter-spacing rules.
  - Remove the tokens `--accent-glow`, `--glass*`, `--green*`, `--red*`, `--yellow*` and `--blue*`. Every page CSS file is migrated to the §2 names; grep shows the old names in colocated `pages/*.css`.
- **Glyphs in markup:** remove `● ▲ ▼ ✓ ✕ ☪ ⚠ ! ↻ ▸ ◂ ◈`. Replace them with the SVG icons, or with plain text and a shape only where §3.10 and §5.1 allow.
- **Remove the controls listed in R43:** Calculate indicators, Calculate valuation (the form), Calculate metrics, Assess score, Assess thesis (the form), Run screening, the purification form, Record membership, Edit peer list, register/upload/parse on the tab, Refresh market data on the Overview, and Re-run scoring. R43 AC-1 is the test.
- **Hard-coded English strings** in all 18 untranslated pages and 5 components move into `dict.ts` (F3). This is the biggest piece of work in the redesign; plan for it.

---

## 8. NEEDS-BACKEND (each has a UI fallback, so none blocks frontend)

| # | Need | Endpoint / field | UI until then |
|---|---|---|---|
| B1 | Stance null when no engine produced an input | `GET /api/stance/*`, `/companies/overview`: `stance:null` when coverage = 0 | the client-side "Not assessed" rule in §5.1 |
| B2 | Shariah block on the companies list | `GET /api/companies/overview` items add `shariah: ShariahStatus` | Shariah column hidden on Companies |
| B3 | Universe-wide Shariah list with ticker and name | `GET /api/screening/companies` items add `ticker`, `name`, `egx33`, `egx33_review_cycle`, covering all companies | the two-section interim in §4.6 |
| B4 | Value traded on the radar | `GET /api/stance/radar` items add `avg_value_traded` (30-day) | the "#" traded-rank column only |
| B5 | Localizable reasons | stance `reasons[]`, `limitations[]` and INSUFFICIENT_DATA reasons add `code` + `params` alongside `text`; drop the bilingual "Research calculation…" string from `limitations` | English text in a `lang="en"` span (§6.11); client filter for the bilingual string |
| B6 | Sector, ISIN, shares outstanding, `name_ar` | company data (null on 200 of 200) | sector filter removed; "not in our data yet" copy; Latin names in `<bdi>` |
| B7 | Mojibake names | e.g. `SociÃ©tÃ© Arabe Internationale de Banque` (SAIB): fix the import encoding | none (data defect, shown as is) |
| B8 | Watchlist rename and delete | W2, unchanged | not built |

---

## 9. Acceptance checks (qa-ui and the post-build ux-expert review)

1. At 1024, 1280 and 1440 px, in EN and AR, `document.documentElement.scrollWidth === document.documentElement.clientWidth` on every route (clientWidth excludes the vertical scrollbar).
2. At 375 px every route has a working menu and search. No page is wider than the viewport; only `.table-wrap` scrolls.
3. In Arabic, no page shows an English heading or label, except backend free text inside `lang="en"` spans and proper nouns. The vitest checks for Eastern digits pass.
4. In Arabic, every `th` computes to the same alignment as its column's cells.
5. ACAP shows "Not assessed" everywhere. ETEL Rankings shows Max drawdown "−30.4%" in neutral text and Trend "+1.00".
6. No raw UUID, snake_case code, "MISSING" or uppercase stance appears outside a "Technical details" disclosure.
7. Contrast: axe or a manual check against §2.5 in both themes. Focus rings are visible on every interactive element.
8. R43 AC-1 holds. `/companies/:t/ai` shows Not found. `/intake` and the 7 old tab paths redirect.
9. `prefers-reduced-motion`: no skeleton animation and no transitions.

---

## 10. Suggested build order for staff-frontend

These slices follow the CONTRACT parallel-lanes rule. Shared files (`App.tsx`, `index.css`, `dict.ts`, `api/client.ts`, `types`) stay router-owned.

1. Tokens, fonts, AppShell, sidebar and drawer, theme toggle, `format.ts`, and the `ui/` components (DataTable, StatStrip, badges, Notice, states, CompanySearch, PriceChart).
2. Routing: the hub layout route, `CompanyHeader`, the 7 tabs, redirects, Not found, and the `/admin` shell.
3. Pages in this order: Recommendations, Companies, the hub tabs, Dashboard, Rankings, Shariah list, Watchlists, Alerts, Events, Admin. Translate each page as it is built.
4. Dead-code and CSS removal (§7) and the RTL tests (§6.14).

NEXT: staff-frontend
