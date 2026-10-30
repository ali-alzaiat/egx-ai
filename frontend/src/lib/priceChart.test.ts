import { describe, expect, it } from "vitest";
import {
  addTradingDays,
  candleData,
  coneOverlay,
  coneValues,
  dateIndex,
  futureTradingDates,
  isCandle,
  lineData,
  patternInView,
  patternOverlay,
  patternValues,
  trimLine,
  priceExtent,
  rangeStart,
  sliceRange,
  sliceRangePadded,
  coneHorizonDays,
  zoomSpan,
  wheelZoomFactor,
  tickLabel,
  tickUnitFor,
  timeToIso,
  type ChartBar,
  type ConeShape,
  type PatternShape,
} from "./priceChart";

const bars: ChartBar[] = [
  { date: "2026-01-15", close: 10 },
  { date: "2026-04-20", close: 12 },
  { date: "2026-07-22", close: 11 },
  { date: "2026-10-22", close: 14 },
];

describe("rangeStart", () => {
  it("counts back whole months from the newest bar", () => {
    expect(rangeStart("2026-10-22", "3M")).toBe("2026-07-22");
    expect(rangeStart("2026-10-22", "1Y")).toBe("2025-10-22");
  });
});

describe("sliceRange", () => {
  it("keeps bars from the range start on", () => {
    expect(sliceRange(bars, "3M").map((b) => b.date)).toEqual(["2026-07-22", "2026-10-22"]);
    expect(sliceRange(bars, "1Y")).toHaveLength(4);
  });
  it("returns nothing for no bars", () => {
    expect(sliceRange([], "1Y")).toEqual([]);
  });
});

describe("ranges: week, month, YTD, 5 years", () => {
  it("counts a week back in days and a month and 5 years in calendar units", () => {
    expect(rangeStart("2026-10-29", "1W")).toBe("2026-10-22");
    expect(rangeStart("2026-10-29", "1M")).toBe("2026-09-29");
    expect(rangeStart("2026-10-29", "5Y")).toBe("2021-10-29");
  });
  it("starts YTD on 1 January of the newest bar's year", () => {
    expect(rangeStart("2026-10-29", "YTD")).toBe("2026-01-01");
    expect(sliceRange(bars, "YTD").map((b) => b.date)).toEqual(bars.map((b) => b.date));
    const crossYear = [{ date: "2025-12-30", close: 9 }, ...bars.slice(1)];
    expect(sliceRange(crossYear, "YTD").map((b) => b.date)).toEqual(["2026-04-20", "2026-07-22", "2026-10-22"]);
  });
  it("keeps at least the last two bars so a line can be drawn", () => {
    const sparse: ChartBar[] = [
      { date: "2026-01-04", close: 1 },
      { date: "2026-10-22", close: 2 },
    ];
    expect(sliceRange(sparse, "1W").map((b) => b.date)).toEqual(["2026-01-04", "2026-10-22"]);
    expect(sliceRange([{ date: "2026-10-22", close: 2 }], "1W")).toHaveLength(1);
  });
  it("slices five years and one year of bars", () => {
    const long: ChartBar[] = [
      { date: "2021-10-31", close: 1 },
      { date: "2022-06-01", close: 2 },
      { date: "2026-10-29", close: 3 },
    ];
    expect(sliceRange(long, "5Y")).toHaveLength(3);
    expect(sliceRange(long, "1Y").map((b) => b.date)).toEqual(["2022-06-01", "2026-10-29"]);
  });
});

describe("series data", () => {
  const ohlc: ChartBar[] = [
    { date: "2026-10-20", open: 10, high: 12, low: 9, close: 11 },
    { date: "2026-10-21", open: 11, high: 13, low: 10, close: 12 },
    { date: "2026-10-22", close: 12.5 },
  ];
  it("maps each bar to a line point on its ISO date", () => {
    expect(lineData(ohlc)).toEqual([
      { time: "2026-10-20", value: 11 },
      { time: "2026-10-21", value: 12 },
      { time: "2026-10-22", value: 12.5 },
    ]);
    expect(lineData([])).toEqual([]);
  });
  it("draws a candle only from a bar with open, high and low", () => {
    expect(candleData(ohlc).map((c) => c.time)).toEqual(["2026-10-20", "2026-10-21"]);
    expect(candleData(ohlc)[0]).toEqual({ time: "2026-10-20", open: 10, high: 12, low: 9, close: 11 });
  });
  it("leaves out a bar whose high or low contradicts its open and close, never repairs it", () => {
    expect(isCandle({ date: "d", open: 10, high: 9, low: 8, close: 9.5 })).toBe(false);
    expect(isCandle({ date: "d", open: 10, high: 12, low: 11, close: 11.5 })).toBe(false);
    expect(isCandle({ date: "d", open: Number.NaN, high: 12, low: 9, close: 11 })).toBe(false);
    expect(isCandle({ date: "d", open: 10, high: 12, low: 9, close: 11 })).toBe(true);
  });
});

