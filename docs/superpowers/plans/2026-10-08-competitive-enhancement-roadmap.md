# Competitive Enhancement Roadmap — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing EGX screener into an Egyptian Shariah-aware research and decision-support platform that explains its conclusions, exposes missing data, and never overstates confidence.

**Architecture:** The roadmap is delivered one phase at a time. Each phase adds one bounded package under `backend/app/<domain>/` (pure, testable functions), one SQLAlchemy model + Alembic migration where state must persist, one router that follows the existing `/api/<domain>/companies/{id}` convention, and frontend surface that reports uncertainty rather than hiding it. Existing engines (metrics, screening, valuation, signals, technical, AI/RAG) are extended in place — no parallel implementations. Phase 1 is specified here in execution detail; every later phase gets its own plan doc written when that phase starts, using the cross-phase contracts locked in the Roadmap section below.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x (async, `asyncpg`), Alembic, Pydantic, pytest + `asyncio_mode=auto`, Ruff, mypy (strict, currently 48 pre-existing errors — do not add to them). React 19 + TypeScript + Vite + TanStack Query, vitest, ESLint. Postgres 16 with pgvector.

**Spec:** The "Stock Analysis App — Competitive Enhancement Roadmap" document in this conversation (30 sections, 10 phases). This plan argues from it.

**Repo state at plan time:** HEAD `377877e`, working tree clean. 17 models, migrations `001`–`009` (head `009`), 33 API routes, 11 frontend pages, 266 backend tests passing last run.

---

## Global Constraints

- No fabricated financial data, market data, company info or sources (AGENTS.md rule 2). Synthetic rows only ever come from `DataSourceType.SYNTHETIC` and only inside tests.
- Every financial number carries a traceable source: `source_id` / `document_id` / `publication_date` must stay intact through any new write path (AGENTS.md rule 3).
- Backtesting and any `as_of`-parameterised analysis may only use rows whose `publication_date <= as_of` (AGENTS.md rule 4).
- Shariah methodology is versioned and configurable — never hard-code thresholds (AGENTS.md rule 5). Same rule extends to any new score: it stores `methodology_version`.
- Financial formulas are deterministic code; LLMs interpret supplied data only (AGENTS.md rules 1, 6).
- Missing financial data returns `{"value": null, "status": "INSUFFICIENT_DATA", "reason": "..."}` — never zero (AGENTS.md "Error Handling").
- No buy/sell execution (rule 9). UI copy says "potentially attractive under these assumptions", never "BUY" (rule 10).
- API keys and DB credentials stay in environment variables only (rule 8).
- Every new formula ships with unit tests covering zero, negative, and missing inputs (rule 7).
- Never bypass CAPTCHAs, auth or robots restrictions on data sources.
- Backend test command: `cd backend && .venv/bin/python -m pytest -q`. Lint: `cd backend && .venv/bin/python -m ruff check app tests`. Frontend: `cd frontend && npm run build && npm run lint && npm test`.
- Prerequisite for any DB-touching task: `docker compose up -d postgres` (Docker was not running at plan time; no DB was reachable).
- New code must not introduce new mypy errors; new files are type-clean under `strict = true`.
- Do not delete or rewrite working functionality; fix root causes in shared code, not at call sites.

---

## Review Focus

Inputs and failure modes the spec implies that no single task naturally catches. Each line is pinned to a test named in the task that owns it.

1. **Missing financial data silently becomes a number or a "FAIL".** Today `screening_rule_results` collapses tri-state to bool (`repositories/screening.py:33` never writes `INSUFFICIENT_DATA`) and three `or` fallbacks discard a legitimate `Decimal("0")`. A user would expect "no data" to stay visible. → Task 3 tests `test_screening_insufficient_status_persisted`, Task 4 tests `test_zero_value_not_replaced`.
2. **Future filings leak into analysis.** `PeriodSelector.select_comparable_periods` accepts `as_of_date` and ignores it; `filter_by_publication_date` has no callers. A backtester or `as_of` metric run would see Q2 2024 data on 2024-07-01. → Task 2 tests `test_as_of_date_excludes_later_publications`.
3. **Synthetic data reaches production analysis.** `FakeMarketDataProvider` / `FakeFinancialDataProvider` are reachable only by accident of wiring, not by config gate. → Task 4 tests `test_synthetic_source_scores_at_most_20` (score-side ceiling) and Task 1 asserts `DataSourceType.SYNTHETIC` maps to reliability ≤ 20.
4. **Scores are recomputed under different weights and compared as if equal.** Every persisted score stores `methodology_version`; reads must filter by it or disclose a version mismatch. → Task 3 tests `test_assessment_upsert_is_scoped_by_methodology_version`, Task 5 tests version filter on GET.
5. **Confident-looking output over stale or absent data.** The quality score must reach downstream responses (screening in Phase 1) and be `null`, not a default, when never computed. → Task 5 tests `test_screening_response_includes_null_data_quality_when_unassessed`.

