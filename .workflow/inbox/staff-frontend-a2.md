# Inbox: staff-frontend-a2 (Lane A2 — Shariah v2)

From: router (frontend parallel lanes) · 2026-10-16
Task: Own Lane A2 end-to-end: `frontend/src/pages/ShariahScreening.tsx` + `frontend/src/pages/ShariahScreening.css` ONLY.

Context (already landed by router, do NOT touch): hooks `usePurification`/`estimatePurification`/`useEgxMembership`/`recordEgxMembership` in `client.ts`, types `PurificationEstimate`/`EgxMembership` + v2 `ScreeningRuleResult` provenance fields in `types/index.ts`. Backend: verify shapes yourself in `backend/app/api/screening.py` — per-rule breakdown (pass/fail/UNKNOWN + threshold + report_date + missing_input/source/source_date), `GET/POST …/purification` (EGP math + inputs; amount stays empty until a ratio exists), `GET/POST …/egx-membership` (Feb/Aug review cycle, side-by-side — membership never overrides the verdict). Keep existing v1 behavior working.

Contract: `.workflow/design/frontend-catchup-contract.md` (Batch A.2 + cross-cutting rules). Conventions: React 19 + TS + TanStack Query; INSUFFICIENT_DATA/UNKNOWN badges with reasons; methodology_version footnote; reconciliation-never-override copy; rule-10 copy (no BUY); vercel-react-best-practices skill, client/rerender/bundle/rendering/js rules only.

FORBIDDEN: `client.ts`, `types/index.ts`, `App.tsx`, `CompanyTabs.tsx`, any other existing file, backend/**, .workflow/**. No commits. No `npm run build`, no `npm test` (shared tree — router runs gates after merge). You may run `npx tsc --noEmit` and `npx eslint <your two files>` only.

Deliverable: complete, polished Lane A2 files. Return: files changed, tsc/eslint pasted output, any gaps as wiring instructions for the router (not edits). End with exactly one: NEXT: router | BLOCKED: <question> | DONE.
