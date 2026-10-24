import { describe, expect, it } from "vitest";
import { t as translate } from "../../i18n/dict";
import { assessedStance, countText, fmtSigned2 } from "./shared";

const en = (key: Parameters<typeof translate>[0], p?: Record<string, string | number>) => translate(key, "en", p);
const ar = (key: Parameters<typeof translate>[0], p?: Record<string, string | number>) => translate(key, "ar", p);

describe("countText", () => {
  it("uses English one/other", () => {
    expect(countText(en, "en", 1, "stocks_count")).toBe("one stock");
    expect(countText(en, "en", 50, "stocks_count")).toBe("50 stocks");
  });
  it("uses the Arabic dual, few, many and other forms with Western digits", () => {
    const l = "ar-EG-u-nu-latn";
    expect(countText(ar, l, 1, "watchlists_count")).toBe("قائمة متابعة واحدة");
    expect(countText(ar, l, 2, "watchlists_count")).toBe("قائمتا متابعة");
    expect(countText(ar, l, 3, "watchlists_count")).toBe("3 قوائم متابعة");
    expect(countText(ar, l, 11, "watchlists_count")).toBe("11 قائمة متابعة");
    expect(countText(ar, l, 0, "stocks_count")).toBe("0 سهم");
  });
});

describe("assessedStance", () => {
  it("treats a missing stance or zero confidence as not assessed", () => {
    expect(assessedStance(null, 20)).toBeNull();
    expect(assessedStance("hold", 0)).toBeNull();
    expect(assessedStance("buy", 28)).toBe("buy");
  });
});

describe("fmtSigned2", () => {
  it("always signs non-zero values with a true minus", () => {
    expect(fmtSigned2("en", 1)).toBe("+1.00");
    expect(fmtSigned2("en", -0.25)).toBe("−0.25");
  });
});