---

## Roadmap

### What already exists and gets reused

| Need | Reuse |
|---|---|
| Provenance | `data_sources` table + `DataSourceRepository`, FK `source_id` on `daily_prices` / `financial_documents`, `publication_date` / `filing_date` / `source_page` on financial rows |
| Validation | `ingestion/validation.py` (`FinancialFactValidator`, ERROR/WARNING) — currently test-only |
| Normalization | `ingestion/normalization.py` (24 label rules) — currently test-only, unversioned |
| Coverage disclosure | `services/universe.py` `CoverageReport`, `universe_coverage_snapshots`, `/api/signals/coverage` |
| Sector / industry | `companies.sector`, `companies.industry` free-text columns + index (no tables) |
| Metrics | 17 `MetricDefinition`s, `MetricEngine` dispatch, `MetricStatus`, `PeriodSelector` |
| Screening | `ShariahMethodology` (versioned thresholds), 4 tri-state rules, `screening_rule_results` audit table |
| Valuation | `calculate_{pe,pb,ev_ebitda,dcf}_valuation`, `calculate_sensitivity` (defined, unused) |
| Scoring | `signals/scoring.py` versioned model, percentile ranking, tier-on-percentile, `explain()` |
| Price history | `daily_prices` (199/229 tickers, ~67k rows), Yahoo provider |
| History of scores | `market_signals` keyed `(company_id, as_of, model_version)` — de facto score history |
| AI | `AIAnalyzer` + `RAGPipeline` + `DocumentChunk`, deterministic, disclaimers attached |

### What does not exist (greenfield)

Data quality score, sector/industry/peer tables, industry metric framework, peer comparison, multi-model valuation orchestration, valuation scenarios/confidence, investment score, investment thesis + versions + invalidation, catalysts, risk engine, Shariah breakdown/UNKNOWN status/purification, disclosure ingestion pipeline, document fact extraction, change detection, watchlist, alerts, backtesting, score-performance analysis.

### Phase → spec section mapping

| Phase | Spec sections | Exit criteria |
|---|---|---|
| **1. Data reliability** (this plan) | §1, plus the correctness bugs §19 implies pre-backtest | Quality score persisted + served + shown; provenance columns; validation/normalization wired; look-ahead no-op fixed |
| **2. Industry intelligence** | §2, §3 | Sector/industry tables, peer groups, configurable industry metrics, peer percentile comparison with written explanation |
| **3. Valuation** | §4, §5 | Multiple models chosen per industry, weighted fair value, bull/base/bear, sensitivity, confidence score fed by data quality |
| **4. Investment score** | §6 | One explainable score with all components visible, confidence separate from score |
| **5. Investment thesis** | §7, §8, §9, §16 (part) | Structured thesis referencing real metrics, scenarios with labelled assumptions, structurally stored invalidation conditions, catalyst records |
| **6. Shariah** | §11, §12 | Per-rule breakdown exposed, UNKNOWN when data missing, methodology + freshness on every result, estimated purification |
| **7. Document intelligence** | §13, §14, §15, §16 | Disclosure → parse → facts with provenance, period comparison, "what changed?" |
| **8. Continuous intelligence** | §17, §23, §24 | Thesis versioning on new data, watchlist, alerts |
| **9. Backtesting** | §18, §19, §20 | Strategy runs, no-lookahead tests, benchmark/return metrics, score-vs-return analysis |
| **10. Product polish** | §21, §22, §29, §30 | Unified company page, saved screens, progressive disclosure |

Cross-cutting for every phase: §25 (AI safety), §26 (API conventions), §27 (schema discipline), §28 (tests), §30 (positioning — no charting/execution/chatbot competition).

### Cross-phase contracts (locked now so phases compose)

