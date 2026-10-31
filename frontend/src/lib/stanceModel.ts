/**
 * Facts about the stance model that the stance API does not return.
 * They mirror backend signals/rules.py for the versions listed here; for any
 * other `rules_version` the UI shows no weights rather than guess.
 */

import type { LimitationItem, StancePart } from "../types";

export const KNOWN_RULES_VERSION = "signal-rules-2.2";

/** Engine weights in the composite, as percent of model weight (signal-rules-2.2). */
const ENGINE_WEIGHTS: Readonly<Record<string, number>> = {
  technical: 40,
  valuation: 35,
  score: 25,
};

/** Engines that feed the composite, in display order. */
export const COMPOSITE_ENGINES = ["technical", "valuation", "score"] as const;
export type CompositeEngine = (typeof COMPOSITE_ENGINES)[number];

export function engineWeight(rulesVersion: string, engine: CompositeEngine): number | null {
  return rulesVersion === KNOWN_RULES_VERSION ? (ENGINE_WEIGHTS[engine] ?? null) : null;
}

/** Which composite engines produced an input (from `reasons[].engine`) and which did not. */
export function engineCoverage(reasonEngines: readonly string[]): {
  used: CompositeEngine[];
  missing: CompositeEngine[];
} {
  const present = new Set(reasonEngines);
  return {
    used: COMPOSITE_ENGINES.filter((e) => present.has(e)),
    missing: COMPOSITE_ENGINES.filter((e) => !present.has(e)),
  };
}

/** Limitation sentences the page already says in its own localized copy. */
const COVERED_ELSEWHERE = [
  "Research calculation", // the localized page footer
  "Reference levels are a volatility band", // the reference-levels caption
  "a risk reference, not an order condition", // the risk reference row
];

/** Limitations worth listing: drops sentences the page carries in localized copy, and exact duplicates. */
export function visibleLimitations(limitations: readonly string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const raw of limitations) {
    const text = raw.trim();
    if (text === "" || COVERED_ELSEWHERE.some((prefix) => text.startsWith(prefix)) || seen.has(text)) continue;
    seen.add(text);
    out.push(text);
  }
  return out;
}

/** Reason sentences, exact duplicates removed. */
export function visibleReasons(reasons: readonly { text: string }[]): string[] {
  return [...new Set(reasons.map((r) => r.text.trim()).filter((t) => t !== ""))];
}

/** A reason to list: the English text (always) and its codes (when the API sent them). */
export interface ReasonEntry {
  text: string;
  parts: readonly StancePart[] | undefined;
}

/** `visibleReasons` that keeps each reason's codes, so the page can write the sentence in its own language. */
export function visibleReasonEntries(reasons: readonly { text: string; parts?: readonly StancePart[] }[]): ReasonEntry[] {
  const seen = new Set<string>();
  const out: ReasonEntry[] = [];
  for (const r of reasons) {
    const text = r.text.trim();
    if (text === "" || seen.has(text)) continue;
    seen.add(text);
    out.push({ text, parts: r.parts });
  }
  return out;
}

/** Limitation codes the page already says in its own localized copy (footer, reference-levels caption, risk row). */
const COVERED_CODES: ReadonlySet<string> = new Set(["compliance_footer", "levels_band", "stop_reference"]);

/** A limitation to list: the English text (always) and its code item (when the API sent them). */
export interface LimitationEntry {
  text: string;
  item: LimitationItem | undefined;
}

/**
 * `visibleLimitations` with the codes kept. When `items` lines up with `limitations`, drops and de-duplicates by
 * code (and parameters); otherwise, or for a code this UI does not know, by the English text as before.
 */
export function visibleLimitationEntries(
  limitations: readonly string[],
  items?: readonly LimitationItem[],
): LimitationEntry[] {
  const aligned = items !== undefined && items.length === limitations.length ? items : undefined;
  const seen = new Set<string>();
  const out: LimitationEntry[] = [];
  limitations.forEach((raw, i) => {
    const text = raw.trim();
    const item = aligned?.[i];
    if (text === "" || (item !== undefined && COVERED_CODES.has(item.code))) return;
    if (COVERED_ELSEWHERE.some((prefix) => text.startsWith(prefix))) return;
    const key = item ? `${item.code}|${JSON.stringify(item.params)}` : text;
    if (seen.has(key) || seen.has(text)) return;
    seen.add(key);
    seen.add(text);
    out.push({ text, item });
  });
  return out;
}

/** Confidence caps and the statement-age limit of signal-rules-2.2 (backend signals/rules.py). */
export const CONFIDENCE_CAPS = {
  technicalOnly: 50,
  lowLiquidity: 30,
  staleStatements: 40,
  staleStatementDays: 400,
} as const;

/** The API sends the horizon as English text; this one value has localized copy. */
export function isSwingHorizon(horizon: string): boolean {
  return horizon.trim().toLowerCase() === "swing (1-3 weeks)";
}

/** Technical indicator types the backend emits (technical/indicators.py). */
export const INDICATOR_TYPES = ["sma", "ema", "rsi", "macd", "bollinger", "obv", "vwap", "atr"] as const;
export type IndicatorType = (typeof INDICATOR_TYPES)[number];

export function isIndicatorType(value: string): value is IndicatorType {
  return (INDICATOR_TYPES as readonly string[]).includes(value.toLowerCase());
}

/** "a", "a and b", "a, b and c" with the caller's localized separator and conjunction. */
export function joinList(items: readonly string[], separator: string, and: string): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(separator)}${and}${items[items.length - 1]}`;
}
