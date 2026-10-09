# Refresh & Assess Contract — closing the two Phase-1 data gaps

**From:** Tarek (architect) · 2026-10-09 · for tech-lead ruling, then staff-backend / staff-frontend
**Verified against live code this session:** `backend/app/ingestion/{sync.py,service.py,egx/provider.py}`,
`backend/app/dataquality/service.py`, `backend/app/api/{data_quality.py,data_sources.py,signals.py}`,
`backend/app/main.py`, `backend/app/db/session.py`, `backend/app/core/config.py`,
`backend/app/services/universe.py`, `frontend/src/api/client.ts`, `frontend/src/types/index.ts`,
`frontend/src/components/DataQualityCard.tsx`, `frontend/src/pages/{Rankings.tsx}`,
prior contracts `.workflow/design/data-quality-contract.md` and `data-quality-card-ux.md`,
roadmap cross-phase contracts (lines 88–94), rulings R12/R15.

**Gaps being closed:**
1. Market data is stale — ingestion is CLI-only (`python -m app.ingestion.sync`); no trigger exists in the app.
2. `data_quality_assessments` has 0 rows — only `POST /api/data-quality/companies/{id}/assess` creates them and nothing calls it.

---

## Decision 1 — Refresh trigger

**Ruling: an explicit user-triggered refresh endpoint that runs a managed in-process background job, polled by the client. CLI stays.**

`POST /api/ingestion/sync` returns **202** immediately with the job descriptor; a detached
`asyncio.create_task` runs *universe sync → price sync → assessment* using **its own**
sessions from `async_session_factory` (never the request session). The client polls
`GET /api/ingestion/sync/status` every 2 s while the job is live. A module-level
single-flight guard makes a second POST return **409** with the current job (mirrors the
`POST /api/signals/run` → 409 precedent in `api/signals.py:304`).

New code lives in the existing domain: job state + runner in `backend/app/ingestion/jobs.py`,
router `backend/app/api/ingestion.py` (prefix `/api/ingestion`), mounted in `main.py`.
**No new table, no migration** — job state is in-memory (process restart ⇒ `idle`; a lost
job has no consumer that cares in a single-user tool).

The runner reuses the CLI's building blocks: `UniverseService.sync()` then the concurrent
fetch / sequential-write pattern of `sync_prices` (`sync.py:68-128`). Small refactor: extract
the body of `sync_prices` into a function that **returns a summary** (counts, failures)
instead of only logging; the CLI keeps calling it and ignores/logs the return. The refresh
path automatically inherits R15's `last_synced_at` stamp because it writes through
`MarketDataIngestionService.write_prices` — verified: stamp is inside `write_prices`
(`service.py:104`), which is the only production write path.

### Status semantics

Six states (the inbox's five plus `idle`, which a status endpoint must have to distinguish
"nothing ever ran" from "finished"):

