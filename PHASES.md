# Project Phases

<!-- ──────────────────────────────────────────────────────────────────────────
     RELIABILITY AUDIT — 2026-10-11
     All outputs are currently computed on SYNTHETIC data (FakeFinancialDataProvider).
     Phase 13 (real data ingestion) is the highest-leverage unblocked work.
     Do not act on any recommendation until Phase 13 + Phase 14 are COMPLETE.
────────────────────────────────────────────────────────────────────────── -->

## Roadmap — prioritized 2026-10-23 (competitive review vs ZBorsa)

Ordered by user impact and value. ZBorsa (zborsa.app) sells technical-only
BUY/SELL/HOLD calls with entry/target/stop to small retail investors (99/199 EGP
per month); it has no Shariah screening, no sourced fundamentals and no published
track record. We win on trust: Shariah, real filings, an honest backtest. The
phase sections below remain the detailed specs; this list sets the order.

1. **Recommendations v2 (signal-rules-2.0)** — Status: IN_PROGRESS.
   v1 scored missing engines as 0, so every stock without fundamentals was
   `reduce` and BUY was unreachable (R41). v2: weighted average over available
   engines only, multi-indicator technical composite (trend, RSI, MACD,
   momentum), ATR reference levels (entry / upside / downside), liquidity flag
   (< EGP 500K/day, Phase 14 rule), missing data lowers confidence instead of
   biasing the stance. Shariah leaves the score and becomes its own block.
2. **Shariah coverage** — Status: IN_PROGRESS.
   Load official EGX33 Shariah Index membership (egx.com.eg constituents page),
   show a Shariah badge + filter on the radar and stance views, side by side
   with our own AAOIFI verdict (never overriding it). Our own verdicts follow
   once item 3 lands real balance-sheet data.
3. **Real financial data for the most-traded companies** — Phase 13.
   Unlocks our own Shariah verdicts, valuation and scores (all synthetic or
   empty today). Start with the EGX33 Shariah members + EGX30.
   Data-first gate (CONTRACT.md): no other work that consumes fundamentals
   starts until `python -m app.dataquality.real_data --min-companies 5` passes.
4. **Published track record** — Phase 10.
   Backtest signal-rules-2.0 on real price history (hit rate, drawdown, vs
   EGX30) and show it in the UI. Directly answers ZBorsa's undefined "64/100".
5. **Alert delivery + data gates** — Phases 11 and 14.
   Web push on stance changes and level crossings; staleness, liquidity and
   data-quality gates on every recommendation.
6. **Reach** — Phase 12 + accounts.
   User accounts, installable PWA, deployment, rate limiting.
7. **Everyday-investor UX.**
   Price-band filters (< 5, 5–20 EGP), budget / position sizing on levels,
   beginner EGX guide, macro strip (CBE rate, USD/EGP, gold, Brent).

Deferred: payments and subscriptions (billing removed 2026-10-23; revisit
after item 6).

## Phase 0 — Import Hotfix (BLOCKER)
Status: COMPLETE (TYPE_CHECKING import present in `app/models/financial.py`)
`TYPE_CHECKING` is missing from `backend/app/models/financial.py` line 5.
This crashes the app at startup and causes all 38 backend test files to fail
at collection time. Must be fixed before any other work proceeds.

  Fix: add `TYPE_CHECKING` to the `from typing import ...` line in
  `backend/app/models/financial.py`.

  Exit criteria: `cd backend && .venv/bin/python -m pytest -q` collects and
  runs; pass-count is reported as the new baseline.

## Phase 1 — Foundation
Status: COMPLETE

## Phase 2 — Companies & Market Prices
Status: COMPLETE
⚠️ Price coverage gap: 30/229 EGX companies return empty price arrays from
Yahoo Finance. Signals and technical scores for those companies report
NOT_RUN but are still included in the ranked universe. Phase 13 must add an
EGX official data fallback and surface per-company coverage gaps in the UI.

## Phase 3 — Financial Statements & Normalized Facts
Status: COMPLETE — DATA WARNING
⚠️ The FRA ingestion folder (`backend/app/ingestion/fra/`) contains only an
empty `__init__.py`. All financial facts in the database come from
`FakeFinancialDataProvider` (synthetic). The normalization and validation
pipelines are wired and tested, but they are processing invented numbers.
All downstream outputs (metrics, ratios, valuations, scores) are therefore
unreliable for real investment decisions until Phase 13 is complete.

## Phase 4 — Financial Metrics & Ratios
Status: COMPLETE — DATA WARNING
Formula logic is correct and deterministic. Outputs are only trustworthy once
real financial data flows in from Phase 13.

## Phase 5 — Shariah Screening
Status: COMPLETE
Screening logic is versioned, auditable, and correctly handles INSUFFICIENT_DATA.
Screening verdicts depend on financial ratios — they inherit the Phase 3 data warning.

## Phase 6 — Valuation
Status: COMPLETE — DATA WARNING
Nine valuation models implemented with Decimal precision and explicit assumptions.
DCF/FCFE/DDM growth inputs are assumptions, not consensus — must be clearly
displayed alongside every fair-value output. Outputs depend on Phase 13 data.

## Phase 7 — Technical Analysis
Status: COMPLETE

## Phase 8 — AI Analyst & RAG
Status: COMPLETE
⚠️ Known startup crash: `app/models/financial.py` missing TYPE_CHECKING import
causes the AI router to fail at import time. Phase 0 hotfix unblocks this.

