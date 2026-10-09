# R18 — Disposition of the two open review items (Task 7 review, Task 8 findings)

**From:** Mostafa (tech-lead) · 2026-10-09
**Purpose:** neither item may be left silently open (STATUS.md carried both as backlog).

## Verified state

- **Task 7** (impl `6486ae7`, `feat(ingestion): record source base_url and last_synced_at`):
  **no review exists.** Checked every `review-*.diff` in the SDD directory — the oldest range
  starting after Task 7 is `review-d5dfdfc..78789a4` (Task 8). No diff, no report, no ledger
  entry records a Task 7 review. Task 7 report shows 3 new tests, suite 335 green, ruff clean,
  mypy within baseline.
- **Task 8** (impl `78789a4`): review **was** run, but its findings were returned inline and
  **never filed** — no `task-8-review` file, no progress.md entry. The only surviving record of
  the findings is the router's summary in `.workflow/inbox/tech-lead.md`: *vitest env
  jsdom→node flagged Important; minor items*. Grep for `Needs fixes`/`Important:` across the
  repo finds nothing else.
- **Task 8 finding verified against the repo:** `frontend/vitest.config.ts` is
  `environment: 'node'` with a comment; `frontend/node_modules/jsdom` does **not** exist and
  `package.json` does not list it; the only test file is `src/lib/quality.test.ts` (pure logic).

## Rulings

**R18.1 — Task 7 review is folded into the Stream A review, with Task 7 named explicitly in
scope.** The reviewer for `task-refresh-assess` reviews `36f5c8e..HEAD`, which spans Task 7's
commit **and** the refresh+assess work, and must check Task 7 against R15 (stamp inside
`write_prices`, `base_url` on create only, no `description`, `PRICE_SOURCE_URL` in sync.py) plus
the inheritance property the new job relies on (a refresh run stamps `last_synced_at` with no
stamping code of its own).
*Why fold, not dispatch now:* Task 7's code is the substrate the refresh job builds on this
same hour; reviewing it in isolation would be re-reviewed immediately by the same reviewer.
Nothing is merged to `main` unreviewed — the branch-level review gate still runs before merge.
*Caveat accepted:* Task 7 stays unreviewed for the duration of Stream A implementation (hours,
not days). *Cost if wrong:* one defective commit sits under a second commit before first
review; blast radius is `service.py`/`sync.py` stamping only, covered by its 3 tests.

**R18.2 — Task 8's Important finding (vitest `jsdom` → `node`) is UPHELD as correct; no code
change now.** Evidence above: the dependency does not exist, the brief forbade new
dependencies, and the suite contains no DOM test. `environment: 'node'` stays, comment stays.
*Condition:* the first brief that wants a component/DOM render test must **name `jsdom` as an
explicit dependency** and flip the env back — that is the documented revert condition already
in the file. Any later change to `quality.ts`/`DataQualityCard.tsx` must keep
`quality.test.ts` green.

**R18.3 — Task 8's unfiled minor items: disposition is "re-raised at the v1 frontend review",
not "closed".** Because the text was never filed, they cannot be actioned individually today.
The single staff-frontend task (R16 frontend + R17 spec) re-covers the whole `frontend/src/**`
surface, Task 8's files included; its code review must re-check that surface and may raise any
still-relevant item from the Task 8 review as a new finding. Recorded here so the loss of the
review text is a documented event with an owner, not a gap.

**R18.4 — STATUS.md backlog line is cleared** by this ruling; progress.md carries the R16/R17/R18
entries.
