# EGX AI — Stock Analysis & Shariah Screening Platform

AI-powered research tool for Egyptian Exchange (EGX) companies.

## Features

- EGX market data ingestion
- Company financial statements & ratios
- Shariah screening (deterministic, configurable)
- Valuation models (P/E, P/B, EV/EBITDA, DCF)
- Technical analysis
- AI-powered document analysis (RAG)
- Investment thesis monitoring
- Historical backtesting
- Configurable alerts

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.x, PostgreSQL, pgvector
- **Frontend:** React 19, TypeScript, Vite, TanStack Query
- **AI:** OpenAI-compatible / Ollama abstraction
- **Infrastructure:** Docker, Alembic

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Node.js 22+

### 1. Clone & configure

```bash
cp .env.example .env
# Edit .env with your settings
```

### 2. Start services

```bash
docker compose up -d postgres
```

### 3. Backend

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Seed development data (synthetic)
python -m app.seed.seed

# Start dev server
uvicorn app.main:app --reload --port 8000
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173
Backend API: http://localhost:8000
API docs: http://localhost:8000/docs

## Development Commands

```bash
make dev          # Start all services
make test         # Run all tests
make lint         # Lint all code
make format       # Format all code
make migrate      # Run database migrations
make seed         # Seed development data
```

## Phase 2 — Companies + Market Prices

### Database Tables

- **companies** — EGX-listed companies with ticker, ISIN, sector, industry, status
- **daily_prices** — Historical OHLC prices with volume and provenance
- **data_sources** — Tracks where data came from (EGX, SYNTHETIC, etc.)

### API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/companies` | List companies (paginated, filterable) |
| `GET /api/companies/{id}` | Get company by ID |
| `GET /api/companies/ticker/{ticker}` | Get company by ticker |
| `GET /api/companies/{id}/prices` | Get historical prices |
| `GET /api/companies/{id}/prices/latest` | Get latest price |

### Ingestion Architecture

The ingestion layer uses a `MarketDataProvider` protocol. Current providers:

- **FakeMarketDataProvider** — Synthetic data for development (clearly labeled `SYNTHETIC`)

To add a real EGX provider, implement `MarketDataProvider` and register it in the ingestion service.

### Development Data

Run `python -m app.seed.seed` to populate the database with 10 synthetic EGX companies and historical price data. All synthetic data is labeled with `source_type = SYNTHETIC`.

## Phase 3 — Financial Statements & Normalized Financial Data

### Database Tables

- **financial_periods** — Reporting periods (annual, quarterly) for each company
- **financial_documents** — Source documents (annual reports, quarterly reports) with provenance
- **financial_facts** — Individual financial data points with full traceability

### Key Enums

- **ReportingPeriodType**: ANNUAL, Q1, Q2, Q3, Q4, SEMI_ANNUAL, INTERIM
- **FactType**: INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW, SHAREHOLDERS_EQUITY, NOTES
- **DocumentStatus**: ORIGINAL, RESTATED, AMENDED, ADJUSTED
- **FactStatus**: REPORTED, NORMALIZED, CALCULATED, INSUFFICIENT_DATA

### API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/financial/periods/{company_id}` | List financial periods for a company |
| `GET /api/financial/documents/{period_id}` | List documents for a period |
| `GET /api/financial/facts/{company_id}` | List financial facts (filterable by type, year, status) |
| `GET /api/financial/facts/{company_id}/latest` | Get latest year's financial facts |

### Normalization & Validation

The ingestion layer includes deterministic normalization and validation:

- **NormalizationService** — Maps reported labels to standardized labels (e.g., "Total Revenue" → "revenue")
- **FinancialFactValidator** — Validates data quality with ERROR/WARNING distinction
  - Errors: Missing required fields, invalid currency
  - Warnings: Missing values, negative revenue, extremely large values

### Financial Data Provider

The `FinancialDataProvider` protocol is separate from `MarketDataProvider`:

- **FakeFinancialDataProvider** — Generates synthetic financial statements for 10 EGX companies
  - 5 years of annual periods per company
  - Income statement, balance sheet, and cash flow data
  - Deterministic variation based on ticker and year

### Development Data

Run `python -m app.seed.seed` to populate:
- 10 synthetic EGX companies
- 4,530+ price records
- 50 financial periods
- 50 financial documents
- 850 financial facts

## Project Structure

```
egx-ai/
├── backend/          # FastAPI backend
│   ├── app/          # Application code
│   │   ├── api/      # API routes
│   │   ├── core/     # Config, logging
│   │   ├── db/       # Database setup
│   │   ├── ingestion/# Data ingestion abstraction
│   │   ├── models/   # SQLAlchemy models
│   │   ├── repositories/ # Data access
│   │   ├── schemas/  # Pydantic schemas
│   │   └── seed/     # Development seeding
│   ├── tests/        # pytest tests
│   └── alembic/      # Database migrations
├── frontend/         # React frontend
│   └── src/          # TypeScript source
├── docs/             # Documentation
├── scripts/          # Utility scripts
└── docker-compose.yml
```

## Important Rules

See [AGENTS.md](./AGENTS.md) for the full list of development rules.

Key rules:
- Financial calculations are deterministic (code, not LLM)
- No fabricated data
- Source attribution for all financial numbers
- No look-ahead bias in backtesting
- Shariah methodology is versioned and configurable

## License

Private — Personal use only.
