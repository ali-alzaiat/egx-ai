import { describe, it, expect } from "vitest";
import { SHORT_COPY, t } from "./dict";
import { fmtNum } from "./format";

describe("i18n", () => {
  it("has EN and AR for every key", () => {
    for (const key of Object.keys(SHORT_COPY)) {
      const k = key as keyof typeof SHORT_COPY;
      expect(SHORT_COPY[k].en.trim()).toBeTruthy();
      expect(SHORT_COPY[k].ar.trim()).toBeTruthy();
    }
  });
  it("resolves copy for both languages", () => {
    expect(t("nav_dashboard", "en")).toBe("Dashboard");
    expect(t("nav_dashboard", "ar")).toBe("لوحة التحكم");
  });
  it("formats numbers with Latin digits in Arabic locale", () => {
    expect(fmtNum("ar-EG-u-nu-latn", "1234.5")).not.toContain("١");
    expect(fmtNum("en", 10_000)).toBe("10,000");
  });
});

describe("ratio percent formatting (QA F1 regression)", () => {
  it("formats API decimals once, never x100 twice", async () => {
    const { fmtPct } = await import("./format");
    // COMI net margin from /ratios (0.479...) and AMOC gross margin (6.63%).
    expect(fmtPct("en", "0.47948")).toBe("47.9%");
    expect(fmtPct("en", "0.0663")).toBe("6.6%");
    expect(fmtPct("ar-EG-u-nu-latn", "0.0663")).not.toContain("663");
    expect(fmtPct("en", null)).toBe("—");
  });
});
