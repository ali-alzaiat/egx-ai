import { describe, expect, it } from "vitest";
import type { PhaseBadge } from "../../types";
import { badgeAvailable, shariahVerdictOf, staleAge, staleDays } from "./watchlistBadges";

const ok = (value: string): PhaseBadge => ({ value, status: "AVAILABLE", reason: null });
const missing: PhaseBadge = { value: null, status: "INSUFFICIENT_DATA", reason: "No price history available" };

describe("watchlist badges", () => {
  it("treats only AVAILABLE badges with a value as usable", () => {
    expect(badgeAvailable(ok("12.5"))).toBe(true);
    expect(badgeAvailable(missing)).toBe(false);
    expect(badgeAvailable(null)).toBe(false);
    expect(badgeAvailable({ value: "", status: "AVAILABLE", reason: null })).toBe(false);
  });

  it("flags stale quotes only past the threshold, never from missing data", () => {
    expect(staleDays(ok("3"))).toBe(3);
    expect(staleAge(ok("7"))).toBeNull();
    expect(staleAge(ok("8"))).toBe(8);
    expect(staleAge(missing)).toBeNull();
    expect(staleDays(ok("soon"))).toBeNull();
  });

  it("maps the server's Shariah text to a verdict, and anything else to none", () => {
    expect(shariahVerdictOf(ok("Compliant"))).toBe("COMPLIANT");
    expect(shariahVerdictOf(ok("Non-Compliant"))).toBe("NON_COMPLIANT");
    expect(shariahVerdictOf(ok("Insufficient Data"))).toBeNull();
    expect(shariahVerdictOf(missing)).toBeNull();
  });
});
