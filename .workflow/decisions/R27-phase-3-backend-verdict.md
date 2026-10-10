# R27 — Phase 3 backend verdict (Valuation, R25/R26)

**From:** Mostafa (tech-lead) · 2026-10-10
**Sources:** qa-api conformance (V1–V6 all PASS, no hard blockers); live code
verified this session: `backend/app/api/valuation.py:171`,
`backend/app/valuation/service.py:562`, `backend/app/db/session.py:22-23`,
`backend/app/repositories/valuation.py:154-191`,
`backend/app/models/valuation.py:159-162`; gates re-run: valuation suites
61 passed, ruff clean, mypy clean (3 touched files).
**Binding:** R25 scope V1–V6; R26 authorization; AGENTS.md rules 1/2/6/7/10.

## F1 ruling — FIX-LIST (follow-up commit; 00cd305 already landed)

F1 facts verified, not taken on faith:

- **F1a (docstring false): CONFIRMED.** `api/valuation.py:171` says the
  snapshot is "flushed (never committed)", but `service.py:562` flushes inside
  a request whose `get_session` (`db/session.py:22-23`) runs
  `await session.commit()` on clean exit. The snapshot **is committed** on
  success (rolled back on exception). A false persistence statement on a GET
  is a future-incident seed — one-line fix, zero risk.
- **F1b (upsert key omits inputs → last-writer-wins): CONFIRMED, behavior
  ACCEPTED, documentation REQUIRED.** `uq_valuation_fair_value` keys on
  `(company_id, methodology_version)` (`models/valuation.py:159-162`); neither
  `profile_key` nor inputs participate, so differing inputs overwrite one row
  and `inputs_echo` records only the latest. That is correct semantics for a
  **latest-snapshot cache** (R25 V6: "one outputs table … echoing
  profile/version/values/weights/counts" — a latest-output row, not a ledger),
  so no schema change and no rework. But undocumented last-writer-wins reads
  as a ledger bug to the next reader — document it at both the endpoint and
  `upsert_snapshot` docstrings.
- **GET-side write: ACCEPTABLE hygiene, same class as qa-api ruled.** The GET
  persists only its own deterministic domain snapshot
  (`valuation_fair_values`); R16 read-only applied to DQ GETs, and R25 V6
  authorizes one outputs table for this domain. Pinned by test, not debated
  further.

## Verdict: FIX-LIST then ship (no rework, no second verdict)

Phase 3 backend **conforms to R25/R26 (V1–V6)** and ships once the follow-up
lands; no return to tech-lead — qa-api re-verifies the fix-list green and the
phase ships per this ruling.

1. **F1a:** correct the `get_fair_value` docstring — flushed in-service,
   committed by `get_session` on success; GET persists a deterministic
   snapshot cache.
2. **F1b:** one-line last-writer-wins note on `upsert_snapshot` + endpoint
   (key is company+methodology; inputs_echo reflects the latest write).
3. **Pinning test** (new, in `test_valuation_fair_value_api.py`): identical-GET
   determinism (same inputs → same fair value, exactly one row per
   company+methodology); last-writer-wins (changed inputs → still one row,
   values + inputs_echo match the latest); domain-table cleanliness (GET
   writes only `valuation_fair_values`).

## Gates (this session)

- `pytest tests/test_valuation_models_v1.py
  tests/test_valuation_fair_value_api.py tests/test_valuation_migration.py` →
  **61 passed**.
- `ruff check` on the 3 touched files → clean; `mypy` on the 3 files → clean.
- Full-suite 434+1 (sole R21-known census failure) taken from qa-api/router
  verification, not re-run here.
