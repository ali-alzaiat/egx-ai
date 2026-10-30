import { describe, expect, it } from "vitest";
import {
  coneGeometry,
  coneValues,
  dateIndex,
  gridValues,
  horizonX,
  linePath,
  monthTicks,
  nearestIndex,
  patternGeometry,
  patternInView,
  patternValues,
  periodTicks,
  rangeStart,
  scaleY,
  sliceRange,
  splitX,
  tickUnit,
  yDomain,
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

describe("yDomain", () => {
  it("covers closes and reference lines with headroom", () => {
    const d = yDomain([10, 14], [8, 20]);
    expect(d).not.toBeNull();
    expect(d!.min).toBeLessThan(8);
    expect(d!.max).toBeGreaterThan(20);
  });
  it("widens a flat series so it can be drawn", () => {
    const d = yDomain([5, 5], []);
    expect(d!.max).toBeGreaterThan(d!.min);
  });
  it("is null with no usable values", () => {
    expect(yDomain([], [])).toBeNull();
    expect(yDomain([Number.NaN], [])).toBeNull();
  });
});

describe("scales", () => {
  it("maps the domain onto the pixel box, high values up", () => {
    const d = { min: 0, max: 10 };
    expect(scaleY(0, d, 10, 110)).toBe(110);
    expect(scaleY(10, d, 10, 110)).toBe(10);
  });
  it("gives four gridlines inside the domain", () => {
    const g = gridValues({ min: 0, max: 100 });
    expect(g).toHaveLength(4);
    expect(g[0]).toBeGreaterThan(0);
    expect(g[3]).toBeLessThan(100);
  });
  it("draws one move then lines", () => {
    const path = linePath(bars, { min: 9, max: 15 }, { left: 0, right: 300, top: 0, bottom: 100 });
    expect(path.startsWith("M0.0 ")).toBe(true);
    expect(path.match(/L/g)).toHaveLength(3);
  });
});

describe("monthTicks", () => {
  it("marks the first bar of each month and thins crowded ticks", () => {
    expect(monthTicks(bars, 0, 300, 10).map((t) => t.index)).toEqual([0, 1, 2, 3]);
    expect(monthTicks(bars, 0, 300, 120).map((t) => t.index)).toEqual([0, 2]);
  });
});

describe("nearestIndex", () => {
  it("snaps a pixel to the closest bar and clamps", () => {
    expect(nearestIndex(0, 4, 0, 300)).toBe(0);
    expect(nearestIndex(160, 4, 0, 300)).toBe(2);
    expect(nearestIndex(999, 4, 0, 300)).toBe(3);
    expect(nearestIndex(-50, 4, 0, 300)).toBe(0);
    expect(nearestIndex(10, 1, 0, 300)).toBe(0);
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

describe("periodTicks", () => {
  const daily: ChartBar[] = [
    { date: "2026-10-25", close: 1 },
    { date: "2026-10-26", close: 1 },
    { date: "2026-10-27", close: 1 },
    { date: "2026-11-01", close: 1 },
  ];
  it("picks the unit from the range", () => {
    expect(tickUnit("1W")).toBe("day");
    expect(tickUnit("1M")).toBe("day");
    expect(tickUnit("YTD")).toBe("month");
    expect(tickUnit("1Y")).toBe("month");
    expect(tickUnit("5Y")).toBe("year");
  });
  it("marks every day, month or year and thins crowded labels", () => {
    expect(periodTicks(daily, "day", 0, 300, 10).map((t) => t.index)).toEqual([0, 1, 2, 3]);
    expect(periodTicks(daily, "day", 0, 300, 150).map((t) => t.index)).toEqual([0, 2]);
    expect(periodTicks(daily, "month", 0, 300, 10).map((t) => t.index)).toEqual([0, 3]);
    expect(periodTicks(bars, "year", 0, 300, 10).map((t) => t.index)).toEqual([0]);
  });
  it("gives no label to a leading partial year", () => {
    const fiveYears: ChartBar[] = [
      { date: "2021-10-31", close: 1 },
      { date: "2022-01-02", close: 1 },
      { date: "2023-01-01", close: 1 },
    ];
    expect(periodTicks(fiveYears, "year", 0, 300, 10).map((t) => t.date)).toEqual(["2022-01-02", "2023-01-01"]);
  });
});

describe("forecast zone", () => {
  const box = { left: 0, right: 400, top: 0, bottom: 200 };
  it("gives the right share of the plot to the forecast", () => {
    expect(splitX(box, 0)).toBe(400);
    expect(splitX(box, 0.25)).toBe(300);
    expect(splitX(box, 5)).toBe(40);
  });
  it("places horizons linearly, the longest at the right edge", () => {
    expect(horizonX(126, 126, 300, 400)).toBe(400);
    expect(horizonX(63, 126, 300, 400)).toBe(350);
    expect(horizonX(0, 126, 300, 400)).toBe(300);
    expect(horizonX(500, 126, 300, 400)).toBe(400);
    expect(horizonX(10, 0, 300, 400)).toBe(300);
  });
  const cone: ConeShape = {
    lastClose: 100,
    levels: [
      { days: 21, p05: 90, p25: 95, p75: 105, p95: 110 },
      { days: 126, p05: 70, p25: 85, p75: 118, p95: 140 },
    ],
  };
  it("lists every price the cone reaches for the y domain", () => {
    const values = coneValues(cone);
    expect(Math.min(...values)).toBe(70);
    expect(Math.max(...values)).toBe(140);
    expect(values).toContain(100);
  });
  it("draws two closed bands that start at the last close and widen to each horizon", () => {
    const geo = coneGeometry(cone, { min: 60, max: 150 }, box, 300);
    expect(geo.band90.startsWith("M300.0 ")).toBe(true);
    expect(geo.band90.endsWith("Z")).toBe(true);
    expect(geo.band50.match(/L/g)).toHaveLength(4);
    expect(geo.marks.map((m) => m.days)).toEqual([21, 126]);
    expect(geo.marks[0]!.x).toBeCloseTo(316.67, 1);
    expect(geo.marks[1]!.x).toBe(400);
    // At the last horizon the 90% band reaches higher on screen (a smaller y) than the 50% band.
    const topAtEnd = (path: string): number =>
      Math.min(...[...path.matchAll(/L400\.0 ([\d.]+)/g)].map((m) => Number(m[1])));
    expect(topAtEnd(geo.band90)).toBeLessThan(topAtEnd(geo.band50));
  });
  it("draws nothing without horizons", () => {
    expect(coneGeometry({ lastClose: 1, levels: [] }, { min: 0, max: 2 }, box, 300)).toEqual({
      band90: "",
      band50: "",
      marks: [],
    });
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
  it("includes points, lines, break level and target in the y domain values", () => {
    expect(patternValues(shape)).toEqual(expect.arrayContaining([130.1, 126.89, 136.7, 144.9]));
    expect(patternValues({ ...shape, target: null })).not.toContain(144.9);
  });
  it("maps dates and prices to pixels inside the history zone", () => {
    const box = { left: 0, right: 300, top: 0, bottom: 100 };
    const domain = { min: 120, max: 150 };
    const geo = patternGeometry(shape, history, domain, box, 240);
    expect(geo.points).toHaveLength(3);
    expect(geo.points[0]!.x).toBe(0);
    expect(geo.points[2]!.x).toBeGreaterThan(geo.points[1]!.x);
    expect(geo.points.every((p) => p.x <= 240)).toBe(true);
    expect(geo.outline.startsWith("M0.0 ")).toBe(true);
    expect(geo.lines).toHaveLength(1);
    expect(geo.breakMark.x).toBe(geo.lines[0]!.x2);
    // Higher prices are higher on screen: the target sits above the break level.
    expect(geo.targetLine!.y).toBeLessThan(geo.breakMark.y);
    expect(geo.targetLine!.x1).toBe(0);
    expect(geo.targetLine!.x2).toBe(geo.breakMark.x);
    expect(patternGeometry({ ...shape, target: null }, history, domain, box, 240).targetLine).toBeNull();
  });
});
