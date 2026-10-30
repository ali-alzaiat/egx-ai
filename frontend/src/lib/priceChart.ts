/** Pure geometry for the PriceChart (no DOM): ranges, scales, ticks, nearest point, forecast cone, pattern overlays. */

export interface ChartBar {
  /** ISO date, "2026-10-22". */
  date: string;
  close: number;
}

/** Line-chart ranges. "1D" is not one: the Day view is a last-session summary, not a line. */
export type ChartRange = "1W" | "1M" | "3M" | "6M" | "YTD" | "1Y" | "5Y";

/** The ranges the company overview offers, left to right. */
export type OverviewRange = "1D" | "1W" | "1M" | "YTD" | "1Y" | "5Y";
export const OVERVIEW_RANGES: readonly OverviewRange[] = ["1D", "1W", "1M", "YTD", "1Y", "5Y"];

const RANGE_MONTHS: Partial<Record<ChartRange, number>> = {
  "1M": 1,
  "3M": 3,
  "6M": 6,
  "1Y": 12,
  "5Y": 60,
};

/** First day included in `range`, counted back from the last bar (UTC, so no day shifts). */
export function rangeStart(lastDate: string, range: ChartRange): string {
  if (range === "YTD") return `${lastDate.slice(0, 4)}-01-01`;
  const d = new Date(`${lastDate}T00:00:00Z`);
  if (range === "1W") {
    d.setUTCDate(d.getUTCDate() - 7);
  } else {
    d.setUTCMonth(d.getUTCMonth() - (RANGE_MONTHS[range] ?? 0));
  }
  return d.toISOString().slice(0, 10);
}

/** Ascending bars within `range` of the newest bar (at least the last two bars, so a line can be drawn). */
export function sliceRange(bars: readonly ChartBar[], range: ChartRange): ChartBar[] {
  const last = bars[bars.length - 1];
  if (!last) return [];
  const start = rangeStart(last.date, range);
  const inRange = bars.filter((b) => b.date >= start);
  return inRange.length >= 2 ? inRange : bars.slice(-2);
}

export interface Domain {
  min: number;
  max: number;
}

/** Y domain over the closes and any reference lines, with 6% headroom. */
export function yDomain(closes: readonly number[], refs: readonly number[]): Domain | null {
  const all = [...closes, ...refs].filter((v) => Number.isFinite(v));
  if (all.length === 0) return null;
  let min = Math.min(...all);
  let max = Math.max(...all);
  if (min === max) {
    min -= 1;
    max += 1;
  }
  const pad = (max - min) * 0.06;
  return { min: min - pad, max: max + pad };
}

/** Four evenly spaced gridline values from low to high of the domain. */
export function gridValues(domain: Domain, count = 4): number[] {
  const step = (domain.max - domain.min) / (count + 1);
  return Array.from({ length: count }, (_, i) => domain.min + step * (i + 1));
}

export function scaleY(value: number, domain: Domain, top: number, bottom: number): number {
  const span = domain.max - domain.min;
  return span === 0 ? bottom : bottom - ((value - domain.min) / span) * (bottom - top);
}

export function scaleX(index: number, count: number, left: number, right: number): number {
  return count <= 1 ? left : left + (index / (count - 1)) * (right - left);
}

/** SVG path for the close line. */
export function linePath(
  bars: readonly ChartBar[],
  domain: Domain,
  box: { left: number; right: number; top: number; bottom: number },
): string {
  return bars
    .map((b, i) => {
      const x = scaleX(i, bars.length, box.left, box.right).toFixed(1);
      const y = scaleY(b.close, domain, box.top, box.bottom).toFixed(1);
      return `${i === 0 ? "M" : "L"}${x} ${y}`;
    })
    .join(" ");
}

export type TickUnit = "day" | "month" | "year";

/** Axis label unit for a range: days for a week or month, months up to a year, years beyond. */
export function tickUnit(range: ChartRange): TickUnit {
  if (range === "1W" || range === "1M") return "day";
  return range === "5Y" ? "year" : "month";
}

const TICK_KEY_LENGTH: Record<TickUnit, number> = {
  day: 10,
  month: 7,
  year: 4,
};

/**
 * Index of the first bar of each day / month / year, thinned so labels keep `minGap` px apart.
 * A leading partial year (the first bar is not in January) gets no label: it would sit on top
 * of the next year's.
 */
