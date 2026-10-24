# R43 contract — computed company data, no input forms

**From:** Tarek (architect) · 2026-10-23 · for staff-backend + staff-frontend sign-off (CONTRACT step 4), then build.
**Decision implemented:** `.workflow/decisions/R43-show-data-not-forms.md` (M1 bridge, M2 auto-compute, M3/M4 UI contract).
**Cross-phase contracts checked:** roadmap §"Cross-phase contracts" (Quality, Package layout, Tables, API, Scores). Result in §0.

**Read before ruling (code, this session):** `statements/{ontology,ratios,service,vendor_import,validator,intake}.py`,
`repositories/{statements,industry,scores,screening,technical}.py`, `metrics/{service,engine,definitions}.py`,
`scores/{service,constants,checks}.py`, `valuation/{service,constants,fairvalue,models}.py`,
`screening/{service,statement_input,methodology,rules,purification}.py`, `thesis/{service,constants,thesis}.py`,
`technical/service.py`, `signals/{engine,stance,stance_cache}.py`, `ingestion/{jobs,sync}.py`,
`dataquality/service.py`, `api/{metrics,valuation,scores,screening,theses,technical,statements,ingestion,disclosures,signals}.py`,
`models/{statements,metrics,technical,valuation,screening,thesis,market}.py`, `db/session.py`,
`frontend/src/{App.tsx,api/client.ts,types/index.ts,components/CompanyTabs.tsx,components/Layout.tsx}` and the
pages that import the AC-1 functions. Vendor JSON field inventory (`data/vendor/stockanalysis/*.json`, 230 files).

**Dev-database facts (read-only queries, 2026-10-23):**

| Fact | Value | Consequence |
|---|---|---|
| Companies | 234 | — |
| Companies with approved/auto_validated statement lines | 203 (all ≥ 2 annual periods; 1,048 ANNUAL periods) | M1 has real inputs |
| Statement lines by method | 100% `vendor_aggregator` (19,010 auto_validated, 1,829 candidate, 99 rejected) | everything M1 produces is **provisional** today |
| Vendor lines with `published_date` | 0 of 20,938 | freshness / report_date must fall back to period end (§1.5) |
| `financial_facts` rows | **0** | the legacy fact path feeds nothing; the bridge **replaces** it (§1.1) |
| `financial_metrics`, `investment_scores`, `technical_indicators` rows | 0 / 0 / 0 | nothing computed today |
| `valuation_fair_values` | 86 rows, all INSUFFICIENT_DATA | DQ `financial_statements` = MISSING for all 234 companies ⇒ intrinsic leg suppressed |
| `companies.shares_outstanding` | 0 of 234 | every per-share number is impossible without a share-count line (§1.2) |
| `companies.industry` / `egx_sector_id` / `gics_sub_industry_id` | **0 / 0 / 0 of 234** | Shariah industry rule is INSUFFICIENT for every company; valuation/score profiles all fall to `default` (see §6, D-9) |
| `eps` lines held as `extraction_candidate` | 1,032 (validator passthru: "share-count identity, v1: never") | EPS must be derived from net income ÷ weighted shares (§1.3) |
| Companies with ≥ 200 price bars | 199 | technical + signals have inputs |
| Latest price date | 2026-10-22 | — |

---

## 0. Cross-phase contract check (no drift)

| Locked contract | Effect of this design | Verdict |
|---|---|---|
| **Quality** — `DataQualityScore \| None`, pinned constants, `methodology_version="1.0"` | Interface and constants unchanged. Only the *row source* of the `financial_statements` scope changes from `FinancialFact` (0 rows) to approved statement lines (§1.5). | No drift |
| **Package layout** — `backend/app/<domain>/` | New: `app/statements/bridge.py`, `app/services/recompute.py`, `app/valuation/assumptions.py`. | No drift |
| **Tables** — one migration per phase, numbered, explicit names/ondelete | One migration `023_r43_computed_data.py`, `down_revision = "022…"` (§3.6). | No drift |
| **API** — `/api/<domain>/companies/{company_id}`, hand-serialized, `str(Decimal)`, `.isoformat()` | All changes are on existing routes; additive fields; no new domain router (admin needs no new endpoint). | No drift |
| **Scores** — persisted ratings store `methodology_version`; reads default to current | Kept. No methodology bump is needed: staleness is tracked by `company_compute_state` (§2.2), not by version. | No drift |

Boundary note (not drift, stated so nobody re-litigates it): `FinancialMetric` stays **the** metric store that Phases 2–5
(peers, valuation, score, thesis) read through `IndustryRepository.latest_metric_values`. The bridge sits *upstream*
of it — it changes where metrics come from, not how downstream phases read them.

---

## 1. M1 — Bridge: engines read approved statement lines

### 1.1 Ruling: statement lines are the only fundamentals input

- Engines (metrics, DQ `financial_statements`, Shariah, purification, fair value, score, thesis) read **only**
  `StatementLineRepository.latest_approved(company_id)` — approved/auto_validated, one winner per
  `(period_id, ontology_code)`, filing beats vendor, then newest `published_date`, then newest `created_at`
  (already implemented, unchanged).
- The `FinancialFact` path (`MetricService._get_facts_dict`, `POST /screening/.../screen`) is **removed from every compute path**.
  Not "alongside": with 0 fact rows, a second path is dead code that can only produce conflicting snapshots.
  `financial_facts` stays as a table (Phase-7 disclosure facts, `/api/financial/*`, comparison/diffs) — those
  surfaces keep working but **do not feed engines**. Getting parsed disclosure numbers into engines = record them
  through the intake (`POST /statements/manual-filings`), which makes them filing-tier lines. (Carry-forward, not R43.)
- **One coherent period per computation.** "Latest period" = the ANNUAL `FinancialPeriod` with the greatest
  `end_date` that has ≥ 1 winner line. A code missing in that period is INSUFFICIENT_DATA — **never** borrowed from an
  older period. "Prior period" = same `period_type`, `fiscal_year − 1`; absent ⇒ growth/averaging metrics INSUFFICIENT.
  (Replaces `statement_input._latest_period_lines`, which picks by `published_date` — null for every vendor line — and
  then falls back to "most lines", i.e. possibly an older year.)
- v1 is ANNUAL-only (the DB holds only ANNUAL periods). Interim periods are ignored by the bridge, not mixed in.

### 1.2 Ontology 1.1 + vendor map 1.1 (additive; required by R43 open note 2)

Without a share count no per-share number, market cap, P/E, BVPS or DPS can exist; without interest income the
Shariah impure-income rule is INSUFFICIENT for every company, so no verdict can ever be COMPLIANT. Both are present
in the vendor files already on disk, so this is mapping, not estimation.

`app/statements/ontology.py` → `STATEMENT_ONTOLOGY_VERSION = "stmt-ontology-1.1"`; `StatementLine` gains a defaulted
field `unit: Literal["currency", "shares", "currency_per_share"] = "currency"` (NamedTuple default — existing
constructors unchanged). `eps` gets `unit="currency_per_share"`.

