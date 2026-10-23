# Inbox: ux-expert

From: router (UI revamp, Claude Code runtime) · 2026-10-23
Task: Produce the redesign spec the frontend will implement (CONTRACT step 5). Inputs: `.workflow/research/ui-ux-direction-2026-10.md` (read in full — tokens, type scale, table/chart/component rules, do-not list, proposed IA) and `.workflow/decisions/R43-show-data-not-forms.md` (company tabs become read-only; data-entry tools move to `/admin`; AI Insights route removed). Walk the current app in the built-in browser first (preview_start name `frontend`, backend already on :8000) in English and Arabic so findings are grounded. Deliver: (1) final IA — grouped sidebar, mobile top bar + menu, company hub header + the 7-tab structure and which current pages/components land in each tab, `/admin` contents; (2) final token sheet (light + dark CSS custom properties, type scale, spacing, radii) — you may tune the research hex values but must keep the stated contrast ratios; (3) per-screen layout spec for: Dashboard, Recommendations, Companies, Company hub (each tab), Rankings, Shariah screening list, Watchlists, Alerts, Events, Admin — what is shown, in what order, empty/loading/error copy; (4) stance and Shariah copy (EN + AR) honouring AGENTS.md principle 10 (no certainty words); (5) explicit RTL rules list for the implementer. Be concrete enough that staff-frontend needs no follow-up questions. Read-only: return the spec inline (router files it as `.workflow/design/ui-redesign-2026-10.md`). End NEXT: staff-frontend | BLOCKED: <question> | DONE.

---

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
