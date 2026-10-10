# R19 — Final verdict on the R16+R17 frontend task (working tree)

**From:** Mostafa (tech-lead) · 2026-10-09
**Inputs ruled on:** inbox brief; handoffs.log L16–L20; STATUS.md; R16, R17, R18; `app-ux-audit.md` F2/F5/F14; live tree files read: `Layout.tsx`, `Dashboard.tsx`, `App.tsx`, `Screening.tsx`, `api/client.ts:42-47`.
**Evidence re-verified:** `npm test` → 10/10 pass (`quality.test.ts`); `npm run lint` → clean; `npm run build` → clean, 114 modules; `Screener` grep over `src/` → zero matches; `useHealthCheck` defined in `client.ts:42`, referenced nowhere else in `src/`.

## Ruling 1 — nav 4th destination: ACCEPT `Screening` (`/screening`)

F14 kills the word `Screener` (it mislabelled `/rankings` and hid screening); F2 demands an honest global path to screening. Tree satisfies both: nav is Dashboard / Companies / Market Rankings / **Screening** (`Layout.tsx:3-8`), `/screening` is a real route (`App.tsx:23`) rendering `h1 Shariah Screening` (`Screening.tsx:31`), word `Screener` gone from `src/` (grep-verified). A second Rankings link would duplicate a destination and leave F2 unfixed. No change.

## Ruling 2 — Dashboard not fetching `/health`: ACCEPT the skip

No card consumes health; the four cards bind companies/coverage/signals/scorable-coverage plus `last_synced_at`. Fetching `/health` would be the dead traffic F5 indicted. Unused `useHealthCheck` export costs nothing (lint clean, tree-shaken, no request fires) — delete it as part of the next frontend touch that edits `client.ts`, no dedicated task. No change required now.

## Ruling 3 — Vercel-skill compliance: ACCEPT

Pass stands: gates green across two qa-ui passes plus spot re-run; one code change (dead line in `Rankings.tsx`); N/A rules correctly excluded for this Vite SPA; `&&`-renders-0 spot-check clean. No violation open.

## Per-task verdict: SHIP AS-IS → DONE

Fix-list: none. Rework: none. Carry-forward (not a blocker): drop unused `useHealthCheck` next time `api/client.ts` is touched.
