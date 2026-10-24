/**
 * Facts about the stance model that the stance API does not return.
 * They mirror backend signals/rules.py for the versions listed here; for any
 * other `rules_version` the UI shows no weights rather than guess.
 */

export const KNOWN_RULES_VERSION = "signal-rules-2.0";

/** Engine weights in the composite, as percent of model weight (signal-rules-2.0). */
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

/** Confidence caps and the statement-age limit of signal-rules-2.0 (backend signals/rules.py). */
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