| New code | Section | label_en | label_ar | unit | Vendor field (`stockanalysis-map-1.1`) | Files carrying it |
|---|---|---|---|---|---|---|
| `interest_income` | income | Interest income | إيرادات الفوائد | currency | `income.interestIncome`; if absent for that period, `income.interestIncomeTotalBank` (first present wins, never both) | 178 (+12 bank) |
| `weighted_avg_shares_basic` | income | Weighted average shares (basic) | المتوسط المرجح لعدد الأسهم | shares | `income.sharesBasic` | 212 |
| `shares_outstanding` | balance | Shares outstanding | عدد الأسهم القائمة | shares | `balance.sharesOutTotalCommon` | 212 |

- `VENDOR_MAPPING_VERSION = "stockanalysis-map-1.1"`; transforms `AS_REPORTED` (all three are positive in the files
  checked: ABUK, COMI).
- Validator (`stmt-validator-1.0` → `1.1`): the three new codes get the non-negative sign rule; nothing else changes.
  `eps` stays passthru (held) — the bridge derives EPS instead (§1.3), matching the `RatioService` precedent.
- `currency` column on a `shares` line holds the filing's reporting currency (column semantics = "currency of the
  filing"); readers must use `unit`, never `currency`, to format it.
- `StatementLineRead` (statements API) gains `unit: str`. `ManualFilingBody.lines` max length follows
  `len(STATEMENT_LINES)` automatically.
- Re-running `python -m app.statements.vendor_import` on the dev DB is a **router data operation at M5**, not a
  staff-backend action (it writes the dev DB).

### 1.3 The bridge module (new): `backend/app/statements/bridge.py`

Single owner of "ontology code → engine input". Pure functions over a loaded bundle; one async loader.

```python
BRIDGE_VERSION = "stmt-bridge-1.0"
SourceTier = Literal["filing", "vendor"]

@dataclass(frozen=True, slots=True)
class LineValue:
    code: str
    value: Decimal                 # never None: a null-valued winner is treated as missing
    line_id: uuid.UUID
    period_id: uuid.UUID
    fiscal_year: int
    period_end: date               # FinancialPeriod.end_date
    source_tier: SourceTier        # vendor iff extraction_method == vendor_aggregator
    document_id: uuid.UUID | None
    document_type: str | None
    document_url: str | None
    source_label_reported: str | None
    source_page: str | None
    published_date: date | None

@dataclass(frozen=True, slots=True)
class PeriodLines:
    period_id: uuid.UUID
    fiscal_year: int
    period_type: str
    period_end: date
    lines: Mapping[str, LineValue]
    def get(self, code: str) -> LineValue | None: ...

@dataclass(frozen=True, slots=True)
class Resolved:
    value: Decimal | None
    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    reason: str | None             # human, names the line: "missing statement line: total_equity (FY2024)"
    missing_input: str | None      # machine: "total_equity"
    sources: tuple[LineValue, ...] # every line that fed the value
    derivation: str | None         # e.g. "net_income / weighted_avg_shares_basic"; None = straight line

@dataclass(frozen=True, slots=True)
class CompanyStatements:
    company_id: uuid.UUID
    periods: tuple[PeriodLines, ...]          # ANNUAL only, newest period_end first
    def latest(self) -> PeriodLines | None: ...
    def prior(self, p: PeriodLines) -> PeriodLines | None: ...        # fiscal_year - 1, same type
    def years_back(self, p: PeriodLines, n: int) -> PeriodLines | None: ...
    def series(self, code: str) -> list[LineValue]: ...                # oldest -> newest

async def load_company_statements(session: AsyncSession, company_id: uuid.UUID) -> CompanyStatements
def line(p: PeriodLines | None, code: str) -> Resolved
def provenance(lv: LineValue) -> dict[str, str | None]   # see §1.4
def tier_of(sources: Iterable[LineValue]) -> SourceTier | None   # "vendor" if any vendor, "filing" if all filing, None if empty
```

Derived values (pure, each returns `Resolved` with `derivation` set; INSUFFICIENT on missing/zero/negative denominator):

| Function | Formula | Status |
|---|---|---|
| `capex_magnitude(p)` | `abs(capex)` (vendor stores capex negative; metrics/FCF assume a positive spend) | exact |
| `free_cash_flow(p)` | `cfo − abs(capex)` | exact (same formula as metric `free_cash_flow`) |
| `eps(p)` | `eps` line if it is a winner, else `net_income / weighted_avg_shares_basic` | exact (RatioService precedent) |
| `book_value_per_share(p)` | `total_equity / shares_outstanding` | exact |
| `revenue_per_share(p)` | `revenue / shares_outstanding` | exact |
| `long_term_liabilities(p)` | `total_liabilities − current_liabilities` | exact |
| `dps(p)` | `abs(dividends_paid) / shares_outstanding` — cash paid **in** the fiscal year | **derived; ANALYST GATE (D-6)** |

Not mapped in v1 (left `None` ⇒ the consuming check is NOT_RUN / leg INSUFFICIENT; no proxies):
`ebit` (no EBIT line; `operating_profit` ≠ EBIT), `net_interest_expense` (`finance_costs` is gross), ROCE, bank-track
inputs (allowance, NPL, deposits, net loans, charge-offs), `prepaid_expenses`, short-term investments (Shariah keeps
the zborsa-Task-8 mapping `cash_and_securities = cash_and_equivalents`; extending it is a Shariah-methodology change,
out of scope), industry/market averages.

### 1.4 Provenance shape (every M1 number)

One shape everywhere a statement-derived number is served (AC-4):

```json
{
  "code": "total_equity",
  "value": "15234000000.0000",
  "line_id": "uuid",
  "fiscal_year": 2024,
  "period_end": "2024-12-31",
  "source_tier": "vendor",
  "provisional": true,
  "document_type": "VENDOR_ANNUAL_STATEMENTS",
  "document_url": "https://stockanalysis.com/quote/egx/COMI/financials/",
  "source_label_reported": "Total Common Equity",
  "source_page": null,
  "published_date": null
}
```

Summary rule for a computed value / snapshot: `source_tier = tier_of(all lines used)`; `provisional = (source_tier == "vendor")`;
`period_end` = the latest period's end date used. UI rule: `provisional === true` ⇒ show "Provisional (vendor data)".

### 1.5 Per-engine mapping

#### Metrics (`MetricService.calculate_from_statements(bundle) -> list[MetricCalculationOutput]`)

Inputs are passed **explicitly per metric** (replace the `inspect.signature` mapper). Two latent bugs found and fixed by
this ruling (probed with the real `_prepare_calculation_input`):
- growth metrics never receive `current_revenue` / `current_net_income` / `current_eps` ⇒ `TypeError` ⇒ always INVALID;
- ROA's `current_assets` parameter picks up the **current-assets** fact when one exists, and `previous_assets` /
  `previous_equity` look up `"assets"` / `"equity"` (prefix-strip) ⇒ ROE/ROA never average.

