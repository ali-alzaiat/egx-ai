/**
 * Maps backend INSUFFICIENT_DATA reason codes to localized copy keys.
 *
 * Known shapes (r43-computed-company-data.md 1.5, statements/ratios.py):
 *   "missing:<line>"                          ratios
 *   "missing statement line: <line> (FY2025)" metrics, fair value, Shariah
 *   "no prior period: FY2024 has no <line>"   metrics (ROE/ROA averages, growth)
 *   "missing"                                 a ratio with no named line
 * Anything else is backend free text: the caller shows it in a `lang="en"` span.
 */

import type { CopyKey } from "../i18n";

export type ReasonParse =
  | { kind: "line"; line: string; year?: string }
  | { kind: "prior"; line: string; year: string }
  | { kind: "default" }
  | { kind: "raw"; text: string };

export function parseReason(reason: string | null | undefined): ReasonParse | null {
  if (!reason) return null;
  const text = reason.trim();
  if (text === "missing") return { kind: "default" };
  const short = /^missing:(\w+)$/.exec(text);
  if (short?.[1]) return { kind: "line", line: short[1] };
  const long = /^missing statement line: (\w+)(?: \(FY(\d{4})\))?$/.exec(text);
  if (long?.[1]) return long[2] ? { kind: "line", line: long[1], year: long[2] } : { kind: "line", line: long[1] };
  const prior = /^no prior period: FY(\d{4}) has no (\w+)$/.exec(text);
  if (prior?.[1] && prior[2]) return { kind: "prior", line: prior[2], year: prior[1] };
  return { kind: "raw", text };
}

export const REASON_KEYS = {
  line: "missing_line",
  lineYear: "fn_missing_line_fy",
  prior: "fn_no_prior_period",
  default: "missing_default",
} as const satisfies Record<string, CopyKey>;

/** Readable fallback when a line code has no label: "current_liabilities" -> "current liabilities". */
export function lineFallback(code: string): string {
  return code.replace(/_/g, " ");
}

export const SOURCE_TYPES = ["DATA_PROVIDER", "EGX", "FRA", "COMPANY", "MANUAL", "SYNTHETIC", "unknown"] as const;
export type SourceType = (typeof SOURCE_TYPES)[number];

/** The data-quality detail "source type: DATA_PROVIDER" carries a raw source code; null for any other text. */
export function parseSourceType(detail: string): SourceType | null {
  const match = /^source type: (\w+)$/.exec(detail.trim());
  const type = match?.[1];
  return SOURCE_TYPES.find((s) => s === type) ?? null;
}
