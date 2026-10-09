# Data Quality API Contract

**Source of truth:** Backend implementation (not roadmap). This documents what exists.

- File: `backend/app/api/data_quality.py`  
- Scale: `"0-100; higher is better; status MISSING|DEGRADED|POOR|OK"`  
- Disclaimer: `"Data quality describes the available inputs. It is not an assessment of the company."`  
- Methodology version: from `app.dataquality.scores.METHODOLOGY_VERSION` (currently `"1.0"`)

## Status enum

`DataQualityStatus` (StrEnum, values as strings):
- `OK` — score >= 70.0
- `DEGRADED` — score >= 40.0 and < 70.0
- `POOR` — score < 40.0
- `MISSING` — no underlying rows (forced when `no_rows=True`), score is `0.0`

(See `backend/app/dataquality/scores.py`)

## Component object

Each component is a `QualityComponent` serialized via `as_dict()`:
```json
{
  "key": string,      // e.g. "completeness", "freshness", "validation", "historical_depth", "source_reliability"
  "label": string,    // human label, e.g. "Completeness"
  "score": number,    // 0-100 float
  "weight": number,   // component weight (sum to 1.0)
  "reason": string
}
```

Components are returned as an array in the score payload (order is deterministic from scoring).

## Issues

`issues` is an array of strings: `string[]`. Populated when any component score < `ISSUE_THRESHOLD` (40.0); format per component: `"{label} below threshold ({score:.0f}/100)"`. Additional issues may be appended by the service in edge cases (e.g. validation/freshness checks not run).

## DataQualityScore shape (full assessment)

Returned by service `as_dict()` and embedded in responses:
```json
{
  "scope": string,                // one of: "price_history" | "company_profile" | "financial_statements"
  "as_of": string,                // ISO 8601 date (YYYY-MM-DD)
  "status": "OK" | "DEGRADED" | "POOR" | "MISSING",
  "score": number,                // overall 0-100, rounded to 1 decimal (aggregate)
  "components": Component[],      // see Component shape
  "issues": string[],             // see Issues
  "methodology_version": string   // e.g. "1.0"
}
```

## Endpoints

### GET /api/data-quality/companies/{company_id}
- Method: `GET`
- Path: `/api/data-quality/companies/{company_id}`
- Query params:
  - `scope` (optional, string) — if provided, only this scope is assessed/latest-fetched? Implementation: builds `scopes = [scope] if scope else ["price_history", "company_profile", "financial_statements"]`. For each scope it calls `service.latest(company_id, s, methodology_version=METHODOLOGY_VERSION)` and if not `None`, appends `result.as_dict()`. (So it returns latest persisted assessments for those scopes; if never assessed, that scope is omitted.)
- Response (200):
```json
{
  "items": DataQualityScore[],  // array of assessments (as_dict)
  "methodology_version": string,
  "scale": string,               // SCALE constant
  "disclaimer": string           // DISCLAIMER constant
}
```
- Errors: 404 if company not found (`_ensure_company_exists`)

### POST /api/data-quality/companies/{company_id}/assess
- Method: `POST`
- Path: `/api/data-quality/companies/{company_id}/assess`
- Query params:
  - `scope` (required, string) — one of `"price_history" | "company_profile" | "financial_statements"` (service validates; unknown → 400 from service)
  - `as_of` (optional, date `YYYY-MM-DD`) — if omitted, defaults to `datetime.now(UTC).date()` in service
- Response (200): returns the computed `DataQualityScore` as dict merged with scale and disclaimer:
```json
{
  // ...all fields from DataQualityScore.as_dict()
  "scale": string,
  "disclaimer": string
}
```
- Errors: 404 if company not found; 400 if unknown scope

## Screening embed (data_quality)
In `GET /api/screening/companies/{company_id}` (see `backend/app/api/screening.py` lines ~35-42), the response includes:
```json
"data_quality": DataQualityScore | null
```
- Computed as: `await DataQualityService(session).latest(company_id, "financial_statements")` → `dq_result.as_dict() if dq_result is not None else None`
- Scope is fixed to `"financial_statements"` for this embed (not parameterized).

## TypeScript interfaces (ready to paste)

Frontend can use these to type mocks and API responses.