export function periodTicks(
  bars: readonly ChartBar[],
  unit: TickUnit,
  left: number,
  right: number,
  minGap: number,
): { index: number; date: string }[] {
  const ticks: { index: number; date: string }[] = [];
  let lastKey = "";
  let lastX = -Infinity;
  bars.forEach((b, i) => {
    const key = b.date.slice(0, TICK_KEY_LENGTH[unit]);
    if (key === lastKey) return;
    lastKey = key;
    if (unit === "year" && i === 0 && b.date.slice(5, 7) !== "01") return;
    const x = scaleX(i, bars.length, left, right);
    if (x - lastX >= minGap) {
      ticks.push({ index: i, date: b.date });
      lastX = x;
    }
  });
  return ticks;
}

/** Index of the first bar of each calendar month, thinned so labels keep `minGap` px apart. */
export function monthTicks(bars: readonly ChartBar[], left: number, right: number, minGap: number): { index: number; date: string }[] {
  return periodTicks(bars, "month", left, right, minGap);
}

/** Index of the bar closest to pixel `x`. */
export function nearestIndex(x: number, count: number, left: number, right: number): number {
  if (count <= 1) return 0;
  const ratio = (x - left) / (right - left);
  return Math.min(count - 1, Math.max(0, Math.round(ratio * (count - 1))));
}

export interface PlotBox {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

// ---- Forecast cone: a range of typical moves to the right of the last close ----

/** Share of the plot width given to the forecast zone when the cone is shown. */
export const FORECAST_SHARE = 0.36;

/**
 * x where the history ends. With no forecast the history fills the plot; with one the
 * right `futureShare` of the plot is the forecast zone. The two zones have their own
 * time scale (the history is per session, the forecast per horizon) and are separated
 * by a "last close" line, so the cone's width is never read against the history's pace.
 */
export function splitX(box: PlotBox, futureShare: number): number {
  const share = Math.min(0.9, Math.max(0, futureShare));
  return box.right - (box.right - box.left) * share;
}

/** x of a horizon in the forecast zone: linear in trading days, the longest horizon at the right edge. */
export function horizonX(days: number, maxDays: number, nowX: number, right: number): number {
  if (maxDays <= 0) return nowX;
  return nowX + (Math.min(Math.max(days, 0), maxDays) / maxDays) * (right - nowX);
}

/** One horizon of the cone as numbers: central 50% is p25..p75, central 90% is p05..p95. */
export interface ConeLevel {
  days: number;
  p05: number;
  p25: number;
  p75: number;
  p95: number;
}

export interface ConeShape {
  lastClose: number;
  /** Ascending by `days`. */
  levels: readonly ConeLevel[];
}

/** Every price the cone reaches, for the y domain. */
export function coneValues(cone: ConeShape): number[] {
  return [cone.lastClose, ...cone.levels.flatMap((l) => [l.p05, l.p25, l.p75, l.p95])];
}

function bandPath(cone: ConeShape, lowKey: "p05" | "p25", highKey: "p75" | "p95", domain: Domain, box: PlotBox, nowX: number): string {
  const maxDays = cone.levels[cone.levels.length - 1]?.days ?? 0;
  const y = (v: number): string => scaleY(v, domain, box.top, box.bottom).toFixed(1);
  const x = (days: number): string => horizonX(days, maxDays, nowX, box.right).toFixed(1);
  const upper = cone.levels.map((l) => `L${x(l.days)} ${y(l[highKey])}`);
  const lower = [...cone.levels].reverse().map((l) => `L${x(l.days)} ${y(l[lowKey])}`);
  return `M${nowX.toFixed(1)} ${y(cone.lastClose)} ${upper.join(" ")} ${lower.join(" ")} Z`;
}

export interface ConeGeometry {
  /** Closed polygons: widen from the last close out to each horizon (straight segments between horizons). */
  band90: string;
  band50: string;
  /** One mark per horizon on the forecast axis. */
  marks: { x: number; days: number }[];
}

/** Polygons and axis marks for the cone; empty when there are no horizons. */
export function coneGeometry(cone: ConeShape, domain: Domain, box: PlotBox, nowX: number): ConeGeometry {
  if (cone.levels.length === 0) return { band90: "", band50: "", marks: [] };
  const maxDays = cone.levels[cone.levels.length - 1]!.days;
  return {
    band90: bandPath(cone, "p05", "p95", domain, box, nowX),
    band50: bandPath(cone, "p25", "p75", domain, box, nowX),
    marks: cone.levels.map((l) => ({
      x: horizonX(l.days, maxDays, nowX, box.right),
      days: l.days,
    })),
  };
}

// ---- Chart patterns: points, lines, break level and target over the visible history ----

export interface DatedPrice {
  date: string;
  price: number;
}

export interface PatternShape {
  /** Unique within the chart. */
  id: string;
  startDate: string;
  confirmationDate: string;
  breakLevel: number;
  target: number | null;
  points: readonly DatedPrice[];
  lines: readonly { start: DatedPrice; end: DatedPrice }[];
  /**
   * Set for a shape still forming (R47 P6): the closes that would confirm it, drawn from its
   * last key point to the latest close. It has no break mark and no measured move.
   */
  forming?: { above: number | null; below: number | null };
}

/** Index of the first bar on or after `date`; the last bar when `date` is later than every bar. */
export function dateIndex(bars: readonly ChartBar[], date: string): number {
  let lo = 0;
  let hi = bars.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (bars[mid]!.date < date) lo = mid + 1;
    else hi = mid;
  }
  return Math.min(lo, Math.max(0, bars.length - 1));
}

