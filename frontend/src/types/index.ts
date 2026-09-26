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

export interface ApiError {
  detail: string
}
