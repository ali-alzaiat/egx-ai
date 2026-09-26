# Phase 6 — Valuation

## Objective
Implement deterministic valuation models with explicit assumptions.

## Scope
- P/E ratio valuation
- P/B ratio valuation
- EV/EBITDA valuation
- DCF model with configurable assumptions
- Sensitivity analysis
- Valuation persistence
- API endpoints for valuation
- Frontend valuation display

## Dependencies
Phase 4 — Financial Metrics & Ratios must be complete.
Phase 5 — Shariah Screening should be complete (for filtered display).

## Requirements
1. Deterministic valuation models:
   - P/E valuation: price vs earnings per share
   - P/B valuation: price vs book value per share
   - EV/EBITDA: enterprise value vs EBITDA
   - DCF: discounted cash flow with configurable WACC, growth rate, terminal value
2. Explicit assumptions for each model
3. Sensitivity analysis for key parameters
4. Valuation results with assumption tracking
5. No LLM-generated inputs
6. API endpoints: calculate valuation, get valuation, sensitivity analysis
7. Frontend: valuation display with assumption transparency

## Acceptance Criteria
- All valuation models use deterministic formulas
- Assumptions are explicit and configurable
- Sensitivity analysis shows impact of parameter changes
- No AI-invented values
- Results clearly state assumptions used
- Synthetic data labeled appropriately

## Required Tests
- Each valuation model tested independently
- DCF calculation verified against known results
- Sensitivity analysis produces expected ranges
- Edge cases: negative earnings, zero growth, missing data

## Required Verification
```bash
pytest
ruff check
mypy
curl http://localhost:8000/api/valuation/companies/{id}
```

## Explicitly Forbidden Features
- No AI-generated valuation inputs
- No "fair value" claims without stating assumptions
- No trading recommendations
- No portfolio optimization

## Expected Deliverables
- `backend/app/valuation/models.py` — valuation calculations
- `backend/app/valuation/service.py` — ValuationService
- `backend/app/models/valuation.py` — ValuationResult
- `backend/app/api/valuation.py`
- `frontend/src/pages/Valuation.tsx`
- Migration for valuation tables
- Documentation of formulas and assumptions

## Special Review Requirements
This phase requires extra architectural review:
- Formulas must be documented with sources
- Assumptions must be explicit
- Sensitivity analysis must be implemented
- No hidden AI involvement