- **Quality:** `from app.dataquality.scores import DataQualityScore` — consumed by Phase 3 (valuation confidence), Phase 4 (score component), Phase 5 (thesis confidence). Each returns `DataQualityScore | None`, never a fabricated default.
- **Package layout:** new domain code lives at `backend/app/<domain>/` (matches `app/signals/`, `app/screening/`), *not* `backend/app/domain/<x>/` — that tree is a 9-package empty skeleton and stays untouched (its `__init__.py` files are 0 bytes; deleting them is out of scope for now).
- **Tables:** one new migration per phase, numbered `010` onward, `down_revision` = previous head. All UUID PKs, `ix_`/`uq_` names, explicit `ondelete`.
- **API:** one router per domain under `backend/app/api/`, mounted in `main.py`, paths `/api/<domain>/companies/{company_id}`, hand-serialized dicts with `str(...)` for Decimal and `.isoformat()` for dates.
- **Scores:** any persisted score/rating stores `methodology_version`; reads default to the current version and say so in the payload.

---

## Phase 1 — Data Quality Engine (detailed)

**Files:**

- Create: `backend/app/dataquality/__init__.py`, `backend/app/dataquality/scores.py`, `backend/app/dataquality/service.py`
- Create: `backend/app/models/data_quality.py`
- Create: `backend/alembic/versions/010_data_quality.py`
- Create: `backend/app/api/data_quality.py`
- Modify: `backend/app/models/__init__.py` (export new model + enum)
- Modify: `backend/app/main.py` (mount router)
- Modify: `backend/app/models/market.py` (`data_sources.last_synced_at`, `daily_prices.ingested_at`)
- Modify: `backend/app/ingestion/service.py` (stamp `last_synced_at`), `backend/app/ingestion/sync.py`
- Modify: `backend/app/ingestion/financial_service.py` (run normalization + validation, keep `document_url`, fix `_find_document`)
- Modify: `backend/app/metrics/period_selector.py` (make `as_of_date` real)
- Modify: `backend/app/api/screening.py:108`, `backend/app/metrics/service.py:386`, `backend/app/ai/document_indexer.py:69,111` (`or` → explicit `is not None` checks)
- Modify: `frontend/src/api/client.ts:154` (escaped `\${ticker}`), `frontend/src/components/Layout.tsx` (drop dead routes), `frontend/src/App.tsx`
- Create: `frontend/src/lib/quality.ts`, `frontend/src/lib/quality.test.ts`, `frontend/src/components/DataQualityCard.tsx`
- Modify: `frontend/src/pages/CompanyDetail.tsx`, `frontend/src/api/client.ts` (hook), `frontend/src/types/index.ts`
- Test: `backend/tests/test_data_quality_scores.py`, `backend/tests/test_data_quality_api.py`, `backend/tests/test_financial_ingestion.py`, extend `backend/tests/test_period_selector.py`

**Interfaces:**

- Consumes: `FinancialFact` / `FinancialPeriod` / `FinancialDocument` (app.models.financial), `DailyPrice` / `DataSource` (app.models.market), `FinancialFactValidator` (app.ingestion.validation), `normalize_fact` (app.ingestion.normalization), `CompanyRepository.get_by_id`.
- Produces (relied on by Phases 3–5):
  - `app.dataquality.scores.DataQualityStatus` — `StrEnum` of `OK | DEGRADED | POOR | MISSING`
  - `app.dataquality.scores.QualityComponent(key: str, label: str, score: float, weight: float, reason: str)`
  - `app.dataquality.scores.DataQualityScore(scope: str, as_of: date, status: DataQualityStatus, score: float, components: tuple[QualityComponent, ...], issues: tuple[str, ...], methodology_version: str)` with `.as_dict() -> dict`
  - `app.dataquality.service.DataQualityService(session)` with
    `async assess(company_id: str, scope: str, as_of: date | None = None) -> DataQualityScore`,
    `async latest(company_id: str, scope: str, methodology_version: str | None = None) -> DataQualityScore | None`
  - Route: `GET /api/data-quality/companies/{company_id}?scope=` → `{items: [...], methodology_version}`; `POST /api/data-quality/companies/{company_id}/assess?scope=&as_of=` → single assessment; 404 unknown company.

**Scoring constants (pinned so later phases can depend on them):**