| status | meaning |
|---|---|
| `idle` | no job since process start (also the answer after a backend restart) |
| `accepted` | POST returned 202, task spawned, not yet in `prices` |
| `running` | job executing (payload carries `phase` + `progress`) |
| `done` | completed, zero ticker failures |
| `partial` | completed with ≥1 ticker failures (matches the CLI's "one bad ticker must not stop the run" behaviour, `sync.py:98`) — assessment still ran |
| `failed` | uncaught exception or wall-clock timeout; `error` carries the message |

Phase order is fixed: `universe` → `prices` → `assessment`. An exception in any phase →
`failed` (payload keeps whatever phase results already landed). Per-ticker price failures do
**not** fail the job; they land in `prices.failed_tickers` and yield `partial`. The
assessment phase runs whenever the prices phase *completes* (even with failures): assessing
stale data is valid — the freshness component scores the staleness honestly.

### Endpoints (exact)

**`POST /api/ingestion/sync`** — start (or refuse) a refresh.

Query params (all optional):
- `tickers` — comma-separated EGX tickers, uppercased server-side; omitted = full universe
- `history_days` — int, default `400`, clamped to `[1, 3650]` (mirrors CLI default)
- `universe_only` — bool, default `false` (skip prices *and* assessment; universe-only runs still skip assessment because there is nothing new to score beyond `updated_at`, which the profile scope already reads)

Responses:
- **202** — job accepted:
```json
{
  "status": "accepted",
  "started_at": "2026-10-09T15:40:12Z",
  "finished_at": null,
  "phase": null,
  "progress": null,
  "universe": null,
  "prices": null,
  "assessment": null,
  "error": null
}
```
- **409** — a job is live or finished-but-not-idle; body is the **current job object** in
  whatever state it is in (`running` … `failed`), so the adopting client can start polling
  without a second GET.
- **400** — malformed `tickers`/`history_days` (FastAPI validation).

**`GET /api/ingestion/sync/status`** — always **200**, no params. Body = the job object:

```json
{
  "status": "running",
  "started_at": "2026-10-09T15:40:12Z",
  "finished_at": null,
  "phase": "prices",
  "progress": { "completed": 118, "total": 229 },
  "universe": { "discovered": 229 },
  "prices": null,
  "assessment": null,
  "error": null
}
```

Finished example (`partial`):
```json
{
  "status": "partial",
  "started_at": "2026-10-09T15:40:12Z",
  "finished_at": "2026-10-09T15:47:03Z",
  "phase": null,
  "progress": { "completed": 229, "total": 229 },
  "universe": { "discovered": 229 },
  "prices": {
    "companies_fetched": 226,
    "companies_total": 229,
    "records_written": 56400,
    "failed_count": 3,
    "failed_tickers": [
      { "ticker": "USCA", "error": "Yahoo returned no history" },
      { "ticker": "SVCE", "error": "Yahoo returned no history" },
      { "ticker": "NCCM", "error": "TimeoutError: ..." }
    ]
  },
  "assessment": { "companies_assessed": 229, "scores_written": 687 },
  "error": null
}
```

`failed_tickers` is capped at the first **20** entries; `failed_count` always carries the
full number. `assessment.scores_written` counts rows actually upserted (company × 3 scopes;
same-day re-runs replace via the existing unique key `uq_data_quality_assessment`).

### Rejected alternatives (with cost-if-wrong)

| alternative | why rejected | cost if the rejection is wrong |
|---|---|---|
| APScheduler / cron / lifespan startup job | hidden network I/O at boot breaks tests and surprises dev; adds a dependency; a single-user tool needs a button, not a schedule | add a scheduler in Phase 12 hardening; job runner is reusable |
| `/api/admin/*` namespace | no auth, no admin concept exists; ceremony for one route | rename/prefix later; handlers unchanged |
| in-request synchronous sync (hold the HTTP request) | full sync = ~229 Yahoo fetches, minutes; proxy/browser timeouts; the inbox itself asks for `accepted` + polling | none — rejected on first principles |
| compute-on-read (GET triggers fetch) | GET must stay side-effect free; would silently couple every price read to Yahoo | none — hard reject, contract violation |
| persisted job table + migration | job history has no consumer; restart-loses-state is acceptable single-user; saves a migration and a model | add a table when multi-user lands; status endpoint shape is unchanged |
| per-company "re-assess" button on the DQ card | second trigger for a case (manual CLI ingest then want fresh scores) the full refresh already covers in minutes; scope cut | user runs full refresh for one company's scores; acceptable |

---

## Decision 2 — Automatic assessment

**Ruling: the refresh job's third phase assesses every company × all three scopes via the
existing `DataQualityService.assess`. `GET /api/data-quality/...` keeps its read-only
contract — unchanged.**

After the price phase completes, the job iterates all companies sequentially (one session,
commit per company, so a mid-loop crash keeps completed assessments) and calls
`assess(company_id, scope)` for `price_history`, `company_profile`, `financial_statements`.
That is ~3 rows per company, upserted on the existing key — idempotent, versioned
(`methodology_version` stored by `_persist`, `service.py:393-407`), no shape changes.

This closes gap 2 completely: after one refresh, the DQ card renders real scores (or honest
`MISSING` where rows are absent) for every company, and the screening embed
(`data_quality` on `GET /api/screening/companies/{id}`) stops being permanently `null`.

**Explicitly pinned, because the inbox asked:** `GET /api/data-quality/companies/{id}`
remains read-only — it returns latest *persisted* assessments and omits never-assessed
scopes, exactly as `.workflow/design/data-quality-contract.md` documents and the
implementation behaves (`data_quality.py:27-48`). No compute-if-missing, no writes on GET.
The per-company `POST .../assess` also stays as-is (API/testing surface; the frontend does
not call it in this contract — see rejected alternatives).

### Rejected alternatives (with cost-if-wrong)

| alternative | why rejected | cost-if-wrong |
|---|---|---|
| compute-if-missing on GET | writes on a read; breaks the frozen read-only GET contract and would make the screening embed trigger writes as a side effect | none — hard reject |
| startup assessment | slow boot, hidden DB writes, test interference; same objection as startup sync | none |
| separate batch `POST /api/data-quality/assess` (all companies) | redundant with the refresh job's phase for the only current caller need; adds a second write trigger to secure and test | add it later if re-assess-without-refetch is wanted; loop code is shared |
| frontend calls per-company POST assess from the card | second trigger + loading/error states on the card; the full refresh already covers it | user must full-refresh to update one company's scores (minutes) — accepted cut |
| assess only the tickers the price phase touched | leaves `company_profile` / `financial_statements` empty for everyone else; the 0-rows gap only half-closes; per-company page would show scores only for refreshed names | none — full-universe loop is ~687 in-DB computations, no network, seconds-scale |

---

## Decision 3 — Safety bounds

Pinned constraints (the inbox's safety clause, mapped to concrete mechanisms):

1. **Event loop never blocks.** Yahoo I/O already runs in worker threads
   (`anyio.to_thread.run_sync`, `egx/provider.py:137,157`); the job is a detached
   `asyncio.create_task`; POST returns 202 before any fetch starts. The task reference is
   held on the job state so it cannot be garbage-collected.
2. **Bounded wall clock.** New `Settings.SYNC_JOB_TIMEOUT_SECONDS: int = 1800`. The whole
   job runs under `asyncio.wait_for`; timeout ⇒ status `failed`, `error` names the timeout.
   Ticker list is finite; `history_days` clamped; provider concurrency stays at its default 8.
3. **One job at a time.** Module-level `asyncio.Lock`/flag; concurrent POST ⇒ 409 + current
   job. Two live syncs would double-hit Yahoo and interleave writes.
4. **Session boundary.** The job opens its own sessions from `async_session_factory`
   (`db/session.py:15`) — the same pattern the CLI uses. It never receives or mutates the
   request-scoped session from `get_session` (that one commits at request end; a background
   task must not share it).
5. **No new secrets, no new sources.** Payloads carry only counts and ticker/error strings.
   Prices still come from Yahoo via yfinance, universe from the existing
   `create_universe_source` — no new scraping surface, no robots/CAPTCHA changes.
6. **Honest failure.** `failed`/`partial` are visible states with reasons; the UI never
   shows stale data as fresh (see `last_synced_at` below).

---

## Decision 4 — Freshness visibility (`last_synced_at`)

The column exists (R15 / migration 011) but `GET /api/data-sources`
(`data_sources.py:14-29`) does not expose it. Pin: add `"last_synced_at": str | None`
(`.isoformat()` or `null`) to each source object in that response. The refresh button's
surrounding UI shows "Last refresh: {max last_synced_at}" — the user's proof the gap closed.
No schema change; one field, hand-serialized per the roadmap API convention.

---

## Decision 5 — Frontend surface

### Refresh button + status feedback

Placement: **CompanyDetail page header** (`.page-header`, beside the company title) — the
place staleness is actually noticed. It is a *global* action on a per-company page, so the
label says so: `Refresh market data` (secondary button style, not primary — it is
maintenance, not the page's job).

Follows the exact `runSignals` pattern (`Rankings.tsx:63-74`, `client.ts:172-176`): plain
async function + local `running` state + `queryClient.invalidateQueries` on completion.
No `useMutation` — the codebase does not use it; do not introduce it here.

Behaviour:
- Click → `startMarketRefresh()` → 202 → `running` local state on, status line appears.
- While job live: button disabled, label `Refreshing…`; status line under the button polls
  `GET /api/ingestion/sync/status` every **2 s** (`refetchInterval` active only while
  `status` is `accepted`/`running`, then stops):
  - phase `universe`: `Refreshing company list…`
  - phase `prices`: `Fetching prices {completed}/{total}…`
  - phase `assessment`: `Scoring data quality…`
- Terminal `done`: status line `Refresh complete — {records_written} price records, {scores_written} quality scores.` for ~4 s, then clears.
- Terminal `partial`: same line plus a warning-tone note `Some tickers failed ({failed_count}) — details in the browser console.` (console gets the full `failed_tickers`; no drill-down route exists, per the UX card rules).
- Terminal `failed`: `.alert.alert-error` with `Refresh failed: {error}`.
- 409 on click: adopt the returned job and start polling (user double-clicked or another tab started it).
- On any terminal state: invalidate query keys `["dataQuality"]`, `["signals"]`, `["prices"]`, `["latestPrice"]`, `["dataSources"]` (keys verified in `client.ts:74-84,102,114,143,179`).

### Data-quality card empty-state change

`DataQualityCard.tsx` empty branch (`items.length === 0`, lines 160-167) keeps its current
copy and gains one muted line directly under it:

> `Refresh market data to compute assessments for every company.`

Exact string pinned. No button inside the card (single trigger rule — see rejected
alternatives). This is a **one-line amendment** to `.workflow/design/data-quality-card-ux.md`
§5/§6 copy tables; everything else in that design stands unchanged. (That doc shipped with
Task 8; ux-expert should note the amendment at UX-review time.)

### TypeScript types (paste into `frontend/src/types/index.ts`)

```typescript
// ─── Market refresh (contract: .workflow/design/refresh-and-assess-contract.md) ─

export type SyncJobPhase = "universe" | "prices" | "assessment";

export type SyncJobState =
  | "idle"
  | "accepted"
  | "running"
  | "done"
  | "failed"
  | "partial";

export interface SyncJobProgress {
  completed: number;
  total: number;
}

export interface SyncJobFailure {
  ticker: string;
  error: string; // capped at 20 entries; see failed_count for the true total
}

export interface SyncJobPrices {
  companies_fetched: number;
  companies_total: number;
  records_written: number;
  failed_count: number;
  failed_tickers: SyncJobFailure[];
}

export interface SyncJobAssessment {
  companies_assessed: number;
  scores_written: number;
}

// Job object returned by POST /api/ingestion/sync (202 and 409 bodies)
// and GET /api/ingestion/sync/status (always 200)
export interface SyncJobStatus {
  status: SyncJobState;
  started_at: string | null; // ISO datetime or null when idle
  finished_at: string | null;
  phase: SyncJobPhase | null;
  progress: SyncJobProgress | null;
  universe: { discovered: number } | null;
  prices: SyncJobPrices | null; // null until the prices phase completes
  assessment: SyncJobAssessment | null; // null until the assessment phase completes
  error: string | null;
}

// GET /api/data-sources — existing DataSource gains one field:
export interface DataSource {
  id: string;
  name: string;
  source_type: "EGX" | "FRA" | "COMPANY" | "DATA_PROVIDER" | "MANUAL" | "SYNTHETIC";
  base_url: string | null;
  description: string | null;
  last_synced_at: string | null; // ISO datetime, null = never synced
}
```

All existing data-quality types (`DataQualityScore`, `DataQualityListResponse`, …) are
**unchanged** — see `data-quality-contract.md`.

### Client functions (in `frontend/src/api/client.ts`)

```typescript
// POST /api/ingestion/sync — follows the runSignals pattern (plain fetch, not useMutation)
export async function startMarketRefresh(params?: {
  tickers?: string;
  history_days?: number;
  universe_only?: boolean;
}): Promise<SyncJobStatus>;

// GET /api/ingestion/sync/status
export function useSyncStatus(): UseQueryResult<SyncJobStatus>;
// refetchInterval: 2000 while status is "accepted" | "running", false otherwise
```

### Mock payloads (for frontend build-before-backend)

**idle:**
```json
{
  "status": "idle",
  "started_at": null,
  "finished_at": null,
  "phase": null,
  "progress": null,
  "universe": null,
  "prices": null,
  "assessment": null,
  "error": null
}
```

**running (prices phase):** the mid-run example in Decision 1.

**done:**
```json
{
  "status": "done",
  "started_at": "2026-10-09T15:40:12Z",
  "finished_at": "2026-10-09T15:46:51Z",
  "phase": null,
  "progress": { "completed": 229, "total": 229 },
  "universe": { "discovered": 229 },
  "prices": {
    "companies_fetched": 229,
    "companies_total": 229,
    "records_written": 56800,
    "failed_count": 0,
    "failed_tickers": []
  },
  "assessment": { "companies_assessed": 229, "scores_written": 687 },
  "error": null
}
```

**partial:** the finished example in Decision 1.

**failed:**
```json
{
  "status": "failed",
  "started_at": "2026-10-09T15:40:12Z",
  "finished_at": "2026-10-09T15:42:40Z",
  "phase": "prices",
  "progress": null,
  "universe": { "discovered": 229 },
  "prices": null,
  "assessment": null,
  "error": "TimeoutError: refresh exceeded 1800s"
}
```

**data-sources with the new field:**
```json
[
  {
    "id": "5f0c…",
    "name": "YAHOO_FINANCE_EGX",
    "source_type": "DATA_PROVIDER",
    "base_url": "https://finance.yahoo.com",
    "description": null,
    "last_synced_at": "2026-10-09T15:46:49Z"
  }
]
```

---

## Cross-phase contract compliance (checked, line by line)

| roadmap contract (lines 88–94) | this design |
|---|---|
| `DataQualityScore` consumed by Phases 3–5, `None` never a default | untouched — we add callers of `assess()`, no shape change; GET still returns `None`-means-absent |
| New domain code at `backend/app/<domain>/` | no new package — job state in existing `app/ingestion/jobs.py`, router in existing `app/api/` |
| One migration per phase, numbered from 010 | **no migration** — in-memory job state, `last_synced_at` column already exists |
| One router per domain, `/api/<domain>/…`, mounted in `main.py`, hand-serialized dicts, `str()`/`.isoformat()` | `app/api/ingestion.py`, prefix `/api/ingestion`, non-company-scoped like the existing `/api/signals/run` and `/api/data-sources` exceptions; payload is primitives only |
| Persisted scores store `methodology_version` | unchanged — `DataQualityService._persist` already writes it; assessment phase reuses that path verbatim |
| R15 (`last_synced_at` stamped in `write_prices`) | inherited automatically — the job writes through `write_prices`; no stamping code duplicated |

No drift found; nothing here needs a `BLOCKED:` escalation.

## Implementation notes for staff-backend (scope sketch, not a plan)

- `backend/app/ingestion/jobs.py` — frozen-in-memory `SyncJob` state, single-flight lock,
  `run_refresh(tickers, history_days, universe_only)` as the composed job; returns/updates
  the job object; wraps everything in `asyncio.wait_for(settings.SYNC_JOB_TIMEOUT_SECONDS)`.
- `backend/app/ingestion/sync.py` — extract summary-returning core from `sync_prices`;
  CLI behaviour unchanged.
- `backend/app/api/ingestion.py` — the two routes + 409 path; hand-serialized job dict.
- `backend/app/core/config.py` — `SYNC_JOB_TIMEOUT_SECONDS`.
- `backend/app/api/data_sources.py` — add `last_synced_at` to the payload.
- `backend/app/main.py` — mount the new router.
- Tests: 202-then-idle-to-done happy path (fake provider), 409 single-flight, partial on
  one failing ticker, failed on raised exception, timeout → failed, assessment rows exist
  after job (`data_quality_assessments` count), GET status always 200, GET data-quality
  still read-only (no rows created by the GET), data-sources exposes `last_synced_at`.

## Implementation notes for staff-frontend (scope sketch)

- Types above pasted verbatim; `startMarketRefresh` + `useSyncStatus` in `client.ts`.
- CompanyDetail header button + polling status line; invalidation list per Decision 5.
- `DataQualityCard` empty state: one added muted line, exact string pinned above.
- Mocks: the five job payloads + data-sources sample above.

## Cost-if-wrong summary (the whole ruling, one glance)

| decision | if wrong | blast radius |
|---|---|---|
| in-process job, no job table | need persistence for multi-user | job state module swaps internals; endpoints unchanged |
| 202 + poll, not synchronous | none foreseeable for a single-user LAN tool | client helper only |
| 6 statuses incl. `idle` | consumers handle one extra state | additive union member |
| assessment inside the refresh job | need re-assess-without-refetch | add batch endpoint later; loop shared |
| GET data-quality stays read-only | none — frozen contract | — |
| 20-cap on `failed_tickers` | user wants full failure list in UI | raise cap or paginate; field names stable |
| timeout default 1800 s | slow networks time out mid-run | one env var |
| CompanyDetail header placement | ux-expert moves the button | markup only |
| `last_synced_at` added to data-sources | none — additive field | — |
