# Phase 9 — Opportunity Detection

## Objective
Combine all analysis into transparent research and screening system.

## Scope
- Multi-factor screening (Shariah, fundamentals, valuation, technical)
- Transparent scoring methodology
- Research report generation
- API endpoints for opportunity detection
- Frontend screening results display

## Dependencies
Phase 5 — Shariah Screening must be complete.
Phase 4 — Financial Metrics should be complete.
Phase 6 — Valuation should be complete.
Phase 7 — Technical Analysis should be complete.

## Requirements
1. Multi-factor screening combining:
   - Shariah compliance
   - Fundamental metrics (growth, profitability, leverage)
   - Valuation metrics (P/E, P/B, DCF)
   - Technical indicators (trend, momentum)
2. Transparent scoring methodology:
   - Each factor weighted explicitly
   - Scores normalized and comparable
   - No black-box algorithms
3. Research summary generation
4. API endpoints: screen opportunities, get research
5. Frontend: opportunity list with factor breakdown

## Acceptance Criteria
- Screening criteria are transparent and configurable
- Each candidate shows factor-by-factor breakdown
- No opaque "recommendation" scores
- All factors traceable to source data
- Results clearly marked as screening outcomes

## Required Tests
- Each factor correctly evaluated
- Scoring methodology documented
- Edge cases: missing factors, partial data
- Deterministic: same inputs → same ranking

## Required Verification
```bash
pytest
ruff check
mypy
curl http://localhost:8000/api/opportunities/screen
```

## Explicitly Forbidden Features
- No opaque recommendation algorithms
- No AI-generated stock picks
- No hidden criteria
- No trading signals

## Expected Deliverables
- `backend/app/screening/multi_factor.py` — multi-factor screening
- `backend/app/screening/scoring.py` — scoring methodology
- `backend/app/api/opportunities.py`
- `frontend/src/pages/Opportunities.tsx`
- Migration for opportunity tables
- Documentation of screening methodology

## Special Review Requirements
This phase requires extra architectural review:
- All screening criteria must be transparent
- Scoring methodology must be documented
- No hidden or opaque algorithms
- Explainability required for all outputs
