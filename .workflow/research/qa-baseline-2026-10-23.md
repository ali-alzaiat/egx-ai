# qa-ui (Hassan): baseline audit before the redesign — EN + AR, 2026-10-23

Gates (`frontend/`: `npx tsc -b; npm run lint; npx vitest run; npm run build`): TSC_EXIT=0, LINT_EXIT=0, VITEST 3 files / 22 tests passed, BUILD_EXIT=0 (single JS chunk 489.76 kB, no route-level code splitting). Playwright not present. Vite log: no server errors.

Method: built-in browser, `preview_start frontend` (port 5173), desktop 1024 (clientWidth 1018); all 9 top-level routes and all 14 company routes for COMI and AMOC, EN then AR (sidebar language button); per route: API statuses, console errors, main text, Latin strings in AR, `scrollWidth - clientWidth`; mobile repeated at 375x812 in both languages. No forms submitted.

| # | Screen / route | Lang | Severity | Evidence |
|---|---|---|---|---|
| F1 | `/companies/:t/ratios` (COMI, AMOC) | EN+AR | HIGH | Percent ratios 100x too large. API `ratios` returns `net_margin "0.47948…"`, `roe "0.26625…"`, `roa "0.04272…"`; UI shows "Net margin 4,794.9%", "Return on equity 2,662.5%", "Return on assets 427.3%", "Revenue growth YoY 1,201.5%". AMOC "Gross margin 663%" (statements give 6.63%). `frontend/src/pages/Ratios.tsx:52-53` multiplies by 100 and then formats with `style: "percent"`. |
| F2 | All routes at 375px | EN+AR | HIGH | No navigation on mobile: `ASIDE.sidebar display=none`, no visible nav links outside `<main>`, language button 0x0 — a phone user can't change language or reach other pages. |
| F3 | Mobile overflow at 375px | EN | HIGH | scrollWidth: `/` 437, `/recommendations` 1190, `/intake` 888, `/companies` 1055, `/rankings` 1083, `/screening` 525, company tabs 1120 (`/disclosures` 402); `/watchlists`, `/alerts`, `/events` 375. |
| F3a | Mobile overflow at 375px | AR | HIGH | Company tabs 1120 (`/disclosures` 410); innerWidth grew to 404 (`/`), 778 (`/intake`), 997 (`/companies`), 1062 (`/rankings`), 485 (`/screening`); Dashboard heading cut at the right edge; company overview header blank, cards cut. |
| F4 | Desktop 1024px overflow | EN/AR | MEDIUM | overflowX EN/AR: company tabs (except disclosures) 362/362, `/recommendations` 432/173, `/intake` 130/20, `/companies` 297/239, `/rankings` 325/304. `MAIN.main-content` 1160px inside 1018px; `NAV.company-tabs scrollWidth=1207`; `/rankings` main right=1344. |
| F5 | Arabic mode pages in English | AR | HIGH | Top-level `/`, `/companies`, `/rankings`, `/screening`, `/watchlists`, `/alerts`, `/events`; company tabs Overview (54 Latin strings), Financial Data, Metrics, Shariah (66), Valuation (84), Technical, AI, Score, Peers, Thesis, Disclosures (68). 19 page files have 0 `useLang` references: AIInsights, Alerts, Companies, CompanyDetail, Dashboard, Disclosures, Events, FinancialData, FinancialMetrics, InvestmentScore, Peers, PendingFinancialData, Rankings, Screening, ShariahScreening, TechnicalAnalysis, Thesis, Valuation, Watchlists. |
| F6 | Signals, Ratios | AR | MEDIUM | Backend English text/raw codes in Arabic UI: "Financial-statements data-quality assessment is MISSING.", "Price below SMA…", "MACD line negative", "Technical-only stance", "Statement freshness unknown."; "بيانات غير كافية (missing:eps)", "(missing:current_liabilities)". |
| F7 | `/companies/:t/screening` | EN+AR | MEDIUM | `404 /api/screening/companies/{id}` and `404 …/purification` on every load (the only console errors in the audit); UI "Not screened yet." |
| F8 | Dashboard "Scorable coverage" | AR | LOW | Bidi reorder: reads "of 234 199" (EN "199 of 234"). |
| F9 | `/intake` subtitle | AR | LOW | Arabic-Indic digits "وأكثر ٣٠ شركة" (`i18n/dict.ts:180`) while locale is `ar-EG-u-nu-latn`. |
| F10 | `/recommendations`, `/companies` | EN+AR | LOW | AGENTS.md rule 10: "Buy" filter option, "▲ Buy" stances, `/companies` "▲ BUY", AR "شراء" (`dict.ts:95 stance_buy`). |
| F11 | `/companies` header | EN+AR | LOW | Header reads "GROSS MARGIN NO DATA". |
| F12 | `/companies/:t/disclosures` | EN+AR | LOW | No company tab bar on this page (`Disclosures.tsx:21` "no CompanyTabs entry") though other tabs link to it. |
| F13 | Empty states COMI/AMOC | EN | INFO | Financial Data: 5 ANNUAL periods but "No income statement facts recorded for COMI yet" while Statements shows provisional values; Metrics, Technical, Score, Thesis "not … yet"; Peers "Sector: — · EGX sector: —", 0 peers; `/screening` lists 1 company; AMOC Shariah "Not screened yet" while Signals shows EGX33 member; Watchlists/Events empty. |

NEXT: tech-lead
