# Inbox: staff-frontend-f3

# Staff-frontend Lane F3 — ZBorsa Task 13: Signals/stance UI + hard invariant (2026-10-22)

Read first: docs/superpowers/plans/2026-10-17-zborsa-upgrade.md (Task 13 + Task 9 StanceResult shape). `StanceResult`/`TargetLevel` types exist in `frontend/src/types/index.ts`; hook `useStance(ticker, params?: { entry_price?: number; stop_pct?: number })` exists in `frontend/src/api/client.ts`. Scope (disjoint, yours only): `frontend/src/pages/Signals.tsx` + new `Signals.css`, new `frontend/src/components/StanceCard.tsx`, new `frontend/src/components/TargetsTable.tsx`, new `frontend/src/components/stanceInvariant.test.ts`. Do NOT touch `App.tsx`, `client.ts`, `types/index.ts`, `CompanyTabs.tsx`, `Companies.tsx`, `Statements.tsx`, `Ratios.tsx`, or any backend path.

## Work
1. **Step 1 — FAILING vitest first:** `stanceInvariant.test.ts` tests a pure helper `requiresLimitations(stance)` (stance requires a non-empty limitations list always) plus exact compliance-copy constant `"Research calculation — not investment advice · حساب بحثي — ليس توصية استثمارية"` assertion.
2. **StanceCard.tsx:** stance badge (BUY/HOLD/REDUCE with shape+color coding, colorblind-aware), confidence meter (0–100), reasons list each prefixed with engine name (`engine` field of Reason), limitations list rendered ALWAYS beside the stance — hard UI rule enforced in component code (never render stance without its limitations block) and covered by the invariant test.
3. **TargetsTable.tsx:** bull/base/bear rows keyed from `targets` dict; each row shows status-aware label (AVAILABLE value vs INSUFFICIENT_DATA — dash + reason, never interpolate), plus `stop_level` row and the "a risk reference, not an order condition" copy.
4. **Signals.tsx:** wire the page — StanceCard + TargetsTable, `entry_price` and `stop_pct` inputs + compute/recompute (stop_pct validated client-side in (0, 90]); FREE-quota 429 handling: disabled input + quota remnant UI with upgrade CTA linking `/pricing` (route exists).
5. Gates (own files): `npx tsc --noEmit`, `npx eslint <touched files>`, `npx vitest run stanceInvariant`. Do NOT run `npm run build` (router runs tree gates). Zero errors zero warnings.

## Rules
- vercel-react-best-practices applicable rules; typed props; no invented data — everything from the API payload or plan-fixed copy.
- Compliance copy must appear verbatim as a limitation (it is the first limitation from the backend).
- Do NOT commit.

## Result contract
End with exactly one: `DONE` (gate evidence + file list), `BLOCKED: <question>`, `ASK USER`, `NEXT`.
