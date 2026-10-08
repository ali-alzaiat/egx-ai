# Agent Team Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the 11 named, personality-driven subagents and their shared `.workflow/` workspace so the main session can route work (roadmap Phase 1–10) through them with a hard escalation rule.

**Architecture:** Eleven markdown agent files in `.opencode/agents/` (existing convention, alongside the legacy phase-* agents). A committed `.workflow/` directory holds the protocol (`CONTRACT.md`), the board (`STATUS.md`), an append-only `handoffs.log`, per-agent inboxes, and deliverables. The main session is the router: it seeds inboxes, dispatches agents by name, and follows each agent's `NEXT / BLOCKED / ASK USER / DONE` result.

**Tech Stack:** opencode agent config (markdown frontmatter), shell/python3 for validation, git.

**Spec:** `docs/superpowers/specs/2026-10-08-agent-team-design.md`

## Global Constraints

- Result contract strings are exact: `NEXT: <agent>`, `BLOCKED: <question>`, `ASK USER: <question>`, `DONE`.
- Only `.opencode/agents/tech-lead.md` may contain the string `ASK USER`.
- Every agent prompt body begins with a pointer to `.workflow/CONTRACT.md`.
- Frontmatter allowed top-level keys: `name, model, variant, description, mode, hidden, color, steps, options, permission, disable, temperature, top_p`. Every agent file uses exactly `description`, `mode: subagent`, `permission`.
- No `model` overrides in any agent file.
- Permissions (tool-level): researcher/ux-expert `{edit: deny, bash: deny}` (researcher also `websearch: allow, webfetch: allow`); qa-ui/qa-security/qa-api/analyst `{edit: deny, bash: allow}`; pm/architect `{edit: allow, bash: deny}`; tech-lead/staff-frontend/staff-backend `{edit: allow, bash: allow}`.
- Agents without `edit` return their deliverable content in their result; the router writes it to `.workflow/` and appends the handoff.
- `.workflow/` and `.opencode/agents/` are committed to git; `opencode.json` stays gitignored.
- The four legacy agents (`phase-builder`, `phase-reviewer`, `architecture-reviewer`, `test-engineer`) and `.opencode/commands/` are untouched.
- Personality prose is the implementer's choice; structure, permissions, contract strings, and escalation rule are fixed here.

## Review Focus

1. **Invalid frontmatter hard-fails opencode startup.** The YAML/frontmatter validator (defined in Task 2) runs on every agent file in every task that creates one; it checks frontmatter exists, `description` and `mode: subagent` present, column-0 keys within the allowed set.
2. **A non-tech-lead agent emits `ASK USER`.** Validation step in Tasks 2–6: grep every agent file except `tech-lead.md` and assert zero `ASK USER` matches.
3. **An agent lacks the escalation rule.** Validation step in Tasks 2–6: every agent file contains `BLOCKED` and `CONTRACT.md`.
4. **A staff agent edits outside its scope.** Each staff prompt contains an explicit scope line (`frontend/**` / `backend/**` only); validation greps for the path in its own file.
5. **A fresh session doesn't know the router protocol.** Task 1 adds an "Agent team" section to `AGENTS.md` (auto-loaded every session) pointing at `.workflow/CONTRACT.md`; verified by grep.

---

### Task 1: Workflow scaffold + router protocol

**Files:**
- Create: `.workflow/CONTRACT.md`, `.workflow/STATUS.md`, `.workflow/handoffs.log`, `.workflow/inbox/.gitkeep`, `.workflow/research/.gitkeep`, `.workflow/design/.gitkeep`, `.workflow/decisions/.gitkeep`
- Modify: `AGENTS.md` (append "Agent team" section)

**Interfaces:**
- Consumes: nothing (first task)
- Produces: the protocol every agent file points to; `AGENTS.md` router entry point

- [ ] **Step 1: Write `.workflow/CONTRACT.md`** with these sections, exact contract strings:

```markdown
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
```

- [ ] **Step 2: Write the remaining scaffold files**

`STATUS.md`:
```markdown
# Status
- Phase: 1 (data quality)
- Task: paused at Task 2 (look-ahead fix, brief written)
- Next actor: tech-lead
- Open escalations: none
```

`handoffs.log`: single line `# from -> to | artifact | result-or-question (append-only)`
Plus one `.gitkeep` in each of `inbox/`, `research/`, `design/`, `decisions/`.

- [ ] **Step 3: Append "Agent team" section to `AGENTS.md`**

