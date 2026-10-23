# Inbox: staff-frontend-f4

# Staff-frontend Lane F4 — ZBorsa Task 14 verification + completion polish (2026-10-22)

Read first: docs/superpowers/plans/2026-10-17-zborsa-upgrade.md (Task 14). Code largely landed in `9e08e23`: `frontend/src/i18n/dict.ts`, `frontend/src/i18n/useLang.ts`, `frontend/src/i18n/i18n.test.ts`, `frontend/src/utils/savings.ts` + test, `frontend/src/pages/Pricing.tsx`, `frontend/src/components/Layout.tsx`. Scope (disjoint, yours only): those same i18n/Pricing/Layout/savings files (you may amend them; they were shipped unverified). Do NOT touch `App.tsx`, `client.ts`, `types/index.ts`, `CompanyTabs.tsx`, `Companies.tsx`, `Statements.tsx`, `Ratios.tsx`, `Signals.tsx`, or any backend path.

## Work
1. **Verify against plan Task 14 spec, fix gaps:**
   - `dict.ts` SHORT_COPY must cover nav, hub, radar, statements, signals, calculation, screening keys — add missing keys.
   - `useLang.ts` persists `'egx-lang'` in localStorage; `t(key)` resolves AR+EN for every key; `i18n.test.ts` must assert every key resolves both languages and missing key throws in dev — extend the existing test file to FULL coverage of dict keys.
   - `Layout.tsx`: toggle button sets `document.documentElement.dir = "rtl"` when ar and updates `lang` attr — verify present and correct; fix if not.
   - `savings.ts`: monthly compounding at `annualRatePct/12`, illustrative-only labeling must appear in the Pricing page near the calculator; extend `savings.test.ts` only if a case from the plan's list is missing (golden 1000/mo ×12 @12%, zero-rate edge, single month).
   - `Pricing.tsx`: feature lists must mirror backend `PLAN_ENTITLEMENTS` exactly (FREE=3 stance/day, FREE=1 radar; company_hub_full False for FREE) — read `backend/app/billing/entitlements.py` for the truth and mirror it with honest copy; checkout button renders only when backend checkout returns a provider URL (Free → no button).
2. **Paywall surfaces:** quota 429 remnant UI exists in Signals (Lane F3 owns Signals.tsx — you own nothing there; only verify no gap needs something from your files and note it in your result if the Pricing link exists).
3. Gates (own files): `npx tsc --noEmit`, `npx eslint <touched files>`, `npx vitest run i18n savings`. Do NOT run `npm run build`. Zero errors zero warnings.

## Rules
- vercel-react-best-practices applicable rules; long analytical prose stays EN (only short copy is bilingual).
- No invented market data anywhere; the savings calculator is deterministic math with an illustrative label.
- Do NOT commit.

## Result contract
End with exactly one: `DONE` (gate evidence + file list), `BLOCKED: <question>`, `ASK USER`, `NEXT`.
