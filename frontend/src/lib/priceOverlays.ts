import type { CopyKey, CopyParams } from "../i18n/dict";
import type {
  ChartPattern,
  ConeCalibrationHorizon,
  FormingChartPattern,
  PatternStats,
  PatternsResponse,
  VolatilityConeResponse,
} from "../types";
import { toNumber } from "./format";
import type { ConeLevel, ConeShape, DatedPrice, PatternShape } from "./priceChart";

/** The cone as numbers for the chart; null unless the answer is AVAILABLE and every price is usable. */
export function coneShape(cone: VolatilityConeResponse | undefined): ConeShape | null {
  if (!cone || cone.status !== "AVAILABLE") return null;
  const lastClose = toNumber(cone.last_close);
  if (lastClose === null) return null;
  const levels: ConeLevel[] = [];
  for (const h of cone.horizons) {
    const p05 = toNumber(h.p05);
    const p25 = toNumber(h.p25);
    const p75 = toNumber(h.p75);
    const p95 = toNumber(h.p95);
    if (p05 === null || p25 === null || p75 === null || p95 === null) return null;
    levels.push({ days: h.days, p05, p25, p75, p95 });
  }
  if (levels.length === 0) return null;
  levels.sort((a, b) => a.days - b.days);
  return { lastClose, levels };
}

/** Stable id of one occurrence (a pattern type can confirm more than once). */
export function patternId(p: ChartPattern): string {
  return `${p.stats_key}:${p.start_date}:${p.confirmation_date}`;
}

function datedPrice(p: { date: string; price: string }): DatedPrice | null {
  const price = toNumber(p.price);
  return price === null ? null : { date: p.date, price };
}

/** A pattern occurrence as numbers for the chart; null when any of its prices is unusable (it is then not drawn). */
export function patternShape(p: ChartPattern): PatternShape | null {
  const breakLevel = toNumber(p.break_level);
  if (breakLevel === null) return null;
  const points: DatedPrice[] = [];
  for (const pt of p.points) {
    const d = datedPrice(pt);
    if (!d) return null;
    points.push(d);
  }
  const lines: PatternShape["lines"][number][] = [];
  for (const ln of p.lines) {
    const start = datedPrice(ln.start);
    const end = datedPrice(ln.end);
    if (!start || !end) return null;
    lines.push({ start, end });
  }
  const target = p.target ? toNumber(p.target.price) : null;
  return {
    id: patternId(p),
    startDate: p.start_date,
    confirmationDate: p.confirmation_date,
    breakLevel,
    target,
    points,
    lines,
  };
}

/** Copy key naming each forming shape type (a symmetrical triangle has no break direction yet). */
export const FORMING_NAME_KEY: Record<string, CopyKey> = {
  head_and_shoulders_top: "pxf_pat_head_and_shoulders_top",
  head_and_shoulders_inverse: "pxf_pat_head_and_shoulders_inverse",
  double_top: "pxf_pat_double_top",
  double_bottom: "pxf_pat_double_bottom",
  ascending_triangle: "pxf_pat_ascending_triangle",
  descending_triangle: "pxf_pat_descending_triangle",
  symmetrical_triangle: "pxf_pat_symmetrical_triangle",
};

/** Stable id of a forming shape (one per pattern type at a time). */
export function formingId(f: FormingChartPattern): string {
  return `forming:${f.pattern}:${f.start_date}`;
}

/** A forming shape as numbers for the chart; null when any of its prices is unusable. */
export function formingShape(f: FormingChartPattern): PatternShape | null {
  const above = f.confirm_above === null ? null : toNumber(f.confirm_above);
  const below = f.confirm_below === null ? null : toNumber(f.confirm_below);
  if ((f.confirm_above !== null && above === null) || (f.confirm_below !== null && below === null)) return null;
  const points: DatedPrice[] = [];
  for (const pt of f.points) {
    const d = datedPrice(pt);
    if (!d) return null;
    points.push(d);
  }
  const lines: PatternShape["lines"][number][] = [];
  for (const ln of f.lines) {
    const start = datedPrice(ln.start);
    const end = datedPrice(ln.end);
    if (!start || !end) return null;
    lines.push({ start, end });
  }
  const level = above ?? below;
  const last = lines[0]?.end.date ?? points[points.length - 1]?.date;
  if (level === null || last === undefined) return null;
  return {
    id: formingId(f),
    startDate: f.start_date,
    // Drawn up to the latest close, so it is in view whenever its start is.
    confirmationDate: last,
    breakLevel: level,
    target: null,
    points,
    lines,
    forming: { above, below },
  };
}

/** Measured odds of a pattern type at 20 or 60 sessions; undefined when the payload has none. */
export function patternStats(res: PatternsResponse, statsKey: string, horizon: "20" | "60"): PatternStats | undefined {
  return res.stats[statsKey]?.[horizon];
}

/** Whether a calibration horizon holds measured shares (not INSUFFICIENT_DATA). */
export function calibrationAvailable(h: ConeCalibrationHorizon): h is ConeCalibrationHorizon & {
  inside_50: number;
  inside_50_low: number;
  inside_50_high: number;
  inside_90: number;
  inside_90_low: number;
  inside_90_high: number;
} {
  return (
    h.status === "AVAILABLE" &&
    h.inside_50 !== null &&
    h.inside_50_low !== null &&
    h.inside_50_high !== null &&
    h.inside_90 !== null &&
    h.inside_90_low !== null &&
    h.inside_90_high !== null
  );
}

/**
 * Label for a forecast horizon given in trading days (21 is about one month). `compact` is the
 * chart-axis form ("3M", Arabic "3 ش"); the full form names the period ("3 months").
 */
export function horizonLabel(t: (key: CopyKey, params?: CopyParams) => string, days: number, compact = false): string {
  if (days === 21) return compact ? t("pxf_axis_1M") : t("pxf_horizon_1M");
  if (days === 63) return compact ? t("pxf_axis_3M") : t("pxf_horizon_3M");
  if (days === 126) return compact ? t("pxf_axis_6M") : t("pxf_horizon_6M");
  return t("pxf_horizon_days", { n: days });
}
