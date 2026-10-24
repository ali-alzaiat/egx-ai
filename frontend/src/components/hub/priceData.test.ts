import { describe, expect, it } from "vitest";
import type { DailyPrice } from "../../types";
import { chartBars, fiftyTwoWeekRange, realBarsNewestFirst } from "./priceData";

function bar(date: string, o: string, h: string, l: string, c: string, volume: number): DailyPrice {
  return {
    id: date, company_id: "c", date, open: o, high: h, low: l, close: c, adjusted_close: null,
    volume, value_traded: null, trades: null, source_id: "s", created_at: date,
  };
}

const items = [
  bar("2026-10-20", "10", "11", "9.5", "10.5", 100),
  bar("2026-10-21", "10.5", "10.5", "10.5", "10.5", 0), // placeholder
  bar("2026-10-22", "10.5", "12", "10", "11.5", 200),
];

describe("realBarsNewestFirst", () => {
  it("drops placeholder bars and sorts newest first", () => {
    expect(realBarsNewestFirst(items).map((b) => b.date)).toEqual(["2026-10-22", "2026-10-20"]);
  });
});

describe("chartBars", () => {
  it("returns ascending numeric closes", () => {
    expect(chartBars(realBarsNewestFirst(items))).toEqual([
      { date: "2026-10-20", close: 10.5 },
      { date: "2026-10-22", close: 11.5 },
    ]);
  });
});

describe("fiftyTwoWeekRange", () => {
  it("takes the lowest low and highest high", () => {
    expect(fiftyTwoWeekRange(items)).toEqual({ low: 9.5, high: 12 });
  });
  it("is null without bars", () => {
    expect(fiftyTwoWeekRange([])).toBeNull();
  });
});
