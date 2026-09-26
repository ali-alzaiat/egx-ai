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

## Project Structure

```
egx-ai/
├── backend/          # FastAPI backend
│   ├── app/          # Application code
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
