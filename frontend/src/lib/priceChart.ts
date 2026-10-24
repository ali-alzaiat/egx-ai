/** Pure geometry for the PriceChart (no DOM): ranges, scales, ticks, nearest point. */

export interface ChartBar {
  /** ISO date, "2026-10-22". */
  date: string;
  close: number;
}

export type ChartRange = "3M" | "6M" | "1Y";

const RANGE_MONTHS: Record<ChartRange, number> = { "3M": 3, "6M": 6, "1Y": 12 };

/** First day included in `range`, counted back from the last bar (UTC, so no day shifts). */
export function rangeStart(lastDate: string, range: ChartRange): string {
  const d = new Date(`${lastDate}T00:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() - RANGE_MONTHS[range]);
  return d.toISOString().slice(0, 10);
}

/** Ascending bars within `range` of the newest bar. */
export function sliceRange(bars: readonly ChartBar[], range: ChartRange): ChartBar[] {
  const last = bars[bars.length - 1];
  if (!last) return [];
  const start = rangeStart(last.date, range);
  return bars.filter((b) => b.date >= start);
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

/** Index of the first bar of each calendar month, thinned so labels keep `minGap` px apart. */
export function monthTicks(
  bars: readonly ChartBar[],
  left: number,
  right: number,
  minGap: number,
): { index: number; date: string }[] {
  const ticks: { index: number; date: string }[] = [];
  let lastMonth = "";
  let lastX = -Infinity;
  bars.forEach((b, i) => {
    const month = b.date.slice(0, 7);
    if (month === lastMonth) return;
    lastMonth = month;
    const x = scaleX(i, bars.length, left, right);
    if (x - lastX >= minGap) {
      ticks.push({ index: i, date: b.date });
      lastX = x;
    }
  });
  return ticks;
}

/** Index of the bar closest to pixel `x`. */
export function nearestIndex(x: number, count: number, left: number, right: number): number {
  if (count <= 1) return 0;
  const ratio = (x - left) / (right - left);
  return Math.min(count - 1, Math.max(0, Math.round(ratio * (count - 1))));
}
