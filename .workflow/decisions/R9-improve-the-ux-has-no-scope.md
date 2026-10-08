# R9 — "improve the UX" carries no actionable scope; escalation closed, no work routed

**Date:** 2026-10-08
**Raised by:** ux-expert (BLOCKED: which screen/flow, which user, what observed friction?)
**Ruled by:** tech-lead

## Evidence

- `.workflow/STATUS.md`: Phase 1 (data quality), paused at Task 2; no UI task in flight.
- Roadmap `docs/superpowers/plans/2026-10-08-competitive-enhancement-roadmap.md`: Phase 1's only
  frontend item is Task 8, a fully specified data-quality card — an implementation task, not a UX
  review. No UX-audit or "improve the UX" work item exists anywhere in Phase 1.
- `.workflow/decisions/` was empty; R1–R8 live in the SDD progress ledger, so this ruling is R9.
- Request context: the dispatch was a deliberately ambiguous workflow smoke-test probe, not real
  product work.

## Ruling

1. **No scope exists to recover.** The plan/spec/code do not answer ux-expert's question because no
   UX work is defined. ux-expert's refusal to fabricate findings was correct.
2. **Disposition: close, do not escalate to the user.** The request was a test of the escalation
   path, not a product request; asking the human to pick a screen would manufacture a question
   nobody asked. No silent default is chosen — the request simply has no work attached to it.
3. **Standing rule for future UX requests:** a "improve the UX" style request is actionable only
   when it names (at minimum) the screen/flow and the user or observed friction — or points at a
   mockup/spec to review. Without those, ux-expert should return BLOCKED exactly as it did here,
   and tech-lead should close it under this ruling unless a real scoping source has appeared.
4. **No handoff:** nothing resumes from this escalation. Board stays at Task 2, next actor
   tech-lead, open escalations none.

## Cost if wrong

If a genuine UX request was intended, it will arrive again with a screen named — R9 costs nothing
but this file.
