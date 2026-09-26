# Phase 4 — Financial Metrics & Ratios

## Objective
Implement deterministic financial metric calculations with provenance tracking.

## Scope
- Metric definitions (17 metrics across 7 categories)
- Deterministic calculation engine using Decimal precision
- Period comparison with publication date awareness
- Metric persistence and provenance
- API endpoints for metric calculation and retrieval
- Frontend metrics page

## Dependencies
Phase 3 — Financial Statements & Normalized Facts must be complete.

## Requirements
1. Metric definitions: growth, margins, profitability, leverage, liquidity, cash flow, per-share
2. Pure deterministic calculations using Decimal (no floats for financial values)
3. Period selector with look-ahead prevention
4. MetricService orchestrating facts → metrics workflow
5. FinancialMetric model for persistence
6. FinancialMetricInput model for provenance tracking
7. Formula versioning for auditability
8. API endpoints: calculate, list, get by period, get specific metric
9. Frontend: grouped metrics display by category
10. Comprehensive tests for all calculations

## Acceptance Criteria
- 17 metrics calculable for companies with sufficient data
- All calculations use Decimal precision
- Provenance tracked for every metric (input facts, formula version)
- Period comparison uses publication date (no look-ahead)
- Synthetic data labeled `source_type = SYNTHETIC`
- All edge cases handled (missing data, zero values, negative values)

## Required Tests
- Each metric calculation has unit tests
- Edge cases: zero denominators, missing data, negative values
- Period selector correctly finds comparable periods
- Provenance tracking records all inputs
- API endpoints return correct data

## Required Verification
```bash
pytest
ruff check
mypy
npm run build
alembic upgrade head
curl -X POST http://localhost:8000/api/metrics/companies/{id}/calculate
```

## Explicitly Forbidden Features
- No valuation models (Phase 6)
- No AI-powered analysis
- No Shariah screening
- No technical indicators
- No DCF or fair value calculations

## Expected Deliverables
- `backend/app/metrics/definitions.py` — 17 metric definitions
- `backend/app/metrics/engine.py` — calculation functions
- `backend/app/metrics/period_selector.py` — period comparison logic
- `backend/app/metrics/service.py` — orchestration service
- `backend/app/models/metrics.py` — FinancialMetric, FinancialMetricInput
- `backend/app/repositories/metrics.py`
- `backend/app/api/metrics.py`
- `frontend/src/pages/FinancialMetrics.tsx`
- Migration 004_financial_metrics.py
- `backend/tests/test_metrics_engine.py`
- `backend/tests/test_period_selector.py`
