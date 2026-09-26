# Phase 10 — Backtesting

## Objective
Implement historical backtesting with strict no-lookahead controls.

## Scope
- Backtesting engine
- Historical simulation
- Performance metrics
- No-lookahead validation
- API endpoints for backtesting
- Frontend backtesting interface

## Dependencies
Phase 4 — Financial Metrics should be complete.
Phase 5 — Shariah Screening should be complete.
Phase 7 — Technical Analysis should be complete.

## Requirements
1. Backtesting engine:
   - Historical simulation with configurable start/end dates
   - Point-in-time data access (publication_date ≤ simulation_date)
   - No look-ahead bias
2. Performance metrics:
   - Total return
   - Sharpe ratio
   - Maximum drawdown
   - Win rate
   - Comparison to benchmark
3. Strategy configuration:
   - Entry/exit rules based on screening criteria
   - Position sizing
   - Rebalancing frequency
4. API endpoints: run backtest, get results, compare strategies
5. Frontend: backtesting interface with results visualization

## Acceptance Criteria
- No look-ahead bias in simulations
- Performance metrics correctly calculated
- Historical data access respects publication dates
- Results reproducible
- Clear documentation of strategy rules

## Required Tests
- No-lookahead validation passes
- Performance metrics match manual calculations
- Edge cases: empty periods, insufficient data
- Reproducible results

## Required Verification
```bash
pytest
ruff check
mypy
curl http://localhost:8000/api/backtest/run
```

## Explicitly Forbidden Features
- No look-ahead bias
- No future data in simulations
- No curve-fitting
- No overfitting

## Expected Deliverables
- `backend/app/backtesting/engine.py` — backtesting engine
- `backend/app/backtesting/metrics.py` — performance metrics
- `backend/app/backtesting/service.py` — BacktestService
- `backend/app/models/backtesting.py` — BacktestResult
- `backend/app/api/backtesting.py`
- `frontend/src/pages/Backtesting.tsx`
- Migration for backtesting tables
- Documentation of no-lookahead controls

## Special Review Requirements
This phase requires extra architectural review:
- Strict no-lookahead validation required
- Publication date controls must be verified
- Performance metrics must be independently verified
- No curve-fitting or overfitting
