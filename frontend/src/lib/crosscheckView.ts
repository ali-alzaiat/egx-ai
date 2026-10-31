import type { CopyKey, CopyParams } from "../i18n";
import type { CrossCheck } from "../types";
import { fmtDate, fmtInt, fmtNum, fmtPct } from "./format";

/**
 * Cross-check rows as translated text (R50). For each known check code the evidence numbers are turned into one
 * sentence plus labelled rows (shares as %, dates localised, empty lists as "none"). Pure: the caller passes `t`
 * and the Intl locale. `null` means "not a check this build knows, or evidence in an unexpected shape": the caller
 * then falls back to the backend's own `detail` and the generic key/value rows.
 */

export type Translate = (key: CopyKey, params?: CopyParams) => string;

export interface CheckRow {
  label: string;
  value: string;
}

export interface CheckView {
  summary: string;
  rows: CheckRow[];
}

type Rec = Record<string, unknown>;

function rec(v: unknown): Rec | null {
  return typeof v === "object" && v !== null && !Array.isArray(v) ? (v as Rec) : null;
}

function int(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function text(v: unknown): string | null {
  return typeof v === "string" && v !== "" ? v : null;
}

function list(v: unknown): Rec[] | null {
  if (!Array.isArray(v)) return null;
  return v.map(rec).filter((x): x is Rec => x !== null);
}

/** An ISO date string (or other text) in the reader's format; anything else is shown as given. */
function date(locale: string, v: unknown): string {
  const s = text(v);
  return s === null ? "" : (fmtDate(locale, s) ?? s);
}

function count(locale: string, n: number): string {
  return fmtInt(locale, n) ?? String(n);
}

function pct(locale: string, v: unknown): string {
  const s = typeof v === "string" || typeof v === "number" ? v : null;
  return (s === null ? null : fmtPct(locale, s)) ?? "";
}

function amount(locale: string, v: unknown): string {
  return typeof v === "string" || typeof v === "number" ? fmtNum(locale, v, { maximumFractionDigits: 2 }) : "";
}

/** A list value: the entries joined, or the word for "none" when empty. */
function joined(items: readonly string[], t: Translate): string {
  return items.length === 0 ? t("xc_none") : items.join("; ");
}

const JOIN = " ";

const EMPTY_SUMMARY: Record<string, CopyKey> = {
  provenance: "xc_sum_prov_empty",
  cross_source: "xc_sum_xs_empty",
  accounting_identity: "xc_sum_id_empty",
  price_sanity: "xc_sum_px_empty",
};

function provenance(e: Rec, locale: string, t: Translate): CheckView | null {
  const lines = int(e.lines);
  const backed = int(e.filing_backed);
  const vendor = int(e.vendor_only);
  const other = int(e.other);
  if (lines === null || backed === null || vendor === null || other === null) return null;
  const share = e.filing_backed_share;
  let summary: string;
  if (backed === 0 && vendor === 0) summary = t("xc_sum_prov_none", { lines: count(locale, lines) });
  else if (backed === 0) summary = t("xc_sum_prov_vendor", { lines: count(locale, lines) });
  else summary = t("xc_sum_prov_ok", { backed: count(locale, backed), lines: count(locale, lines), share: pct(locale, share) });
  return {
    summary,
    rows: [
      { label: t("xc_row_lines"), value: count(locale, lines) },
      { label: t("xc_row_filing_backed"), value: count(locale, backed) },
      { label: t("xc_row_vendor_only"), value: count(locale, vendor) },
      { label: t("xc_row_other"), value: count(locale, other) },
      { label: t("xc_row_share"), value: pct(locale, share) || "—" },
    ],
  };
}

const BAND_KEY: Record<string, CopyKey> = {
  within_1_percent: "xc_band_within",
  "1_to_5_percent": "xc_band_1_to_5",
  over_5_percent: "xc_band_over_5",
};

function crossSource(e: Rec, locale: string, t: Translate): CheckView | null {
  const compared = int(e.compared);
  const within = int(e.within_1_percent);
  const mid = int(e.from_1_to_5_percent);
  const over = int(e.over_5_percent);
  const items = list(e.items);
  if (compared === null || within === null || mid === null || over === null || items === null) return null;
  const off = mid + over;
  const summary =
    off === 0
      ? t("xc_sum_xs_ok", { compared: count(locale, compared) })
      : t("xc_sum_xs_off", { off: count(locale, off), compared: count(locale, compared) });
  // Only the band and OUR value are shown; the backend never sends the vendor figure and nothing here reads one.
  const entries = items.map((it) => {
    const band = text(it.band);
    return t("xc_item_source", {
      period: text(it.period) ?? "—",
      code: text(it.ontology_code) ?? "—",
      band: band && BAND_KEY[band] ? t(BAND_KEY[band]) : (band ?? "—"),
      value: amount(locale, it.our_value) || "—",
    });
  });
  return {
    summary,
    rows: [
      { label: t("xc_row_compared"), value: count(locale, compared) },
      { label: t("xc_row_within_1"), value: count(locale, within) },
      { label: t("xc_row_1_to_5"), value: count(locale, mid) },
      { label: t("xc_row_over_5"), value: count(locale, over) },
      { label: t("xc_row_differing"), value: joined(entries, t) },
    ],
  };
}

const IDENTITY_KEY: Record<string, CopyKey> = {
  "assets = liabilities + equity": "xc_identity_balance",
  "assets = current + non-current assets": "xc_identity_split",
  "gross profit = revenue - cost of revenue": "xc_identity_gross",
};

function identities(e: Rec, locale: string, t: Translate): CheckView | null {
  const evaluated = int(e.evaluated);
  const off = int(e.off);
  const items = list(e.items);
  if (evaluated === null || off === null || items === null) return null;
  const summary =
    off === 0
      ? t("xc_sum_id_ok", { evaluated: count(locale, evaluated) })
      : t("xc_sum_id_off", { off: count(locale, off), evaluated: count(locale, evaluated) });
  const entries = items.map((it) => {
    const name = text(it.identity);
    const params = {
      period: text(it.period) ?? "—",
      identity: name && IDENTITY_KEY[name] ? t(IDENTITY_KEY[name]) : (name ?? "—"),
      diff: pct(locale, it.relative_difference) || "—",
    };
    const left = amount(locale, it.left);
    const right = amount(locale, it.right);
    return left !== "" && right !== "" ? t("xc_item_identity_values", { ...params, left, right }) : t("xc_item_identity", params);
  });
  return {
    summary,
    rows: [
      { label: t("xc_row_evaluated"), value: count(locale, evaluated) },
      { label: t("xc_row_off"), value: count(locale, off) },
      { label: t("xc_row_off_items"), value: joined(entries, t) },
    ],
  };
}

function priceSanity(e: Rec, locale: string, t: Translate): CheckView | null {
  const closes = int(e.closes_checked);
  const nonPositive = Array.isArray(e.non_positive_closes) ? e.non_positive_closes : null;
  const breaches = list(e.limit_breaches);
  const splits = list(e.possible_splits);
  const gaps = list(e.gaps);
  if (closes === null || nonPositive === null || breaches === null || splits === null || gaps === null) return null;
  const parts: string[] = [];
  if (nonPositive.length > 0) parts.push(t("xc_sum_px_nonpos", { n: count(locale, nonPositive.length) }));
  if (breaches.length > 0) parts.push(t("xc_sum_px_breach", { n: count(locale, breaches.length) }));
  if (gaps.length > 0) parts.push(t("xc_sum_px_gaps", { n: count(locale, gaps.length) }));
  if (parts.length === 0) parts.push(t("xc_sum_px_ok", { n: count(locale, closes) }));
  if (splits.length > 0) parts.push(t("xc_sum_px_splits", { n: count(locale, splits.length) }));
  const move = (it: Rec): string => t("xc_item_move", { date: date(locale, it.date), change: pct(locale, it.change) || "—" });
  return {
    summary: parts.join(JOIN),
    rows: [
      { label: t("xc_row_closes"), value: count(locale, closes) },
      { label: t("xc_row_nonpos"), value: joined(nonPositive.map((d) => date(locale, d)).filter((d) => d !== ""), t) },
      { label: t("xc_row_breaches"), value: joined(breaches.map(move), t) },
      { label: t("xc_row_splits"), value: joined(splits.map(move), t) },
      {
        label: t("xc_row_gaps"),
        value: joined(
          gaps.map((g) =>
            t("xc_item_gap", {
              from: date(locale, g.from),
              to: date(locale, g.to),
              days: int(g.missing_days) === null ? "—" : count(locale, int(g.missing_days) ?? 0),
            }),
          ),
          t,
        ),
      },
    ],
  };
}

function freshness(e: Rec, locale: string, t: Translate): CheckView | null {
  if (text(e.as_of) === null) return null;
  const lastClose = text(e.last_close);
  const age = int(e.price_age_trading_days);
  const periodEnd = text(e.latest_period_end);
  const behind = int(e.quarters_behind);
  const parts = [
    lastClose !== null && age !== null
      ? t("xc_sum_fr_price", { date: date(locale, lastClose), age: count(locale, age) })
      : t("xc_sum_fr_no_price"),
    periodEnd !== null && behind !== null
      ? t("xc_sum_fr_period", { date: date(locale, periodEnd), n: count(locale, behind) })
      : t("xc_sum_fr_no_period"),
  ];
  return {
    summary: parts.join(JOIN),
    rows: [
      { label: t("xc_row_as_of"), value: date(locale, e.as_of) },
      { label: t("xc_row_last_close"), value: lastClose === null ? t("xc_none") : date(locale, lastClose) },
      { label: t("xc_row_price_age"), value: age === null ? "—" : count(locale, age) },
      { label: t("xc_row_period_end"), value: periodEnd === null ? t("xc_none") : date(locale, periodEnd) },
      { label: t("xc_row_quarters"), value: behind === null ? "—" : count(locale, behind) },
    ],
  };
}

/** The translated view of a check, or null to fall back to the backend's wording. */
export function describeCheck(check: CrossCheck, locale: string, t: Translate): CheckView | null {
  const e = rec(check.evidence);
  if (e === null) return null;
  if (Object.keys(e).length === 0) {
    // "Not enough data" checks carry no evidence: say why, in words.
    const key = check.status === "insufficient_data" ? EMPTY_SUMMARY[check.code] : undefined;
    return key ? { summary: t(key), rows: [] } : null;
  }
  switch (check.code) {
    case "provenance":
      return provenance(e, locale, t);
    case "cross_source":
      return crossSource(e, locale, t);
    case "accounting_identity":
      return identities(e, locale, t);
    case "price_sanity":
      return priceSanity(e, locale, t);
    case "freshness":
      return freshness(e, locale, t);
    default:
      return null;
  }
}
