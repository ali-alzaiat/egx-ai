# R20 — Stream A verdict: qa-api empty-history blocker + folded Task 7 scope

**From:** Mostafa (tech-lead) · 2026-10-10
**Inputs:** inbox brief; `backend/app/ingestion/sync.py:76-92`; `backend/app/ingestion/egx/provider.py:139-160`; `backend/app/ingestion/jobs.py:197-217`; `backend/tests/test_ingestion_jobs.py:19-40,154-171`; `refresh-and-assess-contract.md:52-60,107-129`; R16, R18.1.

## Verification (read, not remembered)

- `sync.py:81-87` — `fetch_one` appends to `failures` **only** on exception; on success it stores **only non-empty** `bars`. Empty `[]` falls through both branches: neither fetched nor failed. Blocker confirmed as described.
- `egx/provider.py:145,158-160` — `get_daily_prices` docstring says "Returns [] when Yahoo has no data", and `hist is None or hist.empty → return []`. So `[]` is the real-world no-history signal, not a hypothetical.
- Contract `refresh-and-assess-contract.md:53,58,121-123` — `partial` = completed with ≥1 ticker failures; per-ticker failures "land in `prices.failed_tickers` and yield `partial`"; the finished example lists `{ "ticker": "USCA", "error": "Yahoo returned no history" }`. The implementation contradicts its own contract's example.
- `jobs.py:217` — `status = partial if summary.failures else done`. A silent `[]` therefore reports `done / failed_count 0` for a run that lost a ticker. That is a status lie, against the contract's "Honest failure" rule (:204).
- `test_ingestion_jobs.py:38-40` — stub signals failure only via `raise`; no test returns `[]`. Coverage gap confirmed.

## Ruling 1 — FIX NOW via staff-backend (not defer, not accept)

Defer/accept would ship a known-dishonest job status on the most common real-world Yahoo outcome (delisted/thin tickers return empty history, not exceptions). Cost of fix is one branch plus one regression test; cost-if-wrong of deferring is silent coverage loss the UI reports as success. Fix:

1. In `fetch_one` (`sync.py:84-87`), treat empty `bars` as a failure entry with the contract's own message, e.g. `failures.append((ticker, "Yahoo returned no history"))`.
2. Regression test in `test_ingestion_jobs.py`: stub returns `[]` (not raise) for one ticker → assert `partial`, `failed_count == 1`, `failed_tickers == [{"ticker": ..., "error": "Yahoo returned no history"}]`, assessment still ran. Keep the existing raise-path test green.
3. No contract change needed — implementation is brought to the contract, not vice versa. Re-run the jobs tests + ruff + mypy on the touched files.

## Ruling 2 — Stream A verdict: FIX-LIST (one item), not ship, not rework

- **R18.1 folded Task 7 scope: PASS.** Inheritance property confirmed, `base_url`/stamping per R15, read-only DQ GET, `last_synced_at` in data-sources — no Task 7 finding open.
- **Stream A otherwise: PASS per qa-api** with router gates green (pytest 345, ruff clean, mypy 0/106).
- **Fix-list:** the single Ruling-1 item above. No rework. After staff-backend lands the fix and qa-api re-verifies the jobs file, Stream A ships without returning to tech-lead (router may mark DONE on green re-verification).
