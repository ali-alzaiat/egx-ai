# ZBorsa-inspired Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship sourced financial statements (top-10 EGX, 8 quarters + 3 annuals) feeding deterministic ratios/Shariah/valuation, a versioned signals layer (stance/confidence/targets/stop), tiered entitlements with a manual/test payment adapter, and the bilingual hub/radar frontend.

**Architecture:** New `app/statements/` domain (ontology → fetch → extract → validate → pipeline → service/ratios) reading/writing two new tables + document fetch metadata (migration 019). `ScreeningService` gains a statement-fed input builder; `StanceService` (new file in `app/signals/`) is a pure rules engine over existing engine outputs. `app/billing/` adds plan/subscription tables (migration 020) + provider-adapter payments. Frontend restructures the company hub, adds radar/i18n/calculator/pricing.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Alembic, Pydantic v2, httpx (already dep), pdfplumber + xml.etree (already deps — **no new dependencies**), Decimal everywhere for money. Frontend unchanged stack (no i18n lib — small homegrown dictionary module).

**Spec:** `.workflow/design/zborsa-inspired-upgrade-spec.md` (approved). This plan argues from it; executors read both.

## Global Constraints

- Deterministic calculations only; never delegate finance math to an LLM (AGENTS.md 1).
- No fabricated market/financial data: automation drops ambiguous matches as `INSUFFICIENT_DATA`; never approximate (AGENTS.md 2/3 + spec).
- Every number traceable: ontology line carries source doc + label + page + `published_date` (AGENTS.md 3).
- No look-ahead: published Date ≤ usage date (AGENTS.md 4).
- Versioned methodologies: `stmt-ontology-1.0`, `stmt-extractor-alias-1.0`, `stmt-validator-1.0`, `signal-rules-1.0`; Shariah methodology records unchanged.
- No order execution/custody; no certainty language; compliance copy verbatim: `Research calculation — not investment advice · حساب بحثي — ليس توصية استثمارية` (AGENTS.md 9/10).
- Missing data response shape exact: `{"value": null, "status": "INSUFFICIENT_DATA", "reason": "..."}`; never zero-fill (AGENTS.md errors section).
- Every function annotated; containers parameterized; `mypy app` clean; ruff clean.
- User-facing calculations read ONLY `approved`/`auto_validated` lines (`extraction_candidate`/`rejected` excluded).
- Backend gates run with dev servers stopped; zero errors AND zero warnings everywhere; every changed endpoint reachable from the UI in the same phase (Never-behind rule).
- Enum values in migrations must equal Python member names (006–008 lesson, commit b94a958).
- Source labels: no CAPTCHA/auth bypass; rate-limited fetching; ETag/content-hash dedupe.

## Review Focus

1. **Ambiguous alias** (one reported label variant resolves to 2 ontology codes) → expect candidate dropped with drop-reason, never guessed (Task 4 tests).
2. **Zero/negative equity, missing lines** in ratios → `{"value": null, "status": "INSUFFICIENT_DATA", "reason": "<missing code>"}`, never divide-by-zero or zero (Task 7 tests).
3. **Candidate leakage** — an `extraction_candidate`/`rejected` line reaching any user-facing calculation → statements/ratios/shariah tests assert exclusion (Tasks 6–8).
4. **Restatement supersession** — two documents same period → latest `publication_date` wins for calculations, both rows kept, prior marked superseded (Task 6/7 tests).
5. **Forged webhook** — bad/missing signature must be rejected before any entitlement mutation; replayed same-signature request rejected (Task 10 tests).

---

### Task 1: Statement ontology v1

**Files:**
- Create: `backend/app/statements/__init__.py`, `backend/app/statements/ontology.py`
- Test: `backend/tests/test_statement_ontology.py`

**Interfaces:**
- Produces: `STATEMENT_ONTOLOGY_VERSION = "stmt-ontology-1.0"`; `class LineSection(enum.StrEnum): INCOME | BALANCE | CASH_FLOW`; `class StatementLine(NamedTuple): code: str; section: LineSection; label_en: str; label_ar: str`; `STATEMENT_LINES: dict[str, StatementLine]` (keys = codes below); `def line(code: str) -> StatementLine` (raises `KeyError(code)`).

Codes (exact, from spec §ontology): income = `revenue, cost_of_revenue, gross_profit, selling_expenses, admin_expenses, operating_expenses, operating_profit, finance_costs, income_tax, net_income, eps`; balance = `total_assets, current_assets, cash_and_equivalents, interest_bearing_assets, inventory, non_current_assets, total_liabilities, current_liabilities, interest_bearing_debt, total_equity, minority_interests`; cash flow = `cfo, cfi, cff, capex, dividends_paid, debt_repayment`. EN/AR labels must be non-empty for every code (e.g. `revenue`: "Revenue" / "الإيرادات").

- [ ] **Step 1: Write failing tests** — assert all 28 codes present, EN+AR labels non-empty, `line("gross_profit").section is LineSection.INCOME`, `line("cfo").section is LineSection.CASH_FLOW`, unknown code raises `KeyError`, and income/cash sets match the exact lists above.
- [ ] **Step 2:** `cd backend && .venv/bin/python -m pytest tests/test_statement_ontology.py -v` → FAIL (module missing).
- [ ] **Step 3: Implement** `ontology.py` per the produced interface; labels are a plain dict literal — no I/O.
- [ ] **Step 4:** same command → PASS.
- [ ] **Step 5: Commit** `feat: statement ontology v1 (stmt-ontology-1.0)`.

