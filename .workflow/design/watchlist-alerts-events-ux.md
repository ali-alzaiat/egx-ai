# Watchlist / Alerts / Events UX overhaul — findings and fixes

Source: ux-expert review of the three continuous-intelligence pages (2026-10-17).
Methodology: review-only pass over `Watchlists.tsx`, `Alerts.tsx`, `Events.tsx` against the
platform invariant "no user-facing UUIDs", the zero-warning bar and R40's never-behind rule.

## Findings → resolution

### Watchlists
- **W1 (blocker) — dead-end rows.** Company not linked, thesis link was a raw UUID string,
  12 columns forced horizontal scroll. Fixed: company ticker links to
  `/companies/:ticker`, thesis link becomes "Open thesis" → `/companies/:ticker/thesis`;
  collapsed 12 → 7 columns (Company · Note · Price · Score · Shariah · Thesis · Actions);
  group renders as a chip under the company name; edit mode keeps all fields.
- **W2 — no list rename/delete.** NEEDS-BACKEND: `backend/app/api/watchlists.py` exposes
  POST/GET/DELETE over entries only, no PATCH/DELETE on the list itself. UI deliberately
  not built to avoid dead controls. Carried forward in STATUS.md.
- **W3 — price cell.** One column: `formatPrice` + `as of` sub-line (`formatAsOf`),
  change/staleness folded into a tooltip, amber `{d}d old` chip when staleness > 7 days.
  Score/Shariah/Thesis badges get a one-line "next step" hint pointing at the exact page
  action when the input is missing.
- **W4 — mobile cards.** `.wl-entries` grid already degrades; horizontal scroll retained as
  acceptable interim (no per-row card variant shipped yet).

### Alerts
- **A1 (blocker) — scope confusion.** Two independent "optional" selects meant an
  unscoped rule could be created by accident and scope semantics were invisible. Replaced
  with a scope radio (This company only / One watchlist / Whole universe) with consequence
  copy; document family locks the radio to per-list. One `resolvedWatchlistId` /
  `resolvedCompanyId` resolution path; friendly validation errors.
- **A2 — raw snapshot dumps.** Fired alerts showed the raw `inputs_snapshot` map. Now a
  designed per-family summary (threshold/direction/observed close + as-of; gap % / fair
  value; score move; filing fact count) with the full snapshot behind a "Technical details"
  fold.
- **A3 — linkable identifiers.** Rule/fired rows link list names to
  `/watchlists?list=…`, company labels to `/companies/:ticker`, and truncate unknown
  UUIDs with a title tooltip instead of printing full ids.
- **A4 — three-way grid cramped.** In-page tabs Build / Rules / Fired with counts,
  one section visible at a time.

### Events
- **E1 (blocker) — filter expected a UUID.** Symbol filter took raw input while the
  backend expects a company id. Fixed with a ticker dropdown (` TICKER — Name`) resolved
  via `getCompanyByTicker` on Apply; friendly 404 error with retry.
- **E2 — designed rows.** `prettifyEventType` ("fact.landed" → "Fact landed"), symbol
  shown as linked `Company: TICKER`, actor as "Recorded by the system / by you",
  details JSON behind a fold, supersedes anchors kept (`#event-{id}`).
- **E3 — empty states.** Filter-state and no-data empty states distinct ("Clear filters"
  action in the filtered one), `role="alert"` on the error panel.

## Test/gate evidence
- `npx tsc --noEmit` → 0 errors.
- `npx eslint src/pages/{Alerts,Events,Watchlists}.tsx` → clean.
- `npm run build` → 0 warnings (132 modules).
- `npm test -- --run` → 10/10.
- Backend untouched by this batch (scope-matching fix separately verified 653/653).
