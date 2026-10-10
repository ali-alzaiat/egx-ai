import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import type {
  CalculateValuationsResponse,
  Company,
  CompanyValuation,
  DailyPrice,
  DataQualityListResponse,
  DataSource,
  FinancialDocument,
  FinancialFact,
  FinancialMetric,
  FinancialPeriod,
  PaginatedResponse,
  ScreeningResult,
  TechnicalIndicator,
  CalculateIndicatorsResponse,
  SignalsResponse,
  SyncJobStatus,
  UniverseCoverage,
  MarketSignal,
  ScoringModelInfo,
  SignalRun,
  UnscorableCompany,
  ScreenedCompanySummary,
} from "../types";

const API_BASE = "/api";

async function fetchApi<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// Retry once for transient failures, but never retry a 404 — the caller
// renders its not-found state from the first response (F15/F17).
function retryUnless404(failureCount: number, error: Error): boolean {
  return !error.message.includes("404") && failureCount < 1;
}

export function useHealthCheck() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => fetchApi<{ status: string; version: string }>("/health"),
  });
}

export function useCompanies(params: {
  page?: number;
  page_size?: number;
  sector?: string;
  status?: string;
  search?: string;
}) {
  const searchParams = new URLSearchParams();
  if (params.page) searchParams.set("page", String(params.page));
  if (params.page_size) searchParams.set("page_size", String(params.page_size));
  if (params.sector) searchParams.set("sector", params.sector);
  if (params.status) searchParams.set("status", params.status);
  if (params.search) searchParams.set("search", params.search);
  const qs = searchParams.toString();
  return useQuery({
    queryKey: ["companies", params],
    queryFn: () =>
      fetchApi<PaginatedResponse<Company>>(`/companies${qs ? `?${qs}` : ""}`),
    placeholderData: keepPreviousData,
  });
}

export function useCompany(id: string | undefined) {
  return useQuery({
    queryKey: ["company", id],
    queryFn: () => fetchApi<Company>(`/companies/${id}`),
    enabled: !!id,
  });
}

export function useCompanyByTicker(ticker: string | undefined) {
  return useQuery({
    queryKey: ["company", "ticker", ticker],
    queryFn: () => fetchApi<Company>(`/companies/ticker/${ticker}`),
    enabled: !!ticker,
    retry: retryUnless404,
  })
}

export function useDataQuality(companyId: string | undefined, scope?: string) {
  const qs = scope ? `?scope=${encodeURIComponent(scope)}` : "";
  return useQuery({
    queryKey: ["dataQuality", companyId, scope],
    queryFn: () =>
      fetchApi<DataQualityListResponse>(
        `/data-quality/companies/${companyId}${qs}`,
      ),
    enabled: !!companyId,
  });
}

export function useCompanyPrices(
  companyId: string | undefined,
  params: {
    start_date?: string;
    end_date?: string;
    page?: number;
    page_size?: number;
  },
) {
  const searchParams = new URLSearchParams();
  if (params.start_date) searchParams.set("start_date", params.start_date);
  if (params.end_date) searchParams.set("end_date", params.end_date);
  if (params.page) searchParams.set("page", String(params.page));
  if (params.page_size) searchParams.set("page_size", String(params.page_size));
  const qs = searchParams.toString();
  return useQuery({
    queryKey: ["prices", companyId, params],
    queryFn: () =>
      fetchApi<PaginatedResponse<DailyPrice>>(
        `/companies/${companyId}/prices${qs ? `?${qs}` : ""}`,
      ),
    enabled: !!companyId,
  });
}

export function useLatestPrice(companyId: string | undefined) {
  return useQuery({
    queryKey: ["latestPrice", companyId],
    queryFn: () =>
      fetchApi<DailyPrice>(`/companies/${companyId}/prices/latest`),
    enabled: !!companyId,
    retry: retryUnless404,
  });
}

export function useSignals(
  params: {
    limit?: number;
    offset?: number;
    tier?: string;
    min_score?: number;
    as_of?: string;
  } = {},
) {
  const searchParams = new URLSearchParams();
  if (params.limit) searchParams.set("limit", String(params.limit));
  if (params.offset) searchParams.set("offset", String(params.offset));
  if (params.tier) searchParams.set("tier", params.tier);
  if (params.min_score !== undefined)
    searchParams.set("min_score", String(params.min_score));
  if (params.as_of) searchParams.set("as_of", params.as_of);
  const qs = searchParams.toString();
  return useQuery({
    queryKey: ["signals", params],
    queryFn: () => fetchApi<SignalsResponse>(`/signals${qs ? `?${qs}` : ""}`),
    placeholderData: keepPreviousData,
  });
}