describe("trading calendar", () => {
  it("steps over Friday and Saturday only", () => {
    // 2026-10-22 is a Thursday: the next trading day is Sunday the 25th.
    expect(addTradingDays("2026-10-22", 1)).toBe("2026-10-25");
    expect(addTradingDays("2026-10-25", 5)).toBe("2026-11-01");
    expect(addTradingDays("2026-10-22", 0)).toBe("2026-10-22");
  });
  it("gives one date per session to the longest horizon", () => {
    const dates = futureTradingDates("2026-10-22", 126);
    expect(dates).toHaveLength(126);
    expect(dates[20]).toBe(addTradingDays("2026-10-22", 21));
    expect(dates[125]).toBe(addTradingDays("2026-10-22", 126));
  });
  it("lists ascending dates with no weekend day", () => {
    const dates = futureTradingDates("2026-10-22", 12);
    expect(dates[0]).toBe("2026-10-25");
    expect([...dates].sort()).toEqual(dates);
    for (const d of dates) expect([5, 6]).not.toContain(new Date(`${d}T00:00:00Z`).getUTCDay());
    expect(futureTradingDates("2026-10-22", 0)).toEqual([]);
  });
});

describe("time-axis labels", () => {
  it("reads an ISO date from a chart time", () => {
    expect(timeToIso("2026-10-22")).toBe("2026-10-22");
    expect(timeToIso({ year: 2026, month: 3, day: 9 })).toBe("2026-03-09");
    expect(timeToIso(Date.UTC(2026, 9, 22) / 1000)).toBe("2026-10-22");
    expect(timeToIso(Number.NaN)).toBeNull();
  });
  it("maps the library's tick types to day, month and year labels", () => {
    expect(tickUnitFor(0)).toBe("year");
    expect(tickUnitFor(1)).toBe("month");
    expect(tickUnitFor(2)).toBe("day");
    expect(tickUnitFor(3)).toBe("day");
  });
  it("formats English labels", () => {
    expect(tickLabel("en", "2026-10-22", "day")).toBe("22 Oct");
    expect(tickLabel("en", "2026-10-22", "month")).toBe("Oct");
    expect(tickLabel("en", "2026-10-22", "year")).toBe("2026");
  });
  it("keeps Latin digits in Arabic", () => {
    expect(tickLabel("ar-EG-u-nu-latn", "2026-10-22", "day")).toMatch(/22/);
    expect(tickLabel("ar-EG-u-nu-latn", "2026-10-22", "year")).toBe("2026");
  });
});

describe("priceExtent", () => {
  it("is the lowest and highest finite value", () => {
    expect(priceExtent([3, 9, Number.NaN, 1])).toEqual({ min: 1, max: 9 });
    expect(priceExtent([5])).toEqual({ min: 5, max: 5 });
  });
  it("is null with no usable values", () => {
    expect(priceExtent([])).toBeNull();
    expect(priceExtent([Number.NaN, Infinity])).toBeNull();
  });
});

describe("forecast cone on real dates", () => {
  const cone: ConeShape = {
    lastClose: 100,
    levels: [
      { days: 21, p05: 90, p25: 95, p75: 105, p95: 110 },
      { days: 126, p05: 70, p25: 85, p75: 118, p95: 140 },
    ],
  };
  it("lists every price the cone reaches for the price scale", () => {
    const values = coneValues(cone);
    expect(Math.min(...values)).toBe(70);
    expect(Math.max(...values)).toBe(140);
    expect(values).toContain(100);
  });
  it("extends the time axis over every trading day to the longest horizon", () => {
    const overlay = coneOverlay(cone, "2026-10-22")!;
    expect(overlay.futureDates).toHaveLength(126);
    expect(overlay.futureDates[0]).toBe("2026-10-25");
    expect(overlay.horizons).toEqual([
      { days: 21, date: addTradingDays("2026-10-22", 21) },
      { days: 126, date: overlay.futureDates[125] },
    ]);
  });
  it("draws two closed bands that start at the last close and widen to each horizon", () => {
    const overlay = coneOverlay(cone, "2026-10-22")!;
    expect(overlay.band90[0]).toEqual({ date: "2026-10-22", price: 100 });
    // Start, the upper edge at each horizon, then the lower edge back again.
    expect(overlay.band90.map((p) => p.price)).toEqual([100, 110, 140, 70, 90]);
    expect(overlay.band50.map((p) => p.price)).toEqual([100, 105, 118, 85, 95]);
    expect(overlay.band90[2]!.date).toBe(overlay.futureDates[125]);
    expect(overlay.band90[3]!.date).toBe(overlay.futureDates[125]);
    // At the last horizon the 90% band reaches wider than the 50% band.
    expect(overlay.band90[2]!.price).toBeGreaterThan(overlay.band50[2]!.price);
    expect(overlay.band90[3]!.price).toBeLessThan(overlay.band50[3]!.price);
  });
  it("draws nothing without horizons", () => {
    expect(coneOverlay({ lastClose: 1, levels: [] }, "2026-10-22")).toBeNull();
  });
});