| Metric (code, unit unchanged) | Calculator kwargs ← bridge |
|---|---|
| revenue_growth_yoy | current_revenue ← `revenue`(p); previous_revenue ← `revenue`(prior) |
| net_income_growth_yoy | current/previous_net_income ← `net_income` |
| eps_growth_yoy | current/previous_eps ← `eps()` (derived allowed) |
| gross_margin | gross_profit ← `gross_profit`; revenue ← `revenue` |
| operating_margin | operating_income ← `operating_profit`; revenue |
| net_margin | net_income; revenue |
| roe | net_income; current_equity ← `total_equity`(p); previous_equity ← `total_equity`(prior) (None allowed → spot) |
| roa | net_income; current_assets ← **`total_assets`**(p); previous_assets ← `total_assets`(prior) |
| debt_to_equity | total_debt ← `interest_bearing_debt`; total_equity |
| debt_to_assets | total_debt ← `interest_bearing_debt`; total_assets |
| current_ratio | current_assets; current_liabilities |
| quick_ratio | current_assets; current_liabilities; inventory (None allowed) |
| operating_cash_flow_margin | operating_cash_flow ← `cfo`; revenue |
| free_cash_flow | operating_cash_flow ← `cfo`; capex ← `capex_magnitude()` |
| free_cash_flow_margin | same + revenue |
| eps | eps_basic ← `eps()` |
| book_value_per_share | total_equity; shares_outstanding ← `shares_outstanding`(p) |

- Computed for **every** ANNUAL period with lines (history powers the score's 5-year checks and the thesis).
- Missing required input ⇒ `INSUFFICIENT_DATA`, `reason = "missing statement line: <code> (FY<year>)"`; missing prior ⇒
  `"no prior period: FY<year−1> has no <code>"`. Zero/negative denominators keep the engine's existing statuses.
- Persist (replace, §2.3): one `financial_metrics` row per (company, period, metric_code, formula_version) with new
  columns `source_tier`, `provisional`; one `financial_metric_inputs` row per input line (`statement_line_id`,
  `input_role` = calculator kwarg name).
- Fix in the same change: `IndustryRepository.latest_metric_values` orders by **period `end_date` desc**, then
  `calculated_at` desc (today it orders by `calculated_at` only, so after a batch write "latest" is an arbitrary
  period). Joins `FinancialPeriod` on `period_id`. Consumers (peers, score, fair value, thesis) are unchanged.
- `METRICS_INPUT_VERSION = "metrics-stmt-1.0"` (compute-state version; each metric keeps its `formula_version`).

#### Data quality — `financial_statements` scope (`DataQualityService._assess_financial_statements`)

Same `score_for(...)` call and pinned constants; inputs change:

| score_for arg | ← |
|---|---|
| `present` / `required` | `CRITICAL_FACT_LABELS` mapped to codes `revenue, net_income, total_assets, total_equity, cfo`, present in the latest period |
| `observed` / `expected_depth=8` | number of ANNUAL periods with ≥ 1 winner line |
| `days_stale` | `as_of − max(published_date of latest-period winners)`; when none has a published date, `as_of − period_end` of the latest period, and the freshness component `reason` says `"no publication date (vendor data); measured from period end 2024-12-31"` |
| `errors` / `warnings` | rejected / extraction_candidate lines of the latest period |
| `source_type` | lowest-reliability `DataSource.source_type` among the latest period's winner documents (vendor ⇒ `DATA_PROVIDER` = 75) |
| `no_rows` | no winner lines at all |

R14 as-of bound: lines with `published_date > as_of` are excluded; null published dates are included for a live
`as_of` (today). This is not used for backtests (vendor lines cannot be dated; backtesting fundamentals stays out).

#### Shariah — canonical engine = statement lines

`build_screening_input_from_statements(company, statements: CompanyStatements) -> ScreeningInput` (signature changes;
**never returns None for partial data** — missing inputs go in as `None` and each rule reports its own
INSUFFICIENT_DATA with `missing_input`, AC-3). Only "no statements at all" yields a verdict of INSUFFICIENT_DATA with
`overall_reason = "no approved statement lines"`.

| ScreeningInput | ← latest period |
|---|---|
| total_debt | `interest_bearing_debt` |
| total_assets | `total_assets` |
| interest_income | `interest_income` (new in 1.1) |
| total_revenue | `revenue` |
| cash_and_securities | `cash_and_equivalents` |
| industry | `company.industry` (null for all 234 today ⇒ `industry_screen` INSUFFICIENT — §6 D-9) |
| provenance | per rule: `RuleProvenance(source, source_date)`; `source = "<tier>: <document_type> FY<year> (period end <date>)[, p.<page>]"`, `source_date = published_date` (None for vendor) |

- Methodology unchanged (`aaoifi-assets-spot/33-33-5`, spot total-assets denominator). R43 open note 2 is moot for this
  methodology: **no v2 rule is market-cap-denominated**. If a future methodology adds one, it needs
  `price × shares_outstanding` and returns UNKNOWN without both.
- `report_date_reason` for vendor-only inputs: `"vendor data has no publication date; period end <date>"`.
- `POST /screening/companies/{id}/screen` (FinancialFact engine) and `/screen-statements` both go away (§3.3).
- Fix in the same change: re-screening appends rule rows without deleting old ones (`ScreeningRepository.add_rule_result`
  after an upsert). Recompute deletes the result's existing `screening_rule_results` before inserting.

#### Purification — automatic per-share estimate

`estimate_dividend_purification(ticker, is_compliant=<shariah verdict>, dps=dps(p).value, shares_held=Decimal(1),
non_permissible_revenue=interest_income, total_revenue=revenue, ratio_provenance=<lines>, dps_source=<derivation +
lines>, dps_date=period_end)`. Result is **EGP per share**. Missing DPS / interest income / revenue ⇒ INSUFFICIENT_DATA
with the existing `missing_input` naming the line. Ratio = the same impure-income ratio the screen's
`interest_income_ratio` rule uses; `ratio_provenance` must say "interest income only (other impure-income lines are
not in the statement ontology)". The "shares held" calculator is OUT (R43 #6). **ANALYST GATE (D-6)** on DPS
derivation and on interest-income-only as the purification numerator.

#### Fair value — inputs from bridge + sourced assumption record

`FairValueService` is split (this is required, not cosmetic — see "found" below):
- `compute(company_id, inputs: FairValueInput) -> dict[str, Any]` — pure, **never persists**;
- `snapshot(company_id) -> dict[str, Any]` — resolves inputs (below), calls `compute`, upserts the snapshot;
- `latest_payload(company_id) -> dict[str, Any] | None` — serves the stored snapshot row.

Found: `ThesisService._per_scenario_sensitivity` calls `fair_value()` once per scenario and each call **overwrites the
fair-value snapshot** (the stored snapshot ends up being the bull-centred rerun); `StanceService._scenario_targets` also
recomputes and persists on every stance read. Both must use `compute` (no persist) / `latest_payload`.

| FairValueInput field | ← |
|---|---|
| free_cash_flow, affo/ffo fallback | `free_cash_flow(latest)` |
| growth_rate / revenue_growth | metric `revenue_growth_yoy` (fraction) — already resolved this way |
| operating_margin | metric `operating_margin` — already |
| stable_roe | metric `roe` — already |
| earnings_per_share | `eps(latest)` |
| book_value_per_share | `book_value_per_share(latest)` |
| revenue_per_share | `revenue_per_share(latest)` |
| shares_outstanding | `shares_outstanding(latest)` (replaces the always-null `companies.shares_outstanding`) |
| expected_dps | `None` (historical DPS is not an *expected* DPS; DDM fallback leg stays INSUFFICIENT) |
| discount_rate, terminal_growth_rate, stable_growth | **valuation assumption record** (§1.6) |
| pe_ratio (target) and exit_multiple | assumption key `target_pe`; ps_ratio ← `target_ps`; pb_ratio ← `target_pb` |

