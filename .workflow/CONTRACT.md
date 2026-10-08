# Team Contract

The main session is the router. Subagents never dispatch each other.

## Files
- STATUS.md — board: current phase, current task, next actor, open escalations
- handoffs.log — append-only; line format: `YYYY-MM-DD | from -> to | artifact path or - | result or question`
- inbox/<agent>.md — messages for that agent; router seeds it before dispatch
  On dispatch, read your inbox first if it exists.
- research/, design/, decisions/ — deliverables; decisions/ rulings are numbered continuing the R1–R8 ledger

## Result contract (end every result with exactly one)
- NEXT: <agent> — work continues, handoff logged
- BLOCKED: <question> — unsure; never guess; router routes to tech-lead
- ASK USER: <precise question> — tech-lead only; router asks the human
- DONE — task complete

## Standard pipeline (every task/feature)

1. **Researcher runs first.** The router dispatches `researcher` with the task/topic. Researcher gathers competitor data, market context, and prior art — cites every claim with a URL, marks gaps `no data`. Returns findings inline (edit-less). Router files them under `research/`.
2. **PM decides.** The router dispatches `pm` with the research file path. PM reads the research, decides what we will build/change (prioritized requirements, scope cuts, what to skip), writes the decision to `design/` or `decisions/`. PM ends with `NEXT: tech-lead`.
3. **Tech-lead orchestrates.** The router dispatches `tech-lead` with the PM's decision. Tech-lead: (a) reads the SDD ledger and plan to check for collisions or prior rulings, (b) authors the task brief, (c) verifies all required agents are working (dispatches a quick probe to each if needed), (d) updates STATUS.md and handoffs.log, (e) ends with `NEXT: <implementer>` (usually staff-backend or staff-frontend). From here the normal SDD task loop runs: implement → review → verdict.

This pipeline replaces the old "researcher/pm/architect only for new phases" rule. Every task starts at step 1 unless the router explicitly skips it with a ledger note (e.g. pure bugfix with no product decision needed).

## Escalation ladder
1. Unsure -> BLOCKED, never guess.
2. Router dispatches tech-lead with the question.
3. Tech-lead resolves -> writes ruling to decisions/ -> work resumes.
4. Tech-lead cannot resolve -> ASK USER -> router asks the human. No silent defaults.

## Handoffs
The router appends every handoffs.log entry and writes every deliverable file under .workflow/ — agents never append the log themselves (staff agents' prompts forbid touching .workflow/ entirely). Edit-less agents return deliverable content inline; the router files it.

## Roadmap integration (SDD roles)
- Task briefs: tech-lead
- Implementation: staff-backend / staff-frontend
- Reviews: analyst (formulas), qa-ui + ux-expert (UI), qa-security / qa-api (their domains)
- Final verdict: tech-lead
- Plan + ledger: docs/superpowers/plans/2026-10-08-competitive-enhancement-roadmap.md and .superpowers/sdd/.../progress.md (rulings R1–R8 continue)

## Operational notes
- `bash: ask` on researcher/pm/architect/ux-expert is an opencode-bug workaround (bash: deny broke model resolution). Caveat: with permission mode --auto, anything not explicitly deny is auto-approved, so ask becomes allow — do not run dispatches in auto mode.
- Scope lines (frontend/**, backend/**, .workflow/**) are prose-enforced; bash access grants shell-equivalent file access. Path-pattern edit permissions are unverified in agent frontmatter.
