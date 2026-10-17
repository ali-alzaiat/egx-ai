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
top-10 EGX companies with 8 historical quarters + 3 annual years, fetched and parsed
automatically from their published filings and every downstream calculation (ratios, Shariah screening, valuation, score,
and the signals layer above) re-fed from those statements.

## Non-goals (explicit)

- Order execution, brokerage, custody, or handling user funds (hard contract line).
- Any signal/level presented as certainty, FRA-licensed advice, or guaranteed returns —
  copy rules stay "potentially/under these assumptions".
- Real PSP credentials/integration (open blocker; adapter interface only).
- Coverage beyond the first top-10 batch (schema supports more; pipeline is the cost).
- Circumventing CAPTCHAs/authentication/robots on any data source (AGENTS.md source rule).

## Coverage batch ("top 10, deep history")

First batch = 10 most-liquid EGX30 names (selection recorded in `EGX30` order, final list
locked with each company's IR/disclosure feed URLs in the fetch config). Per company:
8 latest quarters + 3 latest fiscal years, pulled automatically from published filings.
Any period/line automation cannot extract confidently stays empty with
`INSUFFICIENT_DATA`; nothing is approximated or hand-invented.

## Part 1 — Data model (backend, migration 019)

`FinancialStatementLine` table:

- `period_id` → FinancialPeriod (existing), `company_id` (denormalized for queries)
- `ontology_code` (string, canonical), `value` numeric(20,4), `currency`
- provenance: `source_document_id` → FinancialDocument, `source_label_reported`,
  `source_label_en`, `source_label_ar`, `source_page` (e.g. "p.12/23"), `extraction_method`
  (`downloaded_document_table` | `downloaded_document_text` | `xbrl` | `manual_seed`),
  `ext_status` (`extraction_candidate` | `auto_validated` | `approved` | `rejected`),
  `published_date`
- `ontology_version` (string, e.g. "stmt-ontology-1.0") — versioned like Shariah methodology
- unique(period_id, ontology_code) — one value per canonical line per period

`FinancialDocument` (existing table) gains fetch metadata (`source_kind` = IR | EGX
disclosure, `fetched_at`, `content_hash`) and `FinancialDocumentBlob` stores the raw
downloaded file bytes (pdf/html) so every extraction is re-runnable against the same bytes
(provenance invariant: same hash → same extraction).

Migrations and repositories follow existing patterns (018 continuous migration as template).

### Statement ontology v1 (`stmt-ontology-1.0`)

Income: `revenue, cost_of_revenue, gross_profit, selling_expenses, admin_expenses,
operating_expenses, operating_profit, finance_costs, income_tax, net_income, eps`

Balance: `total_assets, current_assets, cash_and_equivalents, interest_bearing_assets,
inventory, non_current_assets, total_liabilities, current_liabilities,
interest_bearing_debt, total_equity, minority_interests`

Cash flow: `cfo, cfi, cff, capex, dividends_paid, debt_repayment`

Applied to `FinancialFact` when filing facts exist (fact→ontology) and to pipeline-extracted
lines; ontology is a single source of truth for label translations (EN/AR per code) shipped
as a Python constant, mirrored in the REST contract and TS types.

## Part 2 — Automated fetch → parse → validate pipeline (no hardcoded numbers)

`FetchService`:
- Per-company config lists official feeds: company IR pages + EGX disclosures, ordered,
  robots/auth/CAPTCHA-respecting (AGENTS.md source rule), request rate-limited, ETag/
  content-hash de-duplication against `FinancialDocumentBlob`.
- Triggered on demand + scheduled job → registers documents, stores raw bytes, links to
  `FinancialPeriod` by the document's own date fields, emits `fact.landed` continuous
  events for the existing event ledger.

`StatementExtractor` (pure, fixture-tested):
- Input: document bytes + type (annual report, quarterly, XBRL when present).
- XBRL path first (deterministic tags when the filing ships them); otherwise pdf
  table/text extraction (pdfplumber-class tools) with table boundaries + page numbers
  recorded per cell.
- Arabic + English label matching maps reported lines → ontology codes via an explicit,
  versioned alias table (`source_label variants → code`), never position-guessed alone.
- Output: candidate `FinancialStatementLine`s with full provenance; ambiguous matches
  (same alias to 2 codes, off-balance values, wrong currency) are dropped, not guessed.

`StatementValidator` (pure gates before anything is shown):
- arithmetic identities with tolerance: assets = liabilities + equity, gross_profit =
  revenue − cost_of_revenue, CFO + CFI + CFF ≈ net cash movement, EPS ≈ net_income /
  shares (where share count available);
- currency uniformity per document; sign conventions; period-span sanity (fiscal year
  boundaries);
- gates decide: `auto_validated` (all identities pass) vs `extraction_candidate`
  (extracted but unproven — visible ONLY in the review queue), `rejected` (fail loudly
  with the failing identity in the reason).

Human-in-the-loop only as approval, not data entry: an Ops review queue (extends the
existing `PendingFinancialData` pattern) lists candidates with the document page snapshot;
`approved` lines flow to statements/Shariah/valuation; nothing marked
`extraction_candidate` ever reaches user-facing calculations.

Retry/upsert semantics: re-running the pipeline on the same document hash replaces
candidates idempotently; a restatement (new doc for same period) supersedes earlier lines
per-period with the supersession recorded in provenance (both kept, latest wins for
calculations).

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
approved-stream data exists (never synthetic): `interest_bearing_debt / market_cap`
(market side from quotes as today), `interest_bearing_assets / total_assets`,
non-compliant income share. Output keeps
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
  (zero/negative/missing/insufficient); statement assembly; extractor fixture tests (real
  sample filings in `backend/tests/fixtures/filings/` incl. one Arabic + one English pdf,
  one XBRL) covering: label aliases → codes, identity gates (pass/fail/tolerance),
  supersession, idempotent re-runs; validator gates reject loudly; Shariah re-feed with
  approved inputs (pass/limit-breached/insufficient); user-facing calculations read only
  the `approved`/`auto_validated` stream (candidates excluded); SignalService rubric
  (confidence caps, INSUFFICIENT_DATA gating, stance↔limitations invariant) and
  entitlements enforcement (free/pro/max cuts); webhook verification rejects bad
  signatures.
- `mypy app` clean, ruff clean, backend pytest green incl. warnings-as-errors.
- Frontend: vitest for calculator, bilingual copy resolution, stance-with-limitations
  invariant, pricing/entitlement rendering; tsc/eslint/build gates green.
- Handoffs.log + STATUS.md update; decision ledger R41 (user-approved pivot: zborsa
  signals + payments added to the goal, contract line held at no-execution/no-certainty).

## Sequence

1. Ontology + model + migration 019 + repos → 2. FetchService (feeds config, de-dup,
storage, robots rules) → 3. StatementExtractor + alias table + XML/pdf
fixtures → 4. StatementValidator gates + review queue (approved/candidate exclusion) → 5.
RatioService + Shariah re-feed + tests → 6. Statements + ratio endpoints →
7. SignalService + valuation scenario levels + tests → 8. Entitlements + plan tables +
manual/test payment provider → 9. Frontend hub/statements/ratios → 10. Signals tab + radar
→ 11. Bilingual → 12. Savings calculator + pricing page → 13. Gates, workflow records,
spec-review ruling.
