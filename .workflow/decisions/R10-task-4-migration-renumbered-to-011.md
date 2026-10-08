# R10 — Task 4 migration renumbered: 010_data_quality.py → 011_data_quality.py

**Date:** 2026-10-08
**Raised by:** tech-lead (pre-dispatch brief verification for Task 4)
**Ruled by:** tech-lead

## Evidence

- `backend/alembic/versions/010_screening_insufficient_nullable.py` exists (Task 3, commit
  58af775): `revision = "010"`, `down_revision = "009"` — Task 3 took revision 010 after the
  Task 4 brief was written.
- Task 4 brief (`.superpowers/sdd/2026-10-08-competitive-enhancement-roadmap/task-4-brief.md`)
  instructed: create `backend/alembic/versions/010_data_quality.py` with `down_revision = "009"`
  — two revisions claiming `down_revision = "009"` breaks alembic's linear chain
  (`upgrade head` would fail with multiple heads).
- `backend/alembic/versions/` listing: chain is 001–010 with no 011; Task 4 is next.

## Ruling

Task 4's migration is `backend/alembic/versions/011_data_quality.py`, `revision = "011"`,
`down_revision = "010"`. The brief has been amended in place. Downgrade step in the brief
unchanged in substance (drops the table, the enum, the three columns, the two backfilled
indexes — Task 4 adds nothing that Task 3's 010 owns).

## Cost if wrong

None — the renumbering is forced by the alembic chain, not a preference.