## Phase 9 — Opportunity Detection
Status: COMPLETE — DATA WARNING
The full EGX universe (229 equities) is ranked using the versioned
cross-sectional momentum / risk model. Scores, tiers, and coverage are
persisted and exposed via `/api/signals`. Coverage is disclosed (199/229
have price data). Signal quality for the 30 uncovered companies is undefined.
⚠️ No backtesting evidence that the scoring model predicts EGX returns.
EGX is an illiquid, emerging market — Western scoring heuristics may not
translate. Phase 10 must validate signal efficacy before outputs inform
real decisions.

## Phase 10 — Backtesting
Status: IN_PROGRESS
Historical backtesting requires a real price-history store. The current Yahoo
provider supplies daily closes but lacks a structured OHLCV archive for
rolling-window strategies.

Added requirements from reliability audit:
- Must use real EGX price data (not Yahoo-only) to cover the full 229-equity
  universe.
- Must report Sharpe ratio, max drawdown, win rate, and benchmark comparison
  across ≥3 distinct EGX market regimes, not just total return.
- Must include a liquidity pre-screen gate: exclude companies whose trailing
  30-day average daily value traded < EGP 500,000. Illiquid names must be
  flagged ⚠️ LOW LIQUIDITY in the UI, never silently ranked alongside liquid ones.
- No look-ahead bias: `publication_date ≤ simulation_date` enforced at the
  engine level with a test that verifies a future filing cannot affect a
  past simulation date.
- Results must be reproducible (seeded random where applicable).

## Phase 11 — Alerts & Monitoring
Status: PENDING
Watchlist subscriptions and threshold alerts can be built on top of the
persisted `MarketSignal` rows and `SignalRun` history.

Added requirements from reliability audit:
- Staleness detection is a hard requirement, not a nice-to-have. Every
  company's signals page must display the `data_as_of` date prominently.
- If any score input is older than 90 days, a staleness warning must block
  the score display (not just appear in the API JSON).
- Any ingestion-job failure must trigger a staleness alert within 1 hour.

## Phase 12 — Production Hardening
Status: PENDING
Production hardening includes rate-limits, request signing, read-only mode
for the API, and a formal migration plan for `model_version` so versioned
scores remain comparable across deploys.

Added requirements from reliability audit:
- API rate limiting is a hard requirement before any public access.
- Audit log: every score change must be traceable (when it changed, why,
  which data version triggered the recompute).
- `model_version` migration plan: old scores must not be compared against
  scores computed under a different methodology version.
- EGX-specific risk disclosures must be gated into the UI before any
  recommendation is surfaced: EGP devaluation risk, thin free-float risk,
  FRA regulatory risk, Egyptian GAAP vs IFRS differences.

## Phase 13 — Real Financial Data Ingestion  ← NEW
Status: NOT_STARTED
This is the highest-priority unstarted phase. All financial metrics, valuations,
scores, and Shariah verdicts are currently computed on synthetic data. This phase
wires real company filings into the existing ingestion pipeline.

Scope:
- Implement `backend/app/ingestion/fra/` — currently an empty stub.
  Must produce `FinancialDocument` + `FinancialFact` rows with
  `source_type = FRA` or `COMPANY`, `document_url`, and `publication_date`.
- Parser strategy: start with structured PDFs / XBRL from company IR pages
  and the FRA disclosure portal. Do not bypass authentication or CAPTCHAs.
- Map extracted line items through the existing `NormalizationService` (already
  built and tested). Every unmapped label must log a warning, never silently drop.
- Add an EGX official price data fallback provider to close the 30-company
  coverage gap from Phase 2. Source: egx.com.eg daily CSV downloads or
  official API where available.
- Surface per-company data coverage in the UI: which companies have real vs
  synthetic data, and which have no price history.
- Remove `FakeFinancialDataProvider` from any non-test wiring.

Exit criteria:
- At least one real EGX company has financial facts with `source_type = COMPANY`
  or `FRA` and a valid `document_url`.
- `DataQualityStatus` for that company is `OK` or `DEGRADED`, not `POOR`/`MISSING`.
- Synthetic data can only be inserted by tests via `DataSourceType.SYNTHETIC`;
  the production ingestion path rejects it at the service layer.
- All existing tests continue to pass (synthetic data stays in tests).

## Phase 14 — Data Quality UI Gates & Liquidity Filter  ← NEW
Status: NOT_STARTED
Dependency: Phase 13 must be complete (real data flowing in).

The data quality scoring engine exists (`dataquality/scores.py`) and is tested,
but its output is not wired as a hard gate on what the UI displays. This phase
promotes DQ from an informational API field to a first-class UI control.

Scope:
- Any company with `DataQualityStatus = POOR` or `MISSING` must be visually
  suppressed in ranking lists and stamped with an explicit warning before any
  score or recommendation is shown. Not just in the API JSON — in the UI.
- Valuation outputs for `DEGRADED` data must display a widened fair-value range
  (confidence haircut) and cannot show a point estimate without a visible caveat.
- Every fair-value display must show the exact assumptions used (growth rate,
  discount rate, terminal value) and a sensitivity table (±1% on WACC,
  ±1% on terminal growth rate).
- Liquidity flag: any company whose trailing 30-day average daily value traded
  < EGP 500,000 must be labelled ⚠️ LOW LIQUIDITY before any signal is shown.
  This gate applies to both the ranking list and the individual company page.
- `data_as_of` must be displayed prominently on every signals/score page.
  Scores older than 90 days trigger a staleness banner that cannot be dismissed
  without acknowledging the staleness.

Exit criteria:
- A company with `DataQualityStatus = POOR` cannot reach the recommendation
  surface in the UI without an explicit warning gate.
- A company with avg daily value < EGP 500K is labelled in the UI.
- Valuation sensitivity table is rendered alongside every fair-value figure.
- `data_as_of` is visible on every score/signals page.
