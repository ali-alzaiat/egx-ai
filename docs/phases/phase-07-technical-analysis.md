# Phase 7 — Technical Analysis

## Objective
Implement deterministic technical indicators calculated from market data.

## Scope
- Moving averages (SMA, EMA)
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- Volume indicators
- Indicator persistence
- API endpoints for technical data
- Frontend chart display

## Dependencies
Phase 2 — Companies & Market Prices must be complete.

## Requirements
1. Deterministic technical indicators:
   - SMA (Simple Moving Average)
   - EMA (Exponential Moving Average)
   - RSI (14-period default)
   - MACD (12, 26, 9 default parameters)
   - Bollinger Bands (20-period, 2 std dev)
   - Volume analysis (OBV, VWAP)
2. All indicators calculated from price data only
3. Configurable parameters (periods, multipliers)
4. Indicator persistence with timestamps
5. API endpoints: get indicators, calculate indicators
6. Frontend: price charts with indicators overlay

## Acceptance Criteria
- All indicators calculated deterministically from price data
- No AI involvement in indicator calculation
- Parameters configurable per indicator
- Indicators correctly handle missing data
- Charts display indicators alongside price data

## Required Tests
- Each indicator tested against known values
- Edge cases: insufficient data, single data point
- Parameters correctly affect calculations
- Indicators update with new price data

## Required Verification
```bash
pytest
ruff check
mypy
curl http://localhost:8000/api/technical/companies/{id}
```

## Explicitly Forbidden Features
- No AI-generated trading signals
- No pattern recognition via ML
- No predictive models
- No buy/sell recommendations

## Expected Deliverables
- `backend/app/technical/indicators.py` — indicator calculations
- `backend/app/technical/service.py` — TechnicalService
- `backend/app/models/technical.py` — TechnicalIndicator
- `backend/app/api/technical.py`
- `frontend/src/components/PriceChart.tsx`
- Migration for technical tables

## Special Review Requirements
This phase requires extra architectural review:
- Indicators must be pure functions of price data
- No ML or AI involved in calculation
- Parameters must be documented
- Edge cases must be handled
