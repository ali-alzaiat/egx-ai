# Next Phase Command

This command implements the autonomous phase orchestration workflow.

## Workflow

Execute the following steps in order:

### 1. Read Phase Tracker
Read `PHASES.md` to identify the current state of all phases.

### 2. Find Next Phase
Find the first phase whose status is:
- `IN_PROGRESS` — continue working on it
- `NOT_STARTED` — prepare to start it

If a previous phase has status `READY_FOR_REVIEW`, STOP and tell the user that approval is required before proceeding.

### 3. Check Dependencies
Read the phase specification and verify all dependencies are `COMPLETE`.

If any dependency is not complete:
- Set the phase status to `BLOCKED`
- Report which dependency is missing
- STOP

### 4. Read Phase Specification
Read the phase specification from `docs/phases/phase-NN-*.md`.

### 5. Inspect Repository
Examine the existing codebase to understand:
- Current implementation state
- Existing patterns and abstractions
- What work is already done for this phase
- What remains to be implemented

### 6. Invoke Phase Builder
Delegate to the `phase-builder` agent to implement the phase.

The builder should:
- Implement incrementally
- Add tests alongside code
- Run verification after each major change
- Fix failures before proceeding

### 7. Run Test Engineer
Delegate to the `test-engineer` agent to run full verification.

Verification includes:
- Backend: pytest, ruff, mypy
- Frontend: lint, build, typecheck
- Infrastructure: docker config, alembic

### 8. Run Phase Reviewer
Delegate to the `phase-reviewer` agent to review the implementation.

If the reviewer returns `FAIL`:
- Fix the issues
- Re-run verification
- Re-run the reviewer
- Repeat until `PASS` or iteration limit reached

### 9. Run Architecture Reviewer
Delegate to the `architecture-reviewer` agent to review architectural integrity.

If the reviewer returns `FAIL`:
- Fix the architectural issues
- Re-run verification
- Re-run all reviewers
- Repeat until `PASS` or iteration limit reached

### 10. Update Phase Status
If all verification passes and all reviewers pass:
- Change the phase status to `READY_FOR_REVIEW` in `PHASES.md`
- Generate the phase completion report at `docs/phases/phase-N-report.md`

### 11. STOP
Stop and wait for human approval. Do NOT automatically proceed to the next phase.

## Iteration Limit

If the same problem persists after 3 fix attempts:
- Set phase status to `BLOCKED`
- Produce a report explaining:
  - The failure
  - Attempted fixes
  - Likely root cause
  - What human decision is needed

## Approval Gate

The workflow MUST NOT automatically transition:
```
READY_FOR_REVIEW → COMPLETE
```

The user must explicitly approve by saying something like:
- "approve phase N"
- "phase N is approved"
- "approve"

Only then may the status become `COMPLETE` and the next phase become `IN_PROGRESS`.

## Report Format

Generate `docs/phases/phase-N-report.md` with:

```markdown
# Phase N Report

## Status
READY_FOR_REVIEW

## Objective
...

## Implemented
- ...

## Files Changed
- ...

## Database Changes
- ...

## API Changes
- ...

## Frontend Changes
- ...

## Tests
...

## Verification
...

## Architecture Review
...

## Known Limitations
...

## Technical Debt
...

## Future Work
...

## Human Approval
Pending
```

After approval, update to:
```
Human Approval
Approved by user.
Date: YYYY-MM-DD
```
