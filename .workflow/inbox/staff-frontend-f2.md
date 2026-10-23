# Inbox: staff-frontend-f2

# Staff-frontend Lane F2 — ZBorsa Task 12b: Statements + Ratios tabs (2026-10-22)

Read first: docs/superpowers/plans/2026-10-17-zborsa-upgrade.md (Task 12 + Task 7 output shapes); backend response shapes: `GET /api/statements/companies/{ticker}/statements` (StatementBundle: periods desc, sections income/balance/cash_flow, each line has `label_en`, `label_ar`, `value|null`, `currency`, `status`, provenance fields `source_label_reported`, `source_page`, `published_date`) and `GET /api/statements/companies/{ticker}/ratios` (code/value/status/reason). Hooks `useStatements`/`useRatios` and the types already exist. Scope (disjoint, yours only): `frontend/src/pages/Statements.tsx` + new `Statements.css`, `frontend/src/pages/Ratios.tsx` + new `Ratios.css`. Do NOT touch `App.tsx`, `client.ts`, `types/index.ts`, `CompanyTabs.tsx`, `Companies.tsx`, `Signals.tsx`, or any backend path.

## Work
1. **Statements.tsx:** render the current `Statements.tsx` skeleton into the designed page — period grouping (quarterly/annual headers), three section tables per period, EN label primary + `label_ar` secondary (render AR when the app lang from `useLang()` hook — read frontend/src/i18n/useLang.ts — is `ar`, else EN), `INSUFFICIENT_DATA`/null value rows render **dash, never 0**, provenance sub-line under each value (source label + page + published date). Internal-bank emphasis note: compliance copy none needed here.
2. **Ratios.tsx:** render table with human ratio names mapping (a small local const map code → EN display name is fine; AR display name too), value/status column, `reason` shown as tooltip or muted sub-line when status is INSUFFICIENT_DATA; blank/dash handling same as above.
3. Write both pages then scope-check: `npx tsc --noEmit`, `npx eslint <touched files>`. Do NOT run `npm run build` (router runs tree gates after merge). Zero errors zero warnings.

## Rules
- vercel-react-best-practices applicable rules; no untyped `any`; follow existing page patterns (e.g. StatementReview if any) for styling/semantics.
- No invented data — all values come from the API payload.
- Do NOT commit.

## Result contract
End with exactly one: `DONE` (gate evidence + file list), `BLOCKED: <question>`, `ASK USER`, `NEXT`.
