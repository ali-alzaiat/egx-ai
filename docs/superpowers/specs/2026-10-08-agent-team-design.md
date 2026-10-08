# Agent Team Design — Named Multi-Agent Workflow

**Date:** 2026-10-08
**Status:** Draft for review
**Supersedes:** nothing; extends the existing subagent-driven-development (SDD) setup

## Goal

A roster of named, personality-driven subagents that work on this project as a
team — researcher, PM, tech lead, staff devs, architect, UX, three QA roles,
and a financial analyst — communicating through a shared workspace, with a
hard escalation rule: no agent guesses; blockers go to the tech lead; the
tech lead asks the human when it cannot resolve them.

The workflow **absorbs the existing roadmap**: the 10-phase plan in
`docs/superpowers/plans/2026-10-08-competitive-enhancement-roadmap.md` stays
the source of truth for what to build; this design defines *who* executes it.

## Decisions (confirmed with user)

1. **Absorbs the roadmap** — the tech lead drives the existing Phase 1–10 plan.
2. **Shared workspace files** for agent communication, not prompt-passing.
3. **Reuse SDD** — task briefs, progress ledger, and task reviews stay;
   the named agents fill the SDD roles (implementer, reviewer).

## Architecture

### Subagent definitions

Eleven files in `.opencode/agent/<name>.md`, loaded by opencode at startup
(restart required after changes). Each file:

```markdown
---
description: <one line, what this agent does and when to dispatch it>
mode: subagent
permission:
  <per-agent tool permissions>
---

<system prompt: personality, responsibilities, output contract,
 escalation rule, workspace conventions>
```

The main session (the router) dispatches them by name via the task tool.
Subagents cannot dispatch each other — every handoff passes through the
router.

### Shared workspace: `.workflow/`

Committed to git — research and decisions are project knowledge.

```
.workflow/
  STATUS.md            # the board: current phase, active task, next actor
  handoffs.log         # append-only: from → to | artifact | result-or-question
  inbox/<agent>.md     # messages addressed to that agent (seeded before dispatch)
  research/            # competitor and market research deliverables
  design/              # UX and architecture deliverables
  decisions/           # rulings, same style as the R1–R8 ledger
```

**Message flow:** agent writes deliverable + appends `handoffs.log` entry
naming the next actor and any open question, returns a short summary to the
router; router seeds the next agent's inbox and dispatches it.

**STATUS.md** is updated by whichever agent finishes a step (single-writer
per step, router-owned otherwise). It carries: current phase, current task,
next actor, open escalations.

### Communication contract

Every agent's result back to the router ends with one of:

- `NEXT: <agent>` — work continues, handoff logged
- `BLOCKED: <question>` — router routes to `tech-lead`
- `ASK USER: <precise question>` — tech-lead only, router surfaces to human
- `DONE` — task complete

## Roster

| Agent | Personality | Permissions |
|---|---|---|
| `researcher` | Nadia, competitor analyst. Cites every claim with a URL; no uncited facts. | websearch, webfetch, read |
| `pm` | Sherif, product manager. Turns research + roadmap into prioritized requirements; cuts scope ruthlessly. | read, edit `.workflow/**` |
| `tech-lead` | Mostafa. Escalation point; authors task briefs; arbitrates technical disputes; **only agent permitted to emit `ASK USER`**. Verifies claims by running commands. | read, edit, bash |
| `architect` | Systems thinker. Defines interfaces, flags drift from the plan's cross-phase contracts. | read, edit `.workflow/**` |
| `staff-frontend` | React 19 / TypeScript implementer. Follows repo conventions (TanStack Query, vitest, ESLint). | read, edit `frontend/**`, bash |
| `staff-backend` | Python 3.12 / FastAPI implementer. Follows repo conventions (SQLAlchemy 2.x, Pydantic, pytest, Ruff). | read, edit `backend/**`, bash |
| `ux-expert` | Ruthless usability reviewer. Flags anything that would annoy or confuse a user; never proposes decoration without function. | read |
| `qa-ui` | UI checks: frontend build, lint, vitest; Playwright if present. Reports evidence (command + output), not opinions. | read, bash |
| `qa-security` | Secrets in source, injection, authz gaps, dependency audit. No edits — findings go to tech-lead. | read, bash |
| `qa-api` | Contract correctness, error-shape conformance (`INSUFFICIENT_DATA`), load/stress behavior. | read, bash |
| `analyst` | Verifies financial formulas against tests and the AGENTS.md invariants: no look-ahead bias, no fabricated data, `None`/`MISSING` never zero, versioned Shariah methodology, no "BUY" language. | read, bash |

Read-only agents (researcher, ux-expert, qa-*) explicitly lack `edit`;
`qa-security` and `qa-api` may run commands but not modify files.

## Escalation rule (core invariant)

1. Any agent that is unsure does **not** guess — it returns `BLOCKED: <question>`.
2. Router dispatches `tech-lead` with the question and full context.
3. `tech-lead` resolves from the plan, specs, or code → writes a ruling to
   `.workflow/decisions/` (numbered continuing from the R1–R8 ledger) →
   work resumes.
4. `tech-lead` cannot resolve → returns `ASK USER: <question>` → router asks
   the human with the question tool. **No silent defaults, ever.**

This mirrors the project's existing "don't assume — verify or ask" rule,
applied agent-to-agent.

## Roadmap integration

Nothing in the existing setup moves:

- Plan: `docs/superpowers/plans/2026-10-08-competitive-enhancement-roadmap.md`
- SDD ledger: `.superpowers/sdd/2026-10-08-competitive-enhancement-roadmap/progress.md`
  (rulings R1–R8 preserved; future rulings continue the sequence)
- Task briefs/reports: unchanged location

Role mapping from SDD to the roster:

| SDD role | Filled by |
|---|---|
| Plan author / controller (this session) | router (main session) |
| Task brief author | `tech-lead` |
| Implementer | `staff-backend` or `staff-frontend` |
| Task reviewer (formula/financial tasks) | `analyst` |
| Task reviewer (UI tasks) | `qa-ui` + `ux-expert` |
| Task reviewer (security/API/perf) | `qa-security` / `qa-api` |
| Final approve/reject | `tech-lead` |
| Pre-planning work (new phases) | `researcher` → `pm` → `architect` → plan |

Current state: Phase 1 in progress, paused at Task 2
(`task-2-brief.md` written, dispatch not yet run). Execution resumes through
this workflow: `tech-lead` picks up from the SDD ledger.

## Non-goals

- No direct agent-to-agent chat (impossible in opencode; router-mediated only).
- No new execution process — SDD artifacts stay as they are.
- No changes to product code as part of this design.
- Agents are not hot-reloaded; config changes require restart.
- No per-agent model overrides unless later requested (defaults apply).

## Testing / verification

1. `opencode` restart loads all 11 agents — verify via the agent list.
2. Smoke test: dispatch `researcher` on a one-line question; confirm it
   writes `research/` output + `handoffs.log` entry and returns `NEXT`/`DONE`.
3. Escalation test: dispatch `ux-expert` with an ambiguous request; confirm
   it returns `BLOCKED` instead of guessing; route to `tech-lead`.
4. Dry run: `tech-lead` reads the SDD ledger and resumes Task 2 through
   `staff-backend`, `analyst` review, `tech-lead` verdict — without touching
   anything outside Phase 1's existing scope.
