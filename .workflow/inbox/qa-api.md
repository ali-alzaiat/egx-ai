# Inbox: qa-api

From: router · 2026-10-24
Task: targeted QA of the R43 backend (uncommitted working tree) against `.workflow/design/r43-computed-company-data.md` §1–3 and R43 acceptance criteria AC-1..AC-7, AC-10, AC-11 (`.workflow/decisions/R43-show-data-not-forms.md`).
Focus: (1) GET-only compute: first GET computes, second GET with no new inputs does not (AC-7); (2) INSUFFICIENT_DATA with the missing line named, never 0 (AC-3); (3) filing beats vendor + provenance/provisional on every M1 number (AC-4); (4) hooks: manual filing / approve / reject recompute only that company (AC-5); price-sync job recomputes synced tickers with per-step counts (AC-6); (5) the §3.2 routes are gone (404/405) and §3.3 routes still work; (6) migration 023 upgrade/downgrade; (7) concurrency: two parallel GETs on a stale company don't double-write or 500; (8) a compute error never 500s the request.
Use the isolated test DB only (write new tests under `backend/tests/` if a criterion lacks one — that is in your scope; no app code edits). Gates: pytest (targeted files + full run at the end), ruff, mypy — last 3 lines each.
Deliverable: `.workflow/research/qa-r43-api-2026-10-24.md` — findings table (AC, severity, evidence, file:line). End NEXT: staff-backend (findings) | DONE.
