# Phase 14 — Data Quality UI Gates & Liquidity Filter

> **Dependency: Phase 13 must be COMPLETE** (real data must be flowing in).
> Running this phase on synthetic data would only gate on fake quality scores.

## Objective

Promote the existing data quality scoring engine from an informational API
field to a first-class UI control. Any company with poor, missing, or stale
data must not silently reach the recommendation surface.

## Background

The data quality engine (`dataquality/scores.py`, `dataquality/service.py`) is
implemented and tested. The `DataQualityStatus` enum (`OK | DEGRADED | POOR |
MISSING`) is computed and returned by the API. However:
- The frontend does not gate on it — a `POOR` company renders the same as
  an `OK` company.
- Valuation fair-value outputs show a point estimate regardless of data quality.
- Liquidity is not surfaced anywhere; illiquid small-caps are ranked alongside
  liquid large-caps with no visible distinction.
- Staleness (score age > 90 days) is not surfaced in the UI at all.

## Scope

### 1. Data Quality Gate on Scores & Recommendations

- `DataQualityStatus = POOR` or `MISSING`: company must be visually suppressed
  in the ranked list. A collapsed row with an expand toggle is acceptable; a
  full ranking card is not.
- Before the user can view any score, valuation, or thesis for a `POOR`/`MISSING`
  company, a blocking modal/banner must confirm they understand data is
  insufficient. One acknowledgement per session per company is sufficient.
- `DataQualityStatus = DEGRADED`: company is shown with a persistent amber
  `⚠️ DATA DEGRADED` badge on every score surface (list + detail).

### 2. Valuation Confidence Haircut Display

- Any fair-value output must display:
  - The exact model used (PE, DCF, etc.)
  - The exact inputs/assumptions (growth rate, discount rate, terminal growth)
  - A sensitivity table: ±1% on discount rate, ±1% on terminal growth rate
  - A confidence label (`HIGH | MEDIUM | LOW`) derived from `DataQualityStatus`
- For `DEGRADED` data: show a range (e.g., "EGP 42–58") not a point estimate.
- For `POOR`/`MISSING` data: suppress the fair-value figure entirely; show
  "Insufficient data for valuation" instead.

### 3. Liquidity Filter

- Compute trailing 30-day average daily value traded (close × volume) from
  `daily_prices` for each company.
- Companies with avg daily value < EGP 500,000 are flagged `⚠️ LOW LIQUIDITY`.
- This flag must appear:
  - In the ranking list (next to company name)
  - On the company detail header
  - As a tooltip explaining the risk (cannot exit position without moving price)
- The flag does not exclude the company from the list, but it must be visible
  before any signal card is shown.
- Expose via API: `GET /api/companies/{id}/liquidity` →
  `{ avg_daily_value_egp, is_liquid, threshold_egp, computed_at }`.

### 4. Staleness Banner

- Every signals/score page must display `data_as_of: <date>` prominently
  (not in a tooltip — visible without interaction).
- If `data_as_of` is older than 90 days: a full-width amber staleness banner
  appears above all scores. The banner cannot be dismissed without clicking
  "I understand this data may be stale."
- The 90-day threshold is a named constant in the frontend, not a magic number.

## Dependencies

- Phase 13 (real data ingestion) — COMPLETE
- Phase 0 hotfix — COMPLETE

## Acceptance Criteria

1. A company with `DataQualityStatus = POOR` cannot reach the recommendation
   card in the UI without a blocking acknowledgement gate.
2. A company with avg daily value < EGP 500K has the LOW LIQUIDITY flag
   visible in both the list and detail pages.
3. Every rendered fair-value figure is accompanied by a sensitivity table
   (tested via Playwright snapshot).
4. `data_as_of` is visible on every score/signals page without any hover or
   click (confirmed by Playwright snapshot).
5. A score older than 90 days renders the staleness banner (confirmed via
   Playwright with a mocked old timestamp).
6. `GET /api/companies/{id}/liquidity` returns the correct shape and value.

## Required Tests

Backend:
- `test_liquidity_endpoint_returns_correct_avg` — asserts computation from
  `daily_prices` rows matches expected avg.
- `test_liquidity_flag_below_threshold` — asserts `is_liquid = false` when
  avg < 500,000.

Frontend (vitest):
- `test_dq_gate_blocks_poor_company` — renders the gate modal, not the score card.
- `test_liquidity_badge_rendered` — flag appears for an illiquid company.
- `test_sensitivity_table_rendered` — valuation card includes sensitivity rows.
- `test_staleness_banner_rendered` — banner appears when `data_as_of` > 90 days ago.

UI (Playwright — qa-ui):
- Snapshot: company with `POOR` DQ shows gate, not score card.
- Snapshot: company detail with fair value shows sensitivity table.
- Snapshot: staleness banner for stale score.

## Required Verification

```bash
cd backend && .venv/bin/python -m pytest -q
cd backend && .venv/bin/python -m ruff check app tests
cd frontend && npm run build && npm run lint && npm test
```

## Explicitly Forbidden

- No dismissing the POOR/MISSING gate via a URL parameter or API flag.
- No showing a point estimate fair value for DEGRADED data.
- No suppressing the staleness banner via localStorage without acknowledgement.

## Expected Deliverables

- `backend/app/api/liquidity.py` — liquidity endpoint
- `backend/app/services/liquidity.py` — avg daily value computation
- `backend/tests/test_liquidity.py`
- `frontend/src/components/DataQualityGate.tsx` — blocking gate modal
- `frontend/src/components/LiquidityBadge.tsx`
- `frontend/src/components/StalenessBanner.tsx`
- `frontend/src/components/ValuationSensitivityTable.tsx`
- Updates to `CompanyDetail.tsx`, `CompanyList.tsx`, valuation card components
- `frontend/src/lib/staleness.ts` — threshold constant + helper
- `docs/phases/phase-14-report.md` — completion report
