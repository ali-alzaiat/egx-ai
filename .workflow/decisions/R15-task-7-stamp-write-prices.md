# R15 — Task 7 scope pins (sync stamps source freshness)

Plan: `docs/superpowers/plans/2026-10-08-competitive-enhancement-roadmap.md` lines 251–263.
Verified this session against branch `phase-1-data-quality` (HEAD `36f5c8e`).

## R15.1 — Stamp `last_synced_at` in `write_prices`, not `ingest_prices`

Plan Step 3 (line 261) says "stamp in `ingest_prices` after `write_prices`". That is
unimplementable as written if the goal is Task 7's title ("Sync stamps source freshness"):

- `MarketDataIngestionService.ingest_prices` (`backend/app/ingestion/service.py:49`) has
  **zero callers** in `app/` or `tests/` (verified by grep).
- The only production price path is `sync.py:121`, which calls
  `service.write_prices(ticker, bars)` **directly** — it splits fetch (concurrent) from
  write (sequential, one `AsyncSession`) and never goes through `ingest_prices`.

Ruling: stamp inside `write_prices`, after the `if not price_data: return 0` guard, on the
`DataSource` returned by `source_repo.get_or_create`, before the existing
`await self.session.commit()` (service.py:99) so there is one commit. This is the shared
write path, so both `ingest_prices` and `sync.py` are covered. `last_synced_at` is only set
on a successful non-empty write, matching the plan's "after a successful price write".

Cost if wrong: one line moved.

## R15.2 — `base_url` only; `description` stays default

Plan line 254 says pass "`base_url`/`description` into `get_or_create`", but the interface
(line 257) adds only `source_url` to `__init__`. No source for a `description` value is
specified anywhere in the plan. Ruling: pass `base_url=self.source_url` at both call sites
(`service.py:76` write_prices, `service.py:107` upsert_companies); leave `description` at
its `None` default; do not add a `source_description` parameter. Manufacturing a description
would fabricate provenance metadata (AGENTS.md rule 3).

Cost if wrong: one kwarg.

## R15.3 — `base_url` is set on create only

`DataSourceRepository.get_or_create` (`repositories/data_source.py:13-33`) returns an
existing row unchanged; it never updates `base_url`. Ruling: do not change `get_or_create`
(shared by universe and ingestion paths); backfilling an existing
`YAHOO_FINANCE_EGX.base_url` is out of scope. Fresh rows get `base_url`; existing rows still
get `last_synced_at` stamped because it is set on the returned (session-attached) object.

Cost if wrong: a pre-existing data_sources row keeps `base_url=NULL` until a manual backfill.

## R15.4 — Test file pinned

Plan line 255 allows "extend `backend/tests/test_universe.py` or new
`backend/tests/test_sync_provenance.py`". `test_universe.py` is universe-discovery scope;
price-sync provenance does not belong there. Ruling: new
`backend/tests/test_sync_provenance.py`.

## R15.5 — Yahoo URL constant

Plan says "Yahoo base URL constant alongside `PRICE_SOURCE_NAME`" without pinning a value.
The provider is Yahoo Finance (`backend/app/ingestion/egx/provider.py:1-3`). Ruling:
`PRICE_SOURCE_URL = "https://finance.yahoo.com"` in `sync.py`, next to `PRICE_SOURCE_NAME`
(line 34), passed as `source_url=PRICE_SOURCE_URL` in the service constructor (line 112).