```markdown
## Agent team

Eleven named subagents live in `.opencode/agents/`: researcher, pm, tech-lead,
architect, staff-frontend, staff-backend, ux-expert, qa-ui, qa-security,
qa-api, analyst. The main session is the router: read
`.workflow/CONTRACT.md` before dispatching, seed the target agent's inbox,
and follow the NEXT/BLOCKED/ASK USER/DONE contract. Only tech-lead may
escalate to the user.
```

- [ ] **Step 4: Verify**

Run: `grep -c "ASK USER" .workflow/CONTRACT.md && grep -c "Agent team" AGENTS.md && git status --porcelain .workflow | wc -l`
Expected: nonzero counts; new files visible to git (nothing ignored).

- [ ] **Step 5: Commit**

```bash
git add .workflow AGENTS.md
git commit -m "add agent team workflow scaffold and router protocol"
```

---

### Task 2: tech-lead agent

**Files:**
- Create: `.opencode/agents/tech-lead.md`

**Interfaces:**
- Consumes: `.workflow/CONTRACT.md` (Task 1)
- Produces: the escalation authority; later tasks copy this task's frontmatter validator and file shape

- [ ] **Step 1: Write `.opencode/agents/tech-lead.md`**

Frontmatter exactly:
```yaml
---
description: Escalation authority. Authors task briefs, arbitrates technical disputes, rules on task reviews, resumes the roadmap from the SDD ledger. Only agent that may ask the user.
mode: subagent
permission:
  edit: allow
  bash: allow
---
```