### Task 2: Migration 019 + models + repositories

**Files:**
- Create: `backend/app/models/statements.py`, `backend/app/repositories/statements.py`, `backend/alembic/versions/019_statement_lines_blobs.py`
- Modify: `backend/app/models/financial.py` (3 columns on `FinancialDocument`), `backend/app/models/__init__.py`, `backend/alembic/versions/018_phase8_continuous_intelligence.py` (only if `down_revision` chain needs it — no)
- Test: `backend/tests/test_migration_019.py` (mirror `test_migration_018.py` style: fresh-create table definitions on test DB)

**Interfaces:**
- Produces (models, names locked):
  - `FinancialStatementLine` (`financial_statement_lines`): `id: UUID` pk; `period_id: UUID` FK `financial_periods.id` CASCADE; `company_id: UUID` FK `companies.id` CASCADE; `ontology_code: String(64)`; `ontology_version: String(32)`; `value: Numeric(20,4) | None`; `currency: String(3)`; `source_document_id: UUID | None` FK `financial_documents.id` SET NULL; `source_label_reported: String(255) | None`; `source_label_en: String(255) | None`; `source_label_ar: String(255) | None`; `source_page: String(32) | None`; `extraction_method: ExtractionMethod` (StrEnum members lowercase = values: `downloaded_document_table, downloaded_document_text, xbrl, manual_seed`; pg enum `extraction_method`); `ext_status: ExtStatus` (StrEnum lowercase members: `extraction_candidate, auto_validated, approved, rejected`; pg enum `ext_status`); `ext_reason: Text | None`; `published_date: Date | None`; `supersedes_id: UUID | None` FK self SET NULL; `created_at`. Unique: `(period_id, ontology_code, supersedes_id nullable-distinct)` → implement as `UniqueConstraint(period_id, ontology_code, source_document_id)` named `uq_stmt_line`.
  - `FinancialDocumentBlob` (`financial_document_blobs`): `id` pk; `document_id: UUID` FK `financial_documents.id` CASCADE; `company_id: UUID` FK CASCADE; `content_hash: String(64)` (sha256 hex, indexed unique); `content_type: String(50)`; `content: LargeBinary`; `fetched_at: DateTime(tz)`.
  - `FinancialDocument` gains: `source_kind: String(20) | None` (values `IR` | `EGX_DISCLOSURE` — strings, not enum), `fetched_at: DateTime(tz) | None`, `content_hash: String(64) | None` + `ix_financial_documents_content_hash`.
- Produces (repos): `StatementLineRepository(session)` with `async def upsert_candidates(self, document_id: UUID, lines: Sequence[StatementLineLike]) -> int` (idempotent: deletes non-approved rows for this document+period, inserts candidates); `async def latest_approved(self, company_id: UUID) -> list[FinancialStatementLine]` (approved/auto_validated only; per `(period_id, ontology_code)` the max `published_date` wins; excludes candidates/rejected); `async def list_candidates(self, company_id: UUID | None = None, limit: int = 100) -> Sequence[tuple[FinancialStatementLine, FinancialDocument]]`; `async def set_status(self, line_id: UUID, status: ExtStatus, reason: str | None) -> FinancialStatementLine`; `async def get(self, line_id: UUID) -> FinancialStatementLine | None`. `DocumentBlobRepository(session)`: `async def get_by_hash(self, content_hash: str) -> FinancialDocumentBlob | None`; `async def store(...) -> FinancialDocumentBlob`.
- Migration style: revision `"019"`, down `"018"`, bare strings; enums emitted with tables, dropped explicitly in downgrade (018 pattern).

- [ ] **Step 1: Write failing migration test** — upgrade creates all 3 tables + columns (assert via inspector), unique constraints exist, downgrade drops tables + enums; assert `financial_documents` gains the 3 columns.
- [ ] **Step 2:** `DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/egx_ai_gate" python -m alembic upgrade head` then `pytest tests/test_migration_019.py -v` → run upgrade/downgrade roundtrip on gate DB → PASS only after Step 3; initially FAIL.
- [ ] **Step 3: Implement** models (SQLAlchemy 2.x `mapped_column` style copied from `models/continuous.py`), migration, repositories; register exports in `models/__init__.py`.
- [ ] **Step 4:** migration roundtrip + `pytest tests/test_migration_019.py -v` on gate DB → PASS. Also run `python -m mypy app` → clean.
- [ ] **Step 5: Commit** `feat: statement lines + document blobs (migration 019)`.

### Task 3: FetchService (feeds config, de-dup, robots, event)

**Files:**
- Create: `backend/app/statements/feed_config.py`, `backend/app/statements/fetch_service.py`
- Test: `backend/tests/test_fetch_service.py` (httpx `MockTransport` — injectable client)

