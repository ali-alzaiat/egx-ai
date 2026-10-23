# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

EGX AI is a single-user research tool for Egyptian Exchange stocks: market data, financial statements, metrics, Shariah screening, valuation, technical signals, theses and alerts. **Read [AGENTS.md](AGENTS.md) first** — its rules (deterministic formulas in code, never fabricate data, `INSUFFICIENT_DATA` instead of zero, no look-ahead bias, versioned methodology, no trade execution, strict typing) are binding and are checked by QA.

## Commands

The dev machine is Windows; the Makefile's non-`-windows` targets use bash `source` and won't work in PowerShell. Use the venv's Python directly.

```bash
docker compose up -d postgres                      # Postgres 16 + pgvector on :5432 (required for backend tests too)

# Backend (run from backend/)
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m alembic upgrade head
.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
.venv/Scripts/python -m pytest                                  # all tests
.venv/Scripts/python -m pytest tests/test_billing.py::test_name # single test
.venv/Scripts/python -m ruff check .
.venv/Scripts/python -m mypy app                                # strict; must be clean

# Frontend (run from frontend/)
npm run dev        # Vite on :5173, proxies /api -> localhost:8000
npm test           # vitest run (node environment, no jsdom)
npx vitest run src/pages/companies/radarSort.test.ts            # single file
npm run lint
npm run build      # tsc -b && vite build — the type check

# Data
.venv/Scripts/python -m app.ingestion.sync --universe-only   # refresh EGX company list
.venv/Scripts/python -m app.ingestion.sync --tickers COMI,SWDY
.venv/Scripts/python -m app.db.purge --status                # inspect / clean dev DB (see module docstring)
```

- Set `API_TOKEN` in the repo-root `.env` (read by the backend, docker compose and the Vite dev proxy, which attaches it server-side so it never reaches the browser bundle). `/docs` needs `API_DOCS_ENABLED=true`.
- Backend tests hit the real `DATABASE_URL` database. Use the `client` fixture (authenticated) or `anon_client` (no token). `tests/conftest.py` wraps each test in an outer transaction that is rolled back, so services may call `session.commit()` freely. Stop `uvicorn`/`vite dev` before running gates — they share the dev DB and cause lock contention.
- A task is only "green" with zero errors **and zero warnings** across pytest, ruff, mypy, tsc, eslint, build and vitest.
- The README's `python -m app.seed.seed` and `make seed` are stale — `app/seed/` is empty.

## Architecture

### Backend (`backend/app`)

FastAPI app built in `main.py`; each domain has its own router in `api/` mounted under `/api/<domain>`. The layering is consistent across domains:

- `api/<domain>.py` — thin routers: parse input, call a service, map `LookupError`→404 / `ValueError`→422.
- `<domain>/service.py` — I/O, input resolution, persistence. `<domain>/` also holds **pure** modules (e.g. `valuation/fairvalue.py`, `thesis/thesis.py`, `signals/factors.py`, `metrics/engine.py`) with no DB, clock or I/O — financial math lives there and is what unit tests target.
- `<domain>/constants.py` — thresholds, weights and a `*_METHODOLOGY_VERSION` string. Changing any threshold requires bumping the version; results persist the version they were computed with.
- `repositories/` — SQLAlchemy 2.x async data access; `models/` — ORM tables; `schemas/` — Pydantic I/O.
- `db/session.py` — async engine (`NullPool`) and the `get_session` dependency, which commits on success.
- `domain/` is mostly empty scaffolding; real logic is in the top-level domain packages.

Data flow, upstream to downstream:

1. **Market data** — `ingestion/egx/universe.py` discovers the EGX company list; `ingestion/egx/provider.py` pulls prices from Yahoo Finance. `ingestion/jobs.py` runs universe → prices → assessment as a single in-memory job (one at a time, triggered by `POST /api/ingestion/sync`).
2. **Fundamentals** — two real-data paths, both provenance-tracked:
   - `statements/`: fetched filing blob → `extractor.py` (XBRL first, then HTML/text) → `ontology.py`/`aliases.py` label resolution (unknown or ambiguous labels are *dropped*, never guessed) → `validator.py` → candidate lines that need **human approval** via `/api/statements/lines/{id}/approve` before `StatementService` uses them. `fetch_service.py` honours robots.txt and throttles; it is not exposed via the API.
   - `ingestion/disclosures/`: manual URL registration or PDF upload (sha256-deduped) → `parse.py` (pdfplumber, optional Camelot) → facts with page/table/row/col provenance; restatements supersede earlier facts and write to an append-only diff ledger.
   - Legacy `ingestion/fake_*_provider.py` emit `SYNTHETIC`-labelled data; don't mix it with real data in new work.
3. **Derived engines** consume stored facts and prices: `metrics/`, `statements/ratios.py`, `screening/` (Shariah, methodology in `screening/methodology.py`), `valuation/`, `technical/`, `scores/`, `dataquality/`, `industry/` (peer percentiles), `signals/` (cross-sectional universe ranking + `stance.py` rule engine).
4. **Continuous monitoring** — `continuous/trigger_service.py` is the single entry point when facts land or prices cross; it evaluates alert rules and thesis invalidations and writes to the events ledger (`/api/events`). Thesis changes are *proposals* gated on human review.
5. **AI** (`ai/`) — RAG over indexed company data (`document_indexer.py`, pgvector in `rag_pipeline.py`). The analyzer is currently deterministic/template-based; LLMs may only interpret supplied data.
6. **Auth** (`core/security.py`) — a single shared bearer token (`API_TOKEN`, 32+ chars) protects every router except health; unset fails closed (503). New routers must be mounted in `main.py` with `dependencies=protected`. There are no user accounts: watchlists/alerts use a hard-coded user UUID. Billing was removed (migration 021 drops its tables).

Migrations are in `alembic/versions/` and are numbered sequentially; some have dedicated migration tests (`tests/test_migration_*.py`).

### Frontend (`frontend/src`)

React 19 + Vite SPA with react-router (`App.tsx`). Company-scoped pages live under `/companies/:ticker/<tab>` and share `components/CompanyTabs.tsx`. **All server access goes through TanStack Query hooks in `api/client.ts`**, typed by `types/index.ts` — add new endpoints there rather than calling `fetch` in pages. i18n (English/Arabic, RTL) is in `i18n/`. Follow the vercel-react-best-practices rules noted in AGENTS.md.

## Project workflow

- `PHASES.md` tracks phase status (with reliability warnings about synthetic data); per-phase specs are in `docs/phases/`.
- Multi-agent process: agent definitions in `.opencode/agents/`, coordination files in `.workflow/` (`CONTRACT.md` defines the pipeline and the NEXT/BLOCKED/ASK USER/DONE result contract, `STATUS.md` is the board, `handoffs.log` is append-only). The architect's API contract in `.workflow/design/` is the source of truth both backend and frontend build against, and every backend change must ship with its UI surface in the same phase.
