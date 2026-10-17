# ZBorsa-inspired upgrade: sourced financial statements + dependent calculations + bilingual UX

Date: 2026-10-17 · Status: approved in chat, pending spec review · Next ruling: R41

## Goal

Rebuild the product surface after zborsa.app — dense radar table, bilingual AR/EN, savings
calculator, company-hub structure — while keeping every calculation deterministic, every
number sourced, and every conclusion advisory. ZBorsa's four product pillars are IN scope,
implemented contract-safely (no order execution, nothing presented as certainty, and never
presented as FRA-licensed investment advice):

- **Trading signals** — BUY / SELL / HOLD per company with confidence score and reasons,
  computed deterministically from our owned engines (technical signals, valuation gap,
  score change, Shariah state, statement-freshness), NOT from an LLM and NOT from an
  opaque trained model. Every output carries methodology version, inputs used, and its
  limitations. AGENTS.md rule 9 forbids order *execution*, and the platform implements no
  execution, custody, or brokerage functionality; rule 10 is honored by framing every
  signal as a research finding.
- **Price targets & stop-loss levels** — scenario-derived reference levels (base/bull/bear
  from valuation scenarios; stop anchored to user-chosen percentage or recent range),
  presented as "under these assumptions" with the scenario inputs shown — never "the
  stock is worth X".
- **Payment / subscription flows** — tiered access model (free / pro / max price points
  like zborsa's EGP tiers) with entitlements enforced on the API, but payment *collect*
  runs through a provider-agnostic adapter interface. A local "manual/test" provider ships
  in-repo (dev + self-test only, clearly marked non-production); wiring a real PSP
  (Fawry / InstaPay / card) is an open blocker requiring credentials and is NOT in this
  plan.

Core data addition: real financial statements (income, balance sheet, cash flow) for the
top-10 EGX companies with 8 historical quarters + 3 annual years, curated from published
reports, and every downstream calculation (ratios, Shariah screening, valuation, score,
and the signals layer above) re-fed from those statements.

## Non-goals (explicit)

- Order execution, brokerage, custody, or handling user funds (hard contract line).
- Any signal/level presented as certainty, FRA-licensed advice, or guaranteed returns —
  copy rules stay "potentially/under these assumptions".
- Real PSP credentials/integration (open blocker; adapter interface only).
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

## Part 4 — Signals layer (deterministic, contract-safe)

`SignalService` (pure backend service, input = engine outputs it already owns):

- Inputs: existing technical signal outputs, valuation scenario range, investment score +
  tier, Shariah state, statement freshness (latest `published_date`), alert/score-change
  stats. No LLM, no trained model, no blacklist magic; weights and gating rules are code,
  unit-tested, and versioned (`signal-rules-1.0`).
- Output per company/ticker: `stance` (buy / hold / reduce, mapped zborsa-style but
  presented with full copy: "research stance, not a recommendation"), `confidence` 0–100
  from a documented rubric, `reasons[]` (each reason names its engine + its inputs),
  `limitations[]` (always includes data-freshness and non-advisory wording), and the
  scenario levels below.
- `targets[]`: base/bull/bear levels straight from valuation scenario outputs; when
  valuation is `INSUFFICIENT_DATA` the target is omitted with its status, never
  interpolated.
- `stop_level`: computed as a percentage anchor below the user-chosen entry (input param)
  or off the recent price range — explicitly labeled "a risk reference, not an order
  condition"; no broker/notification coupling.
- Hard checks: if any required engine is `INSUFFICIENT_DATA`, confidence is capped and the
  data gap is listed first; stance NEVER shown without its limitations list rendered beside
  it (UI contract, tested in vitest).
- Compliance copy: every signal surface prints "Research calculation — not investment
  advice · حساب بحثي — ليس توصية استثمارية" (AR/EN).

### Entitlements & subscription (backend)

- `Plan`/`Subscription` tables (tier: free/pro/max; status; period; entitlements JSON) +
  `entitlements` dependency enforcing limits server-side (e.g. free = limited stock
  detail/signals per day; pro = full hub; max = all).
- `PaymentProviderAdapter` protocol: `create_checkout`, `verify_webhook`, `cancel`.
  In-repo providers: `manual/test` (dev-only, marked non-production). Real PSP
  (Fawry/InstaPay/cards) = open blocker requiring merchant credentials; not in this plan.
- No card data touches our DB; webhooks validated by signature before entitlement changes.

## Part 5 — Frontend

- **Company Hub restructure:** company detail keeps one `content` state machine; tabs become
  Overview · Signals (new) · Statements (new) · Ratios (new) · Valuation · Score ·
  Screening · Thesis · Documents (+ existing Technical/Disclosures/Events where live today).
  Signals tab: stance + confidence + reasons + limitations + scenario levels + stop input;
  AR/EN copy; no-red/green-only ranking, colorblind-aware badges.
- **Radar table:** Companies list becomes dense, sortable radar (ticker/name, stance badge,
  price as-of, score, tier badge, Shariah badge, key ratio(s), statement coverage
  indicator); blank ≠ zero. Stance badges carry tooltips with the reason summary.
- **Bilingual toggle:** EN/AR switch in Layout, persisted in localStorage;
  `dir="rtl"` on Arabic; ontology labels AR/EN; UI short-copy dictionary vol. 1 (nav, hub,
  radar, statements, signals, calculation, screening); long analytical prose stays English
  until translated review (marked later).
- **Savings calculator:** deterministic monthly compounding (like zborsa, illustrative-only,
  explicit "not a promise of returns" copy; pure front-end function + tests).
- **Pricing page:** plan cards (Free/Pro/Max EGP mirroring the entitlements contract),
  feature list honesty-checked against server entitlements; checkout only renders when a
  provider is configured.
- **Paywall surfaces:** signals/count limits show remaining quota + upgrade path linking to
  pricing; decline-server-side enforced (client hidden ≠ authorized).

## Part 6 — Testing & gates

- Unit: ontology constants — EN/AR labels resolve per version; RatioService formulas
  (zero/negative/missing/insufficient); statement assembly; seed-loader identity validation;
  Shariah re-feed with real inputs (pass/limit-breached/insufficient); SignalService rubric
  (confidence caps, INSUFFICIENT_DATA gating, stance↔limitations invariant) and
  entitlements enforcement (free/pro/max cuts); webhook verification rejects bad
  signatures.
- `mypy app` clean, ruff clean, backend pytest green incl. warnings-as-errors.
- Frontend: vitest for calculator, bilingual copy resolution, stance-with-limitations
  invariant, pricing/entitlement rendering; tsc/eslint/build gates green.
- Handoffs.log + STATUS.md update; decision ledger R41 (user-approved pivot: zborsa
  signals + payments added to the goal, contract line held at no-execution/no-certainty).

## Sequence

1. Ontology + model + migration 019 + repos → 2. Seed loader + top-10 curated data (real
sources) → 3. RatioService + Shariah re-feed + tests → 4. Statements + ratio endpoints →
5. SignalService + valuation scenario levels + tests → 6. Entitlements + plan tables +
manual/test payment provider → 7. Frontend hub/statements/ratios → 8. Signals tab + radar
→ 9. Bilingual → 10. Savings calculator + pricing page → 11. Gates, workflow records,
spec-review ruling.
