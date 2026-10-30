import { describe, expect, it } from "vitest";
import type { ChartPattern, ConeCalibrationHorizon, FormingChartPattern, PatternsResponse, VolatilityConeResponse } from "../types";
import { calibrationAvailable, coneShape, formingId, formingShape, horizonLabel, patternId, patternShape, patternStats } from "./priceOverlays";
import { formingLevels, patternValues } from "./priceChart";

const calibration: ConeCalibrationHorizon = {
  days: 21,
  status: "AVAILABLE",
  reason: null,
  n_cases: 214,
  first_case: "2022-04-19",
  last_case: "2026-09-23",
  inside_50: 0.5794,
  inside_50_low: 0.5125,
  inside_50_high: 0.6436,
  inside_90: 0.8551,
  inside_90_low: 0.8017,
  inside_90_high: 0.896,
};

const cone: VolatilityConeResponse = {
  company_id: "c",
  version: "volatility-cone-1.0",
  status: "AVAILABLE",
  reason: null,
  as_of: "2026-10-29",
  last_close: "120.4700",
  sigma_daily: 0.019,
  sigma_annual: 0.3,
  n_returns: 252,
  window_start: "2025-10-16",
  horizons: [
    { days: 63, approx_date: "2027-01-26", p05: "93.6892", p25: "108.6689", p50: "120.4700", p75: "133.5527", p95: "154.9060" },
    { days: 21, approx_date: "2026-11-29", p05: "104.1930", p25: "113.5086", p50: "120.4700", p75: "127.8583", p95: "139.2898" },
  ],
  z_50: 0.6745,
  z_90: 1.6449,
  drift: "zero",
  calendar_note: "",
  note: "range of typical moves if past volatility continues, not a prediction",
  calibration: {
    version: "",
    cone_version: "",
    status: "AVAILABLE",
    reason: null,
    n_closes: 1211,
    horizons: [calibration],
    step_sessions: 5,
    min_cases: 30,
    nominal_50: 0.5,
    nominal_90: 0.9,
    interval: "Wilson 95%",
    note: "",
  },
};

const pattern: ChartPattern = {
  pattern: "double_bottom",
  stats_key: "double_bottom",
  direction: "up",
  start_date: "2026-06-08",
  end_date: "2026-06-29",
  known_date: "2026-07-07",
  confirmation_date: "2026-07-07",
  confirmation_close: "137.1800",
  break_level: "136.7000",
  points: [{ label: "trough_1", date: "2026-06-08", price: "130.1000" }],
  lines: [
    {
      label: "neckline",
      start: { label: "neckline", date: "2026-06-21", price: "136.7000" },
      end: { label: "neckline", date: "2026-07-07", price: "136.7000" },
    },
  ],
  target: { price: "144.9050", label: "measured move" },
};

describe("coneShape", () => {
  it("reads the strings as numbers and orders horizons by length", () => {
    const shape = coneShape(cone);
    expect(shape?.lastClose).toBe(120.47);
    expect(shape?.levels.map((l) => l.days)).toEqual([21, 63]);
    expect(shape?.levels[0]).toMatchObject({ p05: 104.193, p25: 113.5086, p75: 127.8583, p95: 139.2898 });
  });
  it("is null when the answer is missing, insufficient or has an unusable price", () => {
    expect(coneShape(undefined)).toBeNull();
    expect(coneShape({ ...cone, status: "INSUFFICIENT_DATA", reason: "no stored prices", horizons: [] })).toBeNull();
    expect(coneShape({ ...cone, last_close: null })).toBeNull();
    expect(coneShape({ ...cone, horizons: [] })).toBeNull();
    expect(coneShape({ ...cone, horizons: [{ ...cone.horizons[0]!, p95: "" }] })).toBeNull();
  });
});

describe("patternShape", () => {
  it("converts a confirmed pattern and gives it a stable id", () => {
    const shape = patternShape(pattern);
    expect(shape?.id).toBe(patternId(pattern));
    expect(shape?.id).toBe("double_bottom:2026-06-08:2026-07-07");
    expect(shape).toMatchObject({ breakLevel: 136.7, target: 144.905, startDate: "2026-06-08", confirmationDate: "2026-07-07" });
    expect(shape?.points).toEqual([{ date: "2026-06-08", price: 130.1 }]);
    expect(shape?.lines).toHaveLength(1);
  });
  it("keeps a pattern without a target and drops one with an unusable price", () => {
    expect(patternShape({ ...pattern, target: null })?.target).toBeNull();
    expect(patternShape({ ...pattern, break_level: "n/a" })).toBeNull();
    expect(patternShape({ ...pattern, points: [{ label: "x", date: "2026-06-08", price: "" }] })).toBeNull();
  });
});