```typescript
export type DataQualityStatus = "OK" | "DEGRADED" | "POOR" | "MISSING";

export interface QualityComponent {
  key: string;      // "completeness" | "freshness" | "validation" | "historical_depth" | "source_reliability"
  label: string;
  score: number;    // 0-100
  weight: number;
  reason: string;
}

export interface DataQualityScore {
  scope: "price_history" | "company_profile" | "financial_statements";
  as_of: string;    // YYYY-MM-DD
  status: DataQualityStatus;
  score: number;    // 0-100 (1 decimal precision)
  components: QualityComponent[];
  issues: string[];
  methodology_version: string;
}

// GET /api/data-quality/companies/{company_id}
export interface DataQualityListResponse {
  items: DataQualityScore[];
  methodology_version: string;
  scale: string;
  disclaimer: string;
}

// POST /api/data-quality/companies/{company_id}/assess
export interface DataQualityAssessResponse extends DataQualityScore {
  scale: string;
  disclaimer: string;
}

// Screening embed
export interface ScreeningWithDataQuality {
  // ...other screening fields per screening API
  data_quality: DataQualityScore | null;
}
```

## Mock payload examples

### Example 1: OK assessment (price_history)
```json
{
  "scope": "price_history",
  "as_of": "2026-10-09",
  "status": "OK",
  "score": 85.5,
  "components": [
    {
      "key": "completeness",
      "label": "Completeness",
      "score": 100.0,
      "weight": 0.3,
      "reason": "5 of 5 required items present"
    },
    {
      "key": "freshness",
      "label": "Freshness",
      "score": 90.0,
      "weight": 0.25,
      "reason": "5 days stale"
    },
    {
      "key": "validation",
      "label": "Validation",
      "score": 100.0,
      "weight": 0.2,
      "reason": "0 errors, 0 warnings"
    },
    {
      "key": "historical_depth",
      "label": "Historical depth",
      "score": 80.0,
      "weight": 0.15,
      "reason": "120 of 150 expected periods present"
    },
    {
      "key": "source_reliability",
      "label": "Source reliability",
      "score": 95.0,
      "weight": 0.1,
      "reason": "source type: EGX"
    }
  ],
  "issues": [],
  "methodology_version": "1.0",
  "scale": "0-100; higher is better; status MISSING|DEGRADED|POOR|OK",
  "disclaimer": "Data quality describes the available inputs. It is not an assessment of the company."
}
```

### Example 2: MISSING assessment (financial_statements)
```json
{
  "scope": "financial_statements",
  "as_of": "2026-10-09",
  "status": "MISSING",
  "score": 0.0,
  "components": [
    {
      "key": "completeness",
      "label": "Completeness",
      "score": 0.0,
      "weight": 0.3,
      "reason": "0 of 5 required items present"
    },
    {
      "key": "freshness",
      "label": "Freshness",
      "score": 0.0,
      "weight": 0.25,
      "reason": "age unknown: no reference date"
    },
    {
      "key": "validation",
      "label": "Validation",
      "score": 100.0,
      "weight": 0.2,
      "reason": "0 errors, 0 warnings"
    },
    {
      "key": "historical_depth",
      "label": "Historical depth",
      "score": 0.0,
      "weight": 0.15,
      "reason": "0 of 8 expected periods present"
    },
    {
      "key": "source_reliability",
      "label": "Source reliability",
      "score": 40.0,
      "weight": 0.1,
      "reason": "source type: unknown"
    }
  ],
  "issues": [
    "Completeness below threshold (0/100)",
    "Freshness below threshold (0/100)",
    "Historical depth below threshold (0/100)",
    "Source reliability below threshold (40/100)"
  ],
  "methodology_version": "1.0",
  "scale": "0-100; higher is better; status MISSING|DEGRADED|POOR|OK",
  "disclaimer": "Data quality describes the available inputs. It is not an assessment of the company."
}
```

## Notes / roadmap alignment

- Backend and roadmap are aligned on endpoints, shapes, screening embed (`data_quality` as object|null for financial_statements), and constants.
- Minor note: roadmap states "scopes: `price_history`, `company_profile`, `financial_statements`" and the contract matches; backend enforces via service. 
- For GET list: the backend returns latest persisted assessments only (omits scopes never assessed). That’s the observable behavior and should be matched by frontend mocks.
- No discrepancies requiring `BLOCKED` — contract is documented directly from backend.