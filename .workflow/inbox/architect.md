# Inbox: architect

From: router (user directive) · 2026-10-09
Task: Define the contract that closes the two Phase-1 data gaps the user reported.

The gaps (verified against the live DB):
1. Market data is stale — ingestion is a manual CLI (`python -m app.ingestion.sync` in
   `backend/app/ingestion/sync.py`); no scheduler, cron, lifespan hook or refresh
   endpoint exists anywhere in `backend/app`.
2. Data-quality scores are empty for every company — `data_quality_assessments` has 0
   rows because only `POST /api/data-quality/companies/{id}/assess` creates them and
   nothing ever calls it automatically.

Read before deciding: `backend/app/ingestion/{sync.py,service.py}`,
`backend/app/dataquality/service.py`, `backend/app/api/data_quality.py`,
`backend/app/api/data_sources.py`, `backend/app/main.py`, `backend/app/db/session.py`,
`backend/app/core/config.py`.

Decide and pin, with a recommendation, the alternatives you rejected, and the cost if wrong:
- **Refresh trigger.** In-request background task, APScheduler startup job, a
  `/api/admin/*` endpoint the UI calls, CLI-only + a button, or compute-on-read. Note
  ingestion does network I/O and can take a while; this is a single-user research tool.
  Give the exact endpoint(s): method, path, request/response JSON, status semantics
  (`accepted`/`running`/`done`/`failed`/`partial`), and how a client polls progress.
- **Automatic assessment.** After a sync, a batch/assess-all endpoint, compute-if-missing
  on `GET`, or startup. State whether `GET /api/data-quality/...` keeps its read-only
  contract. Give exact shapes.
- **Frontend surface** implied by the above: refresh button placement + status feedback,
  and how the data-quality card's empty state changes.
- **Safety:** no network call or long job may block the event loop or a request without a
  bound; no secret leaks; respect robots/CAPTCHA rules already in the providers.

Deliverable: `.workflow/design/refresh-and-assess-contract.md` — endpoints, exact JSON
shapes, the TypeScript types the frontend declares, and a mock payload for each. No code.
Report the summary inline; the router files it.

End with exactly one contract string: NEXT: tech-lead, BLOCKED: <question>, or DONE.
