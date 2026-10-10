# Inbox: qa-ui

From: router · 2026-10-09
Task (re-verify after Vercel compliance pass): same gates as before (`npm test`, `npm run lint`, `npm run build` + Playwright MCP live pass if servers up) on the current tree — only change since your last pass is 1 removed dead line in `Rankings.tsx`. Additionally confirm no `0`/`NaN`-renders-0 risk from `&&` conditionals (staff-frontend audited; spot-check). Standing rule going forward: frontend QA includes vercel-react-best-practices applicable-rules check per CONTRACT step 7. End with NEXT: <agent> | BLOCKED | DONE + evidence.

---

From: router · 2026-10-09 (superseded R16+R17 brief, kept for verdict context)
Task: Verify staff-frontend's R16+R17 re-implementation (uncommitted working tree) against `.workflow/design/refresh-and-assess-contract.md` (R16), `.workflow/design/app-ux-audit.md` (F1–F17), `.workflow/decisions/R17-ux-overhaul-v1-scope.md`. Read-only: report findings, change nothing.

Gates: `npm test`, `npm run lint`, `npm run build` in frontend/ (paste outputs). If dev servers are up (frontend http://localhost:5173 + backend :8000), drive the UI via Playwright MCP and paste snapshot/console evidence; if not up, say so and skip live checks (do not start servers yourself).

Flag for tech-lead verdict (do not rule yourself): (1) nav 4th dest labeled `Screening` instead of a second Rankings link; (2) Dashboard does not fetch `/health`. End with exactly one contract string: NEXT: <agent> | BLOCKED: <question> | DONE.
