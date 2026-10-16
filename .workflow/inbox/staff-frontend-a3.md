# Inbox: staff-frontend-a3 (Lane A3 — Valuation v2)

From: router (frontend parallel lanes) · 2026-10-16
Task: Own Lane A3 end-to-end: `frontend/src/pages/Valuation.tsx` ONLY (+ optional NEW files `frontend/src/components/FairValueCard.tsx`, `FairValueCard.css`, `SensitivityTable.tsx` — nothing else).

Context (already landed by router, do NOT touch): hook `useFairValue` in `client.ts`, type `FairValueResponse` in `types/index.ts`. Backend: verify shapes yourself in `backend/app/api/valuation.py` + `app/valuation/service.py` — `GET …/fair-value` (per-model legs + weights, weighted FV, bull/base/bear, ±1% sensitivity list, DQ confidence ladder). Keep the existing `POST …/calculate` flow working. Fair value ALWAYS paired with assumptions + sensitivity table; DEGRADED data → widened range + caveat, never a bare point estimate.

Contract: `.workflow/design/frontend-catchup-contract.md` (Batch A.3 + cross-cutting rules). Conventions: React 19 + TS + TanStack Query; INSUFFICIENT_DATA badges; `data_as_of` + staleness; methodology_version footnote; rule-10 copy (no BUY); vercel-react-best-practices skill, client/rerender/bundle/rendering/js rules only.

FORBIDDEN: `client.ts`, `types/index.ts`, `App.tsx`, `CompanyTabs.tsx`, any other existing file, backend/**, .workflow/**. No commits. No `npm run build`, no `npm test` (shared tree — router runs gates after merge). You may run `npx tsc --noEmit` and `npx eslint <your files>` only.

Deliverable: complete, polished Lane A3 files. Return: files created/changed, tsc/eslint pasted output, any gaps as wiring instructions for the router (not edits). End with exactly one: NEXT: router | BLOCKED: <question> | DONE.
