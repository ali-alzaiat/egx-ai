import type { CopyKey } from "../../i18n";
import type {
  Company,
  DisclosureFact,
  DisclosureFiling,
  IndustryPeer,
  ThesisCatalyst,
  ThesisInvalidation,
} from "../../types";

// Server-pinned enums (backend/app/ingestion/disclosures/constants.py, thesis/constants.py).
// Selects are built from these so a form can never submit a value the API rejects.
export const FILING_TYPES = ["Q", "H1", "9M", "FY", "BOARD", "AGM", "MATERIAL"] as const;
export const ACCOUNTING_BASES = ["EAS", "EAS+CBE", "IFRS"] as const;
export const INVALIDATION_STATUSES = ["Active", "Triggered", "Reassessed"] as const;
export const LEDGER_CLASSIFICATIONS = ["Confirmed", "Pending", "Challenged", "Invalidated", "New"] as const;
export const CATALYST_OUTCOMES = ["Pending", "Hit", "Miss", "Pushed"] as const;

export const FILING_TYPE_KEY: Record<(typeof FILING_TYPES)[number], CopyKey> = {
  Q: "adm_type_q",
  H1: "adm_type_h1",
  "9M": "adm_type_9m",
  FY: "adm_type_fy",
  BOARD: "adm_type_board",
  AGM: "adm_type_agm",
  MATERIAL: "adm_type_material",
};

export const CLASSIFICATION_KEY: Record<(typeof LEDGER_CLASSIFICATIONS)[number], CopyKey> = {
  Confirmed: "adm_class_confirmed",
  Pending: "adm_class_pending",
  Challenged: "adm_class_challenged",
  Invalidated: "adm_class_invalidated",
  New: "adm_class_new",
};

export const INVALIDATION_KEY: Record<(typeof INVALIDATION_STATUSES)[number], CopyKey> = {
  Active: "adm_inv_active",
  Triggered: "adm_inv_triggered",
  Reassessed: "adm_inv_reassessed",
};

export const OUTCOME_KEY: Record<(typeof CATALYST_OUTCOMES)[number], CopyKey> = {
  Pending: "adm_out_pending",
  Hit: "adm_out_hit",
  Miss: "adm_out_miss",
  Pushed: "adm_out_pushed",
};

/** Look up a localized label for a server enum value; unknown values are shown as sent. */
export function enumLabel<K extends string>(
  value: string,
  keys: Readonly<Record<K, CopyKey>>,
  t: (key: CopyKey) => string,
): string {
  return value in keys ? t(keys[value as K]) : value;
}

export type ParseState = "parsed" | "no_facts" | "reference";

/**
 * A stored PDF with at least one parsed fact pointing at it is "parsed"; stored
 * bytes with none are "no_facts" (the only state that offers "Parse again");
 * a URL-only registration has nothing to parse.
 */
export function filingParseState(filing: DisclosureFiling, facts: readonly DisclosureFact[]): ParseState {
  if (!filing.has_bytes) return "reference";
  return facts.some((f) => f.source?.filing_url === filing.filing_url) ? "parsed" : "no_facts";
}

export interface ParseOutcome {
  status: "none" | "ok" | "failed";
  facts: number;
  reason: string | null;
}

/** Reads the `parse` block of an upload response ({status, reason, facts[]}); missing means not attempted. */
export function parseOutcome(response: unknown): ParseOutcome {
  const parse = (response as { parse?: unknown } | null)?.parse;
  if (parse === null || parse === undefined || typeof parse !== "object") {
    return { status: "none", facts: 0, reason: null };
  }
  const { status, reason, facts } = parse as { status?: unknown; reason?: unknown; facts?: unknown };
  const count = Array.isArray(facts) ? facts.length : 0;
  const text = typeof reason === "string" && reason !== "" ? reason : null;
  return status === "OK" ? { status: "ok", facts: count, reason: null } : { status: "failed", facts: 0, reason: text };
}

/** Optional text fields are sent only when filled in. */
export function optionalFields<K extends string>(values: Record<K, string>): Partial<Record<K, string>> {
  const out: Partial<Record<K, string>> = {};
  for (const key of Object.keys(values) as K[]) {
    const value = values[key].trim();
    if (value !== "") out[key] = value;
  }
  return out;
}

export type PeerIssue = "self" | "duplicate";

/** Adds a peer to the draft list; the company itself and repeats are refused with a reason. */
export function addPeer(
  draft: readonly IndustryPeer[],
  selfId: string,
  company: Pick<Company, "id" | "ticker" | "name">,
): { draft: IndustryPeer[]; issue: PeerIssue | null } {
  if (company.id === selfId) return { draft: [...draft], issue: "self" };
  if (draft.some((p) => p.id === company.id)) return { draft: [...draft], issue: "duplicate" };
  return { draft: [...draft, { id: company.id, ticker: company.ticker, name: company.name }], issue: null };
}

export function removePeer(draft: readonly IndustryPeer[], id: string): IndustryPeer[] {
  return draft.filter((p) => p.id !== id);
}

/** True when the draft differs from the saved list (order ignored). */
export function peersChanged(saved: readonly IndustryPeer[], draft: readonly IndustryPeer[]): boolean {
  if (saved.length !== draft.length) return true;
  const ids = new Set(saved.map((p) => p.id));
  return draft.some((p) => !ids.has(p.id));
}

/** Only invalidation rows the reviewer actually changed travel to the API. */
export function changedInvalidations(
  rows: readonly ThesisInvalidation[],
  chosen: Readonly<Record<string, string>>,
): { metric: string; status: string }[] {
  const out: { metric: string; status: string }[] = [];
  for (const row of rows) {
    const next = chosen[row.metric];
    if (next !== undefined && next !== row.status) out.push({ metric: row.metric, status: next });
  }
  return out;
}

export function changedCatalysts(
  rows: readonly ThesisCatalyst[],
  chosen: Readonly<Record<string, string>>,
): { catalyst_id: string; outcome: string }[] {
  const out: { catalyst_id: string; outcome: string }[] = [];
  for (const row of rows) {
    const next = chosen[row.id];
    if (next !== undefined && next !== row.outcome) out.push({ catalyst_id: row.id, outcome: next });
  }
  return out;
}

/** Shortens a URL for a table cell, keeping the host and the tail readable. */
export function shortUrl(url: string, max = 48): string {
  return url.length > max ? `${url.slice(0, max - 1)}…` : url;
}
