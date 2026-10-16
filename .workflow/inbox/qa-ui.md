# Inbox: qa-ui

From: router (frontend parallel lanes, Batches B–D merge) · 2026-10-16
Task: Live UI verification of all new Batch A–D pages. Start the stack yourself: `docker compose up -d postgres`, backend (`cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m pytest -q` must be green first — if red, STOP and report BLOCKED), seed if empty (`python -m app.seed.seed`), `uvicorn app.main:app --port 8000`; frontend `cd frontend && npm run dev` (default http://localhost:5173).

Verify with Playwright MCP (`@playwright/mcp`, `playwright_*` tools; paste snapshot/console output as evidence):
- `/companies/COMI/score` (assess flow, components, confidence, staleness copy), `/screening` pages (breakdown + purification + EGX33), `/companies/COMI/valuation` (fair value + assumptions + sensitivity), `/companies/COMI/peers`, `/companies/COMI/thesis` (assess + documented update), `/companies/COMI/disclosures` (+ FinancialData header link), `/watchlists`, `/alerts`, `/events` (nav entries work).
- Zero console errors on every page; loading/empty/error states render (not blank); INSUFFICIENT_DATA badges visible; rule-10 copy (no BUY/SELL text anywhere — grep the DOM).
- Run `npm run build && npm run lint && npm test` in frontend/ and paste outputs.

Vercel skill check on the new pages (client/rerender/bundle/rendering/js rules; Next.js-only N/A — list skipped rules with reasons); violations are blockers.

Return: per-page verdicts + pasted evidence (console output, snapshots). QA findings are blockers. End with exactly one: NEXT: tech-lead | BLOCKED: <question> | DONE.
