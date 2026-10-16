# R40 — Batch B–D Frontend Merge Verdict (rules qa-ui F3/F4/F7)

**From:** Mostafa (tech-lead) · 2026-10-16 · **R-number: R40** (ledger ends at R39, verified in `.workflow/decisions/`)
**Sources:** inbox brief 2026-10-16; live tree `frontend/src/api/client.ts`, `frontend/src/pages/ShariahScreening.tsx`, `frontend/src/pages/InvestmentScore.tsx`; AGENTS.md:14; gates re-run 2026-10-16. Router fixes F1/F2/F5/F6/F8 taken as given; this ruling covers only F4/F3/F7 + verdict.

## Rulings

- **F4 — expected-empty-state 404 console noise: ACCEPT, no fix, no carry.** (1) The 404 is the contract working as designed: `useScreeningResult`, `usePurification`, `useEgxMembership` all map 404→null empty state, and `retryUnless404` suppresses retries — the page degrades gracefully by construction. (2) A pre-check would buy console silence only developers see at the price of an extra round-trip on every page load — latency + coupling for zero user gain. (3) Zero-console is unattainable at this layer anyway: the screening GET itself *is* the existence check and 404s when unassessed. Eliminating that means a 404→200-null backend contract change — out of scope for this merge. No carry; revisit only if a batch endpoint is ever scoped.
- **F3 — stale EGX33 side panel after "Run screening": FIX NOW (sole fix-list item).** Genuine user-visible staleness: `handleScreen` invalidates `['screening']` + `refetch()`, but the side-by-side panel renders from the `egxMembership` query, never invalidated or refetched. Fix: add `invalidateQueries({ queryKey: ['egxMembership'] })` + `refetchMembership()` to `handleScreen`. Two lines, one file, no contract change.
- **F7 — "Buy zone" label vs AGENTS.md rule 10: ACCEPT, compliant, no fix, no carry.** Rule 10 bans presenting output as certainty ("BUY"). The page passes on four independent hedges: "(display only)" heading, conditional "potentially of interest under these assumptions" copy, "This is context, not advice.", plus the backend disclaimer. "Buy zone" is a noun label mirroring the API field `buy_zone`, not an imperative.

## Verdict: FIX-LIST (ship-on-green, no return to tech-lead)

F3 applied by router (`ShariahScreening.tsx` handleScreen). F4/F7 accepted. Ship Batches B–D once gates re-verify at zero-errors-zero-warnings.
