.PHONY: dev test lint format migrate seed docker-up docker-down clean

# Development
dev:
	docker compose up -d postgres
	cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000 &
	cd frontend && npm run dev

# Testing
test:
	cd backend && source .venv/bin/activate && pytest
	cd frontend && npm test

test-backend:
	cd backend && source .venv/bin/activate && pytest

test-frontend:
	cd frontend && npm test

# Linting
lint:
	cd backend && source .venv/bin/activate && ruff check .
	cd frontend && npm run lint

format:
	cd backend && source .venv/bin/activate && ruff format .
	cd frontend && npx prettier --write "src/**/*.{ts,tsx,css}"

# Database
migrate:
	cd backend && source .venv/bin/activate && alembic upgrade head

migrate-new:
	cd backend && source .venv/bin/activate && alembic revision --autogenerate -m "$(name)"

# Docker
docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-restart:
	docker compose down && docker compose up -d

# Setup
setup:
	cd backend && python3.12 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
	cd frontend && npm install

# Clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/.venv frontend/node_modules
