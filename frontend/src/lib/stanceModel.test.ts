import { describe, expect, it } from "vitest";
import { KNOWN_RULES_VERSION, engineCoverage, engineWeight, isIndicatorType, isSwingHorizon, joinList, visibleLimitationEntries, visibleLimitations, visibleReasonEntries, visibleReasons } from "./stanceModel";

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

describe("KNOWN_RULES_VERSION", () => {
  it("pins the rules version the backend returns (R46 S2)", () => {
    expect(KNOWN_RULES_VERSION).toBe("signal-rules-2.2");
  });
});

describe("engineWeight", () => {
  it("knows weights for the documented rules version only", () => {
    expect(engineWeight("signal-rules-2.2", "technical")).toBe(40);
    expect(engineWeight("signal-rules-2.2", "valuation")).toBe(35);
    expect(engineWeight("signal-rules-2.0", "technical")).toBeNull();
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

describe("visibleLimitationEntries", () => {
  const item = (code: string, text: string, params: Record<string, string> = {}) => ({ code, params, text });

  it("drops the footer, levels and stop items by code, whatever their text", () => {
    const items = [
      item("compliance_footer", "Some new footer wording"),
      item("technical_only", "Technical-only stance: no fundamentals available yet."),
      item("levels_band", "New levels wording"),
      item("stop_reference", "New stop wording"),
    ];
    const out = visibleLimitationEntries(
      items.map((i) => i.text),
      items,
    );
    expect(out.map((e) => e.item?.code)).toEqual(["technical_only"]);
  });

  it("de-duplicates by code and parameters", () => {
    const items = [item("statement_stale", "a", { days: "450" }), item("statement_stale", "b", { days: "450" }), item("statement_stale", "c", { days: "500" })];
    expect(visibleLimitationEntries(["a", "b", "c"], items).map((e) => e.text)).toEqual(["a", "c"]);
  });

  it("falls back to the English text rules without items, or when the lengths differ", () => {
    const texts = ["Research calculation — not investment advice", "Missing inputs: score.", "Missing inputs: score."];
    expect(visibleLimitationEntries(texts)).toEqual([{ text: "Missing inputs: score.", item: undefined }]);
    expect(visibleLimitationEntries(texts, [item("technical_only", "x")]).map((e) => e.item)).toEqual([undefined]);
  });
});

describe("visibleReasonEntries", () => {
  it("keeps the codes and removes duplicates and blanks", () => {
    const parts = [{ code: "macd", params: { side: "flat" } }];
    expect(visibleReasonEntries([{ text: "a", parts }, { text: " a " }, { text: "" }, { text: "b" }])).toEqual([
      { text: "a", parts },
      { text: "b", parts: undefined },
    ]);
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
