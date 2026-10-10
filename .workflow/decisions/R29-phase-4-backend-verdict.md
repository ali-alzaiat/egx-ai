# R29 — Phase 4 backend verdict (Investment score, R28)

**From:** Mostafa (tech-lead) · 2026-10-10
**Sources:** qa-api conformance (P1–P6 PASS, gates green); live code
verified this session: `backend/app/models/scores.py:59-102`,
`backend/app/scores/service.py:243-257,326-364`,
`backend/app/scores/checks.py:140-160,814-829`; gates re-run:
28 passed (engine+api+migration, from `backend/`), ruff clean, mypy clean
(8 files).
**Binding:** R28 scope P1–P6; AGENTS.md rules 1/2/6/7/10.

## G1 ruling — FIX-LIST (read-path reconstruction; NO new migration)

G1 facts verified, not taken on faith:

- **Dropped fields CONFIRMED.** `_payload_from_row`
  (`service.py:326-364`) hard-codes `"ticker": None` (:338),
  `"health_track": None` (:346), `"reason": None` (:351), while the POST
  path (`_payload`, :290-311) emits all three. The table
  (`models/scores.py:59-102`) persists neither `headline_reason` nor
  `health_track` — but no schema change is needed, because **all three are
  exactly reconstructible at read time from already-persisted data**:
  - `headline.reason` is a pure deterministic function of the persisted
    `components` JSONB — `headline_score` (`checks.py:814-829`) derives
    both value and reason solely from component statuses/scores, and each
    persisted component already carries its own `reason`
    (`checks.py:150-160`). Re-run `headline_score` over the
    reconstructed components in `_payload_from_row`.
  - `health_track` follows from the persisted `profile_key` (re-resolve
    via `ScoreProfileRepository`, same as assess :148-160) or from which
    health checks ran in persisted `checks`; prefer the profile lookup,
    fall back to checks-evidence, and note the choice in a comment.
  - `ticker`: `latest_payload` (:243-257) **already loads the company**
    but drops it before calling `_payload_from_row(row)` — pass
    `company.ticker` through. One line.
- **P5 bites.** R28 P5 demands reason on every response; a GET that
  nulls the headline reason violates the brief's letter even though the
  POST path conforms. Read-path-only fix, zero migration risk → fix now,
  not carry.
- **GET stays read-only.** `latest_payload` performs no flush/upsert
  (verified :243-257) — no R27-class GET-write issue here.

## N1 ruling — FIX-LIST (normalize headline.value to number)

N1 facts verified: POST `_payload` emits `"value": str(headline)` (:303)
while `ComponentResult.as_dict` emits `"score": self.score` as
float|None (:150-160) — string vs number for the same kind of quantity.
Direction ruled: **headline becomes a JSON number**, matching component
scores (both are engine floats; `round()` at :795/:827). The alternative
(stringify components) would churn five component shapes for no gain.
No frontend exists for Phase 4 yet, so the shape change is consequence-free;
note it in the fix commit message. Apply in both `_payload` and
`_payload_from_row` so POST and GET agree exactly.

## N2 ruling — FIX-LIST (same one-line root cause as G1)

`assessment.ticker: None` on GET is the same dropped-company-field class
as G1 (`latest_payload` loads the company, `_payload_from_row` doesn't
receive it). Fold into the G1 fix — pass the ticker through. No separate
test needed beyond the round-trip test below.

## Dividend/growth 3-checks observation — ACCEPTED, no change

Verified this session: 23 checks total —
value 5, past 6, health 6, **dividend 3, growth 3** — against the
≥3-run component floor (R28 P2). A dividend/growth component with a
single not-run check therefore goes INSUFFICIENT_DATA. That is the
**literal R28 application**, deterministic and honest (never zero,
never fail-on-missing); the narrowness is spec'd, not a defect
(R28 ships dividend narrowed and growth degraded-or-absent by design).
Recorded for awareness; revisit breadth in Phase 9/10, not here.

## Verdict: FIX-LIST then ship (no rework, no second verdict)

Phase 4 backend **conforms to R28 (P1–P6)** and ships once the follow-up
lands; no return to tech-lead — qa-api re-verifies the fix-list green
and the phase ships per this ruling.

1. **G1+N2:** reconstruct `headline.reason` (via `headline_score` over
   persisted components), `profile.health_track` (via persisted
   `profile_key` lookup), and `assessment.ticker` (pass-through) in the
   GET read path. No migration.
2. **N1:** headline `value` as JSON number in both `_payload` and
   `_payload_from_row`, matching component `score` types.
3. **Round-trip regression test** (new, in `test_scores_api.py`):
   POST→GET equality on headline (value, status, reason),
   `profile.health_track`, `assessment.ticker`, and headline-vs-component
   value types.

## Gates (this session)

- `.venv/bin/pytest tests/test_scores_engine.py tests/test_scores_api.py
  tests/test_scores_migration.py` (from `backend/`) → **28 passed**.
  (A repo-root invocation failed with `alembic: Path doesn't exist` —
  cwd artifact, not code; green from `backend/` like the other suites.)
- `ruff check` on scores/api/models/repository files → clean; `mypy` on
  the same 8 files → clean.
