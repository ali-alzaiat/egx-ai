import type { CopyKey, CopyParams } from "../../i18n";
import { fmtDate, fmtNum, fmtPrice, plural, toNumber } from "../../lib/format";
import type { AlertRule, Company } from "../../types";

type Translate = (key: CopyKey, params?: CopyParams) => string;

export const FAMILIES = ["price", "valuation_gap", "document", "score_change"] as const;
export type AlertFamily = (typeof FAMILIES)[number];

export function isFamily(value: string): value is AlertFamily {
  return (FAMILIES as readonly string[]).includes(value);
}

export const FAMILY_LABEL: Record<AlertFamily, CopyKey> = {
  price: "al_family_price",
  valuation_gap: "al_family_gap",
  document: "al_family_document",
  score_change: "al_family_score",
};

export const FAMILY_HINT: Record<AlertFamily, CopyKey> = {
  price: "al_hint_price",
  valuation_gap: "al_hint_gap",
  document: "al_hint_document",
  score_change: "al_hint_score",
};

/** The family's label, or a neutral word when the server sent one we do not know. */
export function familyLabel(family: string | undefined, t: Translate): string {
  return family && isFamily(family) ? t(FAMILY_LABEL[family]) : t("al_family_unknown");
}

export type Scope = "company" | "watchlist" | "universe";

export interface RuleInputs {
  threshold: string;
  direction: "above" | "below";
  gapPct: string;
  thresholdPct: string;
}

export type ParamsResult = { ok: true; params: Record<string, unknown> } | { ok: false; error: CopyKey };

/** Validate the family-specific fields and build the rule params. */
export function buildParams(family: AlertFamily, inputs: RuleInputs): ParamsResult {
  if (family === "price") {
    const value = Number.parseFloat(inputs.threshold);
    if (!Number.isFinite(value)) return { ok: false, error: "al_err_price" };
    return { ok: true, params: { threshold: value, direction: inputs.direction } };
  }
  if (family === "valuation_gap") {
    const value = Number.parseFloat(inputs.gapPct);
    if (!Number.isFinite(value) || value <= 0) return { ok: false, error: "al_err_gap" };
    return { ok: true, params: { gap_pct: value } };
  }
  if (family === "score_change") {
    const value = Number.parseFloat(inputs.thresholdPct);
    if (!Number.isFinite(value) || value <= 0) return { ok: false, error: "al_err_score" };
    return { ok: true, params: { threshold_pct: value } };
  }
  return { ok: true, params: {} };
}

export type ScopeResult =
  | { ok: true; companyId?: string; watchlistId?: string }
  | { ok: false; error: CopyKey };

/** One scope, one meaning: document rules are always per-list. */
export function resolveScope(
  family: AlertFamily,
  scope: Scope,
  company: Pick<Company, "id"> | null,
  watchlistId: string,
): ScopeResult {
  const effective: Scope = family === "document" ? "watchlist" : scope;
  if (effective === "company") {
    return company ? { ok: true, companyId: company.id } : { ok: false, error: "al_err_company" };
  }
  if (effective === "watchlist") {
    if (watchlistId.trim() === "") {
      return { ok: false, error: family === "document" ? "al_err_document_list" : "al_err_list" };
    }
    return { ok: true, watchlistId: watchlistId.trim() };
  }
  return { ok: true };
}

/** Snapshot value as a number string in the reader's locale; null when absent. */
function num(locale: string, value: unknown, price = false): string | null {
  const n = toNumber(typeof value === "number" || typeof value === "string" ? value : null);
  if (n === null) return null;
  return price ? fmtPrice(locale, n) : fmtNum(locale, n, { maximumFractionDigits: 2 });
}

function directionWord(value: unknown, t: Translate): string {
  return value === "below" ? t("al_dir_below") : t("al_dir_above");
}

/** What a rule watches for, in one localized phrase. */
export function ruleSummary(rule: AlertRule, t: Translate, locale: string): string {
  const params = rule.params ?? {};
  const dash = t("no_value");
  switch (rule.family) {
    case "price":
      return t("al_rule_price", {
        direction: directionWord(params.direction, t),
        threshold: num(locale, params.threshold, true) ?? dash,
      });
    case "valuation_gap":
      return t("al_rule_gap", { gap: num(locale, params.gap_pct) ?? dash });
    case "score_change":
      return t("al_rule_score", { pct: num(locale, params.threshold_pct) ?? dash });
    case "document":
      return t("al_rule_document");
    default:
      return t("al_rule_other");
  }
}

/** "3 parsed facts" with the right plural form. */
export function factCount(locale: string, n: number, t: Translate): string {
  return plural(locale, n, {
    one: t("trk_facts_one"),
    two: t("trk_facts_two"),
    few: t("trk_facts_few"),
    many: t("trk_facts_many"),
    other: t("trk_facts_other"),
  });
}

/** The facts that matter about why a rule fired; the raw snapshot stays in a details fold. */
export function firedSummary(
  family: string,
  snapshot: Record<string, unknown>,
  t: Translate,
  locale: string,
): string {
  const dash = t("no_value");
  if (family === "price") {
    const asOf = typeof snapshot.price_as_of === "string" ? fmtDate(locale, snapshot.price_as_of) : null;
    const params = {
      direction: directionWord(snapshot.direction, t),
      threshold: num(locale, snapshot.threshold, true) ?? dash,
      observed: num(locale, snapshot.current_close, true) ?? dash,
    };
    return asOf ? t("al_fired_price_asof", { ...params, date: asOf }) : t("al_fired_price", params);
  }
  if (family === "valuation_gap") {
    return t("al_fired_gap", {
      gap: num(locale, snapshot.gap_pct) ?? dash,
      price: num(locale, snapshot.current_close, true) ?? dash,
      fair: num(locale, snapshot.fair_value, true) ?? dash,
    });
  }
  if (family === "score_change") {
    return t("al_fired_score", {
      change: num(locale, snapshot.change_pct) ?? dash,
      previous: num(locale, snapshot.previous_score) ?? dash,
      current: num(locale, snapshot.current_score) ?? dash,
      band: num(locale, snapshot.threshold_pct ?? 5) ?? dash,
    });
  }
  if (family === "document") {
    const ids = snapshot.fact_ids;
    const n = Array.isArray(ids) ? ids.length : 0;
    return n > 0 ? `${t("al_fired_document")} ${factCount(locale, n, t)}` : t("al_fired_document");
  }
  return t("al_fired_other");
}

/** Snapshot entries as display strings for the technical-details fold. */
export function snapshotEntries(snapshot: Record<string, unknown>): [string, string][] {
  return Object.entries(snapshot).map(([key, value]) => {
    if (value === null || value === undefined) return [key, "—"];
    return [key, typeof value === "object" ? JSON.stringify(value) : String(value)];
  });
}
