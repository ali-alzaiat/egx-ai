# Inbox: staff-frontend-b (Lane B — Investment thesis page)

From: router (frontend parallel lanes, Batch B) · 2026-10-16
Task: CREATE `frontend/src/pages/Thesis.tsx` + `frontend/src/pages/Thesis.css` ONLY (both new).

Context (already landed by router, do NOT touch): hooks `useThesis`/`assessThesis`/`updateThesis` in `client.ts`, types `ThesisResponse` et al in `types/index.ts`. Backend (verified): `GET /api/theses/companies/{id}` → `{assessment: null | {header {fair_value {value,status}, horizon_years, is_shareholder}, narrative, assumptions[] {metric,value,horizon,source,author}, bulls[], bears[], scenarios{}, sensitivity{}, invalidations[] {metric,threshold,direction,period,evidence_source,action,status,…}, ledger[] {classification,variable,action,rationale,evidence,reviewer,created_at}, catalysts[] {id,event,date_from,date_to,window,variable,expectation,outcome,provenance,label}, confidence{}, dq{}, score, needs_reassessment, disclaimer}}`; `POST …/assess` (all fields optional); `POST …/update` `{rationale (REQUIRED — disable submit without it), reviewer, classification, invalidations[] {metric,status}, catalysts[] {catalyst_id,outcome}}` — 400 on empty rationale, unknown metric, bad outcome. Unassessed → empty state + assess button, never a default thesis.

Render: narrative skeleton, labelled-assumption table, bull/bear lists, scenarios + sensitivity (generic key/value, honest empty states), invalidation conditions with status + stored action, catalyst records, append-only ledger timeline (newest last or first — pick one, label it), assess + documented-update forms. Break-threshold language: "potentially invalidated under these assumptions" + confirm path; never auto-advice; no BUY/SELL anywhere.

Contract: `.workflow/design/frontend-catchup-contract.md` (Batch B + cross-cutting rules). Conventions: React 19 + TS + TanStack Query keyed `["thesis", id]`, invalidate on assess/update; INSUFFICIENT_DATA/UNKNOWN badges; `data_as_of` + 90-day staleness banner; methodology_version footnote + disclaimer; vercel-react-best-practices client/rerender/bundle/rendering/js rules (Next.js-only N/A — say so when skipping, never silently).

FORBIDDEN: every other existing file, backend/**, .workflow/**. No commits. No `npm run build`, no `npm test` (shared tree — router runs gates after merge). You may run `npx tsc --noEmit` and `npx eslint <your two files>` only. Component: default export `Thesis()` reading `ticker` via `useParams` + `useCompanyByTicker` (same pattern as InvestmentScore.tsx); include `<CompanyTabs ticker>` + not-found handling via `CompanyNotFound`.

Return: files created, tsc/eslint pasted output, wiring instructions (route `/companies/:ticker/thesis` — router adds). End with exactly one: NEXT: router | BLOCKED: <question> | DONE.
