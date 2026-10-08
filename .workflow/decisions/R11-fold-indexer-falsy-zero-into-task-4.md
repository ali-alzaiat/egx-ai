# R11 — Task 3's deferred falsy-zero (document_indexer.py:152) folds into Task 4 as a second commit

**Date:** 2026-10-08
**Raised by:** Task 3 review deferred finding ("valuation falsy-zero same class as fixed bugs —
outside brief; follow-up needed (tech-lead to fold into Task 4+ scope)")
**Ruled by:** tech-lead

## Evidence

- `backend/app/ai/document_indexer.py:152` (verified live): `"value": str(val.value) if val.value
  else None` — a valuation of `0` / `Decimal(0)` indexes as `None`, dropping a real zero. Same
  falsy-zero class Task 3 fixed in the metrics service.
- It is the only remaining `... else None` falsy pattern in `document_indexer.py` (grep verified).
- Roadmap conflict scan (progress.md): `document_indexer.py` is touched by Task 3 only; **no later
  roadmap task (5–9) touches that file**. Deferring to "a later task" therefore names no owner.
- No `backend/tests/test_document_indexer.py` exists — the fix needs its first pinning test.

## Ruling

Fold into Task 4 scope as a **separate second commit** (`fix(ai): keep zero valuations in
indexed chunks`): change line 152 to `str(val.value) if val.value is not None else None`, plus
`tests/test_document_indexer.py::test_zero_valuation_indexes_as_zero` (zero valuation →
`"value": "0"` in chunk metadata; `None` → `None`). Kept out of the `feat(dataquality)` commit
so the migration/model commit stays single-purpose. Brief amended with Steps 6–7.

## Cost if wrong

One small extra commit in the Task 4 branch — trivially dropped if a dedicated fix task appears.
Deferring instead costs a bug with no owner, indefinitely.
