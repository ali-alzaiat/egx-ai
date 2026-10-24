import { describe, expect, it } from "vitest";
import { priceSourceLabel } from "./priceSource";

describe("priceSourceLabel", () => {
  it("names Yahoo Finance and humanizes other codes", () => {
    expect(priceSourceLabel("YAHOO_FINANCE_EGX")).toBe("Yahoo Finance");
    expect(priceSourceLabel("EGX_OFFICIAL")).toBe("Egx Official");
  });
  it("is null with no name", () => {
    expect(priceSourceLabel(undefined)).toBeNull();
    expect(priceSourceLabel("  ")).toBeNull();
  });
});