export function useSignalCoverage() {
  return useQuery({
    queryKey: ["signals", "coverage"],
    queryFn: () => fetchApi<UniverseCoverage>("/signals/coverage"),
  });
}

export function useScoringModel() {
  return useQuery({
    queryKey: ["signals", "model"],
    queryFn: () => fetchApi<ScoringModelInfo>("/signals/model"),
  });
}

export function useUnscorable() {
  return useQuery({
    queryKey: ["signals", "unscorable"],
    queryFn: () => fetchApi<UnscorableCompany[]>("/signals/unscorable"),
  });
}

export function useSignalForTicker(ticker: string | undefined) {
  return useQuery({
    queryKey: ["signals", "ticker", ticker],
    queryFn: () => fetchApi<MarketSignal>(`/signals/${ticker}`),
    enabled: !!ticker,
  });
}

export async function runSignals(): Promise<SignalRun> {
  const res = await fetch(`${API_BASE}/signals/run`, { method: "POST" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
export function useDataSources() {
  return useQuery({
    queryKey: ["dataSources"],
    queryFn: () => fetchApi<DataSource[]>("/data-sources"),
  });
}

export function useFinancialPeriods(companyId: string | undefined) {
  return useQuery({
    queryKey: ["financialPeriods", companyId],
    queryFn: () =>
      fetchApi<FinancialPeriod[]>(`/financial/periods/${companyId}`),
    enabled: !!companyId,
  });
}

export function useFinancialDocuments(periodId: string | undefined) {
  return useQuery({
    queryKey: ["financialDocuments", periodId],
    queryFn: () =>
      fetchApi<FinancialDocument[]>(`/financial/documents/${periodId}`),
    enabled: !!periodId,
  });
}

export function useFinancialFacts(
  companyId: string | undefined,
  params?: {
    fact_type?: string;
    fiscal_year?: number;
  },
) {
  const searchParams = new URLSearchParams();
  if (params?.fact_type) searchParams.set("fact_type", params.fact_type);
  if (params?.fiscal_year)
    searchParams.set("fiscal_year", String(params.fiscal_year));
  const qs = searchParams.toString();
  return useQuery({
    queryKey: ["financialFacts", companyId, params],
    queryFn: () =>
      fetchApi<FinancialFact[]>(
        `/financial/facts/${companyId}${qs ? `?${qs}` : ""}`,
      ),
    enabled: !!companyId,
  });
}

export function useLatestFinancialFacts(
  companyId: string | undefined,
  params?: {
    fact_type?: string;
  },
) {
  const searchParams = new URLSearchParams();
  if (params?.fact_type) searchParams.set("fact_type", params.fact_type);
  const qs = searchParams.toString();
  return useQuery({
    queryKey: ["latestFinancialFacts", companyId, params],
    queryFn: () =>
      fetchApi<FinancialFact[]>(
        `/financial/facts/${companyId}/latest${qs ? `?${qs}` : ""}`,
      ),
    enabled: !!companyId,
  });
}

// Metrics API hooks
export function useCompanyMetrics(companyId: string | undefined) {
  return useQuery({
    queryKey: ["metrics", companyId],
    queryFn: () =>
      fetchApi<FinancialMetric[]>(`/metrics/companies/${companyId}`),
    enabled: !!companyId,
  });
}

export function useCompanyPeriodMetrics(
  companyId: string | undefined,
  periodId: string | undefined,
) {
  return useQuery({
    queryKey: ["metrics", companyId, periodId],
    queryFn: () =>
      fetchApi<FinancialMetric[]>(
        `/metrics/companies/${companyId}/periods/${periodId}`,
      ),
    enabled: !!companyId && !!periodId,
  });
}

export function useMetricDetail(
  companyId: string | undefined,
  periodId: string | undefined,
  metricCode: string | undefined,
) {
  return useQuery({
    queryKey: ["metrics", companyId, periodId, metricCode],
    queryFn: () =>
      fetchApi<FinancialMetric>(
        `/metrics/companies/${companyId}/periods/${periodId}/${metricCode}`,
      ),
    enabled: !!companyId && !!periodId && !!metricCode,
  });
}

// Technical Analysis API hooks
export function useTechnicalIndicators(
  companyId: string | undefined,
  indicatorType?: string,
) {
  const searchParams = new URLSearchParams();
  if (indicatorType) searchParams.set("indicator_type", indicatorType);
  const qs = searchParams.toString();
  return useQuery({
    queryKey: ["technical", companyId, indicatorType],
    queryFn: () =>
      fetchApi<TechnicalIndicator[]>(
        `/technical/companies/${companyId}${qs ? `?${qs}` : ""}`,
      ),
    enabled: !!companyId,
  });
}

export async function calculateIndicators(
  companyId: string,
  prices: string,
  volumes: string,
  indicatorTypes?: string,
): Promise<CalculateIndicatorsResponse> {
  const searchParams = new URLSearchParams();
  searchParams.set("prices", prices);
  searchParams.set("volumes", volumes);
  if (indicatorTypes) searchParams.set("indicator_types", indicatorTypes);
  const qs = searchParams.toString();
  const res = await fetch(
    `${API_BASE}/technical/companies/${companyId}/calculate?${qs}`,
    {
      method: "POST",
    },
  );
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// GET /api/screening/companies (backend/app/api/screening.py::list_screened_companies)
export function useScreenedCompanies(params: {
  is_compliant?: boolean;
  methodology_version?: string;
} = {}) {
  const searchParams = new URLSearchParams();
  if (params.is_compliant !== undefined)
    searchParams.set("is_compliant", String(params.is_compliant));
  if (params.methodology_version)
    searchParams.set("methodology_version", params.methodology_version);
  const qs = searchParams.toString();
  return useQuery({
    queryKey: ["screenedCompanies", params],
    queryFn: () =>
      fetchApi<ScreenedCompanySummary[]>(
        `/screening/companies${qs ? `?${qs}` : ""}`,
      ),
  });
}

// GET /api/screening/companies/{company_id} — 404 means never screened,
// which is an empty state (null), not an error.
export function useScreeningResult(
  companyId: string | undefined,
): UseQueryResult<ScreeningResult | null> {
  return useQuery({
    queryKey: ["screening", companyId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/screening/companies/${companyId}`);
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json() as Promise<ScreeningResult>;
    },
    enabled: !!companyId,
    retry: retryUnless404,
  });
}

// POST /api/screening/companies/{company_id}/screen — plain async, not useMutation.
export async function screenCompany(companyId: string): Promise<ScreeningResult> {
  const res = await fetch(`${API_BASE}/screening/companies/${companyId}/screen`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// GET /api/valuation/companies/{company_id}
export function useValuations(companyId: string | undefined) {
  return useQuery({
    queryKey: ["valuations", companyId],
    queryFn: () =>
      fetchApi<CompanyValuation[]>(`/valuation/companies/${companyId}`),
    enabled: !!companyId,
    retry: retryUnless404,
  });
}

// POST /api/valuation/companies/{company_id}/calculate — plain async, not
// useMutation. Empty call evaluates every model with no supplied assumptions.
export async function calculateValuations(
  companyId: string,
  params?: Record<string, number | undefined>,
): Promise<CalculateValuationsResponse> {
  const searchParams = new URLSearchParams();
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && !Number.isNaN(value)) {
        searchParams.set(key, String(value));
      }
    }
  }
  const qs = searchParams.toString();
  const res = await fetch(
    `${API_BASE}/valuation/companies/${companyId}/calculate${qs ? `?${qs}` : ""}`,
    { method: "POST" },
  );
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// POST /api/metrics/companies/{company_id}/calculate — plain async, not useMutation.
export async function calculateMetrics(companyId: string): Promise<{
  company_id: string;
  periods_calculated: number;
  metrics_persisted: number;
}> {
  const res = await fetch(
    `${API_BASE}/metrics/companies/${companyId}/calculate`,
    { method: "POST" },
  );
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// POST /api/ingestion/sync — follows the runSignals pattern (plain fetch,
// not useMutation). 409 means a job is already live: adopt the returned job
// and start polling it instead of throwing.
export async function startMarketRefresh(params?: {
  tickers?: string;
  history_days?: number;
  universe_only?: boolean;
}): Promise<SyncJobStatus> {
  const searchParams = new URLSearchParams();
  if (params?.tickers) searchParams.set("tickers", params.tickers);
  if (params?.history_days !== undefined)
    searchParams.set("history_days", String(params.history_days));
  if (params?.universe_only !== undefined)
    searchParams.set("universe_only", String(params.universe_only));
  const qs = searchParams.toString();
  const res = await fetch(`${API_BASE}/ingestion/sync${qs ? `?${qs}` : ""}`, {
    method: "POST",
  });
  if (res.status === 409) return res.json() as Promise<SyncJobStatus>;
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// GET /api/ingestion/sync/status — polls every 2 s only while a job is live.
export function useSyncStatus(): UseQueryResult<SyncJobStatus> {
  return useQuery({
    queryKey: ["syncStatus"],
    queryFn: () => fetchApi<SyncJobStatus>("/ingestion/sync/status"),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "accepted" || status === "running" ? 2000 : false;
    },
  });
}
