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
}

export interface ScreeningResult {
  id: string;
  company_id: string;
  is_compliant: boolean;
  status: string; // COMPLIANT | NON_COMPLIANT | INSUFFICIENT_DATA
  methodology_version: string;
  methodology_name: string;
  overall_reason: string | null;
  screened_at: string;
  created_at: string;
  rule_results: ScreeningRuleResult[];
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
