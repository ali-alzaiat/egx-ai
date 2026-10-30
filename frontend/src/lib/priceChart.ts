/**
 * Pure logic for the PriceChart (no DOM, no chart library): ranges, point mapping for the line and
 * candle series, future trading dates for the volatility cone, the cone and pattern shapes in
 * (date, price) space, and time-axis labels. The chart component turns these into pixels.
 */

export interface ChartBar {
  /** ISO date, "2026-10-22". */
  date: string;
  close: number;
  /** Open, high and low are present when the price API returned usable values (candles need all three). */
  open?: number;
  high?: number;
  low?: number;
}

/** Line-chart ranges. "1D" is not one: the Day view is a last-session summary, not a line. */
export type ChartRange = "1W" | "1M" | "3M" | "6M" | "YTD" | "1Y" | "5Y";

/** The ranges the company overview offers, left to right. */
export type OverviewRange = "1D" | "1W" | "1M" | "YTD" | "1Y" | "5Y";
export const OVERVIEW_RANGES: readonly OverviewRange[] = ["1D", "1W", "1M", "YTD", "1Y", "5Y"];

/** How the price history is drawn: a close line (default) or candlesticks from open/high/low/close. */
export type ChartMode = "line" | "candles";
export const CHART_MODES: readonly ChartMode[] = ["line", "candles"];

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

// ---- Series data: one point per bar, the time being the ISO date (a lightweight-charts business day) ----

export interface LinePoint {
  time: string;
  value: number;
}

