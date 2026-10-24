import { describe, expect, it } from "vitest";
import { lineFallback, parseReason, parseSourceType } from "./reasons";

describe("parseReason", () => {
  it("reads the ratio and bridge shapes", () => {
    expect(parseReason("missing:current_liabilities")).toEqual({ kind: "line", line: "current_liabilities" });
    expect(parseReason("missing statement line: cfo (FY2025)")).toEqual({ kind: "line", line: "cfo", year: "2025" });
    expect(parseReason("missing statement line: capex")).toEqual({ kind: "line", line: "capex" });
    expect(parseReason("no prior period: FY2024 has no total_equity")).toEqual({
      kind: "prior",
      line: "total_equity",
      year: "2024",
    });
  });
  it("treats a bare 'missing' as the default", () => {
    expect(parseReason("missing")).toEqual({ kind: "default" });
  });
  it("passes unknown text through", () => {
    expect(parseReason("zero denominator")).toEqual({ kind: "raw", text: "zero denominator" });
  });
  it("is null with no reason", () => {
    expect(parseReason(null)).toBeNull();
    expect(parseReason("")).toBeNull();
  });
});

describe("lineFallback", () => {
  it("makes a code readable", () => {
    expect(lineFallback("current_liabilities")).toBe("current liabilities");
  });
});

describe("parseSourceType", () => {
  it("reads the data-quality source detail", () => {
    expect(parseSourceType("source type: DATA_PROVIDER")).toBe("DATA_PROVIDER");
    expect(parseSourceType("source type: unknown")).toBe("unknown");
  });
  it("is null for other text and unknown codes", () => {
    expect(parseSourceType("1 days stale")).toBeNull();
    expect(parseSourceType("source type: PIGEON")).toBeNull();
  });
});
