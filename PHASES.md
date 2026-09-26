# Project Phases

## Phase 1 — Foundation
Status: COMPLETE

## Phase 2 — Companies & Market Prices
Status: COMPLETE

## Phase 3 — Financial Statements & Normalized Facts
Status: COMPLETE

## Phase 4 — Financial Metrics & Ratios
Status: COMPLETE

## Phase 5 — Shariah Screening
Status: COMPLETE

## Phase 6 — Valuation
Status: COMPLETE

## Phase 7 — Technical Analysis
Status: COMPLETE

## Phase 8 — AI Analyst & RAG
Status: COMPLETE

## Phase 9 — Opportunity Detection
Status: COMPLETE
The full EGX universe (229 equities) is ranked using the versioned
cross‑sectional momentum / risk model. Scores, tiers and coverage are
persisted and exposed via the `/api/signals` surface. Coverage is
explicitly disclosed (199/229 have price data).

## Phase 10 — Backtesting
Status: IN_PROGRESS
Historical backtesting will require a price-history store; the current
priceprovider (Yahoo) supplies daily closes but a structured OHLCV
archive is needed for rolling-window strategies.

## Phase 11 — Alerts & Monitoring
Status: PENDING
Watchlist subscriptions and threshold alerts can be built on top of the
persisted `MarketSignal` rows and `SignalRun` history.

## Phase 12 — Production Hardening
Status: PENDING
Production hardening includes rate‑limits, request signing, read‑only
mode for the API, and a formal migration plan for the `model_version`
field so that versioned scores remain comparable across deploys.

## Phase 11 — Alerts & Monitoring
Status: NOT_STARTED

## Phase 12 — Production Hardening
Status: NOT_STARTED
