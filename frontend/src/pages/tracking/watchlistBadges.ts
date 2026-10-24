import type { PhaseBadge, ShariahStatus } from "../../types";

/** A badge carries a usable value only when the server marked it AVAILABLE and filled it. */
export function badgeAvailable(badge: PhaseBadge | null | undefined): badge is PhaseBadge & { value: string } {
  return (
    !!badge && badge.status === "AVAILABLE" && badge.value !== null && badge.value !== undefined && badge.value !== ""
  );
}

/** A quote older than this many days gets the stale Tag (W3). */
export const STALE_AFTER_DAYS = 7;

/** Whole days since the last trade, from the staleness badge; null when unknown. */
export function staleDays(staleness: PhaseBadge | null | undefined): number | null {
  if (!badgeAvailable(staleness)) return null;
  const n = Number.parseInt(staleness.value, 10);
  return Number.isFinite(n) ? n : null;
}

/** Days old when the quote is stale, otherwise null. */
export function staleAge(staleness: PhaseBadge | null | undefined): number | null {
  const days = staleDays(staleness);
  return days !== null && days > STALE_AFTER_DAYS ? days : null;
}

/** The server's Shariah badge text ("Compliant"...) to our verdict code; null when not a verdict. */
export function shariahVerdictOf(badge: PhaseBadge | null | undefined): ShariahStatus["verdict"] | null {
  if (!badgeAvailable(badge)) return null;
  switch (badge.value) {
    case "Compliant":
      return "COMPLIANT";
    case "Non-Compliant":
      return "NON_COMPLIANT";
    default:
      return null;
  }
}
