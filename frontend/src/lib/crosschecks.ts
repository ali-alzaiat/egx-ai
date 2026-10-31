import type { CopyKey } from "../i18n";
import type { CrossCheckStatus } from "../types";

/** Pure helpers for the Quality tab's cross-checks (R50): status words, check names, evidence as plain key/value text. */

export type CrossCheckTone = "gain" | "warn" | "loss" | "muted";

const STATUS: Record<CrossCheckStatus, { tone: CrossCheckTone; key: CopyKey }> = {
  pass: { tone: "gain", key: "xc_status_pass" },
  warn: { tone: "warn", key: "xc_status_warn" },
  fail: { tone: "loss", key: "xc_status_fail" },
  insufficient_data: { tone: "muted", key: "xc_status_insufficient" },
};

/** Tone (badge variant) and copy key for a status; anything unexpected reads as insufficient data, never as a pass. */
export function crossCheckStatus(status: string): { tone: CrossCheckTone; key: CopyKey } {
  return status in STATUS ? STATUS[status as CrossCheckStatus] : STATUS.insufficient_data;
}

const CODE_KEYS: Record<string, CopyKey> = {
  provenance: "xc_check_provenance",
  cross_source: "xc_check_cross_source",
  accounting_identity: "xc_check_accounting_identity",
  price_sanity: "xc_check_price_sanity",
  freshness: "xc_check_freshness",
};

/** Copy key naming a check; null for a code this build does not know (the raw code is shown). */
export function crossCheckNameKey(code: string): CopyKey | null {
  return CODE_KEYS[code] ?? null;
}

export interface EvidenceRow {
  key: string;
  value: string;
}

const MAX_ROWS = 24;
const MAX_VALUE = 200;
const MAX_DEPTH = 2;

function scalar(v: unknown): string | null {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v.length > MAX_VALUE ? `${v.slice(0, MAX_VALUE)}…` : v;
  if (typeof v === "number") return Number.isFinite(v) ? String(v) : "—";
  if (typeof v === "boolean") return v ? "true" : "false";
  return null;
}

function walk(v: unknown, prefix: string, depth: number, code: string, out: EvidenceRow[]): void {
  if (out.length >= MAX_ROWS) return;
  if (Array.isArray(v)) {
    const simple = v.every((x) => scalar(x) !== null);
    if (simple) {
      out.push({ key: prefix, value: v.map((x) => scalar(x)).join(", ") || "—" });
      return;
    }
    v.forEach((item, i) => walk(item, `${prefix}[${i}]`, depth + 1, code, out));
    return;
  }
  if (typeof v === "object" && v !== null) {
    if (depth >= MAX_DEPTH) {
      out.push({ key: prefix, value: "…" });
      return;
    }
    for (const [k, inner] of Object.entries(v)) {
      // The cross-source check shows only the band and our own value: never surface a vendor figure, whatever the server sends.
      if (code === "cross_source" && /vendor/i.test(k)) continue;
      walk(inner, prefix === "" ? k : `${prefix}.${k}`, depth + 1, code, out);
    }
    return;
  }
  out.push({ key: prefix === "" ? "value" : prefix, value: scalar(v) ?? "—" });
}

/** Evidence of any shape as flat key/value text rows (capped), safe to render as text. */
export function evidenceRows(evidence: unknown, code: string): EvidenceRow[] {
  if (evidence === null || evidence === undefined) return [];
  const out: EvidenceRow[] = [];
  walk(evidence, "", 0, code, out);
  return out;
}