export interface CandlePoint {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

/** The close line, one point per bar. */
export function lineData(bars: readonly ChartBar[]): LinePoint[] {
  return bars.map((b) => ({ time: b.date, value: b.close }));
}

/** A bar can be drawn as a candle only when open, high and low are present and consistent with the close. */
export function isCandle(bar: ChartBar): bar is ChartBar & { open: number; high: number; low: number } {
  const { open, high, low, close } = bar;
  if (open === undefined || high === undefined || low === undefined) return false;
  if (![open, high, low, close].every(Number.isFinite)) return false;
  return high >= Math.max(open, close) && low <= Math.min(open, close);
}

/** Candles for the bars that have usable open/high/low/close; a bar without them is left out, never filled in. */
export function candleData(bars: readonly ChartBar[]): CandlePoint[] {
  const out: CandlePoint[] = [];
  for (const b of bars) {
    if (isCandle(b)) out.push({ time: b.date, open: b.open, high: b.high, low: b.low, close: b.close });
  }
  return out;
}

// ---- Trading calendar: future dates for the cone ----

/** Friday and Saturday as `Date.getUTCDay()` values; the EGX trades Sunday to Thursday. */
const EGX_WEEKEND = new Set([5, 6]);

/**
 * The date `days` trading days after `isoDate`, skipping Friday and Saturday only (the backend's
 * `add_trading_days`: Egyptian public holidays are not in the calendar, so the date is approximate).
 */
export function addTradingDays(isoDate: string, days: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  let left = Math.max(0, Math.floor(days));
  while (left > 0) {
    d.setUTCDate(d.getUTCDate() + 1);
    if (!EGX_WEEKEND.has(d.getUTCDay())) left -= 1;
  }
  return d.toISOString().slice(0, 10);
}

/** The next `count` trading dates after `lastDate`, ascending: the empty time-axis slots the cone sits on. */
export function futureTradingDates(lastDate: string, count: number): string[] {
  const out: string[] = [];
  let current = lastDate;
  for (let i = 0; i < count; i++) {
    current = addTradingDays(current, 1);
    out.push(current);
  }
  return out;
}

// ---- Time-axis labels ----

export type TickUnit = "day" | "month" | "year";

/** A lightweight-charts time: ISO string, UTC seconds, or a business-day object. */
export type TimeLike = string | number | { year: number; month: number; day: number };

/** ISO date ("2026-10-22") of a chart time; null for a value that is not a date. */
export function timeToIso(time: TimeLike): string | null {
  if (typeof time === "string") return time;
  if (typeof time === "number") return Number.isFinite(time) ? new Date(time * 1000).toISOString().slice(0, 10) : null;
  const { year, month, day } = time;
  if (![year, month, day].every(Number.isFinite)) return null;
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

/** lightweight-charts `TickMarkType` values: 0 starts a year, 1 a month, anything else is a day. */
export function tickUnitFor(tickMarkType: number): TickUnit {
  if (tickMarkType === 0) return "year";
  return tickMarkType === 1 ? "month" : "day";
}

const TICK_FORMAT: Record<TickUnit, Intl.DateTimeFormatOptions> = {
  day: { day: "numeric", month: "short", timeZone: "UTC" },
  month: { month: "short", timeZone: "UTC" },
  year: { year: "numeric", timeZone: "UTC" },
};

const tickFormatters = new Map<string, Intl.DateTimeFormat>();

/** Axis label of a date: "22 Oct" (day), "Oct" (month), "2026" (year); Latin digits in Arabic. */
export function tickLabel(locale: string, iso: string, unit: TickUnit): string {
  const key = `${locale}|${unit}`;
  let fmt = tickFormatters.get(key);
  if (!fmt) {
    fmt = new Intl.DateTimeFormat(locale === "en" ? "en-GB" : locale, TICK_FORMAT[unit]);
    tickFormatters.set(key, fmt);
  }
  return fmt.format(new Date(`${iso}T00:00:00Z`));
}

// ---- Prices ----

/** Lowest and highest of the finite values, or null when there are none. */
export function priceExtent(values: readonly number[]): { min: number; max: number } | null {
  let min = Infinity;
  let max = -Infinity;
  for (const v of values) {
    if (!Number.isFinite(v)) continue;
    if (v < min) min = v;
    if (v > max) max = v;
  }
  return min <= max ? { min, max } : null;
}

// ---- Forecast cone: a range of typical moves on the trading days after the last close ----

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

/** Every price the cone reaches, for the price scale. */
export function coneValues(cone: ConeShape): number[] {
  return [cone.lastClose, ...cone.levels.flatMap((l) => [l.p05, l.p25, l.p75, l.p95])];
}

export interface DatedPrice {
  date: string;
  price: number;
}

export interface ConeOverlay {
  /** Every trading date from the day after the last bar to the longest horizon: the time axis is extended over them. */
  futureDates: string[];
  /** Each horizon on its trading date. */
  horizons: { days: number; date: string }[];
  /** Closed polygons: widen from the last close out to each horizon (straight segments between horizons). */
  band90: DatedPrice[];
  band50: DatedPrice[];
}

/** The cone on real dates after `lastDate` (the last bar); null when there are no horizons. */
export function coneOverlay(cone: ConeShape, lastDate: string): ConeOverlay | null {
  const levels = cone.levels.filter((l) => Number.isFinite(l.days) && l.days >= 1);
  const longest = levels[levels.length - 1];
  if (!longest) return null;
  const maxDays = Math.round(longest.days);
  const futureDates = futureTradingDates(lastDate, maxDays);
  const dateOf = (days: number): string => futureDates[Math.min(maxDays, Math.max(1, Math.round(days))) - 1]!;
  const start: DatedPrice = { date: lastDate, price: cone.lastClose };
  const band = (low: "p05" | "p25", high: "p75" | "p95"): DatedPrice[] => [
    start,
    ...levels.map((l) => ({ date: dateOf(l.days), price: l[high] })),
    ...[...levels].reverse().map((l) => ({ date: dateOf(l.days), price: l[low] })),
  ];
  return {
    futureDates,
    horizons: levels.map((l) => ({ days: l.days, date: dateOf(l.days) })),
    band90: band("p05", "p95"),
    band50: band("p25", "p75"),
  };
}

// ---- Chart patterns: points, lines, break level and target over the visible history ----

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

/** Every price a pattern reaches (points, lines, break level, target), for the price scale. */
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

export interface PatternOverlay {
  forming: boolean;
  /** The key points joined in order. */
  outline: DatedPrice[];
  points: DatedPrice[];
  lines: { start: DatedPrice; end: DatedPrice }[];
  /** Where the confirming close broke the pattern, at the break level; null for a forming shape. */
  breakMark: DatedPrice | null;
  /** Horizontal measured-move target across the pattern's width; null when there is none. */
  target: { startDate: string; endDate: string; price: number } | null;
  /** Forming shapes: the confirming levels, from the last key point to the latest close. */
  levels: { startDate: string; endDate: string; price: number; side: "above" | "below" }[];
}

/**
 * A pattern in (date, price) space over `bars`: every date is moved to the first bar on or after it,
 * so each point sits on a bar of the time axis.
 */
export function patternOverlay(shape: PatternShape, bars: readonly ChartBar[]): PatternOverlay {
  const snap = (date: string): string => bars[dateIndex(bars, date)]?.date ?? date;
  const at = (p: DatedPrice): DatedPrice => ({ date: snap(p.date), price: p.price });
  const points = shape.points.map(at);
  const confirmDate = snap(shape.confirmationDate);
  const lastDate = bars[bars.length - 1]?.date ?? confirmDate;
  const lastPoint = points[points.length - 1];
  return {
    forming: !!shape.forming,
    outline: points,
    points,
    lines: shape.lines.map((l) => ({ start: at(l.start), end: at(l.end) })),
    breakMark: shape.forming ? null : { date: confirmDate, price: shape.breakLevel },
    target: shape.target === null ? null : { startDate: snap(shape.startDate), endDate: confirmDate, price: shape.target },
    levels: formingLevels(shape).map((l) => ({
      startDate: lastPoint?.date ?? snap(shape.startDate),
      endDate: lastDate,
      price: l.price,
      side: l.side,
    })),
  };
}
