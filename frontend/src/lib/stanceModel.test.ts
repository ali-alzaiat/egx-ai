import { describe, expect, it } from "vitest";
import { engineCoverage, engineWeight, isIndicatorType, isSwingHorizon, joinList, visibleLimitations, visibleReasons } from "./stanceModel";

describe("engineCoverage", () => {
  it("splits composite engines into used and missing", () => {
    expect(engineCoverage(["technical", "volume"])).toEqual({
      used: ["technical"],
      missing: ["valuation", "score"],
    });
  });
  it("has all engines missing for no reasons", () => {
    expect(engineCoverage([]).used).toEqual([]);
  });
});

describe("engineWeight", () => {
  it("knows weights for the documented rules version only", () => {
    expect(engineWeight("signal-rules-2.0", "technical")).toBe(40);
    expect(engineWeight("signal-rules-9.9", "technical")).toBeNull();
  });
});

describe("visibleLimitations", () => {
  it("drops the bilingual footer, localized duplicates and repeats", () => {
    const out = visibleLimitations([
      "Research calculation — not investment advice · حساب بحثي",
      "Technical-only stance: no fundamentals available yet.",
      "Technical-only stance: no fundamentals available yet.",
      "Reference levels are a volatility band (ATR) around the last close.",
      "a risk reference, not an order condition",
      "Missing inputs: valuation, score.",
    ]);
    expect(out).toEqual(["Technical-only stance: no fundamentals available yet.", "Missing inputs: valuation, score."]);
  });
});

describe("visibleReasons", () => {
  it("removes exact duplicates and blanks", () => {
    expect(visibleReasons([{ text: "a" }, { text: " a " }, { text: "" }, { text: "b" }])).toEqual(["a", "b"]);
  });
});

describe("isSwingHorizon", () => {
  it("recognizes the backend horizon string only", () => {
    expect(isSwingHorizon("swing (1-3 weeks)")).toBe(true);
    expect(isSwingHorizon("position (3-6 months)")).toBe(false);
  });
});

describe("isIndicatorType", () => {
  it("accepts known indicator types in any case", () => {
    expect(isIndicatorType("RSI")).toBe(true);
    expect(isIndicatorType("zigzag")).toBe(false);
  });
});

describe("joinList", () => {
  it("joins with a separator and a final conjunction", () => {
    expect(joinList([], ", ", " and ")).toBe("");
    expect(joinList(["a"], ", ", " and ")).toBe("a");
    expect(joinList(["a", "b"], ", ", " and ")).toBe("a and b");
    expect(joinList(["a", "b", "c"], ", ", " and ")).toBe("a, b and c");
  });
});
