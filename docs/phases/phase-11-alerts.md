# Phase 11 — Alerts & Monitoring

## Objective
Implement configurable alerts for changes in financial data and analysis.

## Scope
- Alert configuration
- Price alerts
- Financial metric alerts
- Valuation alerts
- Shariah status alerts
- Alert persistence
- API endpoints for alerts
- Frontend alert management

## Dependencies
Phase 4 — Financial Metrics should be complete.
Phase 5 — Shariah Screening should be complete.
Phase 6 — Valuation should be complete.

## Requirements
1. Alert types:
   - Price alerts: price crosses threshold, volume spike
   - Metric alerts: metric changes by X%, crosses threshold
   - Valuation alerts: valuation changes, fair value crosses price
   - Shariah alerts: compliance status changes
   - Document alerts: new filing published
2. Alert configuration:
   - Per-company or portfolio-wide
   - Configurable thresholds
   - Notification preferences
3. Alert evaluation:
   - Check new data against alert rules
   - Record alert history
4. API endpoints: create alert, list alerts, get triggered alerts
5. Frontend: alert management, alert history

## Acceptance Criteria
- Alerts correctly trigger on threshold breaches
- Alert history preserved
- Configuration is flexible
- No false positives on normal data changes
- Alert evaluation is deterministic

## Required Tests
- Each alert type triggers correctly
- Thresholds evaluated accurately
- Alert history recorded
- Edge cases: missing data, rapid changes

## Required Verification
```bash
pytest
ruff check
mypy
curl http://localhost:8000/api/alerts
```

## Explicitly Forbidden Features
- No real-time notifications (email, SMS)
- No trading execution based on alerts
- No AI-generated alert rules
- No false urgency

## Expected Deliverables
- `backend/app/alerts/rules.py` — alert rule definitions
- `backend/app/alerts/evaluator.py` — alert evaluation
- `backend/app/alerts/service.py` — AlertService
- `backend/app/models/alerts.py` — Alert, AlertHistory
- `backend/app/api/alerts.py`
- `frontend/src/pages/Alerts.tsx`
- Migration for alert tables

## Special Review Requirements
This phase requires extra architectural review:
- Alert rules must be deterministic
- No false positives on normal market movements
- Alert history must be complete
- Configuration must be flexible
