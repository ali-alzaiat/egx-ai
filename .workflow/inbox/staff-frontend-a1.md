# Inbox: staff-frontend-a1 (Lane A1 — Investment score)

From: router (frontend parallel lanes) · 2026-10-16
Task: Own Lane A1 end-to-end: `frontend/src/pages/InvestmentScore.tsx` + `frontend/src/pages/InvestmentScore.css` ONLY.

Context (already landed by router, do NOT touch): hooks `useScore`/`assessScore` in `frontend/src/api/client.ts`, types `ScoreResponse` et al in `frontend/src/types/index.ts`, route `/companies/:ticker/score` in `App.tsx`, `Score` tab in `CompanyTabs.tsx`. Backend: `GET/POST /api/scores/companies/{id}` — verify shapes yourself in `backend/app/api/scores.py` + `app/scores/service.py` (`assessment: null` = never assessed → empty state + assess button, never a default score).

Contract: `.workflow/design/frontend-catchup-contract.md` (Batch A.1 + cross-cutting rules). Conventions: React 19 + TS + TanStack Query; INSUFFICIENT_DATA badges; `data_as_of` + 90-day staleness banner; methodology_version footnote; rule-10 copy (no BUY); vercel-react-best-practices skill, client/rerender/bundle/rendering/js rules only.

FORBIDDEN: `client.ts`, `types/index.ts`, `App.tsx`, `CompanyTabs.tsx`, any other existing file, backend/**, .workflow/**. No commits. No `npm run build`, no `npm test` (shared tree — router runs gates after merge). You may run `npx tsc --noEmit` and `npx eslint <your two files>` only.

Deliverable: complete, polished Lane A1 files. Return: files changed, tsc/eslint pasted output, any gaps you could not close (as wiring instructions for the router, not edits). End with exactly one: NEXT: router | BLOCKED: <question> | DONE.
