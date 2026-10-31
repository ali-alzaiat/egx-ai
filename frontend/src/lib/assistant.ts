import type { CopyKey } from "../i18n";
import type { AssistantSource, AssistantStage, AssistantStreamEvent } from "../types";
import type { SseMessage } from "./sse";

/** Pure helpers for the AI assistant (R49): stream decoding, error bodies, source links, error copy. */

type Rec = Record<string, unknown>;

function isRec(v: unknown): v is Rec {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function str(v: unknown): string | null {
  return typeof v === "string" ? v : null;
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function strOrNum(v: unknown): string | number | null {
  return typeof v === "string" || (typeof v === "number" && Number.isFinite(v)) ? v : null;
}

const STAGES: readonly AssistantStage[] = ["thinking", "tool", "verifying", "retrying"];

function stageOf(v: unknown): AssistantStage | null {
  return STAGES.find((s) => s === v) ?? null;
}

export function parseSources(v: unknown): AssistantSource[] {
  if (!Array.isArray(v)) return [];
  const out: AssistantSource[] = [];
  for (const item of v) {
    if (!isRec(item)) continue;
    const tool = str(item.tool);
    if (tool === null || tool === "") continue;
    out.push({ tool, ticker: str(item.ticker) });
  }
  return out;
}

function strings(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}

/** Turn one SSE message into a typed event; unknown or malformed messages return null (never thrown). */
export function decodeAssistantEvent(msg: SseMessage): AssistantStreamEvent | null {
  let body: unknown;
  try {
    body = JSON.parse(msg.data);
  } catch {
    return null;
  }
  if (!isRec(body)) return null;
  switch (msg.event) {
    case "meta":
      return { type: "meta", conversation_id: str(body.conversation_id), model: str(body.model) };
    case "status": {
      const stage = stageOf(body.stage);
      return stage === null ? null : { type: "status", stage, tool: str(body.tool) };
    }
    case "answer": {
      const text = str(body.text);
      if (text === null) return null;
      return { type: "answer", text, checked: num(body.checked) ?? 0, sources: parseSources(body.sources) };
    }
    case "unverified":
      return {
        type: "unverified",
        checked: num(body.checked) ?? 0,
        unverified: strings(body.unverified),
        sources: parseSources(body.sources),
      };
    case "error":
      return { type: "error", code: str(body.code) ?? "UNKNOWN", detail: str(body.detail) };
    case "done":
      return {
        type: "done",
        input_tokens: num(body.input_tokens),
        output_tokens: num(body.output_tokens),
        cost_usd: strOrNum(body.cost_usd),
        month_spend_usd: strOrNum(body.month_spend_usd),
      };
    default:
      return null;
  }
}

const CODE_SHAPE = /^[A-Z][A-Z0-9_]{2,}$/;

/** Read an error body from any shape a FastAPI endpoint answers with: {detail: "CODE"}, {detail: {code, detail}}, {code, detail}, validation lists. */
export function parseApiErrorBody(body: unknown): { code: string | null; detail: string | null } {
  if (!isRec(body)) return { code: null, detail: null };
  const top = str(body.code);
  const d = body.detail;
  if (typeof d === "string") {
    return CODE_SHAPE.test(d) ? { code: d, detail: null } : { code: top, detail: d };
  }
  if (isRec(d)) {
    return { code: str(d.code) ?? top, detail: str(d.detail) ?? str(d.message) ?? str(d.msg) };
  }
  if (Array.isArray(d)) {
    const first = d.find(isRec);
    return { code: top, detail: first ? str(first.msg) : null };
  }
  return { code: top, detail: null };
}

/** Copy for an assistant error. `settings` adds a link to Admin > AI settings. */
export interface AssistantErrorCopy {
  key: CopyKey;
  settings: boolean;
}

const ERROR_COPY: Record<string, AssistantErrorCopy> = {
  NO_KEY: { key: "assistant_err_no_key", settings: true },
  CAP_REACHED: { key: "assistant_err_cap", settings: true },
  PROVIDER_ERROR: { key: "assistant_err_provider", settings: false },
  INSUFFICIENT_DATA: { key: "assistant_err_insufficient", settings: false },
  UNKNOWN_MODEL: { key: "assistant_err_model", settings: true },
  HTTP_404: { key: "assistant_err_not_found", settings: false },
  HTTP_422: { key: "assistant_err_rejected", settings: false },
  HTTP_401: { key: "assistant_err_auth", settings: false },
  HTTP_403: { key: "assistant_err_auth", settings: false },
  HTTP_5XX: { key: "assistant_err_server", settings: false },
  NETWORK: { key: "assistant_err_network", settings: false },
  STREAM_INTERRUPTED: { key: "assistant_err_interrupted", settings: false },
};

const FALLBACK_COPY: AssistantErrorCopy = { key: "assistant_err_generic", settings: false };

export function assistantErrorCopy(code: string): AssistantErrorCopy {
  return ERROR_COPY[code] ?? FALLBACK_COPY;
}

/** Chat error code for a request that failed before the stream started. */
export function httpErrorCode(status: number, code: string | null): string {
  if (code !== null && code in ERROR_COPY) return code;
  if (status >= 500) return "HTTP_5XX";
  return `HTTP_${status}`;
}

/** Where a source chip links: the company tab that shows the same figures. */
export function sourceHref(source: AssistantSource): string | null {
  const ticker = source.ticker?.trim();
  if (!ticker) return null;
  const base = `/companies/${encodeURIComponent(ticker)}`;
  switch (source.tool) {
    case "investment_score":
      return `${base}/valuation#score`;
    case "valuation":
      return `${base}/valuation`;
    case "stance":
    case "price_summary":
    case "chart_patterns":
      return `${base}/price`;
    case "shariah_status":
      return `${base}/shariah`;
    case "financial_metrics":
      return `${base}/financials/metrics`;
    default:
      return base;
  }
}

const TOOL_KEYS: Record<string, CopyKey> = {
  company_overview: "assistant_tool_company_overview",
  investment_score: "assistant_tool_investment_score",
  valuation: "assistant_tool_valuation",
  stance: "assistant_tool_stance",
  shariah_status: "assistant_tool_shariah_status",
  price_summary: "assistant_tool_price_summary",
  chart_patterns: "assistant_tool_chart_patterns",
  financial_metrics: "assistant_tool_financial_metrics",
  search_companies: "assistant_tool_search_companies",
  screen_companies: "assistant_tool_screen_companies",
};

/** Copy key naming a tool; null for tools this build does not know (the raw name is shown). */
export function toolKey(tool: string): CopyKey | null {
  return TOOL_KEYS[tool] ?? null;
}

/** One chip per tool+ticker pair, in first-seen order. */
export function uniqueSources(sources: readonly AssistantSource[]): AssistantSource[] {
  const seen = new Set<string>();
  const out: AssistantSource[] = [];
  for (const s of sources) {
    const id = `${s.tool}|${s.ticker ?? ""}`;
    if (seen.has(id)) continue;
    seen.add(id);
    out.push(s);
  }
  return out;
}

/** Ticker of the company page the user is on, or null elsewhere. */
export function tickerFromPath(pathname: string): string | null {
  const match = /^\/companies\/([^/]+)/.exec(pathname);
  if (!match?.[1]) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}

/** A cap typed in the admin form: empty = off (null), else a non-negative decimal with at most 2 places. */
export function parseCapInput(raw: string): { ok: true; value: string | null } | { ok: false } {
  const text = raw.trim();
  if (text === "") return { ok: true, value: null };
  return /^\d{1,9}(\.\d{1,2})?$/.test(text) ? { ok: true, value: text } : { ok: false };
}

/** A stored cap as the input shows it: padding zeros dropped ("0.0000" -> "0", "12.50" -> "12.5"); empty when off. */
export function capInputValue(stored: string | null): string {
  if (stored === null) return "";
  return stored.includes(".") ? stored.replace(/0+$/, "").replace(/\.$/, "") : stored;
}

/** The model to use: the saved choice if it is still available, else the server default, else the first available; null when none. */
export function pickModel(
  models: readonly { id: string; available: boolean }[],
  defaultModel: string | null,
  stored: string | null,
): string | null {
  const available = models.filter((m) => m.available);
  const has = (id: string | null): id is string => id !== null && available.some((m) => m.id === id);
  if (has(stored)) return stored;
  if (has(defaultModel)) return defaultModel;
  return available[0]?.id ?? null;
}
