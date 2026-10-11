# Inbox: architect

From: router (user directive: frontend far behind backend) · 2026-10-11
Task: Frontend catch-up contract — map EVERY backend surface with no UI to frontend routes/components/hooks, organized in implementable batches.

Context: backend has 20 routers (`backend/app/api/`: ai, alerts, companies, data_quality, data_sources, disclosures, events, financial, health, industry, ingestion, metrics, scores, screening, signals, technical, theses, triggers, valuation, watchlists). Frontend (`frontend/src/`) has pages for companies/prices/metrics/financials/screening-v1/signals/technical/valuation-v1/data-quality/AI only — hooks in `frontend/src/api/client.ts` (25 hooks, no industry/scores/theses/disclosures/watchlists/alerts/triggers/events). Company nav: `frontend/src/components/CompanyTabs.tsx` (7 views). No UI for Phases 2–8 backends (industry/peers, 4-model valuation, investment scores, theses, Shariah v2 breakdown+purification, disclosures/parse/diffs, watchlists/alerts/triggers/event ledger). Valuation/Screening pages predate their v2 backends — mark what is stale vs missing.

Inputs to read: the backend routers + schemas above (verify request/response shapes yourself — they are the contract source of truth), `frontend/src/api/client.ts`, `App.tsx`, `CompanyTabs.tsx`, research files `.workflow/research/phase-*.md` + `app-wide-ux-patterns.md` (SWS feed-first, Koyfin table mechanics already researched — reuse, don't redo), AGENTS.md rule 10 (no BUY language) + vercel-react-best-practices constraints (client/rerender/bundle/rendering/js rules; Next.js-only N/A).

Deliverable (return inline; router files as `.workflow/design/frontend-catchup-contract.md`): per missing surface — route, components, TanStack Query hooks, backend endpoints consumed (with shapes), loading/empty/error + INSUFFICIENT_DATA + staleness display rules, what existing pages need upgrading (valuation v2, screening v2) vs new pages; batches ordered by dependency (each batch independently shippable + QA-able, with acceptance); what is explicitly NOT in v1. No code, no file writes. End NEXT: ux-expert | BLOCKED: <question> | DONE.

---

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
