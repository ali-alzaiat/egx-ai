# Inbox: staff-frontend-d3 (Lane D3 — Events ledger page)

From: router (frontend parallel lanes, Batch D) · 2026-10-16
Task: CREATE `frontend/src/pages/Events.tsx` + `frontend/src/pages/Events.css` ONLY (both new). Global route (router mounts at `/events` + nav entry; do NOT touch Layout/App yourself).

Context (already landed by router, do NOT touch): hooks `useEvents`/`exportEvents` in `client.ts`, type `PhaseEvent` in `types/index.ts`. Backend (verified in `backend/app/api/events.py`): `GET /api/events[?symbol&type&date_from&date_to&limit&offset]` → rows {id,ts,actor_type,actor_id,rule_version,type,symbols[],inputs_snapshot,reason,supersedes_id}; `GET /api/events/export[…]` → {events,total,filters} (JSON download via blob link — no CSV).

Render: append-only ledger feed (newest first), filters (symbol/company, event type, date range), per-row ts/actor/type/symbols/reason + inputs_snapshot detail (fact ids + price as-of + methodology version where present) + supersedes link, SWS-style validate-or-invalidate framing per item (copy only), JSON export button (download `events.json` via Blob). Corrections appear as new rows referencing the old (never mutate). No BUY/SELL.

Contract: `.workflow/design/frontend-catchup-contract.md` (Batch D events + cross-cutting rules). Conventions: React 19 + TS + TanStack Query key `["events", params]`; vercel-react-best-practices client/rerender/bundle/rendering/js rules (Next.js-only N/A — say so when skipping).

FORBIDDEN: every other existing file, backend/**, .workflow/**. No commits. No build/test. tsc + eslint on your two files only.

Return: files created, tsc/eslint pasted output, wiring instructions (route + nav). End with exactly one: NEXT: router | BLOCKED: <question> | DONE.
