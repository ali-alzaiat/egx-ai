# Inbox: staff-frontend-d2 (Lane D2 — Alerts page)

From: router (frontend parallel lanes, Batch D) · 2026-10-16
Task: CREATE `frontend/src/pages/Alerts.tsx` + `frontend/src/pages/Alerts.css` ONLY (both new). Global route (router mounts at `/alerts` + nav entry; do NOT touch Layout/App yourself).

Context (already landed by router, do NOT touch): hooks `useAlertRules`/`createAlertRule`/`updateAlertRule`/`deleteAlertRule`/`useFiredAlerts`/`ackFiredAlert` in `client.ts`, types `AlertRule`/`AlertFired` in `types/index.ts`. Backend (verified in `backend/app/api/alerts.py`): families `price` (params: threshold, direction above|below), `valuation_gap` (params: gap_pct), `document` (toggle-only, per-watchlist), `score_change` (threshold_pct, ±5% neutral band); `GET /api/alerts[?watchlist_id&company_id&family]`; `POST` {family,params,watchlist_id?,company_id?,enabled?}; `PATCH /{id}`; `DELETE /{id}`; `GET /fired[?rule_id&company_id&acked]` → rows {rule_id,company_id,inputs_snapshot,fired_at,acked_at}; `POST /{fired_id}/ack`.

Render: 4-family rule builder (family picker + family-specific params + company or watchlist scope + enabled toggle), rules list with enable/disable/delete, fired-alerts feed (rule, company, fired_at, inputs_snapshot summary, ack button; acked rows dimmed but kept). Per-list document toggles grouped by watchlist. No email/push (in-app feed only). Fired rows carry inputs snapshot visibly (fact ids + price as-of + methodology version where present). No BUY/SELL.

Contract: `.workflow/design/frontend-catchup-contract.md` (Batch D alerts + cross-cutting rules). Conventions: React 19 + TS + TanStack Query keys `["alertRules", params]`, `["firedAlerts", params]`, invalidate on mutations; vercel-react-best-practices client/rerender/bundle/rendering/js rules (Next.js-only N/A — say so when skipping).

FORBIDDEN: every other existing file, backend/**, .workflow/**. No commits. No build/test. tsc + eslint on your two files only.

Return: files created, tsc/eslint pasted output, wiring instructions (route + nav). End with exactly one: NEXT: router | BLOCKED: <question> | DONE.