**Interfaces:**
- Consumes: Task 2 repos; `EventRepository.append` with `EventType.FACT_LANDED`; `FinancialPeriodRepository.upsert(FinancialPeriodCreate)`; `DataSourceRepository.get_or_create`.
- Produces:
  - `feed_config.py`: `BATCH_1_TICKERS: tuple[str, ...]` = top-10 EGX30 names as recorded in research (executor must record the actual top-10 by EGX30 list order at execution time in this file + `.workflow/decisions/R41`; do NOT invent tickers — if the list cannot be verified from the running system's EGX universe, leave `tuple()` and BLOCKED-note); `@dataclass class CompanyFeed: ticker: str; ir_urls: list[str]; egx_disclosure: bool`; `def feed_for(ticker: str) -> CompanyFeed` (EGX disclosure URL pattern is the only shipped feed; `ir_urls` start empty and are filled only with user-provided/verified URLs — never guessed).
  - `fetch_service.py`: `class FetchService: __init__(self, session: AsyncSession, http_client: httpx.AsyncClient | None = None)`; `async def fetch_company(self, ticker: str) -> FetchSummary(documents_fetched: int, documents_deduped: int, periods_linked: int, failures: list[str])`; `async def fetch_batch(self, tickers: Sequence[str]) -> dict[str, FetchSummary]`. Behavior: reads `robots.txt` per host and refuses disallowed paths; ≥1s between requests per host; sha256 → `DocumentBlobRepository.get_by_hash` dedupe before download completes; on new bytes: create `FinancialDocument` (`document_type` ∈ `annual_report` / `quarterly_report` inferred from filename/title only, else `other`; `filing_date`/`publication_date` from fetched metadata ONLY — none → dates None), upsert `FinancialPeriod` from document dates, store blob, set doc `source_kind`/`fetched_at`/`content_hash`, and `EventRepository.append(ActorType.SYSTEM, uuid4(), "CI-1.0", EventType.FACT_LANDED, [company_id], {..hash, url..}, reason)` — this is the first emission site of `fact.landed` (see explore note: enum exists, never emitted).
  - `create_fetch_client() -> httpx.AsyncClient` (module util) with UA header `"EGXResearch/0.1 (+research tool; contact: repo owner)"`.
- Tests: MockTransport with embedded robots.txt (allow/deny cases), two identical URLs → 1 blob + 1 dedupe, new hash → 2 docs, `fact.landed` appended once per new doc, denied robots → failure entry, no CAPTCHA/auth code anywhere.

- [ ] **Step 1: Failing tests** per above (robots deny, dedupe, event, summary fields).
- [ ] **Step 2:** `pytest tests/test_fetch_service.py -v` → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** PASS + `mypy app` clean.
- [ ] **Step 5: Commit** `feat: statement fetch service with robots rules and hash dedupe`.

### Task 4: StatementExtractor + alias table

**Files:**
- Create: `backend/app/statements/aliases.py`, `backend/app/statements/extractor.py`, `backend/tests/fixtures/filings/specimen_annual_en.xml` (XBRL subset we author), `backend/tests/fixtures/filings/specimen_annual_ar.xml`
- Test: `backend/tests/test_statement_extractor.py`

**Interfaces:**
- Consumes: Task 1 `STATEMENT_LINES`/`line()`.
- Produces:
  - `aliases.py`: `ALIAS_TABLE_VERSION = "stmt-extractor-alias-1.0"`; `ALIASES: dict[str, tuple[str, ...]]` mapping ontology code → accepted reported-label variants (EN + Arabic), e.g. `{"net_income": ("net income", "profit for the period", "صافي الربح", "صافي دخل", ...)}`; `def resolve_label(label: str) -> tuple[str, Literal["xbrl_tag", "en", "ar"]] | None` returns a code or None when ambiguous/unknown — **ambiguity rule: a variant matching exactly 2+ codes returns None** (drop, not guess).
  - `extractor.py`: `class ExtractionResult: candidates: list[LineCandidate]; drops: list[DropRecord(reason, label, value?)]`; `@dataclass class LineCandidate: ontology_code; value: Decimal; currency: str; source_label_reported: str; source_label_en: str | None; source_label_ar: str | None; source_page: str | None; extraction_method: str; ext_status: Literal["extraction_candidate"]`. `class StatementExtractor: (no state) def extract(self, content: bytes, content_type: str, document_type: str) -> ExtractionResult`.
  - XBRL path: detect via content/xml tag names (etree stdlib); map standard `us-gaap`/`ifrs`/`egx` tag names through `aliases` (tag variant table keyed similarly); take decimals + `scale`/`decimals` attribute; unit → currency.
  - PDF/text/html path: `pdfplumber` for `application/pdf` (tables first, then text lines; capture `page_number`); html via BeautifulSoup; value parsing strips thousand separators, handles `(1,234)` negatives, "EGP '000" scale tokens.
  - Never position-guess: a number is a candidate only when its row label resolves via `resolve_label`.
- Tests: XBRL English specimen → exact expected candidates (codes+values); Arabic XML specimen → Arabic labels resolved via AR aliases; ambiguous duplicate label → in `drops` not candidates; no-match label → drop with `NO_ALIAS`; value normalization cases (`(700)` → -700, “،” thousands separator, `EGP '000` scale → ×1000). See Review Focus #1.

- [ ] **Step 1: Failing tests** (author the two XML fixtures — clearly labeled SYNTHETIC specimen files, deterministic).
- [ ] **Step 2:** FAIL.
- [ ] **Step 3: Implement** aliases + extractor.
- [ ] **Step 4:** PASS + mypy clean.
- [ ] **Step 5:** Optional non-gating follow-up recorded in `decisions/R41`: obtain one real English + one real Arabic PDF filing via the running FetchService into fixtures; until then PDF-path is covered by a generated tiny PDF fallback?? No — leave PDF path tested via Task 6 integration once a real doc lands; log the deferral explicitly.
- [ ] **Step 6: Commit** `feat: statement extractor with versioned alias table (EN/AR/XBRL)`.

### Task 5: StatementValidator

**Files:**
- Create: `backend/app/statements/validator.py`
- Test: `backend/tests/test_statement_validator.py`

**Interfaces:**
- Consumes: `LineCandidate` (Task 4), ontology codes.
- Produces: `VALIDATOR_VERSION = "stmt-validator-1.0"`; `VALIDATION_TOLERANCE = Decimal("0.01")` (relative, i.e. 1%); `@dataclass ValidatedLine: candidate: LineCandidate; ext_status: ExtStatus; failure: str | None`; `class StatementValidator: def validate(self, candidates: Sequence[LineCandidate]) -> ValidationSummary(lines: list[ValidatedLine], auto_validated_count: int, rejected_count: int)`. Identities (each reassigns `rejected` + `ext_reason` naming the failing identity, else `auto_validated` when ALL relevant identities pass for that period's candidate set, else stays `extraction_candidate`):
  - `total_assets == total_liabilities + total_equity (+ minority_interests when present)`
  - `gross_profit == revenue - cost_of_revenue` (both present)
  - `cfo + cfi + cff ≈ net_cash_movement` (net movement line only when present)
  - `eps ≈ net_income / shares` only when share count available (skip silently otherwise → stays candidate)
  - currency uniformity per document (mixed currencies → every line rejected `CURRENCY_MISMATCH`); sign rules: `cost_of_revenue/finance_costs/income_tax >= 0`; period-span sanity left to Task 3/6 (dates live on doc).
- Tests: pass-through (all identities), each identity failing → rejected with reason naming it, tolerance boundary (within 1% passes), mixed-currency rejection, EPS skipped when shares missing.

- [ ] **Step 1: Failing tests.** **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS + mypy. **Step 5: Commit** `feat: statement validator identity gates (stmt-validator-1.0)`.

### Task 6: Pipeline + review queue API

**Files:**
- Create: `backend/app/statements/pipeline.py`, `backend/app/api/statements.py` (prefix `/api/statements`)
- Modify: `backend/app/main.py` (register router)
- Test: `backend/tests/test_statement_pipeline.py`, `backend/tests/test_statement_review_api.py`

**Interfaces:**
- Consumes: Tasks 2/4/5; `EventRepository.append`.
- Produces:
  - `class StatementPipeline: __init__(self, session: AsyncSession); async def process_document(self, document_id: UUID) -> PipelineSummary(candidates_extracted: int, auto_validated: int, rejected: int, drops: int)` — loads blob, runs extractor → validator → `upsert_candidates` (idempotent: re-run on same doc hash replaces non-approved candidates; approved rows never touched); re-runs old superseding logic: on new doc for same period, candidates keep `source_document_id` of new doc and calculations use latest `published_date` (Task 2 `latest_approved` implements latest-wins; supersession recorded via `supersedes_id` when programmatically linking, optional in v1 — log if deferred).
  - Endpoints (schemas in `app/schemas/statements.py` — follow `schemas/continuous.py` ConfigDict pattern): `GET /api/statements/review-queue?company_id=` → candidates + document metadata + page refs; `POST /api/statements/lines/{line_id}/approve`; `POST /api/statements/lines/{line_id}/reject` (body `{"reason": str}`); both raise 404 on unknown id, 409 approving an already-approved row.
- Tests: end-to-end with fixture bytes (Task 4): process → queue lists candidates only; approve → gone from queue, present via `latest_approved`; reject with reason visible; re-process same doc → no duplicate final rows (idempotency); Review Focus #3: `latest_approved` excludes `extraction_candidate`/`rejected` (assert directly).

- [ ] **Step 1: Failing tests.** **Step 2:** FAIL. **Step 3:** Implement pipeline + schemas + router; register in `main.py`. **Step 4:** PASS + mypy + ruff (file-scoped). **Step 5: Commit** `feat: statement pipeline + ops review queue endpoints`.

### Task 7: StatementService + RatioService + endpoints

**Files:**
- Create: `backend/app/statements/service.py`, `backend/app/statements/ratios.py`
- Test: `backend/tests/test_statement_service.py`, `backend/tests/test_ratio_service.py`

**Interfaces:**
- Consumes: `StatementLineRepository.latest_approved` (latest-wins, candidates excluded — Review Focus #3/#4 tests live here and in Task 6).
- Produces:
  - `class StatementService: __init__(self, session); async def company_statements(self, company_id: UUID) -> StatementBundle(periods: list[PeriodStatements])` where `PeriodStatements(period_id, fiscal_year, period_type, published_date, income: list[StatementLineRead], balance: list[...], cash_flow: list[...])` and `StatementLineRead` carries EN/AR labels from `ontology.line(code)` + value/currency/status (`AVAILABLE` if value not None else `INSUFFICIENT_DATA` never invents) + provenance snippet (`source_label_reported`, `source_page`, `published_date`). Periods descending (`fiscal_year` desc, then `period_type` order END_DATE desc).
  - `ratios.py`: `RATIO_VERSION = "stmt-ratios-1.0"`; `class RatioResult(NamedTuple): code: str; value: str | None; status: Literal["AVAILABLE","INSUFFICIENT_DATA"]; reason: str | None`; `class RatioService: @staticmethod def compute(self, lines_by_code: dict[str, Decimal], prior_lines: dict[str, Decimal] | None, shares: Decimal | None) -> list[RatioResult]` covering exactly: `gross_margin = gross_profit/revenue`; `operating_margin = operating_profit/revenue`; `net_margin = net_income/revenue`; `roe = net_income/total_equity`; `roa = net_income/total_assets`; `leverage = interest_bearing_debt/total_equity`; `current_ratio = current_assets/current_liabilities`; `eps` straight from line; `revenue_growth_yoy = revenue/prior[revenue]-1`, `net_income_growth_yoy` same. All Decimal division with `getcontext().prec` left default (28); **missing input code → `RatioResult(code, None, "INSUFFICIENT_DATA", f"{missing}")`; zero/negative denominators → INSUFFICIENT_DATA with reason (`ZERO_EQUITY` etc.), never crash** (Review Focus #2).
  - Endpoint `GET /api/statements/companies/{ticker}/statements` + `GET /api/statements/companies/{ticker}/ratios` (service-constructed, `Depends(get_session)`).
- Tests: assembly groups 3 sections, labels resolve EN+AR, insufficient line → null not zero; ratios: each formula with a golden Decimal case, zero-equity ROE, negative revenue margin, growth when prior missing, currency passthrough.

- [ ] **Step 1: Failing tests.** **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS (+ full `pytest tests -q` green) + mypy. **Step 5: Commit** `feat: statement assembly + ratio service endpoints`.

### Task 8: Shariah re-feed from statements

**Files:**
- Create: `backend/app/screening/statement_input.py`
- Modify: `backend/app/api/screening.py` (new endpoint, existing untouched)
- Test: `backend/tests/test_screening_statement_refeed.py`

**Interfaces:**
- Consumes: `StatementLineRepository.latest_approved`, `ShariahScreeningService.screen_company(ScreeningInput)` (existing, unchanged internals), market cap resolution — follow the existing `/screen` endpoint pattern for quoting (reuse exactly how the current endpoint obtains price/market info; do not invent).
- Produces: `def build_screening_input_from_statements(company_id: UUID, company: Company, lines: Sequence[FinancialStatementLine], market_cap: Decimal | None) -> tuple[ScreeningInput | None, str | None]` — None+reason when required codes absent (`INSUFFICIENT_DATA` path); maps `interest_bearing_debt→total_debt`, `total_assets`, `cash_and_equivalents→cash_and_securities`, `revenue→total_revenue`; non-compliant income share comes from the existing rule inputs (industry-based revenue share as today — statements do not add an income-breakdown code in v1; log that limit in `overall_reason`). Endpoint: `POST /api/screening/companies/{company_id}/screen-statements` → 200 with `ScreeningOutput`-shaped body incl. `methodology_version`; 409 body `{"status":"INSUFFICIENT_DATA","reason":...}` when no approved inputs. Methodology threshold logic untouched (versioned record reused).
- Tests (mock-approved lines via Task 2 repo helpers): compliant pass; 33/33/5 breach path; missing inputs → 409 INSUFFICIENT_DATA; existing `/screen` endpoint still green (no regression).

- [ ] **Step 1: Failing tests.** **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS + mypy. **Step 5: Commit** `feat: shariah screening re-fed from approved statement lines`.

### Task 9: StanceService (signals layer)

**Files:**
- Create: `backend/app/signals/stance.py`, `backend/app/api/stance.py` (prefix `/api/stance` — `/api/signals` already used by market-signal ranking engine)
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_stance_service.py`

**Interfaces:**
- Consumes: `TechnicalService.calculate_indicators` (IndicatorResult list), `ValuationService` scenario dict (`bull/base/bear` keys with `{"value","status","reason","inputs"}` payloads), `ScoreService.latest_payload` / `InvestmentScore.headline`+`headline_status`, screening result (`ScreeningRepository.get_screening_result`), `StatementLineRepository` → freshness = max `published_date` of latest_approved, market close via existing price repo.
- Produces:
  - `SIGNAL_RULES_VERSION = "signal-rules-1.0"`; `class Stance(enum.StrEnum): BUY="buy"; HOLD="hold"; REDUCE="reduce"`; `@dataclass Reason(engine: str, inputs: dict[str, str], text: str)`; `@dataclass StanceResult(company_id, ticker, stance, confidence: int, reasons: list[Reason], limitations: list[str], targets: dict[str, list[TargetLevel]]`... lock exact: `targets: dict[str, TargetLevel]` keyed `bull/base/bear` with `TargetLevel(value: str | None, status: str, reason: str | None)`, `stop_level: TargetLevel`, `statement_freshness: date | None, rules_version, as_of: datetime`; `limitations` always begins `"Research calculation — not investment advice · حساب بحثي — ليس توصية استثمارية"`.
  - `class StanceService: __init__(self, session); async def compute(self, ticker: str, entry_price: Decimal | None = None, stop_pct: Decimal = Decimal("10")) -> StanceResult`. Rules (code, unit-tested):
    - Inputs missing/`INSUFFICIENT_DATA` in ANY engine → confidence capped at 40 and that gap listed first in `limitations` (Review Focus: mirrors spec hard-check).
    - Bull case only when `bear < entry_reference < bull` monotonic sanity holds, else target set to INSUFFICIENT with reason `SCENARIO_ORDER`.
    - Stance rubric (fixed points, 0–100): technical composite (SMA20 vs SMA50 available & price side) ±20; valuation gap (price below base value → +25, above bear → −20, else 0); score tier (STRONGEST/STRONG +10, WEAK/WEAKEST −10); Shariah non-compliant → −30; statement freshness > 400 days → −15 and limitation. Then map ≥60 BUY, ≥35 HOLD, else REDUCE. Every reason names its engine + the exact inputs used.
    - `stop_level` = entry_price × (1 − stop_pct/100) when entry given, else recent-range low from OHLC window; `status` follows input availability; copy "a risk reference, not an order condition" goes in `limitations`.
    - Valuation INSUFFICIENT_DATA → targets keyed but `TargetLevel(status="INSUFFICIENT_DATA", value=None)` — never interpolated.
  - Endpoints: `GET /api/stance/companies/{ticker}?entry_price=&stop_pct=` (validates `stop_pct ∈ (0, 90]`, 422 beyond); `GET /api/stance/radar` (batch: stance summary list for all companies with price — used by radar Task 12; page_size ≤ 50).
- Tests: deterministic rubric golden cases (each rule triggered), cap-on-insufficient, scenario-order guard, stop from entry vs range, limitations invariant: `stance != ""` implies limitations rendered non-empty (assert model invariant + API body), valuation gap INSUFFICIENT → target status INSUFFICIENT_DATA.

- [ ] **Step 1: Failing tests.** **Step 2:** FAIL. **Step 3:** Implement service + router. **Step 4:** PASS + mypy. **Step 5: Commit** `feat: deterministic stance service (signal-rules-1.0)`.

### Task 10: Entitlements + manual payment provider

**Files:**
- Create: `backend/app/billing/__init__.py`, `backend/app/billing/entitlements.py`, `backend/app/billing/provider.py`, `backend/app/billing/manual_provider.py`, `backend/app/billing/service.py`, `backend/app/api/billing.py` (prefix `/api/billing`), `backend/alembic/versions/020_billing.py`, `backend/app/models/billing.py`
- Modify: `backend/app/core/config.py` (+`BILLING_WEBHOOK_SECRET: str = "dev-secret-rotate-me"`), `backend/app/main.py`, `backend/app/signals/stance.py` + `backend/app/api/stance.py` (quota enforcement)
- Test: `backend/tests/test_billing.py`, `backend/tests/test_entitlements.py`

**Interfaces:**
- Produces:
  - Models: `Plan(id, tier: PlanTier StrEnum [FREE, PRO, MAX], price_egp: Numeric(10,2), entitlements: JSONB, active: bool)`, `Subscription(id, user_key: String(64) unique, tier, status [ACTIVE/CANCELED] StrEnum `active/canceled` lowercase members, period_start/period_end: Date, created_at)`, `UsageCounter(user_key, day: Date, view_counter: int, unique uq(user_key, day))`.
  - `entitlements.py`: `PLAN_ENTITLEMENTS: dict[PlanTier, Entitlements]` where `Entitlements` is a frozen dataclass `daily_stance_quota: int` (FREE=3, PRO=10_000, MAX=10_000), `daily_radar: int` (FREE=1, else 100_000), `company_hub_full: bool` (FREE False). Seeds via alembic `op.bulk_insert` idempotently (check-then-insert).
  - `provider.py`: `class PaymentProviderSignatureError(Exception)`; `Protocol PaymentProviderAdapter: def create_checkout(self, subscription: Subscription, plan: Plan) -> Checkout(url: str | None, provider: str, external_id: str | None); def verify_webhook(self, body: bytes, signature: str | None) -> WebhookEvent(event_id, subscription_id, type: Literal["paid","canceled"]) -> None  # raises PaymentProviderSignatureError`; `def cancel(self, subscription: Subscription) -> None` — real PSP = open blocker, adapter only.
  - `manual_provider.py`: HMAC-SHA256 over `body` with `settings.BILLING_WEBHOOK_SECRET`, docstring "DEV/TEST ONLY — not a production payment provider; collects no real funds".
  - `service.py`: `BillingService(session)`: `async def subscription_for(self, user_key: str) -> Subscription` (creates FREE row on miss); `async def assert_quota(self, user_key: str, kind: str)` (increments `UsageCounter`, raises `HTTPException(429)`-shaped domain exception `QuotaExceeded(quota: int, tier: str)`; API layer maps to 429 with `{"error": "QUOTA_EXCEEDED", "quota": n, "tier": t}`); `async def handle_webhook(...)`.
  - API: `GET /api/billing/plans` (honest feature lists per tier); `POST /api/billing/checkout` (Free always returns `{"provider": "manual", "url": None}` — checkout UI renders only when a provider is configured); `POST /api/billing/webhooks/manual` (X-Signature required); `GET /api/billing/me?user_key=` (subscription + usage used). Stance endpoints enforce: `Depends(entitlement("stance"))` mapping between radar/quota kinds.
- Tests: plan seeds exact entitlement numbers; FREE quota cut on 4th stance of day (Task 9 endpoint via client); 429 shape; radar quota; webhook bad signature → `PaymentProviderSignatureError` and **subscription row unchanged** (Review Focus #5); replay protection (same event_id twice → second rejected); canceled sub drops to FREE immediately (quota re-check).

- [ ] **Step 1: Failing tests.** **Step 2:** FAIL. **Step 3:** Implement (migration 020 with `uq_billing_user_key_day` naming). **Step 4:** gates green on gate DB (upgrade 019→020) + full pytest. **Step 5: Commit** `feat: tiered entitlements + manual/test payment adapter (no real PSP)`.

### Task 11: Frontend contract surface (types, client, tabs wiring)

**Files:**
- Modify: `frontend/src/types/index.ts` (+`StatementBundle`, `RatioResult`, `StanceResult`, `BillingPlan`… snake_case-mirroring), `frontend/src/api/client.ts` (+`useStatements(ticker)`, `useRatios(ticker)`, `useStance(ticker, params)`, `useStanceRadar(page)` (+radar ready for Task 12), `useBillingPlans`, `useMyBilling`, `useCheckout`), `frontend/src/components/CompanyTabs.tsx` (tabs: keep existing + insert `Statements`, `Ratios` after Financial Data, `Signals` after Overview), `frontend/src/App.tsx` (+routes)
- Test: none own (pure wiring) — gates in Task 14.

- [ ] **Step 1:** implement the four shared-file changes; tabs order locked: `Overview · Signals · Financial Data · Statements · Ratios · Metrics · Technical · Valuation · Score · Screening · Peers · Thesis · Disclosures` (radar pricing/savings are top-level pages, not tabs).
- [ ] **Step 2:** `cd frontend && npm run build && npx tsc --noEmit` → zero errors.
- [ ] **Step 3: Commit** `feat(frontend): statements/ratios/stance contract surface + hub tabs`.

### Task 12: Statements + Ratios tabs, radar table

**Files:**
- Create: `frontend/src/pages/Statements.tsx`+`.css`, `frontend/src/pages/Ratios.tsx`+`.css`
- Modify: `frontend/src/pages/Companies.tsx` (radar table mode replacing card grid — dense sortable: ticker/name, stance badge w/ tooltip of reason summary, price as-of, score, tier badge, Shariah badge, gross margin, coverage dot; blank ≠ zero; colorblind-aware badge shapes not just colors)

**Interfaces:**
- Consumes: Task 11 hooks; labels from API (EN/AR fields provided by backend — render `label_ar` when lang=ar, see Task 13 hook; before Task 13 lands render EN).
- Unit-testable pure helpers (vitest): `frontend/src/pages/companies/radarSort.ts` (`sortRadarRows(rows, key, dir)`, blanks sort last) + tests file `radarSort.test.ts`.
- [ ] **Step 1:** failing vitest for `radarSort` (null last, asc/desc, numeric strings).
- [ ] **Step 2:** FAIL → implement → PASS.
- [ ] **Step 3:** build statements/ratios pages (quarterly/annual grouped tables, INSUFFICIENT_DATA rows show dash — not 0; provenance sub-line under each value).
- [ ] **Step 4:** `npm run build && npx tsc --noEmit && npx vitest run` zero errors/warnings.
- [ ] **Step 5: Commit** `feat(frontend): statements + ratios tabs, radar table`.

### Task 13: Signals tab (stance)

**Files:**
- Create: `frontend/src/pages/Signals.tsx`+`.css`, `frontend/src/components/StanceCard.tsx` (stance badge, confidence meter, reasons list w/ engine names, limitations list — **hard UI rule: stance never renders without its limitations block beside it**, enforced in component code + test), `frontend/src/components/TargetsTable.tsx` (bull/base/bear rows with status-aware labels), stop input + compute button.
- Test: `frontend/src/components/stanceInvariant.test.ts` (pure helper `requiresLimitations(stance)` + copy constant assertion).

- [ ] **Step 1:** failing vitest for the invariant helper + compliance-copy constant exact string match.
- [ ] **Step 2:** FAIL → implement → PASS.
- [ ] **Step 3:** wire page (useStance hook; disabled input when FREE quota exhausted → 429 shows quota+upgrade link to Pricing Task 14).
- [ ] **Step 4:** gates green.
- [ ] **Step 5: Commit** `feat(frontend): signals/stance tab with limitations invariant`.

### Task 14: Bilingual toggle + savings calculator + pricing/paywall

**Files:**
- Create: `frontend/src/i18n/dict.ts` (`SHORT_COPY: Record<key, {en: string; ar: string}>` — nav, hub, radar, statements, signals, calculation, screening keys; long analytical prose stays EN — literal per spec), `frontend/src/i18n/useLang.ts` (`useLang(): {lang: "en"|"ar"; setLang; t(key)}` — localStorage persist `'egx-lang'`), `frontend/src/pages/Pricing.tsx`+`.css`, `frontend/src/utils/savings.ts` (`projectSavings(monthlyEgp: number, months: number, annualRatePct: number): {month: number; balance: number}[]` — monthly compounding at `annualRatePct/12`, illustrative only).
- Modify: `frontend/src/components/Layout.tsx` (toggle button + `document.documentElement.dir = "rtl"` when ar; `lang` attr), all new pages' copy via `t()` where short-copy; `frontend/src/App.tsx` (+ `/pricing` route).

**Tests:**
- `frontend/src/utils/savings.test.ts`: deterministic golden monthly table (e.g. 1000/mo × 12 months @12% → fixed balances), zero-rate edge, single month.
- `frontend/src/i18n/i18n.test.ts`: `t()` resolves AR+EN for every SHORT_COPY key, missing key throws in dev.
- RTL layout correctness is verified visually at Task 14 Step 4 + ux-expert review (not unit-tested).
- [ ] **Step 1:** failing tests. **Step 2:** FAIL. **Step 3:** implement dict + hook + Layout RTL + calculator + pricing (feature lists mirror `PLAN_ENTITLEMENTS` exactly — no claim the server doesn't enforce; checkout button hidden unless backend says provider configured). Paywall surfaces: 429 quota remnant UI on Signals/radar with upgrade CTA linking `/pricing`.
- [ ] **Step 4:** gates (`vitest`, `tsc`, `eslint`, `build`) zero-clean; run dev servers and verify RTL visually via Playwright snapshot (record screenshot path in handoffs).
- [ ] **Step 5: Commit** `feat(frontend): bilingual toggle, savings calculator, pricing + paywall surfaces`.

### Task 15: Final gates + workflow records

- [ ] **Step 1:** Backend full gates with dev servers stopped: `pytest tests -q` (653+new, zero fail), `ruff check .` zero NEW errors (pre-existing 34 noted), `mypy app` clean — all with `DATABASE_URL=…egx_ai_gate`.
- [ ] **Step 2:** Manual E2E on dev DB: start uvicorn+vite, fetch 2 real companies through FetchService (network, logged outcome), watch pipeline auto-validation land, approve via review queue, ratios + screening + stance respond INSUFFICIENT_DATA-cleanly where gaps. Log DATA-WARNING status (synthetic universe until Phase 13).
- [ ] **Step 3:** Append `handoffs.log`, update `STATUS.md`, file `decisions/R41` (spec-approved pivot + top-10 list record + real-PSP blocker + deferrals: real-PDF fixtures, non-compliant-income-share-from-statements limit), spec status line to "approved, implemented in this plan".
- [ ] **Step 4:** Point-summary commit `docs: R41 decisions + handoffs + status`.

## Self-Review

- **Spec coverage:** ontology (T1), model+migration (T2), fetch pipeline (T3), extractor+aliases EN/AR/XBRL (T4), validator gates+tolerance (T5), human-approval queue + idempotent rerun + supersession (T6), statement service EN/AR provenance (T7), ratio service incl. growth + INSUFFICIENT_DATA contract (T7), Shariah re-feed versioned/insufficiency (T8), signals rubric + targets/stop + hard-checks + compliance copy (T9), entitlements + adapter + manual provider + no card data (T10), hub restructure + radar + bilingual + savings + pricing + paywall (T11–14), gates incl. warnings-errors + workflow records + R41 (T15 + per-task). Spec §"review queue extends PendingFinancialData pattern" — no such backend model exists (explore item 1); resolved as review-queue-over-line-status with the REASON logged in R41.
- **Step scan:** no TBD lines; each step writes one thing; bodies only where tests don't determine them (validator identities, stance rubric — both spec-fixed values).
- **Type consistency:** `TargetLevel(value,status,reason)` used in T9/T12/T13; `latest_approved` in T6/T7/T8/T9; `StatementService.company_statements` vs API path `/statements` consistent; `StanceService.compute(ticker, entry_price, stop_pct)` matches endpoint query params.
- **Review Focus:** all five pinned to owning tasks (T4 #1, T7 #2, T6 #3, T6/T7 #4, T10 #5).
- **Proportion:** plan ≈ spec length; signatures + test names, no transcripts.

## Known deviations to log in decisions/R41 at execution
1. Real-PDF fixtures deferred until a real filing is fetched (T4 note) — spec asked for one now.
2. Non-compliant income share remains industry-rule input (no statement code in ontology v1).
3. `PendingFinancialData` backend pattern does not exist; review queue = line-status filter.
4. Real PSP integration = open blocker (spec §non-goals).
