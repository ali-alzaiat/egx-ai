# Phase 5 — Shariah Screening

## Objective
Implement Shariah compliance screening with explicit, versioned methodology.

## Scope
- Shariah screening methodology configuration
- Financial ratio screening (debt, interest income, prohibited activities)
- Industry/sector screening
- Screening result persistence
- API endpoints for screening
- Frontend screening results display

## Dependencies
Phase 4 — Financial Metrics & Ratios must be complete.

## Requirements
1. Shariah screening methodology must be:
   - Explicit (written rules, not AI decisions)
   - Configurable (thresholds adjustable)
   - Source-backed (references to AAOIFI or other standards)
   - Versioned (methodology version tracked)
   - Auditable (screening logic traceable)
2. Financial ratio screening:
   - Total debt / Total assets < threshold (e.g., 33%)
   - Interest income / Total revenue < threshold (e.g., 5%)
   - Cash & interest-bearing securities / Total assets < threshold
3. Industry screening:
   - Exclude prohibited industries (alcohol, gambling, pork, etc.)
4. Screening result model with methodology version
5. API endpoints: screen company, get screening result, list screened companies
6. Frontend: screening status display, methodology documentation

## Acceptance Criteria
- Screening methodology documented with sources
- All thresholds configurable
- Screening results include methodology version
- Screening is deterministic (same inputs → same result)
- No AI used in screening decisions
- Results clearly marked as screening outcomes, not investment advice

## Required Tests
- Each screening rule tested independently
- Edge cases: missing data, boundary values
- Methodology version tracked in results
- Deterministic: same inputs produce same output

## Required Verification
```bash
pytest
ruff check
mypy
curl http://localhost:8000/api/screening/companies/{id}
```

## Explicitly Forbidden Features
- No AI-based screening
- No investment recommendations
- No Shariah "certification" (only screening)
- No portfolio-level screening

## Expected Deliverables
- `backend/app/screening/methodology.py` — ShariahMethodology
- `backend/app/screening/rules.py` — individual screening rules
- `backend/app/screening/service.py` — ShariahScreeningService
- `backend/app/models/screening.py` — ShariahScreeningResult
- `backend/app/api/screening.py`
- `frontend/src/pages/ShariahScreening.tsx`
- Migration for screening tables
- Documentation of methodology and sources

## Special Review Requirements
This phase requires extra architectural review:
- Methodology must be explicit and sourced
- No AI involvement in screening decisions
- Thresholds must be configurable, not hardcoded
- Results must include methodology version for auditability
