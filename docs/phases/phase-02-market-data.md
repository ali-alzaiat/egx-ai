# Phase 2 — Companies & Market Prices

## Objective
Implement company data models, market data ingestion, and basic API endpoints.

## Scope
- Company data model (EGX-listed companies)
- Daily price data (OHLCV)
- Market data provider abstraction
- Fake provider for development
- Company and price API endpoints
- Basic frontend pages (dashboard, company list, company detail)

## Dependencies
Phase 1 — Foundation must be complete.

## Requirements
1. Company model: ticker, ISIN, name, sector, industry, status
2. DailyPrice model: date, OHLC, volume, value, trades
3. DataSource model: tracks data provenance
4. MarketDataProvider protocol for ingestion
5. FakeMarketDataProvider for development (labeled SYNTHETIC)
6. Company repository with CRUD operations
7. Price repository with date-range queries
8. API endpoints: companies list, company by ID, company by ticker, prices, latest price
9. Frontend: dashboard, companies list, company detail pages
10. Seed script for development data

## Acceptance Criteria
- 10 synthetic companies seeded
- 4,500+ price records seeded
- All API endpoints return correct data
- Frontend displays companies and prices
- All synthetic data labeled `source_type = SYNTHETIC`

## Required Tests
- Company API returns paginated results
- Price API returns date-range filtered results
- Latest price returns most recent record
- Fake provider returns deterministic data

## Required Verification
```bash
pytest
ruff check
npm run build
python -m app.seed.seed
curl http://localhost:8000/api/companies
```

## Explicitly Forbidden Features
- No real EGX API integration yet
- No financial statements
- No authentication
- No trading functionality

## Expected Deliverables
- `backend/app/models/market.py` — Company, DailyPrice, DataSource
- `backend/app/repositories/company.py`
- `backend/app/repositories/price.py`
- `backend/app/api/companies.py`
- `backend/app/ingestion/market_provider.py`
- `backend/app/ingestion/fake_market_provider.py`
- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/pages/Companies.tsx`
- `frontend/src/pages/CompanyDetail.tsx`
- Migration 002_companies_market_prices.py
