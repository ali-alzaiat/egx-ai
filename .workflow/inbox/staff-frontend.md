# Inbox: staff-frontend

From: router · 2026-10-09
Task: Vercel-skill compliance pass over `frontend/**` (standing requirement per user; now encoded in AGENTS.md, your agent definition, and CONTRACT step 7). Read the skill at `/Users/alialzaiat/.claude/skills/vercel-react-best-practices/SKILL.md` plus only the `rules/` files you actually need. Scope: client/rerender/bundle/rendering/js rules; server-*/Next.js-only rules (RSC cache, next/dynamic, streaming, after()) are N/A to this Vite SPA — list skipped rules with one-line reasons, never silently. Fix material violations only; no speculative refactors, no new deps, keep quality.test.ts green. Run `npm test`, `npm run lint`, `npm run build` in frontend/ and paste outputs. End with NEXT: qa-ui | BLOCKED: <question> | DONE + files changed + verification evidence.

---

From: router (re-dispatch, direct, no tech-lead hop) · 2026-10-09
RE-WORK — the prior uncommitted R16/R17 implementation was destroyed by a router-side `git checkout -- frontend/src/` during an inline session. Recovery was attempted (unreachable-commit scan for `useSyncStatus`: zero hits across all 12 dangling commits) and failed. Re-implement from the frozen spec below (unchanged).

Tree state at HEAD `bdc553b` — rebase onto it, do not revert:
- PRESENT, reuse as-is: `useScreenedCompanies` + `ScreenedCompanySummary` (`api/client.ts`, `types/index.ts`); per-page `.css` placeholder files + one import line each (keep the lines; no index.css split in this task); `lib/format.ts`; `components/CompanyTabs.tsx`; `components/CompanyNotFound.tsx`; `pages/Screening.tsx`.
- MISSING, implement per spec: `App.tsx` Screening route; `useScreeningResult` (GET 404=null) + `screenCompany` (POST); `keepPreviousData`/`retryUnless404` client predicates; R16 `SyncJobState` types + `startMarketRefresh` + `useSyncStatus` + CompanyDetail button/status + DataQualityCard pinned line; all §R17 fixes (verify the PRESENT files against spec, fix or keep).
- Verify each PRESENT file against the spec below rather than assuming compliance.

Task: Implement the R16 refresh surface + R17-intersecting UX fixes from the audit + research, in one task. Honor `.workflow/design/refresh-and-assess-contract.md` (R16) and `.workflow/decisions/R17-ux-overhaul-v1-scope.md` + `app-ux-audit.md`. No new deps, no jsdom changes. Keep quality.test.ts green.

## R16 refresh surface (contract-pinned, must deliver)
- Paste TS types (`SyncJobState` etc.) into `frontend/src/types/index.ts` verbatim from contract §Types.
- `startMarketRefresh(params?)` + `useSyncStatus()` into `frontend/src/api/client.ts` (plain async + local state + `queryClient.invalidateQueries`, **no `useMutation`**); polling 2 s gated to `accepted`/`running` only; 409-adoption; invalidation list `["dataQuality"] ["signals"] ["prices"] ["latestPrice"] ["dataSources"]` (keys from contract §Decision 5).
- CompanyDetail `.page-header`: `.btn.btn-secondary` **Refresh market data** → `startMarketRefresh()` + status line underneath; disabled + `Refreshing…` while live.
- `DataQualityCard.tsx` empty branch (`items.length === 0`): keep `data-quality-card-ux.md` copy **and** append R16's pinned line **verbatim**: `Refresh market data to compute assessments for every company.` (one muted line directly under the existing empty copy; R16's one-line amendment to that doc).
- `GET /api/data-sources` payload now carries `last_synced_at` (R16 field); dashboard/freshness line reads it and displays formatted date or `Never`.