With no sourced assumption the intrinsic and relative legs are INSUFFICIENT_DATA with
`reason = "no sourced <key> in valuation assumptions <methodology_version>"` (R43 open note 1, AGENTS rule 5). Caller
overrides disappear (GET query params removed, §3.2). `input_sources` values become provenance strings, e.g.
`"statement:cfo,capex FY2024 (vendor)"`, `"assumption:discount_rate market as_of 2026-10-01"`, `"metric:roe FY2024"`.
`VALUATION_METHODOLOGY_VERSION` stays `"1.0"` (no constant changes).

#### Investment score — `ScoreService.assess(company_id)` resolves from bridge + metrics + FV snapshot

`overrides` parameter is removed (no caller inputs). Inputs that can now run (others stay `None` ⇒ NOT_RUN):

| ScoreInputs | ← |
|---|---|
| current_price / fair_value | latest close / fair-value snapshot (unchanged) |
| eps_now, eps_5y_ago | `eps()` on latest / `years_back(latest, 5)` |
| eps_growth_1y, eps_growth_now | metric `eps_growth_yoy` (fraction) — fallback unchanged |
| eps_growth_5y_avg | arithmetic mean of available yearly `eps_growth_yoy` over the last 5 periods; needs ≥ 3 values else None |
| roe_now, roa_now | metrics `roe`, `roa` (fraction) |
| st_assets, st_liabilities | `current_assets`, `current_liabilities` |
| lt_liabilities | `long_term_liabilities()` |
| de_ratio_now, de_ratio_5y_ago | metric `debt_to_equity` on latest / 5 periods back |
| operating_cash_flow | `cfo` |
| total_debt | `interest_bearing_debt` |
| total_assets, total_equity | lines |
| dps_history, dividend_years | `dps()` per period (oldest→newest), count of periods with a DPS — **D-6 gate** |
| earnings_payout | `dps / eps` latest — **D-6 gate** |
| hist_earnings_growth, hist_revenue_growth | metrics `eps_growth_yoy`, `revenue_growth_yoy` (as today) |
| pe_ratio, pb_ratio | `price / eps`, `price / bvps` (exact; price as-of echoed) |
| market/industry averages, roce, ebit, net_interest_expense, bank_* | None (NOT_RUN) |

`inputs_echo.sources` gains `"statements": [provenance…]` for every line used. `SCORE_METHODOLOGY_VERSION` stays `"1.0"`.
Expected effect: past, health and growth components each reach ≥ 3 runnable checks ⇒ a headline exists for most names.

#### Thesis — automatic assess

`ThesisService.assess` is called by recompute with:
`horizon_years = DEFAULT_HORIZON_YEARS`, `is_shareholder = None`, `fv` = (not used — reads the FV snapshot via
`FairValueService.latest_payload`; per-scenario sensitivity via `compute`), and **assumptions / bulls / bears /
invalidations / catalysts carried over from the stored thesis row** (empty on first assess ⇒ methodology-default
invalidations via `pad_invalidation_specs`). Auto re-assess must never erase what an admin "documented update" wrote.
Ledger: the `"assessed"` row's rationale is prefixed `"Automatic recompute (<trigger>)"`; one row per recompute, and a
recompute only happens when inputs changed (§2.2), so the ledger grows only with real input changes.

#### Technical

`TechnicalService.calculate_indicators` unchanged; input = stored `DailyPrice` closes/volumes/highs/lows for the
company, ascending, **all bars ≤ latest price date** (same lookback the client used to send: the full stored series).
`TECHNICAL_METHODOLOGY_VERSION = "technical-1.0"` (new constant, compute-state only).

### 1.6 Valuation assumption record (new): `backend/app/valuation/assumptions.py` + table `valuation_assumptions`

Versioned, sourced, empty by default — **no seed values, no constants in code**.

| Column | Type | Note |
|---|---|---|
| id | UUID PK | |
| methodology_version | String(20) | = `VALUATION_METHODOLOGY_VERSION` |
| key | String(40) | one of `discount_rate`, `terminal_growth_rate`, `stable_growth`, `target_pe`, `target_pb`, `target_ps` |
| scope | String(50) | `"market"` or a valuation `profile_key` (`banks`, `real_estate`, `industrials`, `default`) |
| value | Numeric(12,6) | fractions for rates (0.25 = 25%), plain multiples for targets |
| source_url | String(500) NOT NULL | must start with `http` |
| source_title | String(255) NOT NULL | |
| as_of | Date NOT NULL | |
| note | Text NULL | |
| recorded_at | timestamptz, server default now() | |

`uq_valuation_assumption (methodology_version, key, scope, as_of)`, `ix_valuation_assumptions_key`.
Resolution: profile-scoped beats `market`; newest `as_of ≤ today`; nothing found ⇒ None (leg INSUFFICIENT).
`resolve_assumptions(session, profile_key) -> AssumptionSet(items: dict[key, AssumptionItem], stamp: str)`.

CLI (the only writer; mirrors the EGX33 CLI precedent, no UI):
```
python -m app.valuation.assumptions set --key discount_rate --scope market --value 0.24 \
    --source-url https://… --source-title "…" --as-of 2026-10-01 [--note …] [--no-recompute]
python -m app.valuation.assumptions list
```
`set` triggers `recompute_many(all companies, engines={fair_value, score, thesis}, trigger="assumptions")` unless
`--no-recompute`. Who sources the numbers is a router action (§6, D-8): until a row exists, fair value is
INSUFFICIENT_DATA for every company and AC-9 must say so.

---

## 2. M2 — Recompute service

### 2.1 Module and public interface: `backend/app/services/recompute.py`

