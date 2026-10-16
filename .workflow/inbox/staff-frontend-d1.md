# Inbox: staff-frontend-d1 (Lane D1 — Watchlists page)

From: router (frontend parallel lanes, Batch D) · 2026-10-16
Task: CREATE `frontend/src/pages/Watchlists.tsx` + `frontend/src/pages/Watchlists.css` ONLY (both new). Global route (router mounts at `/watchlists` + nav entry; do NOT touch Layout/App yourself).

Context (already landed by router, do NOT touch): hooks `useWatchlists`/`createWatchlist`/`useWatchlistEntries`/`addWatchlistEntry`/`updateWatchlistEntry`/`deleteWatchlistEntry` in `client.ts`, types `Watchlist`/`WatchlistEntry`/`PhaseBadge` in `types/index.ts`. Backend (verified in `backend/app/schemas/continuous.py` + `api/watchlists.py`): `GET /api/watchlists` → `[{id,user_id,name,created_at}]`; `POST` {name} → created; `GET /{id}/entries` → entries with computed badges {price,change,as_of,staleness,score,shariah_state,thesis_link_badge} each {value,status,reason} + company_ticker/company_name; `POST /{id}/entries` {company_id,group?,note?,thesis_link?}; `PATCH /{id}/entries/{eid}`; `DELETE …`. Single fixed server user — no auth UI needed.

Render: multi-list CRUD (create list, select list), entries table with group/note/thesis-link editing + per-row badges (or INSUFFICIENT_DATA badge, never blank), delete entry, data_as_of + staleness display per entry. Validate-then-invalidate pattern: SWS-style "validate or invalidate your narrative" framing per item where a thesis link exists (copy only, no advice). No BUY/SELL.

Contract: `.workflow/design/frontend-catchup-contract.md` (Batch D watchlists + cross-cutting rules). Conventions: React 19 + TS + TanStack Query keys `["watchlists"]`, `["watchlistEntries", id]`, invalidate on mutations; methodology_version footnote; vercel-react-best-practices client/rerender/bundle/rendering/js rules (Next.js-only N/A — say so when skipping).

FORBIDDEN: every other existing file, backend/**, .workflow/**. No commits. No build/test. tsc + eslint on your two files only.

Return: files created, tsc/eslint pasted output, wiring instructions (route + nav). End with exactly one: NEXT: router | BLOCKED: <question> | DONE.
