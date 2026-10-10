# R26 — Phase 3 authorization: brief-currency verification + extend-in-place constraints

**From:** Mostafa (tech-lead) · 2026-10-10
**Brief inputs verified:** R25 scope (`.workflow/decisions/R25-phase-3-scope.md`),
research (`.workflow/research/phase-3-valuation.md`), roadmap §4–§5 exit criteria
(roadmap: `docs/superpowers/plans/2026-10-08-competitive-enhancement-roadmap.md:77`).
**Verification method:** live `git status`, migration-chain grep, source reads —
not memory. R25 scope itself stands; this ruling pins build constraints the code
requires. No scope cut/build change.

## Verification (evidence)

1. **013 free — CONFIRMED.** `backend/alembic/versions/` holds `001`–`012`, no `013`
   file (`ls` output 2026-10-10).
2. **012 NOT landed in git — brief premise corrected.** `git log --oneline` for
   `backend/alembic/versions/` ends at `8b7714a` (011, data-quality); `012_industry.py`,
   `backend/app/industry/`, `backend/app/models/industry.py` are all **untracked
   (`??`) working-tree files**. `012` declares `down_revision = "011"` (correct),
   so `013` chains `down_revision = "012"` regardless — but the Phase-3 branch
   **requires the Phase-2 working tree present** for the `gics_sub_industries` FK
   target. If Phase 2 is reverted/renumbered before Phase 3 lands, `013` breaks;
   staff-backend must re-verify the chain at implementation time.
3. **Existing valuation engine CONFIRMED — extend in place.**
   `backend/app/valuation/models.py` (PE/PB/EV_EBITDA/DCF + `calculate_sensitivity`,
   Decimal, INSUFFICIENT_DATA/INVALID tri-state) + `service.py` (`ValuationService`
   orchestrator) exist, unmodified in the working tree (`git status` shows no
   `backend/app/valuation/` entries). Per roadmap architecture §Architecture
   ("Existing engines … are extended in place — no parallel implementations"),
   R25-V1's 4 SWS-parity models are added to these modules; the existing
   calculators stay (V2's relative leg reuses PE/PB). No `backend/app/domain/*`
   code (skeleton stays untouched per cross-phase contract).
4. **Router path occupied — collision RULED, not just noted.**
   `GET /api/valuation/companies/{company_id}` already exists
   (`backend/app/api/valuation.py:19-55`, returns `list` of stored
   `valuation_results`) and is consumed by live frontend
   (`frontend/src/api/client.ts:384`, `types/index.ts:337`, `pages/Valuation.tsx:12`).
   R25-V2's "one router GET … echoing profile/version/values/weights/counts" is a
   **different shape on the same path**. A literal second GET would shadow the
   existing route or break the Valuation page.
5. **Collision scan otherwise CLEAN.** No `industry_valuation_profiles` table, no
   `valuation_profile`/`weighted`/`fair_value` model anywhere (`grep -il` hit only
   `signals/scoring.py`, `dataquality/scores.py`, `technical/indicators.py` —
   unrelated usages). No uncommitted valuation changes. Phase-2 FK target present:
   `GicsSubIndustry` (`gics_sub_industries`, `app/models/industry.py:77-93`).

## Rulings (binding on the Phase-3 implementation)

- **R26.1 — Migration:** single `013_valuation.py`, `down_revision = "012"`;
   up/down round-trip required. Re-verify `012` still heads the chain before writing
   it; if Phase 2 renumbered, follow the new head and say so in the diff.
- **R26.2 — Engine:** V1 extends `app/valuation/models.py` + `service.py` in place
   (new enum members / pure functions + tests for zero/negative/missing per AGENTS
   rule 7). Existing `ValuationModel` members and calculators are not removed or
   forked.
- **R26.3 — Router:** the existing `GET /api/valuation/companies/{company_id}`
   keeps its contract. V2's weighted-fair-value payload lands **additively** —
   either additive fields on the existing response or a new sub-resource under the
   same router (e.g. `GET …/fair-value`); never a duplicate GET on the same path,
   never a breaking shape change without updating `client.ts`/`types`/`Valuation.tsx`
   in the same diff.
- **R26.4 — Cross-phase contracts hold:** one migration, UUID PKs with `ix_`/`uq_`
   names + explicit `ondelete`, `methodology_version` on every new score/profile
   row, hand-serialized Decimal/date, INSUFFICIENT_DATA-never-zero, no BUY language.

## Authorization

R25 (V1–V6) as constrained by R26.1–R26.4 is **authorized for staff-backend
implementation**. Roadmap §4–§5 exit criteria (per-industry model choice, weighted
fair value, bull/base/bear, sensitivity, data-quality-fed confidence) are covered
by R25-V1–V6 + R26 with no gap found.