## R17-intersecting UX fixes (structural, shared; no per-screen copy from full spec)
- **Layout.tsx:** nav `Screener` → `Market Rankings`; `Rankings` added as 4th global dest; prefix-active match for sub-pages highlights `Companies` correctly; `aria-current="page"` on active nav/link.
- **CompanyTabs.tsx** (new shared component): renders 7-tab row on every company view (Overview→Valuation); replaces the 4-button row in CompanyDetail header; single scrollable row under `.sidebar`-squeezed widths; `aria-label="Company sections"`; `.company-tab.active` class.
- **CompanyNotFound.tsx** (new shared component, all 7 company views): echoes ticker in header; two actions: `Browse companies → /companies` + `Search another ticker` → `/companies?search={q}`; single request (no 4xx retry) via client predicate `!error.message.includes("404") && count < 1`.
- **CompanyDetail price strip (F17):** always render strip; if no data → all `—` + muted `No price data from the configured source for {ticker}.`; with data → `As of {date} · end-of-day`.
- **Historical Prices (F11):** server-paginated 50 rows/page (`page_size=50`, `useCompanyPrices(..., {page_size:50})`); format prices `toFixed(2)` (`128.20`, never `128.2000`); volume `toLocaleString()`; drop rows where `open===high===low===close && volume===0` with muted note `Non-trading days are hidden.`.
- **AI Insights (F7):** heading `Index Data for RAG` → `Prepare data for analysis`; button `Prepare data` / running `Prepare data…`; `alert()` deleted → inline `role="status"`: `n>0` → `Prepared {n} data items for {ticker}.`; `n===0` → `.alert.alert-warning` `Nothing to prepare yet`. Failure → `.alert.alert-error` + `Retry`. No pipeline jargon.
- **Shariah Screening (F1/F2):** replace cURL doc line with `Run screening` button calling `POST /api/screening/companies/{id}/screen`; GET 404 → empty state `Not screened yet` + `Run screening`; tri-state badge (Compliant/Not compliant/Not enough data) + `Screened {date} · {methodology} · methodology v{version}`; rules table with verbatim `reason`.
- **Valuation (F1/F2):** replace cURL with `Calculate valuation` button calling `POST /api/valuation/companies/{id}/calculate` (empty call); assumptions form with 5 groups (P/E, P/B, EV/EBITDA, DCF, shared) + muted line `The app does not hold analyst estimates — supply the assumptions you want to test.`; results table with status words `Available`/`Not enough data`/`Invalid inputs`; success toast `Valuation updated — {n} evaluated`.
- **Metrics (F6):** `Calculate metrics` button on `.page-header` calling `POST /api/metrics/companies/{id}/calculate` (runSignals pattern); empty state `No metrics calculated for {ticker}.` + body explaining metrics derive from statements; 0-metric toast `No metrics calculated — no financial statements recorded.`
- **Technical (F4):** delete paste form; `useCompanyPrices(..., {page_size:200})` auto-fetch, build `prices/volumes` strings, call `POST /api/technical/companies/{id}/calculate` (no indicator_types); results table with `AVAILABLE`/`INSUFFICIENT_DATA`/`INVALID` + `reason` verbatim; context line `Calculated from the last {n} trading days … ({firstDate} – {lastDate})`.
- **Rankings (F9/F10/F14):** `keepPreviousData: true` on `useSignals`; first-load copy `Loading rankings…` (not `Scoring the market…`); button disabled while running/fetching; success toast `Scoring complete — results are as of {as_of}.` auto-dismiss 6 s; colour + sign (`▲ +4.2% / ▼ −1.8%`) on momentum/DD/trend cells; H1 stays `Market Rankings`; `Screener` word removed from nav entirely.
- **Financials (F8):** one page-level empty block when all 4 sections empty: `No financial data recorded for {ticker}.`; per-section reasons when partial; error one page-level `.alert.alert-error` + `Retry`; no calculate button.
- **CompanyNotFound (F15/F17):** 4xx no-retry predicate `!error.message.includes("404") && count < 1` (removes duplicate 404); header `We couldn't find a company with ticker "{ticker}"`; body `Check the ticker — EGX tickers are 2–6 letters, e.g. COMI.`; actions `Browse companies → /companies` + `Search another ticker…`.
- **Company list (F12/F13):** drop `Status` + `Currency` columns; keep `Ticker | Name | Sector | Industry`; sector missing → `—` with `title="Sector not recorded"`; explicit coverage note (computed via second `useCompanies` query): default `Showing {universeTotal} companies`; sector filter `Showing {data.total} of {universe} companies · {universe−data.total} excluded by this filter.`; search prefix `Showing {data.total} matches for "{q}" of {universe} companies`; states: loading → `Loading companies...`; keep previous on refetch (no wipe); empty → `.empty` `No companies match these filters.` + `Clear filters`; error → `.alert.alert-error` `Couldn't load companies.` + `Retry`.
- **Dashboard (F5):** delete hardcoded `--` cards + fake table; fetch health/companies/signals/data-sources; 4 card grid: Companies tracked / Market coverage / Scored companies / Scorable coverage; freshness line `Last refresh: {date}` / `Market data has never been refreshed.`; states per card: loading → value, error → `—` + `Not available right now.` + Retry; table empty → `No scores yet.` + `Run scoring from the Rankings page.`; table error → alert + Retry.
- **index.css:** appended `.dq-*` block (`.dq-card` … `.dq-empty`) + `.sr-only`, reusing existing tokens only (`--green/--yellow/--red`, `--text-secondary`, `--border-subtle`, `--radius`, `--transition`); bar track/fill per design; new classes `.breadcrumb`, `.company-tabs`, `.company-tab`, `.company-tab.active`, `.link-btn`; no new icon fonts.
- **New files:** `components/CompanyTabs.tsx`, `components/CompanyNotFound.tsx`, `pages/Screening.tsx` (lightweight route + page); `App.tsx` route added before `/companies/:ticker`; `pages/Rankings.tsx` `placeholderData: keepPreviousData`; `client.ts` `useScreeningResult` (GET 404=null), `screenCompany` (POST), `useCompanyByTicker`/`useLatestPrice` no-retry-on-404; `format.ts` `formatPrice`/`formatVolume`/`formatAsOf` helpers.

## Verification gates
- `cd frontend && npm test` → green (quality.test.ts unchanged, no DOM dependency).
- `npm run lint` → clean.
- `npm run build` → clean build.

## Do not touch
- `backend/**` — already committed and green.
- API contracts (`.workflow/design/*.md`) — R16 is fixed.
- `DataQualityCard` internals beyond the one R16 line.
- No new dependencies; no `jsdom`; no chart libraries.

## Handoff
End with exactly one contract string: NEXT: qa-ui, BLOCKED: <question>, or DONE.