describe("patternStats", () => {
  const res = {
    stats: {
      double_bottom: {
        "20": { status: "INSUFFICIENT_DATA", value: null, reason: "too few cases (4)", n: 4, n_companies: 3 },
      },
    },
  } as unknown as PatternsResponse;
  it("reads a horizon's cell, or nothing when the payload has none", () => {
    expect(patternStats(res, "double_bottom", "20")?.status).toBe("INSUFFICIENT_DATA");
    expect(patternStats(res, "double_bottom", "60")).toBeUndefined();
    expect(patternStats(res, "head_and_shoulders_top", "20")).toBeUndefined();
  });
});

describe("calibrationAvailable", () => {
  it("is true only when the shares are measured", () => {
    expect(calibrationAvailable(calibration)).toBe(true);
    expect(
      calibrationAvailable({ ...calibration, status: "INSUFFICIENT_DATA", reason: "needs at least 30 back-tested cases, have 4" }),
    ).toBe(false);
    expect(calibrationAvailable({ ...calibration, inside_90_high: null })).toBe(false);
  });
});

describe("horizonLabel", () => {
  const t = (key: string, params?: Record<string, string | number>): string => `${key}${params ? JSON.stringify(params) : ""}`;
  it("names the three standard horizons and falls back to sessions", () => {
    expect(horizonLabel(t as never, 21)).toBe("pxf_horizon_1M");
    expect(horizonLabel(t as never, 63)).toBe("pxf_horizon_3M");
    expect(horizonLabel(t as never, 126)).toBe("pxf_horizon_6M");
    expect(horizonLabel(t as never, 40)).toBe('pxf_horizon_days{"n":40}');
  });
  it("has a compact form for the chart axis", () => {
    expect(horizonLabel(t as never, 21, true)).toBe("pxf_axis_1M");
    expect(horizonLabel(t as never, 126, true)).toBe("pxf_axis_6M");
  });
});

const forming: FormingChartPattern = {
  pattern: "head_and_shoulders_top",
  expected: "down",
  start_date: "2026-08-03",
  end_date: "2026-10-12",
  known_date: "2026-10-19",
  sessions_left: 12,
  confirm_above: null,
  confirm_below: "90.0000",
  invalid_above: "115.0000",
  invalid_below: null,
  points: [
    { label: "left_shoulder", date: "2026-08-03", price: "100.0000" },
    { label: "head", date: "2026-09-07", price: "115.0000" },
    { label: "right_shoulder", date: "2026-10-12", price: "100.0000" },
  ],
  lines: [
    {
      label: "neckline",
      start: { label: "neckline", date: "2026-08-20", price: "90.0000" },
      end: { label: "neckline", date: "2026-10-29", price: "90.0000" },
    },
  ],
};

describe("formingShape", () => {
  it("draws to the latest close with its confirming level and no break mark or target", () => {
    const shape = formingShape(forming);
    expect(shape).not.toBeNull();
    expect(shape?.id).toBe(formingId(forming));
    expect(shape?.confirmationDate).toBe("2026-10-29");
    expect(shape?.target).toBeNull();
    expect(shape?.forming).toEqual({ above: null, below: 90 });
    expect(shape && formingLevels(shape)).toEqual([{ price: 90, side: "below" }]);
    expect(shape && patternValues(shape)).toContain(90);
  });

  it("keeps both levels of a symmetrical triangle and drops a shape with an unusable price", () => {
    const sym = formingShape({ ...forming, pattern: "symmetrical_triangle", expected: null, confirm_above: "104.0000", invalid_above: null });
    expect(sym && formingLevels(sym)).toEqual([
      { price: 104, side: "above" },
      { price: 90, side: "below" },
    ]);
    expect(formingShape({ ...forming, confirm_below: "n/a" })).toBeNull();
  });
});