describe("pattern overlays", () => {
  const history: ChartBar[] = [
    "2026-06-08",
    "2026-06-21",
    "2026-06-29",
    "2026-07-07",
    "2026-07-19",
    "2026-07-27",
    "2026-08-02",
  ].map((date, i) => ({ date, close: 100 + i }));
  const shape: PatternShape = {
    id: "double_bottom:2026-06-08:2026-07-07",
    startDate: "2026-06-08",
    confirmationDate: "2026-07-07",
    breakLevel: 136.7,
    target: 144.9,
    points: [
      { date: "2026-06-08", price: 130.1 },
      { date: "2026-06-21", price: 136.7 },
      { date: "2026-06-29", price: 126.89 },
    ],
    lines: [{ start: { date: "2026-06-21", price: 136.7 }, end: { date: "2026-07-07", price: 136.7 } }],
  };
  it("finds the first bar on or after a date and clamps", () => {
    expect(dateIndex(history, "2026-06-08")).toBe(0);
    expect(dateIndex(history, "2026-06-22")).toBe(2);
    expect(dateIndex(history, "2027-01-01")).toBe(history.length - 1);
    expect(dateIndex([], "2026-01-01")).toBe(0);
  });
  it("is drawn only when all of it lies inside the visible bars", () => {
    expect(patternInView(shape, history)).toBe(true);
    expect(patternInView(shape, history.slice(1))).toBe(false);
    expect(patternInView({ ...shape, confirmationDate: "2026-09-01" }, history)).toBe(false);
    expect(patternInView(shape, [])).toBe(false);
  });
  it("trims a line to the price band of the shape's key points", () => {
    // Upper boundary projected back far above the points: it starts where it enters the band.
    const line = { start: { date: "2026-06-08", price: 150 }, end: { date: "2026-07-07", price: 130 } };
    const trimmed = trimLine(line, shape.points, history);
    expect(trimmed).not.toBeNull();
    expect(trimmed!.start.price).toBeLessThanOrEqual(136.7);
    expect(trimmed!.start.date > "2026-06-08").toBe(true);
    expect(trimmed!.end).toEqual(line.end);
    // A flat neckline inside the band is untouched; one outside it is dropped.
    expect(trimLine(shape.lines[0]!, shape.points, history)).toEqual(shape.lines[0]);
    expect(trimLine({ start: { date: "2026-06-08", price: 160 }, end: { date: "2026-07-07", price: 160 } }, shape.points, history)).toBeNull();
    expect(patternValues({ ...shape, lines: [line] })).not.toContain(150);
  });
  it("includes points, break level and target in the price scale values", () => {
    expect(patternValues(shape)).toEqual(expect.arrayContaining([130.1, 126.89, 136.7, 144.9]));
    expect(patternValues({ ...shape, target: null })).not.toContain(144.9);
  });
  it("puts a confirmed pattern on bar dates: points, lines, break mark and target", () => {
    const o = patternOverlay(shape, history);
    expect(o.forming).toBe(false);
    expect(o.points.map((p) => p.date)).toEqual(["2026-06-08", "2026-06-21", "2026-06-29"]);
    expect(o.outline).toEqual(o.points);
    // 2026-07-07 is a bar: the confirming close sits on it, at the break level.
    expect(o.breakMark).toEqual({ date: "2026-07-07", price: 136.7 });
    expect(o.target).toEqual({ startDate: "2026-06-08", endDate: "2026-07-07", price: 144.9 });
    expect(o.lines).toHaveLength(1);
    expect(o.levels).toEqual([]);
  });
  it("moves a date that is not a bar to the next bar", () => {
    const o = patternOverlay({ ...shape, points: [{ date: "2026-06-10", price: 130 }] }, history);
    expect(o.points[0]!.date).toBe("2026-06-21");
  });
  it("has no target when the shape has none", () => {
    expect(patternOverlay({ ...shape, target: null }, history).target).toBeNull();
  });
  it("draws a forming shape's confirming levels from the last key point to the latest bar", () => {
    const forming: PatternShape = {
      ...shape,
      id: "forming:double_top:2026-06-08",
      target: null,
      forming: { above: 140, below: 125 },
    };
    const o = patternOverlay(forming, history);
    expect(o.forming).toBe(true);
    expect(o.breakMark).toBeNull();
    expect(o.target).toBeNull();
    expect(o.levels).toEqual([
      { startDate: "2026-06-29", endDate: "2026-08-02", price: 140, side: "above" },
      { startDate: "2026-06-29", endDate: "2026-08-02", price: 125, side: "below" },
    ]);
    const oneSided = patternOverlay({ ...forming, forming: { above: 140, below: null } }, history);
    expect(oneSided.levels.map((l) => l.side)).toEqual(["above"]);
  });
});

