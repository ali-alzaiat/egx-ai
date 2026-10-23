# Inbox: qa-ui

From: router (baseline before redesign, Claude Code runtime) · 2026-10-23
Task: Baseline functional audit of EVERY screen, in English and in Arabic (RTL), before the UI revamp. Start the UI with `mcp__Claude_Browser__preview_start` name `frontend` (it proxies /api to the running backend on :8000 with the API token). Routes (from `frontend/src/App.tsx`): /, /recommendations, /intake, /companies, /rankings, /screening, /watchlists, /alerts, /events, and for a company with real data (use COMI and AMOC) every tab: /companies/:ticker, /financials, /metrics, /screening, /valuation, /technical, /ai, /score, /peers, /thesis, /disclosures, /signals, /statements, /ratios. For each screen record: HTTP errors (read_network_requests), console errors (read_console_messages, errors only), broken/empty states that should have data, untranslated English left in Arabic mode, RTL layout breaks (mirroring, numbers, tables), overflow at mobile width (resize_window preset mobile, then reset to desktop). Switch language with the sidebar language button. Do NOT submit any form that writes to the database. Also run the gates: `cd frontend && npx tsc -b && npm run lint && npx vitest run && npm run build`. Report a findings table (screen, lang, severity, evidence) — evidence only, no opinions. End NEXT: tech-lead | BLOCKED: <question> | DONE.

---

From: router (frontend parallel lanes, Batches B–D merge) · 2026-10-16
Task: Live UI verification of all new Batch A–D pages. Start the stack yourself: `docker compose up -d postgres`, backend (`cd backend && .venv/bin/python -m alembic upgrade head && .venv/bin/python -m pytest -q` must be green first — if red, STOP and report BLOCKED), seed if empty (`python -m app.seed.seed`), `uvicorn app.main:app --port 8000`; frontend `cd frontend && npm run dev` (default http://localhost:5173).

Verify with Playwright MCP (`@playwright/mcp`, `playwright_*` tools; paste snapshot/console output as evidence):
- `/companies/COMI/score` (assess flow, components, confidence, staleness copy), `/screening` pages (breakdown + purification + EGX33), `/companies/COMI/valuation` (fair value + assumptions + sensitivity), `/companies/COMI/peers`, `/companies/COMI/thesis` (assess + documented update), `/companies/COMI/disclosures` (+ FinancialData header link), `/watchlists`, `/alerts`, `/events` (nav entries work).
- Zero console errors on every page; loading/empty/error states render (not blank); INSUFFICIENT_DATA badges visible; rule-10 copy (no BUY/SELL text anywhere — grep the DOM).
- Run `npm run build && npm run lint && npm test` in frontend/ and paste outputs.

Vercel skill check on the new pages (client/rerender/bundle/rendering/js rules; Next.js-only N/A — list skipped rules with reasons); violations are blockers.

Return: per-page verdicts + pasted evidence (console output, snapshots). QA findings are blockers. End with exactly one: NEXT: tech-lead | BLOCKED: <question> | DONE.
