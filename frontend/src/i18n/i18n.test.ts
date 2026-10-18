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