describe("history padded to the cone horizon", () => {
  const daily: ChartBar[] = Array.from({ length: 200 }, (_, i) => {
    const d = new Date(Date.UTC(2026, 0, 1) + i * 86400000);
    return { date: d.toISOString().slice(0, 10), close: 100 + i };
  });
  it("keeps the range when it already has enough bars", () => {
    expect(sliceRangePadded(daily, "3M", 20)).toEqual(sliceRange(daily, "3M"));
  });
  it("adds earlier bars so a short range is at least as long as the horizon", () => {
    const padded = sliceRangePadded(daily, "1W", 126);
    expect(padded).toHaveLength(126);
    expect(padded[padded.length - 1]).toBe(daily[daily.length - 1]);
    expect(padded.length).toBeGreaterThan(sliceRange(daily, "1W").length);
  });
  it("uses every bar when fewer exist, and no padding for no horizon", () => {
    expect(sliceRangePadded(daily, "1W", 500)).toHaveLength(200);
    expect(sliceRangePadded(daily, "1W", 0)).toEqual(sliceRange(daily, "1W"));
    expect(sliceRangePadded([], "1W", 126)).toEqual([]);
  });
  it("reads the longest horizon of a cone", () => {
    expect(coneHorizonDays({ lastClose: 1, levels: [{ days: 21, p05: 1, p25: 1, p75: 1, p95: 1 }, { days: 126, p05: 1, p25: 1, p75: 1, p95: 1 }] })).toBe(126);
    expect(coneHorizonDays({ lastClose: 1, levels: [] })).toBe(0);
  });
});

describe("wheel zoom", () => {
  it("zooms in about the anchor, keeping it fixed", () => {
    const out = zoomSpan({ from: 0, to: 100 }, 0.5, 0.5, 5, 1000);
    expect(out).toEqual({ from: 25, to: 75 });
    const left = zoomSpan({ from: 0, to: 100 }, 0.5, 0, 5, 1000);
    expect(left).toEqual({ from: 0, to: 50 });
    const right = zoomSpan({ from: 0, to: 100 }, 0.5, 1, 5, 1000);
    expect(right).toEqual({ from: 50, to: 100 });
  });
  it("keeps the span between the limits", () => {
    expect(zoomSpan({ from: 0, to: 10 }, 0.1, 0.5, 5, 100).to - 0).toBeGreaterThan(0);
    const tight = zoomSpan({ from: 0, to: 10 }, 0.01, 0.5, 5, 100);
    expect(tight.to - tight.from).toBe(5);
    const wide = zoomSpan({ from: 0, to: 90 }, 5, 0.5, 5, 100);
    expect(wide.to - wide.from).toBe(100);
  });
  it("ignores a bad factor or an empty span", () => {
    const span = { from: 0, to: 10 };
    expect(zoomSpan(span, 0, 0.5, 1, 100)).toBe(span);
    expect(zoomSpan(span, Number.NaN, 0.5, 1, 100)).toBe(span);
    expect(zoomSpan({ from: 5, to: 5 }, 0.5, 0.5, 1, 100)).toEqual({ from: 5, to: 5 });
  });
  it("zooms in when scrolling up and out when scrolling down", () => {
    expect(wheelZoomFactor(-100)).toBeLessThan(1);
    expect(wheelZoomFactor(100)).toBeGreaterThan(1);
    expect(wheelZoomFactor(0)).toBe(1);
    expect(wheelZoomFactor(1e6)).toBe(wheelZoomFactor(200));
  });
});
