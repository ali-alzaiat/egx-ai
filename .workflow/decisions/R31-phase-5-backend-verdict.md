# R31 — Phase 5 backend verdict (Investment thesis, R30)

**From:** Mostafa (tech-lead) · 2026-10-10
**Sources:** qa-api conformance (R30 P1–P7, gates green); live code
verified this session: `backend/app/thesis/service.py:319-321,381-387,533-561,787-793`,
`backend/app/valuation/service.py:525-535`,
`backend/app/models/thesis.py:46-47`, `backend/app/thesis/thesis.py:284-285`,
`backend/tests/test_theses_api.py:427`, AGENTS.md:49, R30 P1/P6/P7.
**Binding:** R30 scope P1–P7; AGENTS.md rules 1/2/3/5/6/7/9/10.

## Finding F1 ruling — ACCEPT-AND-CARRY (no fix now)

F1 facts verified, not taken on faith:

- **Drop CONFIRMED.** `_payload_from_rows` (`thesis/service.py:787-793`)
  emits header `fair_value` as `{value, status}` only — no `reason` key —
  on both the POST-assess and GET paths (both funnel through
  `_payload_from_rows`; :504). POST and GET agree exactly, so unlike
  Phase-4 G1 there is **no read/write asymmetry**.
- **Source always carries it.** Phase-3 `fair_value()` returns
  `{value, status, reason}` on every path (`valuation/service.py:525-535`;
  reason is `None` on AVAILABLE, explanatory string on INSUFFICIENT_DATA).
- **Reason is not lost to the consumer.** The assess path already feeds
  `fair["fair_value"]["reason"]` into the persisted narrative (:321;
  `thesis.py:284-285` appends it to the `Own fair value:` line), and the
  same response carries `confidence.reason` plus full `dq` statuses. A
  MISSING-scope response is unambiguous: `value: None`,
  `status: INSUFFICIENT_DATA`, narrative names the cause, confidence caps
  at MISSING. R30 P6 (honest degradation) is satisfied in substance.
- **Fix now costs a migration; carry costs nothing.** `investment_theses`
  persists `fair_value` + `fair_value_status` but **no reason column**
  (`models/thesis.py:46-47`), and 015 has landed. Passing the reason
  through therefore requires migration 016 (+ backfill semantics for
  existing rows, else old rows re-emit the same 2-key shape) — directly
  against R30 P7's single-migration acceptance. The alternative
  (re-deriving Phase-3's `fs_reason` copy at read time from persisted
  `dq`) duplicates another phase's strings in Phase-5 with drift risk.
- **Zero consumers today.** No Phase-5 frontend exists yet; no caller
  reads `header.fair_value.reason`. R29's fix-now precedent does not
  transfer: G1 was migration-free reconstruction under an explicit
  brief demand (R28 P5, reason on every response). R30 P1 specifies the
  header as "(own fair value + horizon + shareholder-disclosure toggle)"
  with no reason-key demand, and P6's degradation acceptance (nulls +
  capped confidence + skeleton) is met.

**Carry item (binding on the next migration that touches
`investment_theses`, Phase 8/10 — not a new 016 for one string):**
add nullable `fair_value_reason TEXT`, persist
`fair["fair_value"]["reason"]` at upsert, emit the triple in
`_payload_from_rows`, and widen `test_theses_api.py:427` from exact
2-key equality to assert the reason string. Test :427 stays as-is until
then — it pins current behavior, not a defect.

## Brief-location note — NO ACTION (recorded, not a finding)

qa-api reported the Phase-5 brief missing under `.workflow/`. Verified
this session: it lives at
`.superpowers/sdd/2026-10-08-competitive-enhancement-roadmap/task-phase-5-brief.md`
and is gitignored by project convention (`.superpowers/sdd/.gitignore:1:
*`), not missing. Future QA briefs: check the roadmap task-brief path
before filing "missing brief".

## Verdict: SHIP (no fix-list, no rework, no re-verification)

Phase 5 backend **conforms to R30 (P1–P7)** and ships as committed. No
code change ordered, so no qa-api re-verification is required. Frontend
surface for Phase 5 is NOT in this verdict (R30 is backend-shaped, same
as R22/R28); router may dispatch it per the roadmap.
