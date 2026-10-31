export interface Company {
  id: string
  ticker: string
  isin: string | null
  name: string
  name_ar: string | null
  sector: string | null
  industry: string | null
  currency: string
  shares_outstanding: string | null
  free_float: string | null
  listing_date: string | null
  status: 'ACTIVE' | 'SUSPENDED' | 'DELISTED' | 'UNKNOWN'
  created_at: string
  updated_at: string
  /** Only on GET /companies/{id} and /companies/ticker/{ticker} (R47 Q3). */
  fundamentals?: FundamentalsFreshness
}

/** Latest approved annual period of a company (R47 Q3); never a year when INSUFFICIENT_DATA. */
export interface FundamentalsFreshness {
  status: 'AVAILABLE' | 'INSUFFICIENT_DATA'
  reason?: string | null
  fiscal_year: number | null
  period_end: string | null
  source_tier: 'vendor' | 'filing' | null
  provisional: boolean | null
  published_date: string | null
}

export interface DailyPrice {
  id: string
  company_id: string
  date: string
  open: string
  high: string
  low: string
  close: string
  adjusted_close: string | null
  volume: number
  value_traded: string | null
  trades: number | null
  source_id: string
  created_at: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface DataSource {
  id: string
  name: string
  source_type: 'EGX' | 'FRA' | 'COMPANY' | 'DATA_PROVIDER' | 'MANUAL' | 'SYNTHETIC'
  base_url: string | null
  description: string | null
  last_synced_at: string | null // ISO datetime, null = never synced
}

export interface FinancialPeriod {
  id: string
  company_id: string
  period_type: 'ANNUAL' | 'Q1' | 'Q2' | 'Q3' | 'Q4' | 'SEMI_ANNUAL' | 'INTERIM'
  fiscal_year: number
  fiscal_quarter: number | null
  start_date: string
  end_date: string
  created_at: string
  updated_at: string
}

export interface FinancialDocument {
  id: string
  period_id: string
  source_id: string
  document_status: 'ORIGINAL' | 'RESTATED' | 'AMENDED' | 'ADJUSTED'
  document_type: string
  document_url: string | null
  filing_date: string | null
  publication_date: string | null
  fiscal_year_end: string | null
  notes: string | null
  created_at: string
}

export interface FinancialFact {
  id: string
  period_id: string
  document_id: string
  company_id: string
  fact_type: 'INCOME_STATEMENT' | 'BALANCE_SHEET' | 'CASH_FLOW' | 'SHAREHOLDERS_EQUITY' | 'NOTES'
  reported_label: string
  normalized_label: string | null
  reported_value: string | null
  normalized_value: string | null
  currency: string
  unit: string | null
  scale: number | null
  status: 'REPORTED' | 'NORMALIZED' | 'CALCULATED' | 'INSUFFICIENT_DATA'
  source_page: string | null
  source_line: string | null
  reported_at: string | null
  normalized_at: string | null
  created_at: string
}

export interface FinancialMetric {
  id: string
  company_id: string
  period_id: string
  metric_code: string
  display_name: string
  value: string | null
  unit: string
  status: string
  reason: string | null
  warnings: string | null
  formula_version: number
  calculated_at: string
  created_at: string
  // R43 (r43-computed-company-data.md 3.1): fiscal period and provenance of the inputs.
  fiscal_year: number | null
  period_type: string | null
  period_end: string | null
  source_tier: SourceTier | null
  provisional: boolean
  methodology_version: string | null
  inputs: (Provenance & { input_role: string })[]
}

export interface TechnicalIndicator {
  id: string
  company_id: string
  indicator_type: string
  value: string | null
  status: string
  parameters: Record<string, unknown> | null
  reason: string | null
  calculated_at: string
  created_at: string
  // R43: the price bar the indicator was computed on.
  price_as_of: string | null
  methodology_version: string | null
}

export interface CalculateIndicatorsResponse {
  company_id: string
  ticker: string
  indicators: {
    indicator: string
    value: string | null
    status: string
    parameters: Record<string, unknown> | null
    reason: string | null
  }[]
  calculated_at: string
}

export interface ApiError {
  detail: string
}


// Signal ranking types
export type SignalTier = 'STRONGEST' | 'STRONG' | 'NEUTRAL' | 'WEAK' | 'WEAKEST'

export interface MarketSignal {
  ticker: string
  name: string | null
  as_of: string
  model: string
  status: 'SCORED' | 'INSUFFICIENT_HISTORY' | 'NO_PRICE_DATA' | 'NOT_ACTIVE'
  tier: SignalTier | null
  score: number | null
  rank: number | null
  universe_size: number | null
  data_coverage: number | null
  percentiles: Record<string, number>
  factors: Record<string, number>
  excluded_factors: string[]
  rationale: string | null
  reason: string | null
  sector?: string | null
  industry?: string | null
}

export interface UniverseCoverage {
  universe_total: number
  active_total: number
  with_price_data: number
  priced_of_active: number
  min_history_days: number
  analyzable: number
  unscorable: number
  unpriced_tickers: string[]
  thin_history_tickers: string[]
}

export interface SignalsResponse {
  as_of: string | null
  model: string | null
  total: number
  count: number
  results: MarketSignal[]
  coverage: UniverseCoverage
  disclaimer?: string
  notice?: string
}

export interface SignalRun {
  as_of: string
  model: string
  universe_total: number
  scored_count: number
  unscorable_count: number
  coverage_ratio: number
}

export interface UnscorableCompany {
  ticker: string | null
  name: string | null
  status: string
  reason: string | null
}

// GET /api/screening/companies (backend/app/api/screening.py::list_screened_companies)
export interface ScreenedCompanySummary {
  id: string
  company_id: string
  is_compliant: boolean
  status: string
  methodology_version: string
  overall_reason: string | null
  screened_at: string
}

export interface ScoringFactor {
  key: string
  label: string
  weight: number
  direction: 'HIGHER_IS_BETTER' | 'LOWER_IS_BETTER'
}

export interface ScoringModelInfo {
  name: string
  version: string
  description: string
  min_history_days: number
  factors: ScoringFactor[]
}

// ─── Data Quality (contract: .workflow/design/data-quality-contract.md) ─

export type DataQualityStatus = "OK" | "DEGRADED" | "POOR" | "MISSING";

export interface QualityComponent {
  key: string;      // "completeness" | "freshness" | "validation" | "historical_depth" | "source_reliability"
  label: string;
  score: number;    // 0-100
  weight: number;
  reason: string;
}

export interface DataQualityScore {
  scope: "price_history" | "company_profile" | "financial_statements";
  as_of: string;    // YYYY-MM-DD
  status: DataQualityStatus;
  score: number;    // 0-100 (1 decimal precision)
  components: QualityComponent[];
  issues: string[];
  methodology_version: string;
}

// GET /api/data-quality/companies/{company_id}
export interface DataQualityListResponse {
  items: DataQualityScore[];
  methodology_version: string;
  scale: string;
  disclaimer: string;
}

// ─── Market refresh (contract: .workflow/design/refresh-and-assess-contract.md) ─

export type SyncJobPhase = "universe" | "prices" | "assessment";

export type SyncJobState =
  | "idle"
  | "accepted"
  | "running"
  | "done"
  | "failed"
  | "partial";

export interface SyncJobProgress {
  completed: number;
  total: number;
}

export interface SyncJobFailure {
  ticker: string;
  error: string; // capped at 20 entries; see failed_count for the true total
}

export interface SyncJobPrices {
  companies_fetched: number;
  companies_total: number;
  records_written: number;
  failed_count: number;
  failed_tickers: SyncJobFailure[];
}

export interface SyncJobAssessment {
  companies_assessed: number;
  scores_written: number;
}

// Job object returned by POST /api/ingestion/sync (202 and 409 bodies)
// and GET /api/ingestion/sync/status (always 200)
export interface SyncJobStatus {
  status: SyncJobState;
  started_at: string | null; // ISO datetime or null when idle
  finished_at: string | null;
  phase: SyncJobPhase | null;
  progress: SyncJobProgress | null;
  universe: { discovered: number } | null;
  prices: SyncJobPrices | null; // null until the prices phase completes
  assessment: SyncJobAssessment | null; // null until the assessment phase completes
  error: string | null;
}

// GET /api/data-sources — existing DataSource gains one field:
// last_synced_at is declared on DataSource above.

// ─── Shariah screening (GET/POST /api/screening/companies/{id}[…]) ─

export interface ScreeningRuleResult {
  rule_name: string;
  verdict: string;
  value: string | null;
  threshold: string | null;
  reason: string;
  missing_input?: string | null; // v2 provenance
  source?: string | null; // v2 provenance
  source_date?: string | null; // v2 provenance
}

export interface ScreeningResult extends Partial<ComputeMeta> {
  id: string | null; // null when the computation failed and no snapshot exists
  company_id: string;
  is_compliant: boolean | null; // null = INSUFFICIENT_DATA ("Unknown" in the UI)
  engine?: "statement_lines";
  status: string; // COMPLIANT | NON_COMPLIANT | INSUFFICIENT_DATA
  methodology_version: string;
  methodology_name: string;
  overall_reason: string | null;
  screened_at: string | null;
  report_date: string | null;
  report_date_reason: string | null;
  created_at: string | null;
  rule_results: ScreeningRuleResult[];
  data_quality: Record<string, unknown> | null;
}

// ─── Valuation (GET/POST /api/valuation/companies/{id}[…]) ─

export interface CompanyValuation {
  id?: string;
  company_id: string;
  model: string;
  value: string | null;
  status: string; // AVAILABLE | INSUFFICIENT_DATA | INVALID
  assumptions: Record<string, unknown> | null;
  reason: string | null;
  calculated_at: string;
  created_at?: string;
}

export interface CalculateValuationsResponse {
  company_id: string;
  ticker: string;
  valuations: CompanyValuation[];
  calculated_at: string;
}

// ─── Investment score (GET/POST /api/scores/companies/{id}[…]) ─

export interface ScoreCheck {
  check_key: string;
  component: string;
  status: string; // PASS | FAIL | NOT_RUN | INSUFFICIENT_DATA…
  threshold: string;
  inputs: Record<string, string | null>;
  reason: string;
}

export interface ScoreComponent {
  key: string;
  status: string; // AVAILABLE | INSUFFICIENT_DATA…
  score: number | null;
  passes: number;
  ran: number;
  total: number;
  reason: string;
  checks: ScoreCheck[];
}

export interface ScoreConfidence {
  level: string;
  dq_score: number | null;
  n_checks_run: number;
  bands: { level: string; min_dq_score: number; min_checks_run: number }[];
  reason: string;
}

export interface ScoreAssessment {
  company_id: string;
  ticker: string;
  as_of: string;
  computed_at: string;
  methodology_version: string;
  valuation_methodology_version: string;
  profile: { profile_id: string; methodology_version: string; health_track: string };
  headline: { value: number | null; status: string; reason: string; detail: string };
  components: Record<string, ScoreComponent>;
  checks: ScoreCheck[];
  checks_not_run: string[];
  n_with_data: number;
  n_checks_total: number;
  confidence: ScoreConfidence;
  buy_zone: Record<string, unknown>;
  inputs_echo: {
    inputs: Record<string, string | string[] | null>;
    // R43: `statements` carries the provenance of every statement line used.
    sources: Record<string, string | null | Provenance[]>;
  };
  scale: string;
  disclaimer: string;
}

export interface ScoreResponse extends Partial<ComputeMeta> {
  company_id: string;
  ticker: string;
  assessment: ScoreAssessment | null; // null = assessed never; never a default score
  methodology_version: string;
  scale: string;
  disclaimer: string;
  /** R47 Q1/Q2: shown beside the score, never part of it. Absent on an older backend. */
  piotroski?: PiotroskiBlock;
  dividend_safety?: DividendSafetyBlock;
}

// ─── Score extras (R47 Q1 Piotroski, Q2 dividend safety) ─

export type PiotroskiCheckStatus = "PASS" | "FAIL" | "INSUFFICIENT_DATA";

export interface PiotroskiCheck {
  key: string;
  label: string;
  group: "profitability" | "leverage_liquidity" | "operating_efficiency";
  status: PiotroskiCheckStatus;
  reason: string | null;
  /** Named inputs as decimal strings; null = the input was missing (never a substituted 0). */
  inputs: Record<string, string | null>;
}

export interface PiotroskiBlock {
  version: string;
  status: "AVAILABLE" | "INSUFFICIENT_DATA" | "NOT_RUN";
  reason: string | null;
  fiscal_year: number | null;
  prior_fiscal_year: number | null;
  /** Passes out of the checks that ran; null when none ran. */
  passes: number | null;
  checks_run: number;
  checks_total: number;
  checks: PiotroskiCheck[];
  deviations: string[];
  source_tier: SourceTier;
  provisional: boolean;
  sources: Provenance[];
}

export interface DividendMetric {
  value: string | null;
  status: "AVAILABLE" | "NOT_MEANINGFUL" | "INSUFFICIENT_DATA";
  reason: string | null;
}

export interface DividendYear {
  fiscal_year: number;
  status: "PAID" | "NO_DIVIDEND" | "INSUFFICIENT_DATA";
  reason: string | null;
  inputs: Record<string, string | null>;
  payout_ratio: DividendMetric;
  cash_coverage: DividendMetric;
}

export interface DividendSafetyBlock {
  version: string;
  /** "from dividends paid (derived)": the cash paid in the year, not the dividend declared. */
  label: string;
  status: "AVAILABLE" | "INSUFFICIENT_DATA";
  reason: string | null;
  latest: DividendYear | null;
  years: DividendYear[];
  payout_formula: string;
  coverage_formula: string;
  source_tier: SourceTier;
  provisional: boolean;
  sources: Provenance[];
}

// ─── Industry peers (GET/PUT /api/industry/companies/{id}[…]) ─

export interface IndustryPeer {
  id: string;
  ticker: string;
  name: string;
}

export interface IndustryPercentile {
  metric_key: string;
  display_name: string;
  value: string | null;
  status: string;
  unit: string | null;
  n_peers: number;
  n_with_data: number;
  explanation: string;
  reason: string;
}

export interface IndustrySnapshot {
  company: {
    id: string;
    ticker: string;
    name: string;
    sector: string | null;
    egx_sector: string | null;
    gics: Record<string, string> | null;
  };
  peers: { basis: string; items: IndustryPeer[] };
  profile: { profile_id: string; methodology_version: string; metric_keys: string[] };
  percentiles: IndustryPercentile[];
  n_peers: number;
  methodology_version: string;
  as_of: string;
}

// ─── Weighted fair value (GET /api/valuation/companies/{id}/fair-value) ─

export interface FairValueLeg {
  model: string;
  value: string | null;
  status: string; // AVAILABLE | INSUFFICIENT_DATA | INVALID
  reason: string | null;
  assumptions: Record<string, unknown>;
  /** R46 V9: set when this leg is the residual-income fallback for a failed cash-flow model. */
  fallback_from?: string | null;
  /** The cash-flow model's own reason for failing (backend text). */
  fallback_reason?: string | null;
  /** Set when the fallback ran but also gave no value; the leg then keeps the cash-flow result. */
  fallback_attempt?: { model: string; status: string | null; reason: string | null } | null;
}

export interface FairValueScenario {
  value: string | null;
  status: string;
  reason: string | null;
}

/** One fiscal year of the cash-flow base (R46 V7): every component, or the reason the year has none. */
export interface FcfeBaseYear {
  fiscal_year: number;
  status: string; // AVAILABLE | INSUFFICIENT_DATA
  reason: string | null;
  cfo: string | null;
  capex: string | null;
  /** Operating cash flow minus capex. */
  pre_financing: string | null;
  /** Information only: past borrowing is not part of the base. */
  net_borrowing: string | null;
  parent_share: string | null;
  /** `pre_financing` times `parent_share`: the figure the base averages. */
  flow: string | null;
}

/** The starting cash flow of the two-stage model: the mean of the last `years_required` years (R46 V1/V7). Null for banks. */
export interface FcfeBase {
  method: string;
  years_required: number;
  status: string;
  reason: string | null;
  mean: string | null;
  years: FcfeBaseYear[];
}

/** Starting debt of the cash-flow model (R46 V7): debt grows with the firm, so future borrowing = growth x debt. */
export interface DebtBase {
  method: string;
  /** Interest-bearing debt x parent share. */
  value: string | null;
  fiscal_year: number | null;
  reported_value: string | null;
  parent_share: string | null;
  /** `vendor_omitted_zero`: the vendor omits zero rows, so the absent line is read as no debt. */
  basis: "reported" | "vendor_omitted_zero" | string;
  status: string;
  reason: string | null;
}

/** ROE for the residual-income model (R46 V8): the mean of the last `years_required` years. */
export interface RoeBase {
  method: string;
  years_required: number;
  status: string;
  reason: string | null;
  mean: string | null;
  years: { fiscal_year: number; roe: string | null; status: string; reason: string | null }[];
}

/** Resolved model inputs: decimal strings, plus structured bases (read scalars with `lib/fairValue`). */
export interface FairValueInputs {
  fcfe_base?: FcfeBase | null;
  debt?: DebtBase | null;
  roe_base?: RoeBase | null;
  [key: string]: string | FcfeBase | DebtBase | RoeBase | null | undefined;
}

/** What the price implies under the model (R46 V6): stage-1 growth, or a bank's ROE. */
export interface FairValueImplied {
  metric: "growth_high" | "roe";
  value: string | null;
  status: string; // AVAILABLE | INSUFFICIENT_DATA | INVALID
  reason: string | null;
  compare_to: { key: string; value: string | null };
  bounds: { min: string; max: string } | null;
  price: string | null;
  model: string;
}

/** Trading currency against the statements' currency (R46 C1). Never converted. */
export interface FairValueCurrency {
  status: "MATCH" | "MISMATCH" | "UNKNOWN";
  trading_currency: string | null;
  statements_currency: string | null;
  reason: string | null;
}

export interface FairValueResponse extends Partial<ComputeMeta> {
  company_id: string;
  ticker: string;
  as_of: string;
  computed_at: string;
  methodology_version: string;
  profile: {
    profile_id: string;
    methodology_version: string;
    primary_model: string;
    fallback_model: string;
    preferred_multiple: string | null;
    /** R46 V3: `"sector"` or `"statement_lines: net_loans + total_deposits"`. */
    detection?: string;
  };
  inputs: FairValueInputs;
  input_sources: Record<string, string | null>;
  legs: { intrinsic: FairValueLeg; relative: FairValueLeg; fallback: FairValueLeg };
  weights: Record<string, string>;
  n_with_data: number;
  fair_value: {
    value: string | null;
    status: string;
    reason: string | null;
    /** R46 V5: which legs made the value. */
    basis?: "weighted" | "intrinsic_only" | "relative_only" | null;
    basis_note?: string | null;
  };
  current_price: { value: string | null; as_of: string | null };
  scenarios: { bull: FairValueScenario; base: FairValueScenario; bear: FairValueScenario; note: string };
  sensitivity: Record<string, string | number | null>[];
  confidence: {
    level: string;
    required_discount: string;
    dq_score: number | null;
    dq_status: string;
    reason: string;
    methodology_version: string;
  };
  verdict: { label: string; detail: string; discount: string | null };
  /** R46 V6: the reverse calculation beside the verdict (absent on pre-R46 servers). */
  implied?: FairValueImplied;
  /** R46 C1 (absent on pre-R46 servers). */
  currency?: FairValueCurrency;
  /** R43: sourced valuation assumptions behind the estimate (absent on pre-R43 servers). */
  assumptions?: FairValueAssumptions;
}

// ─── Purification + EGX33 (GET/POST /api/screening/companies/{id}/…) ─

export interface PurificationEstimate extends Partial<ComputeMeta> {
  id?: string;
  company_id: string;
  status: string; // OK | ESTIMATE_PARTIAL | INSUFFICIENT_DATA
  basis?: "per_share"; // amount_egp and dividend_egp are EGP per share
  dps_derivation?: string | null;
  branch: string;
  doctrine: string;
  amount_egp: string | null;
  dividend_egp: string | null;
  ratio: string | null;
  ratio_provenance: string | null;
  dps: string | null;
  dps_source: string | null;
  dps_date: string | null;
  reason: string | null;
  missing_input: string | null;
  note: string | null;
  methodology_version?: string;
  computed_at?: string;
}

export interface EgxMembership {
  id?: string;
  company_id: string;
  member: boolean;
  review_cycle: string;
  effective_date: string | null;
  source: string | null;
  note: string | null;
  recorded_at?: string;
}

// GET /api/screening/companies/{id}/egx-membership — side-by-side envelope
// (our verdict + latest EGX33 record + history + discrepancy flag).
export interface EgxMembershipStatus {
  company_id: string;
  our_verdict: {
    is_compliant: boolean | null;
    status: string;
    methodology_version: string;
    screened_at: string;
    report_date: string | null;
  } | null;
  egx33: {
    member: boolean;
    review_cycle: string;
    effective_date: string | null;
    source: string | null;
    note: string | null;
  } | null;
  history: {
    member: boolean;
    review_cycle: string;
    effective_date: string | null;
    source: string | null;
    note: string | null;
  }[];
  discrepancy: { flagged: boolean; reason: string | null };
}

// ─── Investment thesis (GET/POST /api/theses/companies/{id}[…]) ─

export interface ThesisAssumption {
  metric: string;
  value: string | null;
  horizon: string | null;
  source: string;
  author: string;
}

export interface ThesisInvalidation {
  metric: string;
  threshold: string;
  direction: string;
  period: string;
  evidence_source: string;
  action: string;
  status: string;
  extraction_confidence: string | null;
  version: number;
  methodology_version: string;
}

export interface ThesisCatalyst {
  id: string;
  event: string;
  date_from: string | null;
  date_to: string | null;
  window: string | null;
  variable: string | null;
  expectation: string | null;
  outcome: string;
  provenance: string;
  label: string;
  methodology_version: string;
}

export interface ThesisLedgerRow {
  classification: string;
  variable: string;
  action: string;
  rationale: string;
  evidence: Record<string, unknown>;
  reviewer: string | null;
  created_at: string | null;
  methodology_version: string;
}

export interface ThesisAssessment {
  horizon_source?: "methodology_default";
  company_id: string;
  ticker: string;
  as_of: string;
  computed_at: string;
  methodology_version: string;
  valuation_methodology_version: string;
  header: {
    fair_value: { value: string | null; status: string };
    horizon_years: number;
    is_shareholder: boolean | null;
  };
  narrative: string | null;
  assumptions: ThesisAssumption[];
  bulls: string[];
  bears: string[];
  scenarios: Record<string, unknown>;
  sensitivity: Record<string, unknown>;
  invalidations: ThesisInvalidation[];
  ledger: ThesisLedgerRow[];
  catalysts: ThesisCatalyst[];
  confidence: Record<string, unknown>;
  dq: Record<string, unknown>;
  score: number | Record<string, unknown> | null;
  needs_reassessment: boolean;
  disclaimer: string;
}

export interface ThesisResponse extends Partial<ComputeMeta> {
  company_id: string;
  ticker: string;
  assessment: ThesisAssessment | null; // null = never assessed; never a default thesis
  methodology_version: string;
  disclaimer: string;
}

// ─── Disclosures (POST/GET /api/disclosures/…) ─

export interface DisclosureFiling {
  id: string;
  company_id: string;
  filing_url: string;
  bulletin_id: string | null;
  report_date: string;
  filing_type: string;
  accounting_basis: string;
  content_hash: string | null;
  byte_size: number | null;
  storage_path: string | null;
  has_bytes: boolean;
  downloaded_at: string;
  created_at: string;
}

export interface DisclosureFact {
  id: string;
  metric: string;
  value: { value: string | null; status: string; reason: string | null };
  currency_unit: string | null;
  period: { end: string | null; type: string | null; audit_state: string | null };
  source: {
    filing_url: string | null;
    bulletin_id: string | null;
    company: string;
    report_date: string | null;
    filing_type: string | null;
  };
  locator: Record<string, unknown>;
  extraction: Record<string, unknown>;
  accounting_basis: string | null;
  eas_tags: string[];
  methodology_version: string;
  status: string; // OK | UNKNOWN
  supersedes: string | null;
  is_restated: boolean;
  created_at: string | null;
}

export interface DisclosureDiff {
  id: string;
  metric: string;
  kind: string | null;
  prior_value: string | null;
  current_value: string | null;
  delta: string | null;
  delta_pct: string | null;
  prior_period: string | null;
  current_period: string | null;
}

// ─── Watchlists / alerts / events (Phase 8) ─

export interface PhaseBadge {
  value: string | null;
  status: string; // AVAILABLE | INSUFFICIENT_DATA
  reason: string | null;
}

export interface Watchlist {
  id: string;
  user_id: string;
  name: string;
  created_at: string;
}

export interface WatchlistEntry {
  id: string;
  watchlist_id: string;
  company_id: string;
  group: string | null;
  note: string | null;
  thesis_link: string | null;
  created_at: string;
  price: PhaseBadge | null;
  change: PhaseBadge | null;
  as_of: PhaseBadge | null;
  staleness: PhaseBadge | null;
  score: PhaseBadge | null;
  shariah_state: PhaseBadge | null;
  thesis_link_badge: PhaseBadge | null;
  company_ticker: string | null;
  company_name: string | null;
}

export interface AlertRule {
  id: string;
  user_id: string;
  watchlist_id: string | null;
  company_id: string | null;
  family: string; // price | valuation_gap | document | score_change
  params: Record<string, unknown>;
  methodology_version: string;
  enabled: boolean;
  created_at: string;
}

export interface AlertFired {
  id: string;
  rule_id: string;
  company_id: string;
  inputs_snapshot: Record<string, unknown>;
  fired_at: string;
  acked_at: string | null;
}

export interface PhaseEvent {
  id: string;
  ts: string;
  actor_type: string;
  actor_id: string;
  rule_version: string;
  type: string;
  symbols: string[];
  inputs_snapshot: Record<string, unknown>;
  reason: string;
  supersedes_id: string | null;
}

// PUT /api/industry/companies/{id}/peers — override receipt (not a snapshot).
export interface PeerOverrideReceipt {
  company_id: string;
  peer_company_ids: string[];
  methodology_version: string;
  updated_at: string;
}


export interface StatementLineRead {
  ontology_code: string
  label_en: string
  label_ar: string
  value: string | null
  status: 'AVAILABLE' | 'INSUFFICIENT_DATA'
  currency: string
  source_label_reported: string | null
  source_page: string | null
  published_date: string | null
  document_url: string | null
  /** "filing" = official document, "vendor" = provisional aggregator data. */
  source_tier: 'filing' | 'vendor' | null
  provisional: boolean
  /** R43: how to format the value. Absent from older backends (treated as "currency"). */
  unit?: 'currency' | 'shares' | 'currency_per_share'
}

export interface PeriodStatements {
  period_id: string
  fiscal_year: number
  period_type: string
  published_date: string | null
  income: StatementLineRead[]
  balance: StatementLineRead[]
  cash_flow: StatementLineRead[]
}

export interface StatementBundle {
  periods: PeriodStatements[]
}

export interface RatioResult {
  code: string
  value: string | null
  status: 'AVAILABLE' | 'INSUFFICIENT_DATA'
  reason: string | null
}

export interface RatioBundle {
  fiscal_year: number | null
  ratios_version: string
  ratios: RatioResult[]
}

export interface TargetLevel {
  value: string | null
  status: string
  reason: string | null
}

/** One sentence of a stance reason as a code plus parameters (R51); `params` are strings as the English text prints them. */
export interface StancePart {
  code: string
  params: Record<string, string>
}

/** One limitation as a code plus parameters, with the English sentence as the fallback (R51). */
export interface LimitationItem extends StancePart {
  text: string
}

export interface StanceReason {
  engine: string
  inputs: Record<string, string>
  text: string
  /** One per sentence in `text`, same order. Absent on stored or older payloads. */
  parts?: StancePart[]
}

/** Our verdict and EGX33 membership side by side — never merged. */
export interface ShariahStatus {
  verdict: 'COMPLIANT' | 'NON_COMPLIANT' | 'INSUFFICIENT_DATA' | 'NOT_SCREENED'
  methodology_version: string | null
  egx33: 'member' | 'not_member' | 'unknown'
  egx33_review_cycle: string | null
  egx33_source: string | null
  note: string | null
}

/** ATR volatility band around the last close (signal-rules-2.2). */
export interface ReferenceLevels {
  entry: string
  upside: string
  downside: string
  atr: string
  horizon: string
}

export interface LiquidityInfo {
  avg_value_traded: string | null
  window: number
  low: boolean | null
}

export interface StanceResult {
  company_id: string
  ticker: string
  stance: 'buy' | 'hold' | 'reduce'
  confidence: number
  price: string | null
  score: string | null
  coverage: string
  reasons: StanceReason[]
  limitations: string[]
  /** Same order and length as `limitations`. Absent on stored or older payloads. */
  limitation_items?: LimitationItem[]
  targets: Record<string, TargetLevel>
  stop_level: TargetLevel
  reference_levels: ReferenceLevels | null
  liquidity: LiquidityInfo
  shariah: ShariahStatus
  statement_freshness: string | null
  rules_version: string
  as_of: string
}

export interface StanceRadarItem {
  ticker: string
  company_id: string
  name: string
  stance: 'buy' | 'hold' | 'reduce' | null
  confidence: number | null
  score: string | null
  price: string | null
  reference_levels: ReferenceLevels | null
  low_liquidity: boolean | null
  shariah: ShariahStatus | null
}

/** GET /api/statements/intake — priority companies and their filing coverage. */
export interface IntakeItem {
  company_id: string
  ticker: string
  name: string
  reasons: Array<'egx33' | 'most_traded'>
  filing_years: number[]
  vendor_years: number[]
  target_year: number
  status: 'missing' | 'vendor_only' | 'filed'
  disclosure_url: string | null
}

export interface IntakeLineDef {
  code: string
  label_en: string
  label_ar: string
  section: 'income' | 'balance' | 'cash_flow'
}

export interface IntakeResponse {
  items: IntakeItem[]
  lines: IntakeLineDef[]
}

export interface ManualFilingRequest {
  ticker: string
  fiscal_year: number
  period_end: string
  document_url: string
  publication_date: string | null
  currency: string
  lines: Array<{ code: string; value: string; page: string }>
}

export interface ManualFilingResponse {
  document_id: string
  period_id: string
  lines: Array<{ code: string; status: string; reason: string | null }>
}

/** GET /api/companies/overview — one Companies-table page in one request. */
export interface CompanyOverviewRow {
  company_id: string
  stance: { stance: 'buy' | 'hold' | 'reduce'; confidence: number; reasons: string[] } | null
  latest_price: { close: string; date: string } | null
  gross_margin: { value: string | null; status: string; reason: string | null } | null
  /** Only with `forming=true`: shapes forming at the last session (R47 P7). */
  forming?: FormingSummary[]
}

/** One forming shape as the Companies table shows it (no points or lines). */
export interface FormingSummary {
  pattern: string
  expected: 'up' | 'down' | null
  known_date: string
  sessions_left: number
  confirm_above: string | null
  confirm_below: string | null
}

/** Companies filter choices: any forming shape, or by its expected break. */
export type FormingFilter = 'any' | 'up' | 'down'

export interface CompaniesOverviewResponse {
  items: Record<string, CompanyOverviewRow>
  missing: string[]
  price_date: string | null
}

export interface StanceRadarResponse {
  items: StanceRadarItem[]
  count: number
  rules_version: string
}

// ─── R43 provenance and compute meta (r43-computed-company-data.md 1.4, 3.1, 4.2) ─

export type SourceTier = "filing" | "vendor";

/** One statement line behind a computed number. `provisional` means vendor data. */
export interface Provenance {
  code: string;
  value: string;
  line_id: string;
  fiscal_year: number;
  period_end: string;
  source_tier: SourceTier;
  provisional: boolean;
  document_type: string | null;
  document_url: string | null;
  source_label_reported: string | null;
  source_page: string | null;
  published_date: string | null;
}

/** Meta block merged into every GET that computes on read. */
export interface ComputeMeta {
  calculated_at: string;
  methodology_version: string;
  trigger: "statement_import" | "price_sync" | "first_view" | "assumptions" | "backfill";
  compute_status: "ok" | "failed";
  compute_error?: string;
  source_tier: SourceTier | null;
  provisional: boolean;
  period_end: string | null;
  price_as_of: string | null;
}

// ─── Valuation assumptions (GET /api/valuation/companies/{id}/fair-value) ─

/** One sourced row of the valuation assumption record. */
export interface ValuationAssumptionItem {
  key: string;
  scope: string;
  value: string;
  source_url: string;
  source_title: string;
  as_of: string;
}

export interface FairValueAssumptions {
  methodology_version: string;
  items: ValuationAssumptionItem[];
  /** Stored keys with no fresh sourced row. */
  missing: string[];
  stale?: { key: string; reason: string }[];
  computed?: {
    discount_rate: string | null;
    terminal_growth_rate: string | null;
    formula?: string;
  };
}

// ─── Disclosure comparison (GET /api/disclosures/comparison) ─

/** A value that may be missing, with the reason it is. */
export interface ComparisonValue {
  value: string | null;
  status: string; // OK | INSUFFICIENT_DATA
  reason?: string | null;
}

export interface ComparisonYoy {
  metric: string;
  current_label: string;
  prior_label: string;
  current: string | null;
  prior: string | null;
  delta: string | null;
  delta_pct: string | null;
  status: string;
  reason?: string | null;
}

export interface DisclosureComparison {
  comparison: {
    metric: string;
    ttm: ComparisonValue;
    yoy: ComparisonYoy;
    quarters_used: string[];
    accounting_bases: string[];
    methodology_version: string;
  };
  ttm_margin_vs_prior_year: {
    current: ComparisonValue;
    prior: ComparisonValue;
    delta: string | null;
    status: string;
    reason?: string | null;
  };
}

// ---- Price history chart (R47 P1-P5) ----

/** GET /api/companies/{id}/prices/latest: the newest stored session and its change vs the one before. */
export interface LatestPriceMissing {
  status: "INSUFFICIENT_DATA";
  company_id: string;
  reason: string;
  date: null;
  close: null;
}

export interface LatestPriceAvailable extends DailyPrice {
  status: "AVAILABLE";
  previous_close: string | null;
  previous_date: string | null;
  change: string | null;
  /** Percent, already x100 ("0.48" is 0.48%). */
  change_pct: string | null;
  change_reason: string | null;
}

export type LatestPrice = LatestPriceAvailable | LatestPriceMissing;

/** One horizon of the volatility cone; prices are 4-dp strings. */
export interface ConeHorizon {
  days: number;
  approx_date: string;
  p05: string;
  p25: string;
  p50: string;
  p75: string;
  p95: string;
}

export interface ConeCalibrationHorizon {
  days: number;
  status: "AVAILABLE" | "INSUFFICIENT_DATA";
  reason: string | null;
  n_cases: number;
  first_case: string | null;
  last_case: string | null;
  /** Shares as decimals (0.5794 is 57.9%). */
  inside_50: number | null;
  inside_50_low: number | null;
  inside_50_high: number | null;
  inside_90: number | null;
  inside_90_low: number | null;
  inside_90_high: number | null;
}

export interface ConeCalibration {
  version: string;
  cone_version: string;
  status: "AVAILABLE" | "INSUFFICIENT_DATA";
  reason: string | null;
  n_closes: number;
  horizons: ConeCalibrationHorizon[];
  step_sessions: number;
  min_cases: number;
  nominal_50: number;
  nominal_90: number;
  interval: string;
  note: string;
}

/** GET /api/technical/companies/{id}/volatility-cone: a range of typical moves, not a prediction. */
export interface VolatilityConeResponse {
  company_id: string;
  version: string;
  status: "AVAILABLE" | "INSUFFICIENT_DATA";
  reason: string | null;
  as_of: string | null;
  last_close: string | null;
  sigma_daily: number | null;
  sigma_annual: number | null;
  n_returns: number;
  window_start: string | null;
  horizons: ConeHorizon[];
  z_50: number;
  z_90: number;
  drift: string;
  calendar_note: string;
  note: string;
  calibration: ConeCalibration;
}

export interface ChartPatternPoint {
  label: string;
  date: string;
  price: string;
}

export interface ChartPatternLine {
  label: string;
  start: ChartPatternPoint;
  end: ChartPatternPoint;
}

/** One confirmed pattern occurrence (detected with the prices known at its confirmation session). */
export interface ChartPattern {
  pattern: string;
  stats_key: string;
  direction: "up" | "down";
  start_date: string;
  end_date: string;
  known_date: string;
  confirmation_date: string;
  confirmation_close: string;
  break_level: string;
  points: ChartPatternPoint[];
  lines: ChartPatternLine[];
  target: { price: string; label: string } | null;
}

export interface PatternStatsOk {
  status: "OK";
  n: number;
  n_companies: number;
  hits: number;
  /** Shares as decimals. */
  hit_rate: number;
  base_rate: number;
  difference: number;
  wilson_low: number;
  wilson_high: number;
  median_return: number;
  interval_excludes_base: boolean;
}

export interface PatternStatsMissing {
  status: "INSUFFICIENT_DATA";
  value: null;
  reason: string;
  n: number;
  n_companies: number;
}

export type PatternStats = PatternStatsOk | PatternStatsMissing;

/** GET /api/technical/companies/{id}/patterns: display only, nothing feeds the stance. */
export interface PatternsResponse {
  company_id: string;
  version: string;
  as_of: string | null;
  status: "OK" | "INSUFFICIENT_DATA";
  reason: string | null;
  /** Newest confirmation first. */
  patterns: ChartPattern[];
  note: string;
  /** stats_key -> horizon in sessions ("20" | "60") -> measured odds. */
  stats: Record<string, Partial<Record<"20" | "60", PatternStats>>>;
  universe: {
    companies: number;
    stock_days: number;
    period_start: string | null;
    period_end: string | null;
    horizons: number[];
    min_cases: number;
  };
  overlap_note: string;
  /** Shapes still forming at the last session (R47 P6), most recently known first. */
  forming: FormingChartPattern[];
  forming_note: string;
  /** Pattern type -> odds measured from the forming stage. */
  forming_stats: Record<string, FormingStats>;
}

/** A shape with no breakout yet: the closes that would confirm or invalidate it, at the last session. */
export interface FormingChartPattern {
  pattern: string;
  /** Expected break; null for a symmetrical triangle (either way). */
  expected: "up" | "down" | null;
  start_date: string;
  end_date: string;
  known_date: string;
  sessions_left: number;
  confirm_above: string | null;
  confirm_below: string | null;
  invalid_above: string | null;
  invalid_below: string | null;
  points: ChartPatternPoint[];
  lines: ChartPatternLine[];
}

interface FormingStatsBase {
  expected: "up" | "down" | null;
  n: number;
  n_companies: number;
  /** Empty for a symmetrical triangle (no expected direction before the break). */
  horizons: Partial<Record<"20" | "60", PatternStats>>;
}

export interface FormingStatsOk extends FormingStatsBase {
  status: "OK";
  confirmed: number;
  failed: number;
  expired: number;
  confirm_rate: number;
  confirm_wilson_low: number;
  confirm_wilson_high: number;
  /** Share of confirmed breaks that went up; null when none confirmed. */
  up_break_share: number | null;
}

export interface FormingStatsMissing extends FormingStatsBase {
  status: "INSUFFICIENT_DATA";
  value: null;
  reason: string;
}

export type FormingStats = FormingStatsOk | FormingStatsMissing;


// ---- AI assistant (R49 contract: .workflow/design/R49-ai-assistant-contract.md) ----

export type AssistantProviderId = "anthropic" | "openai" | "gemini";
export type AssistantLang = "en" | "ar";
export type AssistantCard = "score" | "valuation" | "stance" | "shariah" | "data_check";

export interface AssistantModel {
  id: string;
  label: string;
  provider: AssistantProviderId;
  /** The provider has a key (saved in the UI or in .env). */
  available: boolean;
  /** The model can search the web for news (R50). */
  web_search: boolean;
}

export interface AssistantModelsResponse {
  default_model: string | null;
  models: AssistantModel[];
}

export interface AssistantProviderRow {
  provider: AssistantProviderId;
  label: string;
  configured: boolean;
  source: "ui" | "env" | null;
  last4: string | null;
  set_at: string | null;
  /** Free-tier key (R49 A10): calls are stored at $0 and skip the monthly cap. */
  free_tier: boolean;
}

export interface AssistantSettings {
  providers: AssistantProviderRow[];
  default_model: string | null;
  /** Decimal string; null = no cap. */
  monthly_cap_usd: string | null;
  month_spend_usd: string | number | null;
  secrets_key_set: boolean;
}

export interface AssistantSettingsUpdate {
  default_model?: string;
  /** Decimal string, or null to switch the cap off. */
  monthly_cap_usd?: string | null;
  /** The full list of free-tier providers. */
  free_tier_providers?: AssistantProviderId[];
}

export interface AssistantKeyTest {
  ok: boolean;
  detail: string | null;
}

export interface AssistantConversationSummary {
  id: string;
  title: string;
  ticker: string | null;
  updated_at: string;
}

export interface AssistantStoredMessage {
  role: "user" | "assistant";
  content: string;
  status: "answered" | "unverified" | "error" | "cap_reached" | null;
  model: string | null;
  /** Shape is owned by the backend verifier; read defensively. */
  verification: unknown;
  created_at: string;
}

export interface AssistantConversation {
  id: string;
  title: string;
  ticker: string | null;
  messages: AssistantStoredMessage[];
}

export interface AssistantChatRequest {
  message: string;
  conversation_id?: string;
  model?: string;
  ticker?: string;
  lang: AssistantLang;
}

export interface AssistantExplainRequest {
  ticker: string;
  card: AssistantCard;
  model?: string;
  lang: AssistantLang;
}

/** Whether news was checked for an answer (R50 B16): searched | not_offered | unsupported | refused. Unknown values decode to null. */
export type AssistantNews = "searched" | "not_offered" | "unsupported" | "refused";

/** Why a provider call failed (R50 B15). Unknown values decode to null. */
export type AssistantProviderReason = "auth" | "rate_limit" | "quota" | "unavailable" | "bad_request" | "unknown";

export type AssistantStage = "thinking" | "tool" | "verifying" | "retrying";

/** A figure's origin: a data tool (optionally for one company). */
export interface AssistantDataSource {
  tool: string;
  ticker?: string | null;
}

/** A web page the model's news search cited (R50). Only http(s) URLs survive decoding. */
export interface AssistantWebSource {
  tool: "web";
  url: string;
  title: string;
}

export type AssistantSource = AssistantDataSource | AssistantWebSource;

export type AssistantStreamEvent =
  | {
      type: "meta";
      conversation_id: string | null;
      model: string | null;
      /** Whether this model can search the web this turn; null when the server did not say. */
      web_search: boolean | null;
    }
  | { type: "status"; stage: AssistantStage; tool: string | null }
  | {
      type: "answer";
      text: string;
      checked: number;
      sources: AssistantSource[];
      /** General information, not checked against our data (R50). */
      general: boolean;
      news: AssistantNews | null;
    }
  | { type: "unverified"; checked: number; unverified: string[]; sources: AssistantSource[]; news: AssistantNews | null }
  | { type: "error"; code: string; detail: string | null; reason: AssistantProviderReason | null }
  | {
      type: "done";
      input_tokens: number | null;
      output_tokens: number | null;
      cost_usd: string | number | null;
      month_spend_usd: string | number | null;
    };

// ---- Data cross-checks (R50 contract section 3): GET/POST /api/data-quality/companies/{id}/crosschecks[/run] ----

export type CrossCheckStatus = "pass" | "warn" | "fail" | "insufficient_data";

export interface CrossCheck {
  code: string;
  status: CrossCheckStatus;
  detail: string;
  /** Backend-owned shape; shown as key/value text only. */
  evidence: unknown;
}

export interface CrossCheckRun {
  company_id: string;
  /** Null when the checks have never run (then `checks` is empty). */
  computed_at: string | null;
  methodology_version: string | null;
  overall: CrossCheckStatus | null;
  checks: CrossCheck[];
}
