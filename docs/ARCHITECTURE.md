# EGX AI — Architecture

How the system is put together, where each piece lives, and how data flows from an
external source to something you see on screen.

---

## 1. System overview

```
┌─────────────────────────────┐        ┌──────────────────────────────────┐
│  Frontend (React 19 + TS)   │  HTTP  │  Backend (FastAPI + SQLAlchemy)   │
│  Vite dev server :5173      │ ─────► │  Uvicorn :8000                    │
│  TanStack Query for fetch   │        │  app/api/*.py routers             │
└─────────────────────────────┘        └───────────────┬──────────────────┘
                                                        │ async SQL
                                       ┌────────────────▼──────────────────┐
                                       │  PostgreSQL 16 + pgvector :5432   │
                                       │  (docker compose service)         │
                                       └────────────────▲──────────────────┘
                                                        │ writes
                                       ┌────────────────┴──────────────────┐
                                       │  Ingestion CLI (manual)           │
                                       │  python -m app.ingestion.sync     │
                                       └───────────────────────────────────┘
```

Three processes matter:

1. **Backend** — FastAPI app serving `/api/*` JSON, reading/writing PostgreSQL.
2. **Frontend** — React SPA that calls `/api/*` through Vite's dev proxy.
3. **Ingestion** — a **command-line job** that pulls market data and writes it to the DB. It is **not** a background service. Nothing runs it on a schedule.

There is also an optional **AI provider** (Ollama or OpenAI-compatible) used only by
the RAG/analysis endpoints.

---

## 2. Backend layering

Every feature follows the same layers. Reading top-to-bottom:

| Layer | Folder | Responsibility |
|---|---|---|
| **API / routing** | `backend/app/api/` | HTTP: parse params, check existence, call a service or repository, shape the JSON response |
| **Service / domain** | `backend/app/{metrics,screening,valuation,technical,signals,dataquality,services}/` | Deterministic business logic (formulas, rules, scores) |
| **Repositories** | `backend/app/repositories/` | All database queries (SQLAlchemy `select`, upserts) |
| **Models** | `backend/app/models/` | SQLAlchemy table definitions |
| **Schemas** | `backend/app/schemas/` | Pydantic request/response validation |
| **DB session** | `backend/app/db/` | Engine, session factory, `get_session()` dependency |
| **Config** | `backend/app/core/config.py` | Settings loaded from env / `.env` |

### The session pattern

`app/api/*.py` routes take `session: AsyncSession = Depends(get_session)`. The
dependency (`backend/app/db/session.py`) opens a session, **commits on success, and
rolls back on exception**. Routers don't need to manage transactions (the few
routes that commit explicitly do so mid-request).

### Where to look for a feature

- Form-looking API? → `backend/app/api/<name>.py`
- Wrong number? → the service that computes it (`app/<domain>/service.py` or `engine.py`)
- Data not saved? → `backend/app/repositories/<name>.py`
- Table/column missing? → `backend/app/models/<name>.py` + a migration

---

## 3. Data model (tables)

11 Alembic migrations under `backend/alembic/versions/`. The tables:

| Table | Migration | Holds |
|---|---|---|
| `companies` | 002 | EGX listed companies (ticker, ISIN, sector, industry, status) |
| `data_sources` | 002 | Provenance of data (Yahoo, EGX, synthetic) with `base_url`, `last_synced_at` |
| `daily_prices` | 002 | OHLCV bars per company per day, with `ingested_at` |
| `financial_periods` | 003 | Reporting periods (annual/quarterly) |
| `financial_documents` | 003 | Source documents (annual report, etc.) with `publication_date` |
| `financial_facts` | 003 | Individual line items; `reported_*` and `normalized_*`, `status` |
| `financial_metrics` | 004 | Computed ratios with formula version + provenance |
| `shariah_screening_results` / `screening_rule_results` | 005, 010 | Screening verdicts (tri-state `is_compliant`) |
| `valuation_results` | 006 | DCF / multiple valuations |
| `technical_indicators` | 007 | SMA/RSI/etc. |
| `documents` / `document_chunks` | 008 | RAG corpus + embeddings (pgvector) |
| `market_signals` | 009 | Ranked opportunity scores per company |
| `data_quality_assessments` | 011 | Data-quality score per company/scope/as_of |