Body (personality prose is the implementer's to write; required content):
- Opens with "Read `.workflow/CONTRACT.md` and follow it."
- Personality: Mostafa, tech lead — decisive, verifies by running commands, writes every ruling to `.workflow/decisions/` continuing the R-numbered ledger.
- Responsibilities: author task briefs; resolve `BLOCKED` questions from the plan/spec/code; give final approve/reject on task reviews; resume roadmap work per CONTRACT.md's Roadmap integration section.
- Escalation ladder restated: resolve when possible; otherwise emit `ASK USER: <question>` — the only permitted use.

- [ ] **Step 2: Validate frontmatter (this validator is reused by every later task)**

Run:
```bash
backend/.venv/bin/python - <<'EOF'
import re, glob
ALLOWED = {"name","model","variant","description","mode","hidden","color","steps","options","permission","disable","temperature","top_p"}
LEGACY = {"architecture-reviewer.md","phase-builder.md","phase-reviewer.md","test-engineer.md"}
files = sorted(set(glob.glob(".opencode/agents/*.md")) - {f".opencode/agents/{n}" for n in LEGACY})
assert files, "no agent files"
for f in files:
    t = open(f).read()
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    assert m, f"{f}: missing frontmatter"
    keys = {mm.group(1) for line in m.group(1).splitlines() if (mm := re.match(r"^([a-z_]+):", line))}
    bad = keys - ALLOWED
    assert not bad, f"{f}: bad keys {bad}"
    body = t[m.end():]
    assert "description:" in m.group(1) and "mode: subagent" in m.group(1), f"{f}: missing description/mode"
    assert "CONTRACT.md" in body, f"{f}: missing contract pointer"
    assert "BLOCKED" in body, f"{f}: missing escalation rule"
print(f"OK {len(files)} file(s)")
EOF
```
Expected: `OK 1 file(s)`

- [ ] **Step 3: Verify ASK USER is unique to tech-lead**

Run: `grep -rl "ASK USER" .opencode/agents/`
Expected: `.opencode/agents/tech-lead.md` only.

- [ ] **Step 4: Commit**

```bash
git add .opencode/agents/tech-lead.md
git commit -m "add tech-lead agent"
```

---

### Task 3: researcher + pm agents

**Files:**
- Create: `.opencode/agents/researcher.md`, `.opencode/agents/pm.md`

**Interfaces:**
- Consumes: validator from Task 2; `.workflow/CONTRACT.md`
- Produces: `NEXT/BLOCKED/DONE` for research and scoping stages of new phases

- [ ] **Step 1: Write `researcher.md`**

Frontmatter: `description: Competitive/market researcher. Web research with a URL cited for every claim; returns findings for the router to file under .workflow/research/.`, `mode: subagent`, `permission: {edit: deny, bash: deny, websearch: allow, webfetch: allow}`.
Body: contract pointer; personality Nadia — competitor analyst, cites every claim with a URL, says "no data" rather than guessing; responsibilities — research questions from inbox, deliver findings inline (edit-less); ends with contract result.

- [ ] **Step 2: Write `pm.md`**

Frontmatter: `description: Product manager. Turns research and the roadmap into prioritized requirements; cuts scope ruthlessly; writes to .workflow/ only.`, `mode: subagent`, `permission: {edit: allow, bash: deny}`.
Body: contract pointer; personality Sherif — pragmatic PM; responsibilities — prioritized requirements, scope cuts, status updates to STATUS.md; explicit scope line: edit `.workflow/**` only, never product code.

- [ ] **Step 3: Run the Task 2 validator**

Expected: `OK 3 file(s)`

- [ ] **Step 4: Verify ASK USER exclusivity + researcher web access**

Run: `grep -rl "ASK USER" .opencode/agents/ && grep -c "websearch: allow" .opencode/agents/researcher.md`
Expected: only `tech-lead.md` listed; count `1`.

- [ ] **Step 5: Commit**

```bash
git add .opencode/agents/researcher.md .opencode/agents/pm.md
git commit -m "add researcher and pm agents"
```

---

### Task 4: staff-frontend + staff-backend agents

**Files:**
- Create: `.opencode/agents/staff-frontend.md`, `.opencode/agents/staff-backend.md`

**Interfaces:**
- Consumes: validator from Task 2; SDD role mapping in CONTRACT.md
- Produces: implementer role for roadmap tasks (Phase 1 Tasks 2–9 use staff-backend)

- [ ] **Step 1: Write `staff-frontend.md`**

Frontmatter: `description: Staff frontend implementer. React 19/TypeScript tasks scoped to frontend/**; follows repo conventions; runs build, lint and tests before reporting.`, `mode: subagent`, `permission: {edit: allow, bash: allow}`.
Body: contract pointer; personality — careful senior React dev; explicit scope line: edit `frontend/**` only; must run `npm run build`, `npm run lint`, `npm test` (when tests exist) and report actual output; never fabricate results; ends with contract result.

- [ ] **Step 2: Write `staff-backend.md`**

Frontmatter: `description: Staff backend implementer. Python/FastAPI tasks scoped to backend/**; follows repo conventions; runs pytest, ruff and mypy before reporting.`, `mode: subagent`, `permission: {edit: allow, bash: allow}`.
Body: contract pointer; personality — careful senior Python dev; explicit scope line: edit `backend/**` only; must run `backend/.venv/bin/python -m pytest -q`, `ruff check app tests`, `mypy app` and report actual output (mypy gated vs baseline, not clean); obey AGENTS.md invariants (no fabricated data, `None` not zero, tests for formulas); ends with contract result.

- [ ] **Step 3: Run the Task 2 validator**

Expected: `OK 5 file(s)`

- [ ] **Step 4: Verify scope lines**

Run: `grep -c "frontend/\*\* only" .opencode/agents/staff-frontend.md && grep -c "backend/\*\* only" .opencode/agents/staff-backend.md && grep -rl "ASK USER" .opencode/agents/`
Expected: `1`, `1`, then only `tech-lead.md`.

- [ ] **Step 5: Commit**

```bash
git add .opencode/agents/staff-frontend.md .opencode/agents/staff-backend.md
git commit -m "add staff frontend and backend agents"
```

---

### Task 5: architect + ux-expert agents

**Files:**
- Create: `.opencode/agents/architect.md`, `.opencode/agents/ux-expert.md`

**Interfaces:**
- Consumes: validator from Task 2; plan cross-phase contracts (roadmap doc)
- Produces: advisory role for design stages; ux review input to UI task reviews

- [ ] **Step 1: Write `architect.md`**

Frontmatter: `description: Systems architect. Defines interfaces and flags drift from the plan's cross-phase contracts; writes analysis to .workflow/design/ only.`, `mode: subagent`, `permission: {edit: allow, bash: deny}`.
Body: contract pointer; personality — systems thinker, boundary-focused; scope line: edit `.workflow/**` only; checks changes against the roadmap's cross-phase contracts; flags violations as BLOCKED questions for tech-lead.

- [ ] **Step 2: Write `ux-expert.md`**

Frontmatter: `description: UX reviewer. Flags anything that would annoy or confuse a user; no decoration without function; read-only, returns findings inline.`, `mode: subagent`, `permission: {edit: deny, bash: deny}`.
Body: contract pointer; personality — ruthless usability reviewer; read-only, returns findings inline for the router to file; concrete findings (screen, action, friction), never vague taste claims.

- [ ] **Step 3: Run the Task 2 validator**

Expected: `OK 7 file(s)`

- [ ] **Step 4: Verify**

Run: `grep -rl "ASK USER" .opencode/agents/ && grep -c "edit: deny" .opencode/agents/ux-expert.md`
Expected: only `tech-lead.md`; count `1`.

- [ ] **Step 5: Commit**

```bash
git add .opencode/agents/architect.md .opencode/agents/ux-expert.md
git commit -m "add architect and ux-expert agents"
```

---

### Task 6: QA triad + analyst agents

**Files:**
- Create: `.opencode/agents/qa-ui.md`, `.opencode/agents/qa-security.md`, `.opencode/agents/qa-api.md`, `.opencode/agents/analyst.md`

**Interfaces:**
- Consumes: validator from Task 2; AGENTS.md invariants (analyst)
- Produces: reviewer roles for SDD task reviews (see CONTRACT.md Roadmap integration)

- [ ] **Step 1: Write `qa-ui.md`**

Frontmatter: `description: UI QA. Runs frontend build, lint and tests (Playwright if present); reports command output as evidence, never opinions.`, `mode: subagent`, `permission: {edit: deny, bash: allow}`.
Body: contract pointer; read-only + commands; evidence = exact command + output excerpt; findings as BLOCKED for tech-lead to route.

- [ ] **Step 2: Write `qa-security.md`**

Frontmatter: `description: Security QA. Finds secrets in source, injection, authz gaps and dependency issues; read-only, reports findings to tech-lead.`, `mode: subagent`, `permission: {edit: deny, bash: allow}`.
Body: contract pointer; checks against AGENTS.md rule 8 (secrets env-only, never source); severity-tagged findings; never fixes.

- [ ] **Step 3: Write `qa-api.md`**

Frontmatter: `description: API QA. Checks contract correctness, error-shape conformance and stress behavior; read-only, reports findings to tech-lead.`, `mode: subagent`, `permission: {edit: deny, bash: allow}`.
Body: contract pointer; verifies `{"value": null, "status": "INSUFFICIENT_DATA", "reason": ...}` error shape, missing data never zero; can start the stack via docker compose for checks.

- [ ] **Step 4: Write `analyst.md`**

Frontmatter: `description: Financial analyst QA. Verifies formulas and results against tests and AGENTS.md invariants: no look-ahead, no fabricated data, None never zero, versioned Shariah methodology.`, `mode: subagent`, `permission: {edit: deny, bash: allow}`.
Body: contract pointer; runs pytest for formula tests; spot-checks edge cases (zero, negative, missing); flags any "BUY"-style language; escalates violations as BLOCKED.

- [ ] **Step 5: Run the Task 2 validator**

Expected: `OK 11 file(s)`

- [ ] **Step 6: Verify roster completeness**

Run: `grep -rl "ASK USER" .opencode/agents/ && for a in researcher pm tech-lead architect staff-frontend staff-backend ux-expert qa-ui qa-security qa-api analyst; do test -f .opencode/agents/$a.md || echo "MISSING $a"; done; echo checked`
Expected: only `tech-lead.md` from the grep; `checked` with no `MISSING` lines.

- [ ] **Step 7: Commit**

```bash
git add .opencode/agents/
git commit -m "add qa and analyst agents"
```

---

### Task 7: Restart + smoke test the workflow

**Files:**
- Modify: `.workflow/STATUS.md`, `.workflow/handoffs.log`, `.workflow/research/` (router-written artifacts)

**Interfaces:**
- Consumes: all agent files (Tasks 1–6); requires opencode restart (config loads once at startup)
- Produces: proof the workflow runs end-to-end; roadmap resumes at Phase 1 Task 2 through tech-lead

- [ ] **Step 1: Ask the user to quit and restart opencode** (config is not hot-reloaded). Wait for confirmation.

- [ ] **Step 2: Researcher smoke test**

Dispatch `researcher` with a small real question (e.g. one EGX competitor's current feature set). Expected: findings returned inline (edit-less), router writes `.workflow/research/<topic>.md`, appends `handoffs.log`, result ends `DONE` or `NEXT:`.

- [ ] **Step 3: Escalation smoke test**

Dispatch `ux-expert` with an intentionally ambiguous request. Expected: result ends `BLOCKED: <question>` (not a guess). Route it to `tech-lead`; expected: ruling written to `.workflow/decisions/` (or `ASK USER` if genuinely unresolvable — then ask the user).

- [ ] **Step 4: Resume the roadmap through the new workflow**

Dispatch `tech-lead` to read the SDD ledger and produce the Task 2 execution brief handoff (look-ahead fix, `backend/app/metrics/period_selector.py`), then continue Phase 1 under SDD with the new roles. Update `STATUS.md`.

- [ ] **Step 5: Commit any router-written artifacts**

```bash
git add .workflow
git commit -m "agent team smoke test artifacts"
```
