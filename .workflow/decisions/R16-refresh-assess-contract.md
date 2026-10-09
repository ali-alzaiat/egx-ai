# R16 — Refresh & Assess contract: ACCEPTED with one binding amendment

**From:** Mostafa (tech-lead) · 2026-10-09
**Subject:** `.workflow/design/refresh-and-assess-contract.md` (Tarek, architect) — Stream A, "fix the gaps"
**Verdict:** **Accepted as the single source of truth for Stream A**, amended only by A1 below.
A1 is binding on staff-backend; everything else in the contract stands verbatim (JSON shapes,
TS types, status semantics, rejected alternatives, cost-if-wrong tables).

## What I verified myself (not taken on trust)

Every load-bearing claim in the contract I re-checked against the repo this session:

| Contract claim | Verified |
|---|---|
| 409 single-flight precedent in `POST /api/signals/run` | ✅ `backend/app/api/signals.py` raises `HTTPException(409)` on the busy path |
| `write_prices` stamps `DataSource.last_synced_at` (R15 inheritance) | ✅ `backend/app/ingestion/service.py` — `data_source.last_synced_at = datetime.now(UTC)` inside `write_prices`, before commit |
| Job opens its own sessions; never the request session | ✅ `backend/app/db/session.py` — `async_session_factory` exists; `get_session` commits at request end |
| `GET /api/data-sources` does **not** expose `last_synced_at` | ✅ `backend/app/api/data_sources.py` payload has id/name/source_type/base_url/description only |
| `DataQualityService.assess(company_id, scope, as_of=None)` exists; `_persist` writes `methodology_version` | ✅ `backend/app/dataquality/service.py` |
| Yahoo I/O already on worker threads (event loop never blocks) | ✅ `backend/app/ingestion/egx/provider.py` — `anyio.to_thread.run_sync` at two call sites |
| `sync_prices` at `sync.py:68`, "one bad ticker must not stop the run" at `:98`, CLI `--history-days` default 400 | ✅ all three |
| New files are new (`app/api/ingestion.py`, `app/ingestion/jobs.py`) and the router is not yet mounted | ✅ neither file exists; `main.py` has no ingestion router; `SYNC_JOB_TIMEOUT_SECONDS` absent from `Settings` |
| Frontend anchors: DQ card empty branch, `client.ts` query keys, `runSignals` pattern | ✅ `DataQualityCard.tsx` (`data && items.length === 0`), keys `dataQuality`/`prices`/`latestPrice`/`signals`/`dataSources` in `client.ts`, plain async `handleRun` in `Rankings.tsx` |

No claim I checked was wrong. Cross-phase contract table (roadmap lines 88–94) also holds:
no migration, no shape change to `DataQualityScore`, router under `app/api/` + `main.py`.

## A1 — binding amendment: 409 only while a job is live

**Contract as written:** "409 — a job is live *or finished-but-not-idle*."

**Amended:** `POST /api/ingestion/sync` returns **409 only when `status ∈ {accepted, running}`**.
When the stored job is terminal (`done` / `partial` / `failed`) or there has never been a job
(`idle`), the POST **starts a new job**, returns 202, and replaces the stored job object.

**Why:** as written, the first successful refresh puts the process in `done` forever, and every
subsequent click of the refresh button — the entire point of the feature, "refresh again
tomorrow" — returns 409 until the backend restarts. The contract defines no transition back to
`idle`, and the frontend flow ("409 on click → adopt the returned job and start polling") would
adopt a stale finished job and never refresh again. The single-flight rule the 409 exists to
enforce (one live job, no double-hit on Yahoo, no interleaved writes) is fully preserved.

**Cost if wrong:** none foreseeable. The only behaviour I remove is a permanent lock-out after
the first run; the only behaviour I keep is "cannot start a job while one is running".

**Test pin (added to the brief):** after a job reaches a terminal state, a second POST → 202 and
a *new* `started_at`; while a job is running, a second POST → 409 with the live job object.

## C1 — clarification (not an amendment)

`history_days`: out-of-range integers are **clamped** to `[1, 3650]` silently (no error), per the
contract's own text; a non-integer or malformed `tickers` value surfaces as FastAPI's normal
validation status. Neither error path is special-cased by the frontend — it shows a generic
failure line. No shape changes.

## What this ruling authorises

- The staff-backend brief at
  `.superpowers/sdd/2026-10-08-competitive-enhancement-roadmap/task-refresh-assess-brief.md`
  (authored by this ruling; A1/C1 folded in).
- Stream A backend starts **now**, in parallel with Stream B design (disjoint trees:
  `backend/app/**` vs `.workflow/design/**`).
- The frontend half of this contract (Decision 5: refresh button, status line, DQ empty-state
  line, TS types, mocks) is **deferred to the single staff-frontend task** that also implements
  the UX overhaul — see R17. Placement of the refresh button may be moved by that UX spec;
  the contract's labels, payloads and behaviour are not open for re-decision.