**Provenance is a first-class rule**: `data_sources` + FK columns (`source_id`,
`document_id`) let any number be traced back to where it came from.

---

## 4. How data gets into the system (the ingestion pipeline)

This is the part that explains "why is my data old".

```
Yahoo Finance / EGX
        │  (network fetch)
        ▼
app/ingestion/egx/provider.py      EGXMarketDataProvider  (implements the protocol)
        │
        ▼
app/ingestion/service.py           MarketDataIngestionService
        │  writes via repositories + stamps source provenance
        ▼
PostgreSQL (daily_prices, data_sources.last_synced_at)
```

The entry point is a **CLI**, not a server:

```bash
cd backend
python -m app.ingestion.sync                 # universe + prices for everything
python -m app.ingestion.sync --tickers COMI,SWDY
python -m app.ingestion.sync --coverage      # report only, no writes
python -m app.ingestion.sync --universe-only # refresh the company list
```

- `app/ingestion/sync.py` — orchestration + CLI argument parsing.
- `app/ingestion/service.py` — the write logic (`write_prices` stamps `data_sources`).
- `app/ingestion/egx/provider.py` — the real Yahoo-backed provider.
- `app/ingestion/provider.py` — the `MarketDataProvider` **protocol** (interface).
- `app/ingestion/fake_provider.py` — synthetic provider (tests/dev only).
- `app/ingestion/financial_service.py` + `normalization.py` + `validation.py` — the
  financial-statement path (normalize labels, validate facts). **Not wired to any
  route or scheduled job yet** — real fundamentals arrive in Phase 7.

### Why the app shows old data

- The ingestion job is **manual**. There is no scheduler, cron, or startup hook
  anywhere in `backend/app` (grep for `schedule|APScheduler|cron|lifespan` → nothing).
- Data is only as fresh as the last time someone ran `python -m app.ingestion.sync`.
- The frontend does not trigger ingestion — it only reads `/api/*`.

**To refresh:** run the sync CLI (above). To make it automatic you must add a
scheduler (e.g. APScheduler in `create_app`, a cron entry, or a `/api/admin/sync`
endpoint). That has not been built.

---

## 5. Domain modules (the deterministic engines)

Each of these is pure code — no LLM — per `AGENTS.md`.

| Module | Files | What it does |
|---|---|---|
| **metrics** | `metrics/{definitions,engine,period_selector,service}.py` | 17 financial ratios; `period_selector` enforces no-look-ahead via `publication_date <= as_of` |
| **screening** | `screening/{methodology,rules,service}.py` | Versioned Shariah screening; three-valued result (yes / no / insufficient) |
| **valuation** | `valuation/{models,service}.py` | P/E, P/B, EV/EBITDA, DCF |
| **technical** | `technical/{indicators,service}.py` | SMA, EMA, RSI, MACD, Bollinger |
| **signals** | `signals/{engine,factors,scoring}.py` | Cross-sectional ranking of the whole universe → `market_signals` |
| **dataquality** | `dataquality/{scores,service}.py` | Scores how complete/fresh each company's data is (scopes: price_history, company_profile, financial_statements) |
| **financial ingestion** | `ingestion/{financial_service,normalization,validation}.py` | Normalize reported labels → canonical, validate facts |
| **ai** | `ai/{analyzer,document_indexer,rag_pipeline}.py` | RAG over documents + analyzed summaries (the only LLM layer) |

### Data-quality scoring (important, newly added)

