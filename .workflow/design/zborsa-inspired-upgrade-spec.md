# ZBorsa-inspired upgrade: sourced financial statements + dependent calculations + bilingual UX

Date: 2026-10-17 · Status: approved in chat, pending spec review · Next ruling: R41

## Goal

Rebuild the product surface after zborsa.app — dense radar table, bilingual AR/EN, savings
calculator, company-hub structure — while keeping every calculation deterministic, every
number sourced, and every conclusion advisory (no BUY/SELL/HOLD signals, no targets/stops,
no subscriptions/payments: excluded deliberately; AGENTS.md contract confirmed by user).

Core addition: real financial statements (income, balance sheet, cash flow) for the
top-10 EGX companies with 8 historical quarters + 3 annual years, curated from published
reports, and every downstream calculation (ratios, Shariah screening, valuation, score)
re-fed from those statements.

## Non-goals (explicit)

- Trading signals, price targets, stop-losses, payment/subscription flows (contract).
- Auto-parsing statements from filings (heavier path; later phase).
- Coverage beyond the first top-10 batch (schema supports more; curation is the cost).

## Coverage batch ("top 10, deep history")

First batch = 10 most-liquid EGX30 names (selection recorded in `EGX30` order, final list
locked in the seed data file with each company's document URLs). Per company:
8 latest quarters + 3 latest fiscal years. Any period/line the public record does not
clearly publish stays empty with `INSUFFICIENT_DATA`; nothing is approximated.

## Part 1 — Data model (backend, migration 019)

`FinancialStatementLine` table:

- `period_id` → FinancialPeriod (existing), `company_id` (denormalized for queries)
- `ontology_code` (string, canonical), `value` numeric(20,4), `currency`
- provenance: `source_document_id` → FinancialDocument (nullable if curated pre-Phase-7),
  `source_label_reported`, `source_label_en`, `source_label_ar`, `source_page`
  (free-text, e.g. "p.12/23"), `published_date`
- `ontology_version` (string, e.g. "stmt-ontology-1.0") — versioned like Shariah methodology
- unique(period_id, ontology_code) — one value per canonical line per period

Migrations and repositories follow existing patterns (018 continuous migration as template).

### Statement ontology v1 (`stmt-ontology-1.0`)

Income: `revenue, cost_of_revenue, gross_profit, selling_expenses, admin_expenses,
operating_expenses, operating_profit, finance_costs, income_tax, net_income, eps`

Balance: `total_assets, current_assets, cash_and_equivalents, interest_bearing_assets,
inventory, non_current_assets, total_liabilities, current_liabilities,
interest_bearing_debt, total_equity, minority_interests`

Cash flow: `cfo, cfi, cff, capex, dividends_paid, debt_repayment`

Applied to `FinancialFact` when filing facts exist (fact→ontology) and to curated lines;
ontology is a single source of truth for label translations (EN/AR per code) shipped as a
Python constant, mirrored in the REST contract and TS types.

## Part 2 — Ingestion & curation

Seed loader (backend service + script) ingests curated statement lines per company/period
from a reviewed data file (`data/statement-seed/*.json` in repo, with `source_url`,
`source_label_reported`, `published_date` per value). Loader rejects duplicates and
validates arithmetic identities where possible (assets = liabilities + equity; gross profit
= revenue − cost of revenue) with tolerance; violations fail ingestion loudly — no silent
patching. Curation happens during implementation from company IR/EGX disclosures; each file
records retrieval date. DB unchanged for companies without curated data (still
`INSUFFICIENT_DATA`).

## Part 3 — Calculation services (all deterministic, unit-tested)

`StatementService`: assembles per-period ordered statements (income/balance/cash-flow)
with EN/AR labels, publication dates, and provenance; groups by period descending.

`RatioService` (pure functions over ontology values, Decimal arithmetic):
margins (gross/operating/net), ROE, ROA, leverage (debts/equity), current ratio, EPS,
revenue and net-income growth (YoY, needs 2 periods). Any missing input returns
`{"value": null, "status": "INSUFFICIENT_DATA", "reason": "<missing code>"}` — never zero,
matching the existing error contract. Edge cases tested: zero equity, negative revenue,
missing lines.

`ShariahScreeningService` re-feed: existing versioned methodology (v2, AAOIFI-based,
thresholds from the stored methodology record — unchanged) now reads real inputs where
curated data exists: `interest_bearing_debt / market_cap` (market side from quotes as
today), `interest_bearing_assets / total_assets`, non-compliant income share. Output keeps
the version + reason strings; companies without data stay `INSUFFICIENT_DATA` instead of
synthetic pass/fail.

Valuation and InvestmentScore consume canonical codes through the same services (revenue,
net_income, cfo, capex, total_equity feed DCF/factors) — behavior unchanged where data is
missing; existing synthetic-data banner stays visible until Phase 13.

## Part 4 — Frontend

- **Company Hub restructure:** company detail keeps one `content` state machine; tabs become
  Overview · Statements (new) · Ratios (new) · Valuation · Score · Screening · Thesis ·
  Documents (+ existing Technical/Disclosures/Events where live today).
- **Statements tab:** EN/AR line labels (ontology), period columns (never mixed), all-zero
  cross-period banner when `INSUFFICIENT_DATA`, provenance tooltip per line (source label
  as published + date).
- **Radar table:** Companies list becomes dense, sortable radar (ticker/name, price as-of,
  score, tier badge, Shariah badge, key ratio(s), statement coverage indicator); blank ≠ zero.
- **Bilingual toggle:** EN/AR switch in Layout, persisted in localStorage;
  `dir="rtl"` on Arabic; ontology labels AR/EN; UI short-copy dictionary vol. 1 (nav, hub,
  radar, statements, calculation, screening); long analytical prose stays English until
  translated review (marked later).
- **Savings calculator:** deterministic monthly compounding (like zborsa, illustrative-only,
  explicit "not a promise of returns" copy; pure front-end function + tests).

## Part 5 — Testing & gates

- Unit: ontology constants — EN/AR labels resolve per version; RatioService formulas
  (zero/negative/missing/insufficient); statement assembly; seed-loader identity validation;
  Shariah re-feed with real inputs (pass/limit-breached/insufficient).
- `mypy app` clean, ruff clean, backend pytest green incl. warnings-as-errors.
- Frontend: vitest for calculator + bilingual copy resolution; tsc/eslint/build gates green.
- Handoffs.log + STATUS.md update; decision ledger R41 (user-approved contract call:
  zborsa-UX, contract signals exclusion).

## Sequence

1. Ontology + model + migration 019 + repo 2. Seed loader + top-10 curated data (real sources) 3. RatioService + Shariah re-feed + tests 4. Statements + ratio endpoints 5. Frontend hub/statements/ratios 6. Radar 7. Bilingual 8. Calculator 9. Gates, workflow records, spec-review ruling.
