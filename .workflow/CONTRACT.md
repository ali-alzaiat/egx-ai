# Team Contract

The main session is the router. Subagents never dispatch each other.

## Files
- STATUS.md — board: current phase, current task, next actor, open escalations
- handoffs.log — append-only; line format: `YYYY-MM-DD | from -> to | artifact path or - | result or question`
- inbox/<agent>.md — messages for that agent; router seeds it before dispatch
- research/, design/, decisions/ — deliverables; decisions/ rulings are numbered continuing the R1–R8 ledger

## Result contract (end every result with exactly one)
- NEXT: <agent> — work continues, handoff logged
- BLOCKED: <question> — unsure; never guess; router routes to tech-lead
- ASK USER: <precise question> — tech-lead only; router asks the human
- DONE — task complete

## Escalation ladder
1. Unsure -> BLOCKED, never guess.
2. Router dispatches tech-lead with the question.
3. Tech-lead resolves -> writes ruling to decisions/ -> work resumes.
4. Tech-lead cannot resolve -> ASK USER -> router asks the human. No silent defaults.

## Edit-less agents
Agents with edit: deny return deliverable content in the result;
the router writes it to .workflow/ and appends the handoff.

## Roadmap integration (SDD roles)
- Task briefs: tech-lead
- Implementation: staff-backend / staff-frontend
- Reviews: analyst (formulas), qa-ui + ux-expert (UI), qa-security / qa-api (their domains)
- Final verdict: tech-lead
- Plan + ledger: docs/superpowers/plans/2026-10-08-competitive-enhancement-roadmap.md and .superpowers/sdd/.../progress.md (rulings R1–R8 continue)
