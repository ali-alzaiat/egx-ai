import type { CopyKey, CopyParams } from "../../i18n";
import { fmtDate } from "../../lib/format";
import { humanizeCode } from "../shared/humanize";
import { factCount } from "./alertsFormat";

type Translate = (key: CopyKey, params?: CopyParams) => string;

/** Event types the ledger records, each with a localized label. */
export const EVENT_TYPES = [
  "watchlist.add",
  "watchlist.remove",
  "alert.created",
  "alert.fired",
  "alert.acked",
  "fact.landed",
  "check.evaluated",
  "restatement.detected",
  "thesis.updated",
  "rule.changed",
  "note.added",
] as const;
export type EventType = (typeof EVENT_TYPES)[number];

const TYPE_KEY: Record<EventType, CopyKey> = {
  "watchlist.add": "ev_type_watchlist_add",
  "watchlist.remove": "ev_type_watchlist_remove",
  "alert.created": "ev_type_alert_created",
  "alert.fired": "ev_type_alert_fired",
  "alert.acked": "ev_type_alert_acked",
  "fact.landed": "ev_type_fact_landed",
  "check.evaluated": "ev_type_check_evaluated",
  "restatement.detected": "ev_type_restatement_detected",
  "thesis.updated": "ev_type_thesis_updated",
  "rule.changed": "ev_type_rule_changed",
  "note.added": "ev_type_note_added",
};

export function isEventType(value: string): value is EventType {
  return (EVENT_TYPES as readonly string[]).includes(value);
}

/** Localized label; an unknown type from a newer backend falls back to a readable form. */
export function eventTypeLabel(type: string, t: Translate): string {
  return isEventType(type) ? t(TYPE_KEY[type]) : humanizeCode(type);
}

export interface EventFilters {
  /** Company id, not ticker (the API filters on ids). */
  symbol: string;
  type: string;
  date_from: string;
  date_to: string;
}

export const EMPTY_FILTERS: EventFilters = { symbol: "", type: "", date_from: "", date_to: "" };

export function hasFilters(filters: EventFilters): boolean {
  return filters.symbol !== "" || filters.type !== "" || filters.date_from !== "" || filters.date_to !== "";
}

/** Drop empty filters so the request carries only what is set. */
export function toQueryParams(filters: EventFilters): Partial<EventFilters> {
  const params: Partial<EventFilters> = {};
  if (filters.symbol) params.symbol = filters.symbol;
  if (filters.type) params.type = filters.type;
  if (filters.date_from) params.date_from = filters.date_from;
  if (filters.date_to) params.date_to = filters.date_to;
  return params;
}

/**
 * The well-known provenance keys out of an opaque inputs snapshot, as localized
 * phrases. Fact ids are counted, never listed: ids belong in the details fold.
 */
export function snapshotHighlights(
  snapshot: Record<string, unknown>,
  t: Translate,
  locale: string,
): string[] {
  const out: string[] = [];
  const facts = snapshot.fact_ids ?? snapshot.facts ?? snapshot.factIds;
  if (Array.isArray(facts) && facts.length > 0) out.push(factCount(locale, facts.length, t));
  const priceAsOf = snapshot.price_as_of ?? snapshot.priceAsOf;
  if (typeof priceAsOf === "string" && priceAsOf) {
    out.push(t("ev_price_as_of", { date: fmtDate(locale, priceAsOf) ?? priceAsOf }));
  }
  const methodology = snapshot.methodology_version ?? snapshot.methodologyVersion;
  if (typeof methodology === "string" && methodology) out.push(t("ev_methodology", { version: methodology }));
  return out;
}

export function stringifySnapshot(snapshot: Record<string, unknown>): string {
  try {
    return JSON.stringify(snapshot, null, 2);
  } catch {
    return String(snapshot);
  }
}