- Scopes: `price_history`, `company_profile`, `financial_statements`.
- Weights: completeness 0.30, freshness 0.25, validation 0.20, historical_depth 0.15, source_reliability 0.10. `sum == 1.0`.
- Overall = `round(100 * Σ(weight × component), 1)`; components are 0–100 floats.
- Status: `MISSING` when no underlying rows; else `OK` ≥ 70, `DEGRADED` ≥ 40, `POOR` < 40.
- Freshness (days stale): 0→100, ≤30→90, ≤90→70, ≤180→50, ≤365→30, >365→10; unknown→0.
- Validation: `max(0.0, 100 - 20×errors - 5×warnings)`.
- Depth: `min(100, 100 × observed / expected)`; expected is 8 periods for annual financials, trading days ≈ calendar days × 5/7 for prices.
- Source reliability by `DataSourceType`: `EGX` 95, `FRA` 95, `COMPANY` 90, `DATA_PROVIDER` 75, `MANUAL` 60, `SYNTHETIC` 20. Unknown type → 40.
- `methodology_version = "1.0"`.

---

### Task 1: Pure quality scoring functions

**Files:**
- Create: `backend/app/dataquality/__init__.py` (empty), `backend/app/dataquality/scores.py`
- Test: `backend/tests/test_data_quality_scores.py`

**Interfaces:** Produces `DataQualityStatus`, `QualityComponent`, `DataQualityScore`, and the free functions `freshness_score(days_stale: int | None) -> float`, `validation_score(errors: int, warnings: int) -> float`, `depth_score(observed: int, expected: int) -> float`, `completeness_score(present: int, required: int) -> float`, `source_reliability(source_type: DataSourceType | str | None) -> float`, `aggregate(components: Sequence[QualityComponent]) -> float`, `score_for(scope, as_of, present, required, expected_depth, days_stale, errors, warnings, source_type, no_rows) -> DataQualityScore`.

- [ ] **Step 1: Write failing tests** covering: weights sum to exactly 1.0; `no_rows=True` → `MISSING` with `score == 0.0`; `SYNTHETIC` reliability ≤ 20 and `EGX` ≥ 90; freshness boundaries (0/30/31/365/366 days, `None`→0); validation penalty at 1 error and 5 warnings; completeness when 2 of 5 required labels missing; depth when `observed > expected` clamps at 100; `aggregate` rounds to 1 decimal; every component key present in `.as_dict()`; negative/zero inputs (`freshness_score(-1) == 0.0`, `depth_score(0,0) == 0.0`).
- [ ] **Step 2: Run and confirm failure** — `cd backend && .venv/bin/python -m pytest tests/test_data_quality_scores.py -q` → FAIL (module not found).
- [ ] **Step 3: Implement `scores.py`** as pure functions + frozen dataclasses, no imports outside stdlib, `app.models.market.DataSourceType`.
- [ ] **Step 4: Run tests, then full backend suite** — `pytest tests/test_data_quality_scores.py -q` → PASS; `pytest -q` → 266 + new pass.
- [ ] **Step 5: Lint** — `.venv/bin/python -m ruff check app/dataquality tests/test_data_quality_scores.py` → clean.
- [ ] **Step 6: Commit** `feat(dataquality): pure data-quality scoring functions`.

---

### Task 2: Look-ahead fix in period selection

**Files:**
- Modify: `backend/app/metrics/period_selector.py:29-63, 103`
- Test: extend `backend/tests/test_period_selector.py`

**Interfaces:** `select_comparable_periods(periods, target_period, as_of_date)` keeps its signature; behaviour becomes: when `as_of_date` is given, a period is usable only if at least one of its `documents` has `publication_date <= as_of_date`; periods with no documents are excluded from the *previous* period choice but never exclude `target_period` itself.

- [ ] **Step 1: Write failing tests** — `test_as_of_date_excludes_later_publications` (period published 2024-08-15, `as_of_date=2024-07-01` → that period is not selectable as `previous`), `test_as_of_date_includes_earlier_publications`, `test_period_without_documents_excluded_when_as_of_given`, `test_no_as_of_date_keeps_current_behaviour`.
- [ ] **Step 2: Run** those tests → FAIL (as_of_date ignored).
- [ ] **Step 3: Implement** by routing the candidate list through `filter_by_publication_date(periods, as_of_date)` at the top of `select_comparable_periods` when `as_of_date is not None`, and make `filter_by_publication_date` exclude document-less periods (drop the "conservative include" branch).
- [ ] **Step 4: Run** `pytest tests/test_period_selector.py tests/test_metrics_engine.py -q` → PASS.
- [ ] **Step 5: Commit** `fix(metrics): honour as_of_date in period selection`.

