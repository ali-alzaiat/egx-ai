import { describe, it, expect } from "vitest";
import {
  fmtChange,
  fmtCycle,
  fmtDate,
  fmtEgpCompact,
  fmtEgpMillions,
  fmtInt,
  fmtPct,
  fmtPrice,
  fmtRatio,
  fmtScore,
  fmtSignedPct,
  formatAsOf,
  plural,
  toNumber,
} from "./format";

const EN = "en";
const AR = "ar-EG-u-nu-latn";

describe("missing values return null, never 0/NaN/Never", () => {
  const missing = [null, undefined, "", "abc", Number.NaN, Number.POSITIVE_INFINITY];
  it.each(missing)("helpers return null for %s", (v) => {
    expect(toNumber(v as never)).toBeNull();
    expect(fmtPrice(EN, v as never)).toBeNull();
    expect(fmtPct(EN, v as never)).toBeNull();
    expect(fmtSignedPct(EN, v as never)).toBeNull();
    expect(fmtRatio(EN, v as never)).toBeNull();
    expect(fmtInt(EN, v as never)).toBeNull();
    expect(fmtEgpMillions(EN, v as never)).toBeNull();
    expect(fmtEgpCompact(EN, v as never)).toBeNull();
    expect(fmtScore(EN, v as never)).toBeNull();
    expect(fmtChange(EN, v as never, 0.01)).toBeNull();
    expect(fmtChange(EN, 1, v as never)).toBeNull();
  });
  it("dates and cycles", () => {
    expect(fmtDate(EN, null)).toBeNull();
    expect(fmtDate(EN, "not a date")).toBeNull();
    expect(fmtCycle(EN, "2026-13x")).toBeNull();
    expect(formatAsOf(null)).toBe("—");
  });
  it("zero is a real value, not missing", () => {
    expect(fmtPrice(EN, 0)).toBe("0.00");
    expect(fmtPct(EN, 0)).toBe("0.0%");
    expect(fmtScore(EN, 0)).toBe("0");
  });
});

describe("formatting rules", () => {
  it("prices are 2 dp", () => {
    expect(fmtPrice(EN, "133.9")).toBe("133.90");
    expect(fmtPrice(AR, 1.14)).toBe("1.14");
  });
  it("change uses a real minus sign and always shows the sign", () => {
    expect(fmtChange(EN, -7.05, -0.05)).toBe("−7.05 (−5.00%)");
    expect(fmtChange(EN, 1.5, 0.0123)).toBe("+1.50 (+1.23%)");
    expect(fmtChange(EN, 0, 0)).toBe("0.00 (0.00%)");
  });
  it("percent takes decimals once", () => {
    expect(fmtPct(EN, 0.42)).toBe("42.0%");
    expect(fmtPct(EN, -0.0525)).toBe("−5.3%");
    expect(fmtPct(AR, -0.0525)).not.toContain("-");
    expect(fmtSignedPct(EN, 0.631)).toBe("+63.1%");
    expect(fmtSignedPct(EN, -0.143)).toBe("−14.3%");
  });
  it("ratios, integers and millions", () => {
    expect(fmtRatio(EN, 1.1823)).toBe("1.18");
    expect(fmtInt(EN, 4461086)).toBe("4,461,086");
    expect(fmtEgpMillions(EN, 106672946000)).toBe("106,672.9");
  });
  it("compact EGP in both languages with Western digits", () => {
    expect(fmtEgpCompact(EN, 237_900_000)).toBe("EGP 237.9m");
    expect(fmtEgpCompact(EN, 1_234_000_000)).toBe("EGP 1.23bn");
    expect(fmtEgpCompact(EN, 500_000)).toBe("EGP 500K");
    expect(fmtEgpCompact(AR, 237_900_000)).toBe("237.9 مليون ج.م");
  });
  it("score is a signed integer", () => {
    expect(fmtScore(EN, 40.2)).toBe("+40");
    expect(fmtScore(EN, -20)).toBe("−20");
  });
  it("dates are read as UTC and never shift a day", () => {
    expect(fmtDate(EN, "2026-10-22")).toBe("22 Oct 2026");
    expect(fmtDate(EN, "2026-01-01")).toBe("1 Jan 2026");
    expect(fmtDate(AR, "2026-10-22")).toMatch(/^22 /);
    expect(fmtCycle(EN, "2026-08")).toBe("Aug 2026");
  });
  it("plural picks the right Arabic form", () => {
    const forms = { zero: "لا شركات", one: "شركة", two: "شركتان", few: "{n} شركات", other: "{n} شركة" };
    expect(plural(AR, 0, forms)).toBe("لا شركات");
    expect(plural(AR, 3, forms)).toBe("3 شركات");
    expect(plural(AR, 234, forms)).toBe("234 شركة");
    expect(plural(EN, 1, { one: "{n} company", other: "{n} companies" })).toBe("1 company");
  });
});
