# Staff-frontend Lane F1 — ZBorsa Task 12a: Companies radar mode (2026-10-22)

Read first: docs/superpowers/plans/2026-10-17-zborsa-upgrade.md (Task 12), types `StanceResult`/`TargetLevel` already in `frontend/src/types/index.ts`, hook `useStanceRadar` already in `frontend/src/api/client.ts`. Scope (disjoint, yours only): `frontend/src/pages/Companies.tsx`, new `frontend/src/pages/companies/radarSort.ts`, `frontend/src/pages/companies/radarSort.test.ts`, optional `frontend/src/pages/Companies.css`. Do NOT touch `App.tsx`, `client.ts`, `types/index.ts`, `CompanyTabs.tsx`, `Statements.tsx`, `Ratios.tsx`, `Signals.tsx`, or any backend path.

## Work
Replace the card grid on `Companies.tsx` with the dense sortable radar table per plan Task 12:
- Columns: ticker/name, stance badge (tooltip = reason summary; show dash + `INSUFFICIENT_DATA` styling when stance fetch fails/absent), price as-of, score, tier badge, Shariah badge, gross margin (from ratios hook if wired — do not add new API client functions; if no hook exists for gross margin per company, render blank column with a header note `no data` rather than inventing a fetch), coverage dot.
- Guidance per plan/AGENTS.md: blank ≠ zero (null value renders as dash); colorblind-aware badge shapes, not color-only.
- `radarSort.ts`: pure `sortRadarRows(rows, key, dir)` — blanks always sort last, numeric-string values compare numerically, asc/desc. Write the FAILING vitest first (radarSort.test.ts), then implement, then PASS.
- Keep existing Companies page routing/params behavior intact.

## Gates (own files only, shared-tree rule)
Run `npx tsc --noEmit` and `npx eslint <touched files>` and `npx vitest run radarSort` scoped where possible; report outputs verbatim. Do NOT run `npm run build` (router runs tree gates after merge). Zero errors zero warnings.

## Rules
- Follow vercel-react-best-practices client/rerender/bundle/rendering/js rules.
- No invented data; missing value → dash + status label.
- Do NOT commit.

## Result contract
End with exactly one: `DONE` (gate evidence + file list), `BLOCKED: <question>`, `ASK USER`, `NEXT`.