---

### Task 3: Persist screening status honestly (tri-state) + `or` fallback fixes

**Files:**
- Modify: `backend/app/screening/service.py:131-142`, `backend/app/api/screening.py:108`, `backend/app/metrics/service.py:386`, `backend/app/ai/document_indexer.py:69,111`
- Test: extend `backend/tests/test_screening.py`, `backend/tests/test_metrics_engine.py`

**Interfaces:** `ScreeningOutput.is_compliant` becomes `bool | None` (`None` = insufficient data). `POST /api/screening/...` persists `ShariahScreeningResult.status = ScreeningStatusDB.INSUFFICIENT_DATA` and `is_compliant = None` when any rule is `INSUFFICIENT_DATA` and none `FAIL`. Response keeps the same keys; `is_compliant` may be `null`.

- [ ] **Step 1: Write failing tests** — `test_screening_insufficient_status_persisted` (no FAIL, one INSUFFICIENT → `status == INSUFFICIENT_DATA`, `is_compliant is None`), `test_screening_any_fail_overrides_insufficient`, `test_zero_value_not_replaced` for the metrics `or` path (`Decimal("0")` survives), same for the fact fallback in `api/screening.py:108` and both `document_indexer.py` sites.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** — `_determine_compliance` returns `tuple[bool | None, str]`; repository maps `None → INSUFFICIENT_DATA` (`repositories/screening.py:33`); replace all four `x or y` fact fallbacks with `y if x is None else x`.
- [ ] **Step 4: Run** `pytest tests/test_screening.py tests/test_metrics_engine.py tests/test_ai.py -q` → PASS.
- [ ] **Step 5: Commit** `fix(screening): keep insufficient data visible, stop dropping zero values`.

---

### Task 4: Migration 010 + models

**Files:**
- Create: `backend/alembic/versions/010_data_quality.py`
- Create: `backend/app/models/data_quality.py`
- Modify: `backend/app/models/market.py` (add `last_synced_at DateTime(timezone=True) | None` on `DataSource`; `ingested_at DateTime(timezone=True) server_default=func.now()` on `DailyPrice`), `backend/app/models/__init__.py`

**Interfaces:** `DataQualityAssessment` → table `data_quality_assessments`: `id`, `company_id` FK `companies` CASCADE NOT NULL, `scope String(50) NOT NULL`, `as_of Date NOT NULL`, `score Numeric(5,2) NOT NULL`, `status Enum('data_quality_status') NOT NULL`, `components JSONB NOT NULL server_default '[]'`, `issues JSONB NOT NULL server_default '[]'`, `methodology_version String(20) NOT NULL`, `source_id UUID FK data_sources RESTRICT NULL`, `computed_at DateTime(timezone=True) NOT NULL`, `created_at`. Unique `(company_id, scope, as_of, methodology_version)` named `uq_data_quality_assessment`; index `ix_data_quality_assessment_company_scope` on `(company_id, scope, as_of DESC)`. Enum values: `OK, DEGRADED, POOR, MISSING`. Migration also: `ALTER TABLE data_sources ADD COLUMN last_synced_at TIMESTAMPTZ NULL`, `ALTER TABLE daily_prices ADD COLUMN ingested_at TIMESTAMPTZ NOT NULL server_default now()`, and the two indexes declared in `models/screening.py` but missing from migration 005 (`ix_shariah_screening_results_methodology_version`, `ix_screening_rule_results_rule_name`) via `CREATE INDEX IF NOT EXISTS`. JSONB `server_default` matches migration 009's style.

- [ ] **Step 1: Write failing test** — `tests/test_data_quality_api.py::test_model_roundtrip` (insert assessment, read back, unique conflict on duplicate `(company_id, scope, as_of, methodology_version)`).
- [ ] **Step 2: Run** → FAIL (table absent).
- [ ] **Step 3: Write the model + migration**, `down_revision = "009"`, downgrade drops table, enum, the three columns/indexes it added.
- [ ] **Step 4: Apply** — `cd backend && .venv/bin/python -m alembic upgrade head` → succeeds, `.venv/bin/python -m alembic downgrade -1 && upgrade head` → succeeds (round-trip proves downgrade works).
- [ ] **Step 5: Run test** → PASS.
- [ ] **Step 6: Commit** `feat(dataquality): data_quality_assessments table + provenance columns`.

