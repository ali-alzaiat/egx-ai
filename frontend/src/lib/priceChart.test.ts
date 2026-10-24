import { describe, expect, it } from "vitest";
import { gridValues, linePath, monthTicks, nearestIndex, rangeStart, scaleY, sliceRange, yDomain, type ChartBar } from "./priceChart";

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
