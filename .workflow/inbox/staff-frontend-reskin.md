# Inbox: staff-frontend (FE-2 re-skin to variant A)

From: router · 2026-10-24
Task: apply the user-chosen variant **A "Cobalt Cards"** (`.workflow/design/ui-friendly-direction.md`, sections for variant A and the §3 component changes; preview `.workflow/design/friendly-variants-2026-10.html` #va) to the shared layer: `frontend/index.html` (font link: Plus Jakarta Sans + Cairo, drop IBM Plex), `src/styles/tokens.css` (light, dark, Arabic overrides), `src/styles/shell.css`, `src/styles/ui.css`, `src/components/ui/*`, `src/components/hub/*` (visual only). Decision record: `.workflow/decisions/R45-owner-review-r43-ui.md`.
Files you own: exactly those. Do NOT edit pages (`src/pages/**`) or `i18n/dict/*` — two lane agents are editing pages in parallel and style only through tokens/ui components, so the re-skin must land centrally. `styles/legacy.css`: only token renames if needed.
Also add the phone card pattern to `DataTable` if the variant notes require it (cards below 768px), keeping its existing API backward compatible.
Verify in the built-in browser (`preview_start` name `frontend`, own tab, close after): shell, a hub tab, Recommendations, in EN/AR, light/dark, at 1280 and 375 — no overflow, focus rings visible, contrast as the doc states. Reset viewport.
Gates: `cd frontend && npx tsc -b; npm run lint; npx vitest run; npm run build` (last 3 lines each). If a choice the doc doesn't settle comes up, stop with BLOCKED + options. Handback ≤150 words. End NEXT: qa-ui | BLOCKED.