---

### Task 5: Assessment service + API

**Files:**
- Create: `backend/app/dataquality/service.py`, `backend/app/api/data_quality.py`
- Modify: `backend/app/main.py`, `backend/app/api/screening.py` (add `data_quality` field to `GET /api/screening/companies/{id}`)
- Test: `backend/tests/test_data_quality_api.py`

**Interfaces:**

- `DataQualityService.assess(company_id, scope, as_of=None) -> DataQualityScore` — loads rows for scope, calls `score_for`, upserts on the unique key, returns the score. `price_history`: latest/oldest `DailyPrice`, bar count vs expected trading days, source reliability from the bars' `source_id`. `company_profile`: count of populated of `name/sector/industry/shares_outstanding/free_float` (required = 5), freshness = age of `updated_at`. `financial_statements`: `FinancialPeriod` count vs 8, latest `FinancialDocument.publication_date` freshness, `CRITICAL_FACT_LABELS = ("revenue", "net_income", "total_assets", "total_equity", "operating_cash_flow")` completeness, `FinancialFactValidator.validate_facts` errors/warnings for validation.
- `DataQualityService.latest(company_id, scope, methodology_version=None)` — newest assessment, defaulting to `"1.0"`, returns `None` when never assessed.
- Routes as declared in Interfaces above; assessment response includes `disclaimer`: `"Data quality describes the available inputs. It is not an assessment of the company."`
- Screening `GET` response gains `"data_quality": {…} | null` (scope `financial_statements`).

