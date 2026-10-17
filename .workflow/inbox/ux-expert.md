# Inbox: ux-expert

From: router (UX overhaul: Watchlists / Alerts / Events) · 2026-10-16
Task: Live UX review of three pages + concrete, implementable fix list. Dev servers are already up (backend :8000, frontend :5173 — verify with a quick probe; if down, say so and stop, do NOT start infrastructure yourself).

Pages (read the .tsx + .css for each first, then drive live via Playwright MCP with snapshot/console evidence):
- `frontend/src/pages/Watchlists.tsx` — 12-column badge table; raw thesis-link UUID field; no list rename/delete; rows not linked to companies.
- `frontend/src/pages/Alerts.tsx` — builder + rules + fired feed stacked on one page; watchlist-scope vs company-scope combinations unexplained; fired rows show raw `inputs_snapshot` UUID dumps; no link from a rule/firing to the company.
- `frontend/src/pages/Events.tsx` — rows show raw UUID symbols (`events-symbol` spans), `Actor: user · 0000…` internals, `CHECK_EVALUATED`-style SCREAMING type codes, full JSON dump in `<details>` as the primary "detail" affordance; symbol filter takes raw text (backend expects a company UUID, so typing COMI returns nothing — verify live).

Ground rules for your recommendations (non-negotiable, from CONTRACT + AGENTS.md):
- No user-facing UUIDs anywhere: tickers + names + links instead; truncated ids only as a last-resort fallback with a tooltip.
- No raw JSON as content: expand the important 2–3 facts into designed UI; full snapshots stay behind a discreet "technical details" affordance at most.
- Rule 10: hedged copy ("potentially … under these assumptions"), never BUY/SELL.
- Respect existing global CSS tokens and colocated page CSS; no new deps; vercel-react-best-practices client/rerender/bundle/rendering/js rules (Next.js-only N/A).
- Keep every backend contract shape as-is: recommend UI-only changes. If a change truly needs a backend tweak (e.g. symbol-by-ticker filter), mark it `NEEDS-BACKEND` with the exact endpoint/param — do not assume it.

Deliverable (return inline; router files as `.workflow/design/watchlist-alerts-events-ux.md`): per page, numbered findings with severity (blocker/annoyance/polish), each with: what's wrong (one line + Playwright evidence), the concrete fix (component/layout/copy, precise enough to implement without guessing), and what NOT to change. End with exactly one: NEXT: router | BLOCKED: <question> | DONE.
