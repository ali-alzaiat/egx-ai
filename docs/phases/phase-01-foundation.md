# Phase 1 — Foundation

## Objective
Set up the project repository, development environment, and core architecture.

## Scope
- Python 3.12 backend with FastAPI
- React 19 frontend with TypeScript and Vite
- PostgreSQL database with pgvector
- Docker Compose for local development
- Alembic for database migrations
- Basic health check endpoint

## Dependencies
None — this is the first phase.

## Requirements
1. Backend project structure following modular monolith pattern
2. Frontend project with TypeScript, ESLint, Vite
3. Docker Compose with PostgreSQL + pgvector
4. Alembic migration setup
5. Health check endpoint (`/api/health`)
6. Basic test setup (pytest for backend)
7. Environment configuration (.env.example)
8. Makefile for common commands

## Acceptance Criteria
- `docker compose up -d postgres` starts a working database
- `alembic upgrade head` runs without errors
- Backend starts and responds to health check
- Frontend starts and renders
- Basic test suite passes

## Required Tests
- Health endpoint returns 200
- Database connection works
- Frontend builds without errors

## Required Verification
```bash
pytest
docker compose config
alembic upgrade head
npm run build
```

## Explicitly Forbidden Features
- No business logic
- No data models beyond basic setup
- No authentication
- No external API integration

## Expected Deliverables
- `backend/` directory with FastAPI app
- `frontend/` directory with React app
- `docker-compose.yml` with PostgreSQL
- `Makefile` with dev commands
- `.env.example` with required variables
- `AGENTS.md` with project rules
