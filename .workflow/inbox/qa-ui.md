# Inbox: qa-ui

From: router · 2026-10-24
Task: QA the FE-1 foundation only (shell, tokens, shared ui/ components, hub routing, /admin shell). Page bodies are NOT migrated yet (lanes A/B/C come next), so English inside unmigrated page bodies and backend 500s from `/api/stance/*` (R43 backend WIP) are out of scope; note them in one line, don't itemize.

Spec: `.workflow/design/ui-redesign-2026-10.md` §1 (IA, routes, sidebar, narrow screens, hub, admin), §2 (tokens, themes, Arabic), §3.1–3.9, §6 (RTL), §9 checks 1, 2, 7 (focus rings), 8, 9.

Check, in EN and AR, at 1280 and 375 px (reset to desktop after):
- Every top-level route and the 7 hub tabs for COMI: renders, no console errors from frontend code, no horizontal overflow (`scrollWidth === innerWidth`).
- Old tab paths and `/intake` redirect per §1.1; `/companies/COMI/ai` shows Not found; unknown ticker shows Not found.
- Mobile: menu drawer opens/closes (Esc, backdrop), search overlay works, language and theme toggles reachable.
- RTL: sidebar on the right, icons/chevrons mirrored, numbers Western digits, `dir`/`lang` on `<html>` switch.
- Dark theme: toggle works, no unreadable text in the shell.
- Keyboard: Tab through shell and search, focus visible; `/` or the spec's shortcut opens search if specified.

Start the UI with `preview_start` name `frontend` (proxies to the backend on :8000). Do not submit forms. Gates: `cd frontend && npx tsc -b; npm run lint; npx vitest run; npm run build` (last 3 lines each).

Deliverable: `.workflow/research/qa-fe1-2026-10-24.md` — findings table (route, lang, width, severity, evidence, file:line if known). Evidence only. End with NEXT: staff-frontend (if findings) | DONE.
