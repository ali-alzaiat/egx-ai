# R13 — Task 6: two provenance fields added to ingestion provider data

**From:** tech-lead · 2026-10-09
**Inputs:** roadmap plan lines 234–248 (Task 6); live code `backend/app/ingestion/financial_provider.py`, `financial_service.py`, `fake_financial_provider.py`

## Finding

Task 6's Interfaces (plan line 241) require `document_url` to be "written through from `FinancialDocumentData`" and `_find_document` to "filter `document_type`". Live code does not support either:

- `FinancialDocumentData` (financial_provider.py:17) has **no** `document_url` field; `financial_service.py:113` hard-codes `document_url=None`.
- `FinancialFactData` (financial_provider.py:30) has **no** `document_type` field; `_find_document` (financial_service.py:201) queries `period_id` + `source_id` only and uses `scalar_one_or_none()`, so two documents of different types for one period raise `MultipleResultsFound` — the exact failure Task 6's test pins.

The plan's Task 6 Files list names only `financial_service.py`, `normalization.py` and the new test, but neither mandated behaviour is implementable without the provider data carrying these fields. No other discriminator exists: the repo's only `document_type` value is `ANNUAL_REPORT`, and `fact_type` holds statement types (`INCOME_STATEMENT`/`BALANCE_SHEET`/`CASH_FLOW`), not document types.

## Ruling

Amend Task 6 scope to also modify `backend/app/ingestion/financial_provider.py` and `backend/app/ingestion/fake_financial_provider.py`:

- `FinancialDocumentData` gains `document_url: str | None = None` as a trailing defaulted field (it has no other defaults, so this stays backward-compatible). `financial_service.py` writes `d.document_url` through instead of `None`; `FinancialDocumentRepository.upsert` already persists that column (repositories/financial.py:87).
- `FinancialFactData` gains `document_type: str` as a trailing **required** field — no silent default, provenance must be stated (AGENTS.md rule 3). `fake_financial_provider.py` tags every synthetic fact `document_type="ANNUAL_REPORT"` to match its synthetic documents.
- `_find_document` becomes `_find_document(period_id, source_id, document_type)` filtering all three; `uq_financial_document (period_id, source_id, document_type)` guarantees at most one row, so `scalar_one_or_none()` stays safe (models/financial.py:132).

## Cost if wrong

One NamedTuple field plus one constructor argument in the fake provider, and one extra query predicate — all reversible. The alternative (a `fact_type → document_type` map) rejects itself: it would fabricate provenance against the only real document type in the repo.

## Collision check (Task 5 → Task 6)

Task 5 (commit 8746adc) touched `app/dataquality/service.py`, `app/api/data_quality.py`, `app/api/screening.py`, `app/main.py`, `tests/test_data_quality_api.py`. Task 6 touches `app/ingestion/*` + a new test file — **zero file overlap**. The only shared surface is `app/ingestion/validation.py`: Task 5 imports `FinancialFactValidator`; Task 6 consumes it and must not change its public behaviour.