```python
class Engine(StrEnum):
    DQ_FS = "data_quality_fs"; DQ_PH = "data_quality_ph"; METRICS = "metrics"; SHARIAH = "shariah"
    PURIFICATION = "purification"; TECHNICAL = "technical"; FAIR_VALUE = "fair_value"; SCORE = "score"; THESIS = "thesis"

class Trigger(StrEnum):
    STATEMENT_IMPORT = "statement_import"; PRICE_SYNC = "price_sync"; FIRST_VIEW = "first_view"
    ASSUMPTIONS = "assumptions"; BACKFILL = "backfill"

ENGINE_ORDER: tuple[Engine, ...] = (DQ_FS, DQ_PH, METRICS, SHARIAH, PURIFICATION, TECHNICAL, FAIR_VALUE, SCORE, THESIS)

DEPENDS_ON: dict[Engine, tuple[Engine, ...]] = {
    DQ_FS: (), DQ_PH: (), METRICS: (), TECHNICAL: (),
    SHARIAH: (), PURIFICATION: (SHARIAH,),
    FAIR_VALUE: (METRICS, DQ_FS, DQ_PH),
    SCORE: (METRICS, FAIR_VALUE, DQ_FS, DQ_PH),
    THESIS: (METRICS, FAIR_VALUE, SCORE, DQ_FS, DQ_PH),
}
OWN_INPUTS: dict[Engine, frozenset[str]]   # subset of {"statements", "prices", "company", "assumptions"}
    # DQ_FS, METRICS: statements | DQ_PH, TECHNICAL: prices | SHARIAH: statements, company
    # PURIFICATION: statements, company | FAIR_VALUE: statements, prices, company, assumptions
    # SCORE, THESIS: statements, prices, company
ENGINE_VERSION: dict[Engine, str]          # read from each engine's own constant (never duplicated literals)

@dataclass(frozen=True, slots=True)
class InputStamps:
    statements: str        # md5 over calc-status lines: id:value:ext_status, ordered by id ('' when none)
    prices: str            # "<max date>:<close at max date>" ('' when none)
    company: str           # industry|egx_sector_id|gics_sub_industry_id
    assumptions: str       # ids of resolved assumption rows ('' when none)
    price_as_of: date | None

@dataclass(frozen=True, slots=True)
class EngineOutcome:
    engine: Engine
    status: Literal["computed", "fresh", "failed"]
    error: str | None

@dataclass(frozen=True, slots=True)
class RecomputeReport:
    company_id: uuid.UUID
    trigger: Trigger
    outcomes: tuple[EngineOutcome, ...]

class RecomputeService:
    def __init__(self, session: AsyncSession) -> None
    async def stamps(self, company_id: uuid.UUID) -> InputStamps
    async def stale(self, company_id: uuid.UUID, engines: Collection[Engine]) -> list[Engine]   # upstream closure, ENGINE_ORDER
    async def recompute_company(self, company_id: uuid.UUID, trigger: Trigger,
                                engines: Collection[Engine] | None = None, force: bool = False) -> RecomputeReport
    async def ensure_fresh(self, company_id: uuid.UUID, engine: Engine) -> ComputeState   # the first-view hook

async def recompute_many(company_ids: Sequence[uuid.UUID], trigger: Trigger,
                         engines: Collection[Engine] | None = None,
                         session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] = ...) -> BatchReport
async def after_statement_import(company_ids: Sequence[uuid.UUID]) -> BatchReport     # engines: all except TECHNICAL, DQ_PH
async def after_price_sync(company_ids: Sequence[uuid.UUID]) -> PriceSyncRecompute       # §2.4
```

`BatchReport = {companies: int, computed: dict[Engine, int], fresh: int, failed: int, failed_companies: list[{ticker, engine, error}] (≤ 20)}`.

### 2.2 Staleness rule and idempotency (one snapshot per company + methodology_version)

New table `company_compute_state` (migration 023):

| Column | Type |
|---|---|
| id | UUID PK |
| company_id | UUID FK companies.id **ON DELETE CASCADE** |
| engine | String(32) |
| methodology_version | String(64) |
| inputs_fingerprint | String(64) (sha256 hex) |
| status | String(16) — `ok` / `failed` |
| trigger | String(32) |
| calculated_at | timestamptz |
| price_as_of | Date NULL |
| period_end | Date NULL |
| source_tier | String(10) NULL — `filing` / `vendor` |
| provisional | Boolean NOT NULL default false |
| error | Text NULL |

`uq_company_compute_state (company_id, engine, methodology_version)`, `ix_company_compute_state_company_id`.

- `fingerprint(E) = sha256(E, ENGINE_VERSION[E], stamps of OWN_INPUTS[E], fingerprint(dep) for dep in DEPENDS_ON[E])`.
- **Stale** ⇔ no row for (company, E, current version) **or** stored fingerprint ≠ current fingerprint. A `failed` row
  stores the fingerprint it failed on, so it is *not* retried on every GET; it retries when inputs change, on
  `--force`, or after a version bump. (Deploying a bug fix = `python -m app.services.recompute --all --force`.)
- Fingerprints make the first-view hook catch **any** writer (vendor CLI, intake, approve/reject, pipeline, a forgotten
  hook) without timestamps — the triggers below exist only to keep snapshots warm (AC-5/AC-6).
- **Concurrency:** `recompute_company` and a stale `ensure_fresh` take
  `SELECT pg_advisory_xact_lock(hashtextextended('recompute:' || :company_id, 0))`, then **re-check** staleness
  (double-checked) — the company page's parallel GETs serialize and the second one finds fresh state.
- **Atomicity:** each engine runs inside `session.begin_nested()` (SAVEPOINT). On exception: rollback to the savepoint,
  write the state row `status=failed, error=<type: msg>`, continue with engines that don't depend on it (dependents of a
  failed engine are marked failed with `error="upstream failed: <engine>"`). The request is never 500'd by a compute error.