`app/dataquality/service.py` runs `assess(company_id, scope, as_of)` and persists a
row in `data_quality_assessments`. It is **only computed when someone calls the
`POST /api/data-quality/companies/{id}/assess` endpoint** (or the test suite).
The `GET` endpoint returns whatever rows exist — so an empty card means **no
assessment has ever been run for that company**. The frontend renders that as
"No data-quality assessment has been run for this company yet."

Why it's empty in the current DB: `data_quality_assessments` has 0 rows, because no
one has called the assess endpoint. It is not a bug in the card.

---

## 6. API surface

All routers are registered in `backend/app/main.py` under `/api`:

| Router | Prefix | Purpose |
|---|---|---|
| `health` | `/api/health` | Liveness + version |
| `companies` | `/api/companies` | Company list/detail, prices |
| `financial` | `/api/financial` | Periods, documents, facts |
| `metrics` | `/api/metrics` | Compute/read ratios |
| `screening` | `/api/screening` | Shariah verdicts (embeds data quality) |
| `valuation` | `/api/valuation` | Valuation models |
| `technical` | `/api/technical` | Indicators |
| `signals` | `/api/signals` | Ranked opportunities, coverage |
| `data_quality` | `/api/data-quality` | Assessments |
| `data_sources` | `/api/data-sources` | Provenance registry |
| `ai` | `/api/ai` | RAG/analysis |

Interactive docs: **http://localhost:8000/docs** (FastAPI auto-generated).

---

## 7. Frontend

```
frontend/src/
├── main.tsx           entry, mounts <App/>
├── App.tsx            routes
├── api/client.ts      every backend call as a TanStack Query hook (useCompanies, useDataQuality, …)
├── types/index.ts     TypeScript types mirroring the API
├── components/        Layout (nav), DataQualityCard
├── lib/               pure helpers (e.g. quality.ts: status → tone/label)
└── pages/             one file per screen (Companies, CompanyDetail, Rankings, …)
```

Pattern: a page calls a hook from `api/client.ts`; the hook fetches and caches via
TanStack Query. `fetchApi<T>` throws on non-2xx. Dev calls go to `/api/...` and Vite
proxies them to the backend.

Tests: vitest (`npm test`), lint `npm run lint`, build `npm run build`.

---

## 8. Running it locally

```bash
docker compose up -d postgres          # 1. database
cd backend && .venv/bin/alembic upgrade head   # 2. schema
python -m app.ingestion.sync           # 3. pull data (manual!)
.venv/bin/uvicorn app.main:app --reload --port 8000   # 4. backend
cd ../frontend && npm run dev          # 5. frontend → http://localhost:5173
```

Or `make dev`, `make migrate`, `make test`, `make lint` (see `Makefile`).

---

## 9. Guiding rules (why the code looks the way it does)

From `AGENTS.md`:

- **Deterministic financial math** — formulas are code, never LLM output.
- **No fabricated data** — missing values are `None` / `INSUFFICIENT_DATA`, never `0`.
- **Everything is sourced** — provenance FKs on every fact.
- **No look-ahead bias** — analysis filtered by `publication_date <= as_of`.
- **Shariah methodology is versioned** — thresholds stored with a version, not hard-coded.
- **No trading execution** — research tool only.

---

## 10. Known gaps (honest list)

- **Ingestion is manual** — no scheduler; data goes stale until the CLI is run.
- **No real financial-statement provider** — `financial_statements` quality will
  report `MISSING` until Phase 7; `financial_service.py` is intentionally unwired.
- **Data-quality assessments are not auto-generated** — nothing calls `assess` yet.
- **`frontend` has no component tests** — vitest runs in `node` env (jsdom not installed).
- **`app/domain/*`** is an empty package skeleton.
- **30 of 229 tickers** have no price data.

---

*Generated from the code on branch `phase-1-data-quality`. If something here
disagrees with the code, the code wins — update this file.*