- [ ] **Step 1: Write failing API tests** — assess + GET round-trip for `price_history`; `GET` returns `[]` then `[{...}]` after assess; 404 unknown company (both routes); idempotent re-assess overwrites rather than duplicates; `data_quality` key present and `null` in screening GET before assessment (Review Focus #5); GET with `scope=` filter returns only that scope; stale-assessment second run with different `methodology_version` does not overwrite the 1.0 row.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement service and router**, mount `data_quality.router` in `main.py` after the other routers.
- [ ] **Step 4: Run** `pytest tests/test_data_quality_api.py -q` → PASS, then `pytest -q` → all green.
- [ ] **Step 5: Lint** — `ruff check app tests` → clean.
- [ ] **Step 6: Commit** `feat(dataquality): assessment service, API, screening propagation`.

---

### Task 6: Wire validation + normalization into financial ingestion

**Files:**
- Modify: `backend/app/ingestion/financial_service.py` (keep `document_url`, run `normalize_fact` then `FinancialFactValidator.validate`, set `status`/`normalized_*`, fix `_find_document` to filter `document_type`)
- Modify: `backend/app/ingestion/normalization.py` (add `NORMALIZATION_VERSION = "1.0"`)
- Test: create `backend/tests/test_financial_ingestion.py`

**Interfaces:** `FinancialDataIngestionService.ingest_financial_data(ticker, fiscal_year=None)` keeps its signature and return type; returned dict gains `normalized` and `invalid` counts. `document_url` written through from `FinancialDocumentData`. Fact rows land with `status=NORMALIZED` when a rule matched, `status=REPORTED` otherwise, and invalid facts get `status=INSUFFICIENT_DATA` plus `normalized_value=None` — never a fabricated value.

- [ ] **Step 1: Write failing tests** using `FakeFinancialDataProvider` (tests only, never production wiring): facts are persisted with `normalized_label` set for known labels; `document_url` preserved; `ingest` of a period with two document types does not raise `MultipleResultsFound`; a fact failing validation keeps its reported value but has `status=INSUFFICIENT_DATA`; returned counts match.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** in `financial_service.py`; keep the module unused by any production route (a real provider is Phase 7).
- [ ] **Step 4: Run** `pytest tests/test_financial_ingestion.py tests/test_financial_validation.py -q` → PASS.
- [ ] **Step 5: Commit** `feat(ingestion): run normalization and validation when loading financial facts`.

---

### Task 7: Sync stamps source freshness

**Files:**
- Modify: `backend/app/ingestion/service.py:76,107` (pass `base_url`/`description` into `get_or_create`), `backend/app/ingestion/sync.py`
- Test: extend `backend/tests/test_universe.py` or new `backend/tests/test_sync_provenance.py`

**Interfaces:** `MarketDataIngestionService.__init__` gains optional `source_url: str | None = None` (positional-compatible); after a successful price write, the service sets `DataSource.last_synced_at = now(UTC)`.

- [ ] **Step 1: Write failing test** — ingesting prices through the service with `FakeMarketDataProvider` (tests only) creates a `data_sources` row with `base_url` populated and `last_synced_at` not null afterwards.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** — stamp in `ingest_prices` after `write_prices`, pass source URL from `sync.py` (Yahoo base URL constant alongside `PRICE_SOURCE_NAME`).
- [ ] **Step 4: Run** → PASS; full `pytest -q`.
- [ ] **Step 5: Commit** `feat(ingestion): record source base_url and last_synced_at`.

---

### Task 8: Frontend — data quality card + navigation fixes

**Files:**
- Create: `frontend/src/lib/quality.ts`, `frontend/src/lib/quality.test.ts`, `frontend/src/components/DataQualityCard.tsx`
- Modify: `frontend/src/api/client.ts` (add `useDataQuality(companyId, scope?)`; fix line 154 `` `/signals/\${ticker}` `` → `` `/signals/${ticker}` ``), `frontend/src/types/index.ts`, `frontend/src/pages/CompanyDetail.tsx`, `frontend/src/components/Layout.tsx` (remove `/watchlist`, `/research`, `/alerts` entries — they have no routes and render blank; they return in Phases 8/10), `frontend/src/index.css` (styles for `.quality-card`, `.quality-bar`, reusing `--green/--yellow/--red`)

**Interfaces:** `GET /api/data-quality/companies/{id}` returns `{items, methodology_version}`. `quality.ts` exports `qualityTone(status: "OK"|"DEGRADED"|"POOR"|"MISSING"): "positive"|"warning"|"negative"|"muted"` and `qualityLabel(status): string` — the only place the card maps status to colour/word.

- [ ] **Step 1: Write failing vitest test** `frontend/src/lib/quality.test.ts` — all four statuses map to the expected tone and label; unknown status falls back to `muted`/`Unknown`. (This is the frontend suite's first test file, so `npm test` goes from "no test files found" to passing.)
- [ ] **Step 2: Run** `cd frontend && npm test` → FAIL (module missing).
- [ ] **Step 3: Implement** `quality.ts`, the `useDataQuality` hook, `DataQualityCard` (score, status badge, component bars with weights, issues list, disclaimer), mount it in `CompanyDetail`.
- [ ] **Step 4: Fix `client.ts:154`** and the nav; run `npm test && npm run lint && npm run build` → all clean.
- [ ] **Step 5: Commit** `feat(frontend): data-quality card, fix signal hook path, drop unroutable nav links`.

---

### Task 9: Phase verification and report

- [ ] **Step 1:** `docker compose up -d postgres`, then `cd backend && .venv/bin/python -m alembic upgrade head`, `pytest -q`, `ruff check app tests`.
- [ ] **Step 2:** `cd frontend && npm run build && npm run lint && npm test`.
- [ ] **Step 3:** Manual smoke — start backend + frontend, open `/companies/COMI`, confirm the data-quality card renders a real score (or an honest `MISSING`), confirm `/rankings` still works, confirm sidebar has no dead links.
- [ ] **Step 4:** Update `PHASES.md` and write `docs/phases/phase-1-data-quality.md` with: files changed, features, tests added, tests passed, remaining limitations, next phase.
- [ ] **Step 5: Commit** `docs: phase 1 data quality report`.

---

## Known limitations carried out of Phase 1

- No real financial-statement provider exists; `financial_statements` quality will legitimately report `MISSING` until Phase 7. `financial_service.py` stays unwired to any route/CLI on purpose.
- `FakeMarketDataProvider` / `FakeFinancialDataProvider` remain ungated by config — they are unreachable by wiring only. Adding a `Settings` gate belongs in Phase 12 production hardening.
- `app/domain/*` empty package skeleton left in place.
- Pre-existing: 48 mypy errors in 24 files, fresh-DB Alembic reproducibility (`DuplicateObjectError: type "screening_status"`), universe source is StockAnalysis rather than an official EGX feed, 30 of 229 tickers have no price data.
- Not verified at plan time: nothing was executed — Docker/Postgres was down, so no test run and no DB inspection happened in this session.