/** A pattern is drawn only when all of it falls inside the visible history. */
export function patternInView(shape: PatternShape, bars: readonly ChartBar[]): boolean {
  const first = bars[0];
  const last = bars[bars.length - 1];
  return !!first && !!last && shape.startDate >= first.date && shape.confirmationDate <= last.date;
}

/** Every price a pattern reaches (points, lines, break level, target), for the y domain. */
export function patternValues(shape: PatternShape): number[] {
  return [
    ...shape.points.map((p) => p.price),
    ...shape.lines.flatMap((l) => [l.start.price, l.end.price]),
    ...(shape.forming ? [] : [shape.breakLevel]),
    ...(shape.target === null ? [] : [shape.target]),
    ...(shape.forming?.above != null ? [shape.forming.above] : []),
    ...(shape.forming?.below != null ? [shape.forming.below] : []),
  ];
}

/** The confirming levels of a forming shape (none for a confirmed one). */
export function formingLevels(shape: PatternShape): { price: number; side: "above" | "below" }[] {
  const f = shape.forming;
  if (!f) return [];
  return [
    ...(f.above !== null ? [{ price: f.above, side: "above" as const }] : []),
    ...(f.below !== null ? [{ price: f.below, side: "below" as const }] : []),
  ];
}

export interface PatternGeometry {
  points: { x: number; y: number }[];
  /** The key points joined in order. */
  outline: string;
  lines: { x1: number; y1: number; x2: number; y2: number }[];
  /** Where the confirming close broke the pattern, at the break level. */
  breakMark: { x: number; y: number };
  /** Horizontal measured-move target across the pattern's width; null when there is none. */
  targetLine: { x1: number; x2: number; y: number } | null;
  /** Forming shapes: the confirming levels, from the last key point to the latest close. */
  levels: { x1: number; x2: number; y: number; side: "above" | "below" }[];
}

/** Pixel geometry of one pattern over `bars` drawn between `box.left` and `nowX`. */
export function patternGeometry(
  shape: PatternShape,
  bars: readonly ChartBar[],
  domain: Domain,
  box: PlotBox,
  nowX: number,
): PatternGeometry {
  const x = (date: string): number => scaleX(dateIndex(bars, date), bars.length, box.left, nowX);
  const y = (price: number): number => scaleY(price, domain, box.top, box.bottom);
  const points = shape.points.map((p) => ({ x: x(p.date), y: y(p.price) }));
  const confirmX = x(shape.confirmationDate);
  return {
    points,
    outline: points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" "),
    lines: shape.lines.map((l) => ({
      x1: x(l.start.date),
      y1: y(l.start.price),
      x2: x(l.end.date),
      y2: y(l.end.price),
    })),
    breakMark: { x: confirmX, y: y(shape.breakLevel) },
    targetLine: shape.target === null ? null : { x1: x(shape.startDate), x2: confirmX, y: y(shape.target) },
    levels: formingLevels(shape).map((l) => ({
      x1: points[points.length - 1]?.x ?? box.left,
      x2: nowX,
      y: y(l.price),
      side: l.side,
    })),
  };
}
