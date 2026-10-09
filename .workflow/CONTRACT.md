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

1. **Researcher runs first.** `researcher` gathers competitor + market + UX findings (how competitors do it, UX best practices), every claim cited with a URL, gaps marked `no data`. Router files under `research/`.
2. **PM decides.** `pm` turns the research into prioritized requirements and scope cuts → `decisions/`.
3. **Architect designs the backend.** `architect` defines the backend interfaces and the API contract (endpoints, request/response shapes, field types) → `design/`. This is the single source of truth both sides build against.
4. **Backend + frontend agree on the contract.** Both staff agents review the architect's contract and sign off before any code. Disagreement → BLOCKED → tech-lead.
5. **UX designs from research.** `ux-expert` reads the competitor/UX research and produces the design → `design/`. Frontend implements that design — not its own invention.
6. **Parallel implementation.** Backend implements the real endpoints; frontend builds against **mocks** of the frozen contract. They do not block each other. Frontend swaps mocks for the real backend once it lands (integration step).
7. **Every finished task goes straight to QA.** No task is called done until QA has run: `qa-api` (contract/conformance), `qa-ui` (build/lint/test/UX), `qa-security` (secrets/injection/authz), and `analyst` for financial logic. QA findings are blockers.
8. **Code review on every code change.** A reviewer (`general`, medium tier) reviews each implementer's diff before it merges. No code merges unreviewed.
9. **UX reviews the built design.** After frontend ships, `ux-expert` reviews the implementation against the design and flags gaps.
10. **Tech-lead final verdict** per task and phase.

Pipeline runs end to end for new features. Pure technical fixes may skip researcher/pm with a ledger note, but **never skip architect-contract, QA, code review, or UX where UI is touched**.

**Parallel rule:** at any stage, dispatch agents whose scopes are disjoint in parallel — backend, frontend (mocked), ux-expert, qa-ui, qa-api, qa-security, and code reviewers. Tech-lead verifies disjointness. Overlapping or dependent scopes run sequentially.

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
- Playwright MCP (`@playwright/mcp`, `playwright_*` tools) is available for qa-ui and ux-expert to drive the running frontend (default `http://localhost:5173`). Use it when dispatch asks for live UI verification; paste snapshot/console output as evidence. Requires the dev server to be running. Adding/changing agents or MCP servers needs an opencode restart.