- **Replace semantics:** metrics (delete company's rows for current formula versions, insert), technical (delete
  company's rows, insert one set), screening rule rows (delete for the result, insert). Fair value / score / thesis /
  screening result / purification already upsert on `(company_id, methodology_version)`.
- A company with no inputs still computes (snapshot with INSUFFICIENT_DATA reasons) — so `assessment: null` /
  404 "never assessed" disappear for known companies (AC-7). Second GET with no new inputs = `fresh`, no writes.

### 2.3 Inline, not queued — and why

Ruling: **inline** in the caller's process; no queue, no worker, no scheduler.
- Single user, ~230 companies, one Postgres. Per-company compute is pure Python over ≤ ~150 lines and ≤ ~1,000 bars;
  the heaviest engine (fair value: base + 3 scenarios + 8 sensitivity reruns of a closed-form pipeline) is
  milliseconds. Target budget: **≤ 1 s per company for all engines** — staff-backend measures it in M5 and reports it.
- Bulk paths (vendor import of 203 companies, price sync of ~230) already run as a CLI or as the in-process job with a
  1,800 s bound; adding ≤ ~4 min is inside it. They use one session per company and commit per company
  (the `_assess_all_companies` pattern), so a failure loses one company, not the batch.
- A queue would add a job table, a worker process and an eventual-consistency UI state ("computing…") for no benefit
  at this scale. Cost if wrong: if a company ever takes > 2 s, the first-view GET is slow once; the fix is to move that
  engine's bulk path earlier, not to add a queue.
- **Batch surfaces never compute.** Stance radar, Recommendations, Rankings, Companies overview, `/screening/companies`
  list read snapshots only (warm from the triggers + backfill). Only per-company GETs call `ensure_fresh`.

### 2.4 The three hooks (exact call sites)

**After statement import** (engines: DQ_FS, METRICS, SHARIAH, PURIFICATION, FAIR_VALUE, SCORE, THESIS — only stale ones run):

| Writer | Hook |
|---|---|
| `python -m app.statements.vendor_import` | `import_payload` records `company.id` into `ImportSummary.company_ids`; after the commit, `main()` runs `after_statement_import(summary.company_ids)` and prints the `BatchReport`. New flag `--no-recompute`. |
| `POST /api/statements/manual-filings` | after `record_manual_filing`, in the same transaction before commit: `RecomputeService(session).recompute_company(company_id, Trigger.STATEMENT_IMPORT)`. Response adds `"recompute": RecomputeReport` (shape §3.4). |
| `POST /api/statements/lines/{id}/approve` and `/reject` | same, for `line_row.company_id` (reject changes the approved set when the line was auto_validated). Response model gains `recompute`. |
| `StatementPipeline.process_document` | no hook (not wired to any entry point); first-view catches it. |

After a statement-triggered recompute in the API process: `stance_cache.clear()`.

**After price sync** — `after_price_sync(company_ids)` is called by **both** `ingestion/jobs.py::_run_phases` (new
phase `"recompute"` after `"assessment"`) and the sync CLI `sync_prices` (new flag `--no-recompute`). Steps, in order:
1. TECHNICAL for each synced company (`recompute_many(..., engines={TECHNICAL})`);
2. `SignalEngine(session).run(persist=True)` once (universe-wide; skipped with a recorded reason if no price data);
3. FAIR_VALUE, SCORE, THESIS for synced companies (DQ_PH is already fresh from the assessment phase; the DAG re-checks);
4. `stance_cache.clear()`.

Job status gains `recompute` (AC-6 per-step counts):
```json
"recompute": {
  "technical":  {"computed": 199, "fresh": 0, "failed": 0},
  "signals":    {"ran": true, "as_of": "2026-10-22", "scored": 186, "error": null},
  "fair_value": {"computed": 199, "fresh": 0, "failed": 0},
  "score":      {"computed": 199, "fresh": 0, "failed": 0},
  "thesis":     {"computed": 199, "fresh": 0, "failed": 0},
  "failed_companies": [{"ticker": "XXXX", "engine": "score", "error": "ValueError: …"}]
}
```
`phase` enum gains `"recompute"`; `recompute` is `null` until that phase completes.

**On first view** — each per-company GET (§3.1) calls `RecomputeService(session).ensure_fresh(company_id, <engine>)`
before reading; `get_session` commits on success (same pattern the fair-value GET already uses).

**Backfill CLI:** `python -m app.services.recompute [--all | TICKER ...] [--engines a,b] [--force]` (trigger `backfill`),
prints the `BatchReport`. Router runs `--all` once at M5 after the vendor re-import.

**Coverage report (AC-9, read-only):** `python -m app.services.coverage_report` prints, over companies with ≥ 1 winner
line and ≥ 1 price bar: per-engine `% non-null headline` (metrics: ≥ 1 AVAILABLE metric in latest period; fair value:
`fair_value.value`; score: `headline.value`; Shariah: verdict distribution COMPLIANT / NON_COMPLIANT / INSUFFICIENT_DATA;
purification: OK share; technical: ≥ 1 AVAILABLE indicator; thesis: assessment present), `% provisional`, and the top 5
INSUFFICIENT reasons per engine. Stance before/after: `python -m app.signals.sanity` (existing).

---

## 3. API contract changes

### 3.1 GET endpoints that compute on read

Every payload below gains the **compute meta block**, merged at the top level of object payloads and per row of array
payloads (array payloads stay arrays — non-breaking for existing consumers):

```json
{
  "calculated_at": "2026-10-23T12:00:00+00:00",
  "methodology_version": "…",
  "trigger": "first_view",
  "compute_status": "ok",
  "source_tier": "vendor",
  "provisional": true,
  "period_end": "2024-12-31",
  "price_as_of": "2026-10-22"
}
```
(`compute_status: "failed"` ⇒ the last good snapshot is served if one exists, plus `compute_error: string`; otherwise the
engine's INSUFFICIENT_DATA payload with `reason = "computation failed: …"`. Existing `computed_at` fields stay.)

| Endpoint | ensure_fresh | Shape change |
|---|---|---|
| `GET /api/metrics/companies/{id}` (+ `/periods/{pid}`, `/periods/{pid}/{code}`) | METRICS | Array rows add `fiscal_year`, `period_type`, `period_end`, `source_tier`, `provisional`, `methodology_version: "metrics-stmt-1.0"`, `inputs: Provenance[]` (+ `input_role`). Detail `provenance[]` items become `{statement_line_id, input_role, …Provenance}` (no `fact_id`). |
| `GET /api/valuation/companies/{id}/fair-value` | FAIR_VALUE | **19 query params removed** (FastAPI ignores extras, so old clients don't break). Serves the snapshot (`latest_payload`). Adds meta block and `assumptions: {methodology_version, items: [{key, scope, value, source_url, source_title, as_of}], missing: [key…]}`. `input_sources` values are provenance strings (§1.5). |
| `GET /api/scores/companies/{id}` | SCORE | `assessment` is non-null for every known company (null only when compute failed and no snapshot exists). Meta block top-level. `assessment.inputs_echo.sources.statements: Provenance[]`. |
| `GET /api/screening/companies/{id}` | SHARIAH | **No more 404 for a known company.** Meta block; `engine: "statement_lines"`; rule `source` strings per §1.5; `is_compliant: boolean \| null` (null = INSUFFICIENT_DATA, labelled "Unknown" in UI). |
| `GET /api/screening/companies/{id}/purification` | PURIFICATION | **No more 404.** Adds `basis: "per_share"` (amount_egp and dividend_egp are EGP per share), `dps_derivation: "abs(dividends_paid) / shares_outstanding"`, meta block. |
| `GET /api/technical/companies/{id}` | TECHNICAL | Returns **only the latest set** (today it returns every historic row). Rows add `price_as_of`, `methodology_version: "technical-1.0"`. |
| `GET /api/theses/companies/{id}` | THESIS | `assessment` non-null for known companies. `assessment` adds `horizon_source: "methodology_default"`. Meta block top-level. |
| `GET /api/stance/companies/{ticker}` | SCORE (pulls FAIR_VALUE upstream) | none; stance reads `FairValueService.latest_payload` instead of recomputing. |
| `GET /api/data-quality/companies/{id}` | — (job + DQ engines keep it fresh) | none (row source change only, §1.5). |
| `GET /api/statements/companies/{ticker}/statements` | — | lines add `unit`. |

Unchanged read-only: `/api/stance/radar`, `/api/signals*`, `/api/companies/overview`, `/api/screening/companies`
(list), `/api/statements/.../ratios`, `/api/industry/companies/{id}` (values change because `latest_metric_values`
now means latest period).

### 3.2 Removed routes (write paths that bypass compute state)

R43 lists retirement as optional; for these routes it is **required**, because each writes the same snapshot rows the
automatic engine owns with caller-supplied numbers, and the fingerprint would then keep serving the caller's numbers
as "computed":

| Route | Why it must go |
|---|---|
| `POST /api/technical/companies/{id}/calculate` | client-sent prices land in `technical_indicators`; GET would serve them |
| `POST /api/valuation/companies/{id}/calculate` (+ `GET /api/valuation/companies/{id}` legacy per-model list, `valuation_results` table untouched) | 12 hand-typed inputs; the per-model table leaves user screens (R43 #1) |
| `POST /api/metrics/companies/{id}/calculate` and `/periods/{pid}/calculate` | FinancialFact path (0 rows) would overwrite statement-derived metrics |
| `POST /api/scores/companies/{id}/assess` | caller overrides overwrite the score snapshot |
| `POST /api/theses/companies/{id}/assess` | caller inputs + FV reruns overwrite FV and thesis snapshots |
| `POST /api/screening/companies/{id}/screen` and `/screen-statements` | legacy engine / duplicate of the recompute path |
| `POST /api/screening/companies/{id}/purification` | shareholder calculator is OUT; GET is automatic |

Their tests are deleted or rewritten as GET-based tests (AC-2/3/5/7). `ScoreAssessBody`, `ThesisAssessBody` and the
valuation `ValuationInput` NamedTuple go with them if nothing else imports them (mypy will say).

### 3.3 Kept, now admin-only by convention (no auth change — R43: grouping, not a security boundary)

| Route | Admin surface |
|---|---|
| `GET /api/statements/intake`, `POST /api/statements/manual-filings` | `/admin/intake` |
| `POST /api/disclosures/register`, `POST /api/disclosures/upload`, `POST /api/disclosures/filings/{id}/parse` | `/admin/companies/:ticker` |
| `PUT /api/industry/companies/{id}/peers` | `/admin/companies/:ticker` |
| `POST /api/theses/companies/{id}/update` | `/admin/companies/:ticker` (404 "assess first" becomes unreachable: GET auto-assesses — the admin page loads `GET /theses/…` first) |
| `POST /api/ingestion/sync`, `GET /api/ingestion/sync/status` | `/admin` |
| `POST /api/screening/companies/{id}/egx-membership` | none — CLI `python -m app.screening.egx33` (R42); route kept, unused by UI |
| `POST /api/signals/run` | none — runs inside the price-sync job; route kept, unused by UI |
| `POST /api/disclosures/facts`, `/api/ai/*` | untouched, unused by UI |

`POST /api/disclosures/upload` change (R43 #11 "parse auto-runs after upload"): new form field `auto_parse: bool = True`;
after storing bytes it calls `DisclosureService.parse_filing(filing.id, <ParseBody defaults>)` and returns
`{"filing": …, "created": bool, "parse": <parse payload> | {"status": "failed", "reason": str} | null}`. A parse failure
never fails the upload. Parsed disclosure facts land in `financial_facts` and **do not** feed engines (§1.1).

### 3.4 Shapes for the hook responses

```json
// added to POST /statements/manual-filings, /lines/{id}/approve, /lines/{id}/reject
"recompute": {
  "company_id": "uuid",
  "trigger": "statement_import",
  "outcomes": [{"engine": "metrics", "status": "computed", "error": null}, …]
}
```

### 3.5 Admin page API needs

No new endpoint. `/admin` uses: `useSyncStatus` / `startMarketRefresh` (job status incl. `recompute`),
`useFilingsIntake` / `recordManualFiling`, `useCompanyByTicker`, `useFilings` / `registerFiling` / `uploadFiling` /
`parseFiling`, `useIndustrySnapshot` / `putPeerOverride`, `useThesis` / `updateThesis`.

### 3.6 Migration `023_r43_computed_data.py` (`down_revision` = 022 head)

1. `company_compute_state` (§2.2).
2. `valuation_assumptions` (§1.6).
3. `financial_metric_inputs`: `fact_id` → nullable; add `statement_line_id UUID NULL FK financial_statement_lines.id ON DELETE CASCADE`;
   `ck_financial_metric_inputs_one_source CHECK ((fact_id IS NULL) <> (statement_line_id IS NULL))`;
   `ix_financial_metric_inputs_statement_line_id`; `uq_financial_metric_input_line (metric_id, statement_line_id, input_role)`.
4. `financial_metrics`: add `source_tier String(10) NULL`, `provisional Boolean NOT NULL server_default false`.

Downgrade drops all of the above (deleting any statement-line-only input rows before restoring `fact_id NOT NULL`).
No data migration; the router's backfill (`--all`) populates everything.

---

## 4. Frontend contract (M3 read-only tabs, M4 `/admin`)

### 4.1 Client functions (AC-1)

**Deleted from `api/client.ts`** (no admin use): `calculateValuations`, `useValuations`, `calculateIndicators`,
`calculateMetrics`, `assessScore`, `assessThesis`, `screenCompany`, `estimatePurification`, `runSignals`; and the AI
hooks if nothing else imports them. Types `CalculateIndicatorsResponse`, `CompanyValuation` (and friends) go with them.

**Kept, imported only under `src/pages/admin/` (or `src/components/admin/`):** `updateThesis`, `putPeerOverride`,
`registerFiling`, `uploadFiling`, `parseFiling`, `startMarketRefresh`, `recordManualFiling`.

**`recordEgxMembership`**: deleted (CLI only, R42).

AC-1 check is mechanical: `grep -rE "<those names>" src/pages src/components --exclude-dir=admin` returns nothing.

### 4.2 Types (`types/index.ts`, router-owned)

```ts
export type SourceTier = "filing" | "vendor";
export interface Provenance {
  code: string; value: string; line_id: string; fiscal_year: number; period_end: string;
  source_tier: SourceTier; provisional: boolean; document_type: string | null; document_url: string | null;
  source_label_reported: string | null; source_page: string | null; published_date: string | null;
}
export interface ComputeMeta {
  calculated_at: string; methodology_version: string;
  trigger: "statement_import" | "price_sync" | "first_view" | "assumptions" | "backfill";
  compute_status: "ok" | "failed"; compute_error?: string;
  source_tier: SourceTier | null; provisional: boolean; period_end: string | null; price_as_of: string | null;
}
// FinancialMetric += ComputeMeta-subset: fiscal_year, period_type, period_end, source_tier, provisional,
//                    methodology_version, inputs: (Provenance & {input_role: string})[]
// TechnicalIndicator += price_as_of: string | null; methodology_version: string
// ScreeningResult: is_compliant: boolean | null; engine: "statement_lines"; & ComputeMeta
// PurificationEstimate += basis: "per_share"; dps_derivation: string | null; & ComputeMeta
// FairValueResponse & ComputeMeta; += assumptions: { methodology_version: string;
//     items: {key: string; scope: string; value: string; source_url: string; source_title: string; as_of: string}[];
//     missing: string[] }
// ScoreResponse & ComputeMeta;  ThesisResponse & ComputeMeta;  ThesisAssessment += horizon_source: "methodology_default"
// StatementLineRead += unit: "currency" | "shares" | "currency_per_share"
// SyncJobPhase += "recompute";  SyncJobStatus += recompute: SyncJobRecompute | null   (shape §2.4)
```

### 4.3 M3 — company tabs become read-only

| Tab / page | Remove | Show instead |
|---|---|---|
| Valuation | 12-field form, Calculate, legacy per-model table (`useValuations`) | FairValueCard + SensitivityTable from `useFairValue`; assumptions block (sourced items with link + as-of, or the `missing` keys as INSUFFICIENT_DATA "no sourced discount rate recorded"); copy "estimate under the stated methodology" (AC-10) |
| Technical | Calculate, client price→CSV logic | `useTechnicalIndicators`; "prices as of {price_as_of}" |
| Financial Metrics | Calculate | metrics grouped by fiscal year; INSUFFICIENT reason text (names the line) instead of "click Calculate"; per-row provenance popover |
| Investment Score | Assess | assessment; empty state only when `compute_status === "failed"` |
| Shariah | Screen; 8-field purification form; EGX33 entry form | verdict (INSUFFICIENT_DATA ⇒ "Unknown"), per-rule value/threshold/source/missing input, per-share purification card (EGP per share, or INSUFFICIENT naming the missing line), read-only EGX33 block |
| Thesis | Assess (horizon, shareholder) form; documented-update form | thesis; "Horizon: {horizon_years} years (methodology default)"; read-only ledger timeline |
| Peers (`PeersTab`) | Edit peer list | default peers + percentiles |
| Disclosures | Register / Upload / per-row Parse | registry, provenance facts, comparison **metric selector (kept)**, "What changed" |
| Company overview (`CompanyDetail`) | Refresh market data, Re-run signals | price with as-of date |
| Rankings | Re-run scoring, refresh | last run `as_of` |
| AI Insights | route `/companies/:ticker/ai` + page | — (no tab linked to it) |

Every computed number whose payload says `provisional: true` shows the "Provisional (vendor data)" badge (AC-4); the
Shariah verdict carries it too. `calculated_at` is shown as "computed {relative time}". No new certainty copy (AC-10).

Vitest (AC-1): render each company tab with mocked payloads; assert no `input`/`select`/`textarea` except the
Disclosures comparison selector, and no `button` except retry, pagination and view selectors.

### 4.4 M4 — `/admin`

| Route | Content (moved unchanged, R43 #9 #10 #11 #14 #16) |
|---|---|
| `/admin` | Market refresh panel (start + status polling, incl. new `recompute` counts) + links to the two pages below |
| `/admin/intake` | `FilingsIntake` page as-is; `/intake` redirects here; Intake leaves the main sidebar |
| `/admin/companies/:ticker` | company picker; Disclosures register/upload(auto-parse)/parse; peer override; thesis documented update |

Sidebar: remove "Intake"; add a small "Admin" link in the sidebar footer. `App.tsx`, `Layout.tsx`, `CompanyTabs.tsx`,
`api/client.ts`, `types/index.ts` are router-owned shared files (CONTRACT frontend lanes rule) — lanes return wiring
instructions. Frontend builds against mocks of §3 / §4.2 while backend implements (CONTRACT step 6).

---

## 5. Build plan, ownership, tests

**Backend (staff-backend), in order — each step leaves all gates green:**

| Step | Files | Tests (pytest, seeded on `egx_ai_test`) |
|---|---|---|
| M1a ontology/vendor 1.1 | `statements/{ontology,vendor_import,validator,service}.py`, `schemas` if any | vendor mapping of the 3 codes incl. bank fallback precedence; sign rule rejects negative shares; `unit` served |
| M1b bridge | `statements/bridge.py` | each derived function: zero / negative / missing denominator; period coherence (no borrowing from older period); filing-beats-vendor winner reaches the bridge; `tier_of` |
| M1c engines | `metrics/service.py`, `repositories/{metrics,industry,screening}.py`, `dataquality/service.py`, `screening/statement_input.py`, `valuation/{service,assumptions}.py`, `scores/service.py`, `thesis/service.py`, `signals/stance.py`, migration 023, `models/*` | AC-3 one test per engine (missing line ⇒ null + INSUFFICIENT + reason names the line, never 0); AC-4 filing beats vendor + provisional flags; growth + ROA/ROE averaging regression tests for the two latent bugs; `latest_metric_values` picks latest period; screening rule rows replaced not appended; FV snapshot not overwritten by thesis/stance |
| M2 recompute | `services/recompute.py`, `services/coverage_report.py`, `ingestion/{jobs,sync}.py`, `statements/vendor_import.py`, `api/{statements,metrics,valuation,scores,screening,technical,theses,disclosures}.py` | AC-2 GET-only computed payloads (≥ 2 periods, ≥ 200 bars); AC-5 import/manual filing/approve refresh X only; AC-6 job reports per-step counts; AC-7 first GET computes, second GET does not (assert `calculated_at` unchanged + no new rows); failed engine ⇒ 200 with `compute_status: failed`; advisory-lock double-check (two concurrent `ensure_fresh` ⇒ one compute) |

**Frontend (staff-frontend):** M3 then M4 per §4, against mocks; vitest per AC-1/AC-8; vercel-react-best-practices review.

**QA:** qa-api (§3 conformance), qa-ui, qa-security (admin routes are not an auth boundary — confirm no new exposure),
**analyst** (D-6 DPS derivation + interest-income purification numerator; metric input map; score input map).

**M5 (router + QA):** run `vendor_import` (map 1.1) → `python -m app.services.recompute --all` → `coverage_report` +
`app.signals.sanity` before/after, on the dev DB.

---

## 6. Decisions and open items

| # | Decision | Status |
|---|---|---|
| D-1 | Statement lines replace (not complement) FinancialFact as engine input | ruled |
| D-2 | Ontology 1.1: `interest_income`, `weighted_avg_shares_basic`, `shares_outstanding` + vendor map 1.1 | ruled (mapping of fields already on disk; answers R43 open note 2) |
| D-3 | Statement-lines engine is the canonical Shariah engine; legacy `/screen` removed | ruled |
| D-4 | Inline compute with fingerprinted `company_compute_state`; no queue | ruled |
| D-5 | Caller-input write routes removed (§3.2: technical/valuation/metrics calculate, score/thesis assess, screen, screen-statements, purification POST) | ruled (correctness, not optional) |
| D-6 | DPS = `abs(dividends_paid) / shares_outstanding` (cash paid in the year); purification numerator = interest income only | **analyst gate** at QA; if rejected, purification and dividend checks stay INSUFFICIENT/NOT_RUN — no other code changes |
| D-7 | No methodology bumps (score 1.0, valuation 1.0, thesis 1.0, Shariah v2, DQ 1.0) — compute state handles staleness | ruled |
| D-8 | **Valuation assumptions have no source yet.** Fair value is INSUFFICIENT_DATA for every company until sourced rows (EGP cost of equity, terminal/stable growth, target P/E / P/B / P/S per profile or market) are recorded via the CLI. | **router action:** dispatch researcher to find citable values; until then AC-9 must report fair-value coverage 0% with this reason (inputs-exist-but-no-assumptions is not the 0%-defect case) |
| D-9 | **No company has an industry or sector** (`industry`, `egx_sector_id`, `gics_sub_industry_id` all null; `industry/backfill.py` has no CLI and no data). The Shariah industry rule is INSUFFICIENT for all ⇒ no verdict can be COMPLIANT; banks are valued/scored on the `default` profile. | **router action:** schedule sector data (backfill from an official EGX listing) as a separate data task; AC-9 Shariah distribution until then = NON_COMPLIANT (ratio fails) + INSUFFICIENT_DATA, explained by D-9 |
| D-10 | Metrics tab and Ratios tab both show ROE/margins from the same lines with different formulas (average vs spot equity) | note for ux-expert/pm — not changed here |

NEXT: staff-backend
