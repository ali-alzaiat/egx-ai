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
   **Briefing is the router's job, not a pipeline stop.** The router writes each task brief directly from the architect contract (or from the previous artifact) and dispatches. Do NOT route routine briefs or scope checks through tech-lead — that hop is reserved for escalation/arbitration, a disputed review, and the final per-task/per-phase verdict.
7. **Every finished task goes straight to QA.** No task is called done until QA has run: `qa-api` (contract/conformance), `qa-ui` (build/lint/test/UX), `qa-security` (secrets/injection/authz), and `analyst` for financial logic. QA findings are blockers. Frontend tasks are additionally checked against the vercel-react-best-practices skill (applicable client/rerender/bundle/rendering/js rules; Next.js/RSC-only rules N/A) — violations are blockers.
   **Real-data check (added 2026-10-23).** Conformance is not correctness: every task that changes a scoring, stance, screening or valuation output also runs that output on the real dev database and reports its distribution. For stances: `cd backend && python -m app.signals.sanity`. If one outcome covers more than 80% of names, the QA handoff must explain why (e.g. market breadth) or the task is NOT done. A test that pins an output nobody would accept on real data (e.g. "max bullish case is hold") is a defect, not a golden.
8. **Code review on every code change.** A reviewer (`general`, medium tier) reviews each implementer's diff before it merges. No code merges unreviewed.
9. **UX reviews the built design.** After frontend ships, `ux-expert` reviews the implementation against the design and flags gaps.
10. **Tech-lead final verdict** per task and phase.

Pipeline runs end to end for new features. Pure technical fixes may skip researcher/pm with a ledger note, but **never skip architect-contract, QA, code review, or UX where UI is touched**.

**Fast lane (added 2026-10-23).** A change qualifies when it adds no endpoint, no table/migration and no new page, and touches at most ~5 source files (bug fixes, copy, refactors, config, docs). Fast lane = implementer → code review → gates green (CI) → real-data check if it changes an output → router logs DONE. It skips researcher, pm, architect, UX design and the tech-lead verdict. Anything that turns out bigger mid-task goes back to the full pipeline.

**Parallel rule:** at any stage, dispatch agents whose scopes are disjoint in parallel — backend, frontend (mocked), ux-expert, qa-ui, qa-api, qa-security, and code reviewers. Tech-lead verifies disjointness. Overlapping or dependent scopes run sequentially.

**Never-behind rule (added 2026-10-16):** the frontend is never behind the backend again. Every backend phase ships its frontend surface in the same phase — no backend task is DONE while its UI counterpart is missing, stale, or red. Concretely:
- Each phase brief must name the UI surface (new page/tab/section or upgrade of an existing one) alongside the endpoints; phases with no user-visible surface must say so explicitly with a reason.
- At phase kickoff the router lists uncovered backend endpoints in STATUS; at phase close the router verifies each new/changed endpoint is reachable from the UI (or under an explicit logged deferral) before the DONE handoff.
- A task with any error or warning in its gates (pytest, ruff, mypy, tsc, eslint, build, vitest) is NOT done — warnings are blockers, not advisories. Zero-errors-zero-warnings is the only green.
- Backend tests run against their own database (`<dev db>_test`, or `TEST_DATABASE_URL`), created and migrated by `tests/conftest.py` — never the dev database. Tests seed every row they need; a test that only passes on one machine's data is a defect. CI (`.github/workflows/ci.yml`) runs every gate on push/PR and must be green before a task is DONE.
- Logged deferrals go to `decisions/` with a reason + owner phase, and stay on the STATUS carry-forward list until shipped.

**Frontend parallel lanes (Batch A, added 2026-10-16):** one staff-frontend agent per lane, each with its own inbox (`inbox/staff-frontend-a1.md` … `a4.md`) and disjoint file ownership (A1: InvestmentScore page; A2: ShariahScreening page; A3: Valuation page; A4: new PeersTab component). Shared files (`api/client.ts`, `types/index.ts`, `App.tsx`, `CompanyTabs.tsx`) are router-owned — lanes return wiring instructions instead of editing them. No lane runs `npm run build`/`npm test` (shared tree); router runs gates after merge.

**Parallel sessions (added 2026-10-23).** Two sessions or lanes never edit the same checkout: each works on its own branch in its own git worktree, and the router merges. Shared files stay router-owned. (Seen 2026-10-23: a parallel session's page edits overwrote local ones during a rebase.)

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

## Model tiers (updated 2026-10-16)

Single tier per user directive — all agents run on the parent model.

| Tier | Model | Agents | Rationale |
|---|---|---|---|
| **All** | `opencode/muse-spark-1.3-contributor-free` | researcher, pm, architect, tech-lead, staff-backend, staff-frontend, analyst, qa-api, qa-ui, qa-security, ux-expert | Parent model everywhere; no tier split |

To change a tier: edit the `model:` line in the agent's `.opencode/agents/<name>.md` frontmatter. Requires an opencode restart to take effect.

## Data-first gate (replaces the 2026-10-11 warning-only gate, 2026-10-23)

A phase or task that **consumes fundamentals** (metrics, ratios, valuation, scores, thesis, Shariah verdicts, anything reading financial facts or statement lines) may not start until real data exists:

```bash
cd backend && python -m app.dataquality.real_data --min-companies 5
```

Exit 1 = BLOCKED: the only fundamentals work allowed is getting real data in (Phase 13). The old rule let phases ship on synthetic data with a warning; 14 phases were marked COMPLETE while the database held 0 real financial facts. Price-only work (technical, liquidity, stance on prices) is not blocked.

## PM fast-path (added 2026-10-11)

For phases where the roadmap spec section (§N) is already written and researcher findings are thin (<3KB), the router may dispatch PM directly without a researcher step. PM reads the spec section and files scope cuts as usual. Log the skip in handoffs.log: `YYYY-MM-DD | router -> pm | - | fast-path: researcher skipped (spec §N complete)`.
