# Phase 3 — Financial Statements & Normalized Facts

## Objective
Implement financial data ingestion, normalization, validation, and storage.

## Scope
- Financial period model (annual, quarterly)
- Financial document model (source documents with provenance)
- Financial fact model (individual data points with traceability)
- Financial data provider abstraction
- Normalization service (label standardization)
- Validation service (data quality checks)
- API endpoints for financial data
- Frontend pages for financial data

## Dependencies
Phase 2 — Companies & Market Prices must be complete.

## Requirements
1. FinancialPeriod model: period type, fiscal year/quarter, dates
2. FinancialDocument model: document type, status, URL, filing date, publication date
3. FinancialFact model: fact type, reported/normalized labels and values, status, provenance
4. FinancialDataProvider protocol
5. FakeFinancialDataProvider for development (labeled SYNTHETIC)
6. NormalizationService — maps reported labels to standardized labels
7. FinancialFactValidator — validates data quality (ERROR/WARNING)
8. FinancialDataIngestionService — orchestrates ingestion pipeline
9. API endpoints: periods, documents, facts, latest facts
10. Frontend: financial data page with facts display

## Acceptance Criteria
- 50 financial periods seeded (5 years × 10 companies)
- 50 financial documents seeded
- 850 financial facts seeded
- All facts have full provenance (source, document, period)
- Normalization maps reported labels to standardized labels
- Validation catches data quality issues
- Frontend displays financial facts grouped by type

## Required Tests
- Period API returns correct periods
- Facts API filters by type and year
- Normalization correctly maps labels
- Validation catches invalid data
- Fake provider returns deterministic data

## Required Verification
```bash
pytest
ruff check
mypy
npm run build
python -m app.seed.seed
curl http://localhost:8000/api/financial/facts/{company_id}
```

## Explicitly Forbidden Features
- No metric calculations (Phase 4)
- No AI analysis
- No real financial data ingestion
- No document upload

## Expected Deliverables
- `backend/app/models/financial.py` — FinancialPeriod, FinancialDocument, FinancialFact
- `backend/app/repositories/financial.py`
- `backend/app/api/financial.py`
- `backend/app/ingestion/financial_provider.py`
- `backend/app/ingestion/fake_financial_provider.py`
- `backend/app/ingestion/normalization.py`
- `backend/app/ingestion/validation.py`
- `backend/app/ingestion/financial_service.py`
- `frontend/src/pages/FinancialData.tsx`
- Migration 003_financial_data.py
