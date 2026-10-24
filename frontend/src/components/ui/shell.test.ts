import { describe, it, expect } from "vitest";
import type { Company, DailyPrice } from "../../types";
import { activeTab, FINANCIALS_SECTIONS, HUB_TABS, isSectionActive, relativePath } from "../hub/tabs";
import { latestTwoBars } from "../hub/CompanyHeader";
import { isNotAssessed } from "./Badges";
import { isActivePath, routeTitleKey } from "./AppShell";
import { sortCompanyResults } from "./CompanySearch";
import { missingReasonText } from "./Missing";
import { t } from "../../i18n";

const bar = (date: string, close: string, volume = 100, flat = false): DailyPrice =>
  ({
    id: date,
    company_id: "c",
    date,
    open: flat ? close : "1.00",
    high: flat ? close : "2.00",
    low: flat ? close : "0.50",
    close,
    adjusted_close: null,
    volume,
  }) as DailyPrice;

describe("stance 'Not assessed' rule (QA F5)", () => {
  it("treats a missing stance, or the empty default hold, as not assessed", () => {
    expect(isNotAssessed(null, null, null)).toBe(true);
    expect(isNotAssessed("hold", 0, 0)).toBe(true);
    expect(isNotAssessed("hold", 28, 2)).toBe(false);
    expect(isNotAssessed("buy", 0, 3)).toBe(false);
  });
});

describe("hub change inputs", () => {
  it("skips placeholder bars and returns the two newest real bars", () => {
    const items = [
      bar("2026-10-19", "120"),
      bar("2026-10-22", "133.9"),
      bar("2026-10-21", "130", 0, true),
      bar("2026-10-20", "140.95"),
    ];
    const two = latestTwoBars(items);
    expect(two.map((b) => b.date)).toEqual(["2026-10-22", "2026-10-20"]);
  });
  it("returns fewer than two bars when history is short", () => {
    expect(latestTwoBars([bar("2026-10-22", "1")])).toHaveLength(1);
    expect(latestTwoBars([])).toEqual([]);
  });
});

describe("hub routing helpers", () => {
  const base = "/companies/ETEL";
  it("maps paths to tabs; unknown paths have no tab (Not found)", () => {
    expect(activeTab(HUB_TABS, relativePath(base, base))?.path).toBe("");
    expect(activeTab(HUB_TABS, relativePath(`${base}/`, base))?.path).toBe("");
    expect(activeTab(HUB_TABS, relativePath(`${base}/financials/ratios`, base))?.path).toBe("/financials");
    expect(activeTab(HUB_TABS, relativePath(`${base}/ai`, base))).toBeNull();
    expect(activeTab(HUB_TABS, relativePath("/companies/OTHER", base))).toBeNull();
  });
  it("highlights exactly one financials section", () => {
    const active = (rel: string): string[] =>
      FINANCIALS_SECTIONS.filter((s) => isSectionActive(s, rel)).map((s) => s.path);
    expect(active("")).toEqual([""]);
    expect(active("/ratios")).toEqual(["/ratios"]);
    expect(active("/quality")).toEqual(["/quality"]);
  });
});

describe("shell navigation helpers", () => {
  it("keeps Companies active on hub routes", () => {
    expect(isActivePath("/companies", "/companies/ETEL/price")).toBe(true);
    expect(isActivePath("/", "/companies")).toBe(false);
  });
  it("titles come from nav keys, except hub, admin and unknown routes", () => {
    expect(routeTitleKey("/rankings")).toBe("nav_rankings");
    expect(routeTitleKey("/companies/ETEL")).toBeNull();
    expect(routeTitleKey("/admin/market")).toBeNull();
    expect(routeTitleKey("/nope")).toBeNull();
  });
});

describe("company search ordering", () => {
  it("puts the exact ticker match first", () => {
    const co = (ticker: string): Company => ({ id: ticker, ticker, name: ticker }) as Company;
    const out = sortCompanyResults([co("COMIX"), co("COMI"), co("ABUK")], "comi");
    expect(out.map((c) => c.ticker)).toEqual(["COMI", "COMIX", "ABUK"]);
  });
});

describe("missing reasons", () => {
  const tEn = (key: Parameters<typeof t>[0], params?: Record<string, string | number>): string => t(key, "en", params);
  it("maps missing:<line> and passes other text through", () => {
    expect(missingReasonText("missing:eps", tEn)).toBe("Missing line: eps");
    expect(missingReasonText("missing:net_income", tEn, (l) => l.toUpperCase())).toBe("Missing line: NET_INCOME");
    expect(missingReasonText("provider timeout", tEn)).toBe("provider timeout");
    expect(missingReasonText(null, tEn)).toBe("Not available");
  });
});
