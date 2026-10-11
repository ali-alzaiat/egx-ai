# Phase 13 — Real Financial Data Ingestion

> **Priority: HIGHEST.** All financial metrics, valuations, scores, and
> Shariah verdicts are currently computed on synthetic data
> (`FakeFinancialDataProvider`). This phase is the prerequisite for any
> real-money research use of the platform.

## Objective

Wire real EGX company filings into the existing ingestion pipeline. By the end
of this phase, at least a subset of companies have financial facts backed by
actual filed documents with full provenance.

## Background

The ingestion layer already has:
- `NormalizationService` — 24 label-mapping rules, tested
- `FinancialFactValidator` — ERROR/WARNING validation, tested
- `FinancialDocument` / `FinancialFact` models with `document_url`,
  `publication_date`, `source_type`, `source_page`
- `DataSourceType` enum with `FRA`, `COMPANY`, `EGX` variants
- `DataQualityService` — quality scoring wired but only running on synthetic rows

What is missing: anything that actually fetches real documents.
`backend/app/ingestion/fra/` is an empty stub (`__init__.py` only).

## Scope

### 1. FRA / Company Disclosure Ingestion

Implement `backend/app/ingestion/fra/provider.py`:

- Source: FRA disclosure portal and/or company investor-relations pages.
- Do NOT bypass CAPTCHAs, authentication, or `robots.txt` restrictions.
- Start with structured annual reports (PDF or XBRL) for the top 20 EGX
  companies by market cap as a pilot batch.
- Extract: revenue, net income, total assets, total liabilities,
  shareholders' equity, cash from operations, capital expenditure, EPS,
  dividends paid — the minimum set required by the existing 17 metric
  definitions.
- Every extracted fact must carry:
  - `document_url` — direct link to the source filing
  - `publication_date` — the date the document was published/filed
  - `source_page` — page number or section where the value appears
  - `source_type = DataSourceType.COMPANY` or `DataSourceType.FRA`
- Map extracted labels through `NormalizationService`. Unmapped labels
  must log a WARNING and be stored with `status = REPORTED` (not dropped).
- Run `FinancialFactValidator` on every extracted document. Validation
  errors block ingestion; warnings are stored and surfaced via the DQ score.

### 2. EGX Official Price Fallback

Add `backend/app/ingestion/egx/official_provider.py`:

- Source: egx.com.eg daily CSV download or official EGX API (if available).
- Use as a fallback when Yahoo Finance returns an empty price array.
- Target: close the 30/229 coverage gap identified in Phase 2.
- Every price row ingested via this provider must have
  `source_type = DataSourceType.EGX`.

### 3. Guard Against Synthetic Data in Production

- The production ingestion service must reject any write that would set
  `source_type = DataSourceType.SYNTHETIC`. Synthetic rows may only be
  inserted by test fixtures via `conftest.py`.
- `FakeFinancialDataProvider` must not be importable from any non-test
  module. Move it to `tests/fakes.py` or add a module-level guard.

### 4. UI Coverage Disclosure

- The `/api/companies/{id}` response must include a `data_coverage` object:
  - `has_real_financials: bool`
  - `oldest_real_filing: date | null`
  - `newest_real_filing: date | null`
  - `price_coverage: "FULL" | "PARTIAL" | "NONE"`
- The company list and company detail pages must surface this visibly.
  Companies with `has_real_financials = false` must be labelled
  **⚠️ SYNTHETIC DATA** in the UI.

## Dependencies

- Phase 1–4 must be COMPLETE (they are).
- Phase 0 hotfix must be COMPLETE (test suite must be runnable).

## Acceptance Criteria

1. At least one real EGX company has ≥1 `FinancialFact` row with
   `source_type` ∈ `{FRA, COMPANY}` and a non-null `document_url`.
2. `DataQualityStatus` for that company is `OK` or `DEGRADED` (not
   `POOR` / `MISSING`) after the ingestion run.
3. The production ingestion path cannot write `source_type = SYNTHETIC`.
   Confirmed by a test that asserts the guard raises at the service layer.
4. All 38 existing backend tests continue to pass (synthetic data stays
   in tests only).
5. The `/api/companies/{id}` response includes `data_coverage`.
6. Yahoo price gaps for ≥10 previously uncovered companies are resolved
   via the EGX official fallback provider.

## Required Tests

- `test_fra_provider_extracts_real_document` — mocked HTTP, asserts fact
  rows have `document_url` and `publication_date`.
- `test_normalization_logs_unmapped_labels` — unmapped label → WARNING,
  not silent drop.
- `test_synthetic_write_rejected_in_production_service` — service raises
  when caller tries to insert `SYNTHETIC` source type.
- `test_egx_official_price_fallback_fills_gap` — mocked EGX CSV,
  asserts prices ingested for a ticker Yahoo had returned empty.
- `test_data_coverage_in_company_response` — API returns `data_coverage`
  field with correct `has_real_financials` value.

## Required Verification

```bash
cd backend && .venv/bin/python -m pytest -q
cd backend && .venv/bin/python -m ruff check app tests
cd backend && .venv/bin/python -m mypy app
```

## Explicitly Forbidden

- No CAPTCHA bypassing or scraping behind authentication.
- No fabricating or interpolating missing financial values.
- No writing `source_type = SYNTHETIC` from production code paths.
- No hardcoded financial numbers (all values come from parsed documents).

## Expected Deliverables

- `backend/app/ingestion/fra/provider.py` — FRA/company disclosure parser
- `backend/app/ingestion/egx/official_provider.py` — EGX official price fallback
- `backend/app/ingestion/provider_registry.py` — wires real providers; no fake
- `backend/tests/fakes.py` — consolidated home for all fake providers (moved from prod)
- `backend/tests/test_fra_provider.py`
- `backend/tests/test_egx_official_provider.py`
- Alembic migration: add `data_coverage` view or computed columns
- `docs/phases/phase-13-report.md` — completion report
