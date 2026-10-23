import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";
import type {
  AlertFired,
  AlertRule,
  CalculateValuationsResponse,
  Company,
  CompanyValuation,
  DailyPrice,
  DataQualityListResponse,
  DataSource,
  DisclosureDiff,
  DisclosureFact,
  DisclosureFiling,
  EgxMembership,
  EgxMembershipStatus,
  FairValueResponse,
  FinancialDocument,
  FinancialFact,
  FinancialMetric,
  FinancialPeriod,
  IndustrySnapshot,
  PaginatedResponse,
  PeerOverrideReceipt,
  PhaseEvent,
  PurificationEstimate,
  ScreeningResult,
  ScoreResponse,
  TechnicalIndicator,
  CalculateIndicatorsResponse,
  SignalsResponse,
  SyncJobStatus,
  ThesisResponse,
  UniverseCoverage,
  MarketSignal,
  ScoringModelInfo,
  SignalRun,
  UnscorableCompany,
  ScreenedCompanySummary,
  StatementBundle,
  RatioBundle,
  StanceResult,
  StanceRadarResponse,
  BillingPlan,
  BillingMe,
  CheckoutResult,
  Watchlist,
  WatchlistEntry,
} from "../types";

const API_BASE = "/api";

async function fetchApi<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// POST variant — plain fetch with a JSON body (billing checkout).
async function postApi<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// Retry once for transient failures, but never retry a 404 — the caller
// renders its not-found state from the first response (F15/F17).
function retryUnless404(failureCount: number, error: Error): boolean {
  return !error.message.includes("404") && failureCount < 1;
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

export async function getCompanyByTicker(ticker: string): Promise<Company | null> {
  const res = await fetch(`${API_BASE}/companies/ticker/${encodeURIComponent(ticker)}`);
  if (res.status === 404) return null;
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

// GET /api/scores/companies/{company_id} — 404 means unknown company;
// a known but unassessed company returns { assessment: null } (empty state).
export function useScore(companyId: string | undefined) {
  return useQuery({
    queryKey: ["score", companyId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/scores/companies/${companyId}`);
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json() as Promise<ScoreResponse>;
    },
    enabled: !!companyId,
    retry: retryUnless404,
  });
}

// POST /api/scores/companies/{company_id}/assess — plain async, not useMutation.
export async function assessScore(companyId: string): Promise<ScoreResponse> {
  const res = await fetch(`${API_BASE}/scores/companies/${companyId}/assess`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{}",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// GET /api/industry/companies/{company_id}
export function useIndustrySnapshot(companyId: string | undefined) {
  return useQuery({
    queryKey: ["industry", companyId],
    queryFn: () =>
      fetchApi<IndustrySnapshot>(`/industry/companies/${companyId}`),
    enabled: !!companyId,
    retry: retryUnless404,
  });
}

// PUT /api/industry/companies/{company_id}/peers — plain async, not useMutation.
export async function putPeerOverride(
  companyId: string,
  peerCompanyIds: string[],
): Promise<PeerOverrideReceipt> {
  const res = await fetch(`${API_BASE}/industry/companies/${companyId}/peers`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ peer_company_ids: peerCompanyIds }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// GET /api/valuation/companies/{company_id}/fair-value
export function useFairValue(companyId: string | undefined) {
  return useQuery({
    queryKey: ["fairValue", companyId],
    queryFn: () => fetchApi<FairValueResponse>(`/valuation/companies/${companyId}/fair-value`),
    enabled: !!companyId,
    retry: retryUnless404,
  });
}

// GET /api/screening/companies/{company_id}/purification — 404 means never estimated.
export function usePurification(companyId: string | undefined) {
  return useQuery({
    queryKey: ["purification", companyId],
    queryFn: async () => {
      const res = await fetch(
        `${API_BASE}/screening/companies/${companyId}/purification`,
      );
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json() as Promise<PurificationEstimate>;
    },
    enabled: !!companyId,
    retry: retryUnless404,
  });
}

// POST /api/screening/companies/{company_id}/purification — plain async.
export async function estimatePurification(
  companyId: string,
  body: {
    dividend_egp?: number;
    dps?: number;
    shares_held?: number;
    non_permissible_revenue?: number;
    total_revenue?: number;
    ratio_provenance?: string;
    dps_source?: string;
    dps_date?: string;
  },
): Promise<PurificationEstimate> {
  const res = await fetch(
    `${API_BASE}/screening/companies/${companyId}/purification`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// GET /api/screening/companies/{company_id}/egx-membership — 404 means never recorded.
// Returns the side-by-side envelope, not the flat POST record.
export function useEgxMembership(companyId: string | undefined) {
  return useQuery({
    queryKey: ["egxMembership", companyId],
    queryFn: async () => {
      const res = await fetch(
        `${API_BASE}/screening/companies/${companyId}/egx-membership`,
      );
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json() as Promise<EgxMembershipStatus>;
    },
    enabled: !!companyId,
    retry: retryUnless404,
  });
}

// POST /api/screening/companies/{company_id}/egx-membership — plain async.
export async function recordEgxMembership(
  companyId: string,
  body: { member: boolean; review_cycle: string; effective_date?: string; source: string; note?: string },
): Promise<EgxMembership> {
  const res = await fetch(
    `${API_BASE}/screening/companies/${companyId}/egx-membership`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
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
export async function getSyncStatus(): Promise<SyncJobStatus> {
  return fetchApi<SyncJobStatus>("/ingestion/sync/status");
}

export function useSyncStatus(): UseQueryResult<SyncJobStatus> {
  return useQuery({
    queryKey: ["syncStatus"],
    queryFn: getSyncStatus,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "accepted" || status === "running" ? 2000 : false;
    },
  });
}

// ─── Investment thesis (GET/POST /api/theses/companies/{id}[…]) ─

// 404 = unknown company; a known but unassessed company returns { assessment: null }.
export function useThesis(companyId: string | undefined) {
  return useQuery({
    queryKey: ["thesis", companyId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/theses/companies/${companyId}`);
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json() as Promise<ThesisResponse>;
    },
    enabled: !!companyId,
    retry: retryUnless404,
  });
}

// POST /api/theses/companies/{company_id}/assess — plain async, not useMutation.
export async function assessThesis(
  companyId: string,
  body: Record<string, unknown> = {},
): Promise<ThesisResponse> {
  const res = await fetch(`${API_BASE}/theses/companies/${companyId}/assess`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// POST /api/theses/companies/{company_id}/update — rationale required server-side.
export async function updateThesis(
  companyId: string,
  body: {
    rationale: string;
    reviewer?: string;
    classification?: string;
    invalidations?: { metric: string; status: string }[];
    catalysts?: { catalyst_id: string; outcome: string }[];
  },
): Promise<ThesisResponse> {
  const res = await fetch(`${API_BASE}/theses/companies/${companyId}/update`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ─── Disclosures (POST/GET /api/disclosures/…) ─

// GET /api/disclosures/filings?company_id= — 404 means unknown company.
export function useFilings(companyId: string | undefined) {
  return useQuery({
    queryKey: ["filings", companyId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/disclosures/filings?company_id=${companyId}`);
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json() as Promise<DisclosureFiling[]>;
    },
    enabled: !!companyId,
    retry: retryUnless404,
  });
}

// POST /api/disclosures/register — plain async.
export async function registerFiling(body: {
  company_id: string;
  filing_url: string;
  bulletin_id?: string;
  report_date: string;
  filing_type?: string;
  accounting_basis?: string;
  content_hash?: string;
}): Promise<{ filing: DisclosureFiling; created: boolean }> {
  const res = await fetch(`${API_BASE}/disclosures/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// POST /api/disclosures/upload — multipart form.
export async function uploadFiling(form: FormData): Promise<{ filing: DisclosureFiling; created: boolean }> {
  const res = await fetch(`${API_BASE}/disclosures/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// POST /api/disclosures/filings/{filing_id}/parse — plain async.
export async function parseFiling(
  filingId: string,
  body: Record<string, unknown> = {},
): Promise<unknown> {
  const res = await fetch(`${API_BASE}/disclosures/filings/${filingId}/parse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// GET /api/disclosures/facts?company_id=&metric= — 404 means unknown company.
export function useFacts(companyId: string | undefined, metric?: string) {
  const qs = metric ? `&metric=${encodeURIComponent(metric)}` : "";
  return useQuery({
    queryKey: ["facts", companyId, metric],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/disclosures/facts?company_id=${companyId}${qs}`);
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json() as Promise<DisclosureFact[]>;
    },
    enabled: !!companyId,
    retry: retryUnless404,
  });
}

// POST /api/disclosures/facts — plain async.
export async function recordFact(body: {
  filing_id: string;
  metric: string;
  value?: number;
  statement_name?: string;
  page?: number;
  table_id?: number;
  row?: number;
  col?: number;
  fact_type?: string;
  currency?: string;
  audit_state?: string;
  eas_tags?: string[];
  estimate?: number;
}): Promise<unknown> {
  const res = await fetch(`${API_BASE}/disclosures/facts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// GET /api/disclosures/comparison?company_id=&metric= — 404 unknown, 422 mixed basis.
export function useComparison(companyId: string | undefined, metric = "revenue") {
  return useQuery({
    queryKey: ["comparison", companyId, metric],
    queryFn: async () => {
      const res = await fetch(
        `${API_BASE}/disclosures/comparison?company_id=${companyId}&metric=${encodeURIComponent(metric)}`,
      );
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json() as Promise<{
        comparison: Record<string, unknown>;
        ttm_margin_vs_prior_year: Record<string, unknown>;
      }>;
    },
    enabled: !!companyId,
    retry: retryUnless404,
  });
}

// GET /api/disclosures/diffs?company_id= — 404 means unknown company.
export function useDiffs(companyId: string | undefined) {
  return useQuery({
    queryKey: ["diffs", companyId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/disclosures/diffs?company_id=${companyId}`);
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      return res.json() as Promise<DisclosureDiff[]>;
    },
    enabled: !!companyId,
    retry: retryUnless404,
  });
}

// ─── Watchlists (GET/POST/PATCH/DELETE /api/watchlists…) ─

export function useWatchlists() {
  return useQuery({
    queryKey: ["watchlists"],
    queryFn: () => fetchApi<Watchlist[]>("/watchlists"),
  });
}

export async function createWatchlist(name: string): Promise<Watchlist> {
  const res = await fetch(`${API_BASE}/watchlists`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export function useWatchlistEntries(watchlistId: string | undefined) {
  return useQuery({
    queryKey: ["watchlistEntries", watchlistId],
    queryFn: () => fetchApi<WatchlistEntry[]>(`/watchlists/${watchlistId}/entries`),
    enabled: !!watchlistId,
  });
}

export async function addWatchlistEntry(
  watchlistId: string,
  body: { company_id: string; group?: string; note?: string; thesis_link?: string },
): Promise<WatchlistEntry> {
  const res = await fetch(`${API_BASE}/watchlists/${watchlistId}/entries`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function updateWatchlistEntry(
  watchlistId: string,
  entryId: string,
  body: { group?: string; note?: string; thesis_link?: string },
): Promise<WatchlistEntry> {
  const res = await fetch(`${API_BASE}/watchlists/${watchlistId}/entries/${entryId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function deleteWatchlistEntry(watchlistId: string, entryId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/watchlists/${watchlistId}/entries/${entryId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

// ─── Alerts (GET/POST/PATCH/DELETE /api/alerts…) ─

export function useAlertRules(params: { watchlist_id?: string; company_id?: string; family?: string } = {}) {
  const searchParams = new URLSearchParams();
  if (params.watchlist_id) searchParams.set("watchlist_id", params.watchlist_id);
  if (params.company_id) searchParams.set("company_id", params.company_id);
  if (params.family) searchParams.set("family", params.family);
  const qs = searchParams.toString();
  return useQuery({
    queryKey: ["alertRules", params],
    queryFn: () => fetchApi<AlertRule[]>(`/alerts${qs ? `?${qs}` : ""}`),
  });
}

export async function createAlertRule(body: {
  family: string;
  params?: Record<string, unknown>;
  watchlist_id?: string;
  company_id?: string;
  enabled?: boolean;
}): Promise<AlertRule> {
  const res = await fetch(`${API_BASE}/alerts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function updateAlertRule(
  alertId: string,
  body: { params?: Record<string, unknown>; enabled?: boolean },
): Promise<AlertRule> {
  const res = await fetch(`${API_BASE}/alerts/${alertId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function deleteAlertRule(alertId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/alerts/${alertId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
}

export function useFiredAlerts(params: { rule_id?: string; company_id?: string; acked?: boolean } = {}) {
  const searchParams = new URLSearchParams();
  if (params.rule_id) searchParams.set("rule_id", params.rule_id);
  if (params.company_id) searchParams.set("company_id", params.company_id);
  if (params.acked !== undefined) searchParams.set("acked", String(params.acked));
  const qs = searchParams.toString();
  return useQuery({
    queryKey: ["firedAlerts", params],
    queryFn: () => fetchApi<AlertFired[]>(`/alerts/fired${qs ? `?${qs}` : ""}`),
  });
}

export async function ackFiredAlert(firedId: string): Promise<AlertFired> {
  const res = await fetch(`${API_BASE}/alerts/${firedId}/ack`, { method: "POST" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// ─── Events ledger (GET /api/events…) ─

export function useEvents(params: { symbol?: string; type?: string; date_from?: string; date_to?: string } = {}) {
  const searchParams = new URLSearchParams();
  if (params.symbol) searchParams.set("symbol", params.symbol);
  if (params.type) searchParams.set("type", params.type);
  if (params.date_from) searchParams.set("date_from", params.date_from);
  if (params.date_to) searchParams.set("date_to", params.date_to);
  const qs = searchParams.toString();
  return useQuery({
    queryKey: ["events", params],
    queryFn: () => fetchApi<PhaseEvent[]>(`/events${qs ? `?${qs}` : ""}`),
  });
}

export async function exportEvents(params: { symbol?: string; type?: string; date_from?: string; date_to?: string } = {}): Promise<{
  events: PhaseEvent[];
  total: number;
  filters: Record<string, unknown>;
}> {
  const searchParams = new URLSearchParams();
  if (params.symbol) searchParams.set("symbol", params.symbol);
  if (params.type) searchParams.set("type", params.type);
  if (params.date_from) searchParams.set("date_from", params.date_from);
  if (params.date_to) searchParams.set("date_to", params.date_to);
  const qs = searchParams.toString();
  const res = await fetch(`${API_BASE}/events/export${qs ? `?${qs}` : ""}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
export function useStatements(ticker: string | undefined) {
  return useQuery({
    queryKey: ["statements", ticker],
    queryFn: () => fetchApi<StatementBundle>(`/statements/companies/${ticker}/statements`),
    enabled: !!ticker,
  });
}

export function useRatios(ticker: string | undefined) {
  return useQuery({
    queryKey: ["ratios", ticker],
    queryFn: () => fetchApi<RatioBundle>(`/statements/companies/${ticker}/ratios`),
    enabled: !!ticker,
  });
}

export function useStance(ticker: string | undefined, params?: { entry_price?: number; stop_pct?: number }) {
  const sp = new URLSearchParams();
  if (params?.entry_price !== undefined) sp.set("entry_price", String(params.entry_price));
  if (params?.stop_pct !== undefined) sp.set("stop_pct", String(params.stop_pct));
  const qs = sp.toString();
  return useQuery({
    queryKey: ["stance", ticker, params],
    queryFn: () => fetchApi<StanceResult>(`/stance/companies/${ticker}${qs ? `?${qs}` : ""}`),
    enabled: !!ticker,
  });
}

export function useStanceRadar(pageSize = 50) {
  return useQuery({
    queryKey: ["stanceRadar", pageSize],
    queryFn: () => fetchApi<StanceRadarResponse>(`/stance/radar?page_size=${pageSize}`),
  });
}

export function useBillingPlans() {
  return useQuery({
    queryKey: ["billingPlans"],
    queryFn: () => fetchApi<BillingPlan[]>(`/billing/plans`),
  });
}

export function useMyBilling(userKey: string | undefined) {
  return useQuery({
    queryKey: ["billingMe", userKey],
    queryFn: () => fetchApi<BillingMe>(`/billing/me?user_key=${encodeURIComponent(userKey!)}`),
    enabled: !!userKey,
  });
}

export function useCheckout() {
  return useMutation({
    mutationFn: (payload: { user_key: string; tier: string }) =>
      postApi<CheckoutResult>(`/billing/checkout`, payload),
  });
}

