import { useQuery } from "@tanstack/react-query";
import type {
  Company,
  DailyPrice,
  DataSource,
  FinancialDocument,
  FinancialFact,
  FinancialMetric,
  FinancialPeriod,
  PaginatedResponse,
  TechnicalIndicator,
  CalculateIndicatorsResponse,
  SignalsResponse,
  UniverseCoverage,
  MarketSignal,
  ScoringModelInfo,
  SignalRun,
  UnscorableCompany,
} from "../types";

const API_BASE = "/api";

async function fetchApi<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
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
    queryFn: () => fetchApi<MarketSignal>(`/signals/\${ticker}`),
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
