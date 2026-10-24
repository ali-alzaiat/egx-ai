import { describe, it, expect } from "vitest";
import { COPY_MODULES, SHORT_COPY, t } from "./dict";
import { fmtNum, fmtPct } from "../lib/format";

describe("i18n", () => {
  it("has EN and AR for every key", () => {
    for (const key of Object.keys(SHORT_COPY)) {
      const k = key as keyof typeof SHORT_COPY;
      expect(SHORT_COPY[k].en.trim()).toBeTruthy();
      expect(SHORT_COPY[k].ar.trim()).toBeTruthy();
    }
  });
  it("keeps keys unique across the per-area modules", () => {
    const seen = new Map<string, string>();
    for (const [moduleName, copy] of Object.entries(COPY_MODULES)) {
      for (const key of Object.keys(copy)) {
        expect(seen.get(key), `${key} is defined in ${seen.get(key)} and ${moduleName}`).toBeUndefined();
        seen.set(key, moduleName);
      }
    }
    expect(seen.size).toBe(Object.keys(SHORT_COPY).length);
  });
  it("never uses Eastern Arabic digits in AR copy (Western digits only)", () => {
    for (const [key, entry] of Object.entries(SHORT_COPY)) {
      expect(/[٠-٩۰-۹]/.test(entry.ar), `${key} has Eastern digits`).toBe(false);
    }
  });
  it("uses the same placeholders in EN and AR", () => {
    const names = (s: string): string[] => (s.match(/\{\w+\}/g) ?? []).sort();
    for (const [key, entry] of Object.entries(SHORT_COPY)) {
      expect(names(entry.ar), `${key} placeholders differ`).toEqual(names(entry.en));
    }
  });
  it("resolves copy for both languages", () => {
    expect(t("nav_dashboard", "en")).toBe("Dashboard");
    expect(t("nav_dashboard", "ar")).toBe("لوحة المعلومات");
  });
  it("fills placeholders", () => {
    expect(t("stance_confidence", "en", { c: 28 })).toBe("Confidence 28/100");
    expect(t("search_no_results", "ar", { q: "COMI" })).toContain("COMI");
  });
  it("never labels a stance as an instruction", () => {
    for (const key of ["stance_buy", "stance_hold", "stance_reduce"] as const) {
      expect(SHORT_COPY[key].en).not.toMatch(/^(buy|sell|hold|reduce)$/i);
    }
  });
  it("formats numbers with Latin digits in Arabic locale", () => {
    expect(fmtNum("ar-EG-u-nu-latn", "1234.5")).not.toContain("١");
    expect(fmtNum("en", 10_000)).toBe("10,000");
  });
});

describe("ratio percent formatting (QA F1 regression)", () => {
  it("formats API decimals once, never x100 twice", () => {
    // COMI net margin from /ratios (0.479...) and AMOC gross margin (6.63%).
    expect(fmtPct("en", "0.47948")).toBe("47.9%");
    expect(fmtPct("en", "0.0663")).toBe("6.6%");
    expect(fmtPct("ar-EG-u-nu-latn", "0.0663")).not.toContain("663");
    expect(fmtPct("en", null)).toBeNull();
  });
});
