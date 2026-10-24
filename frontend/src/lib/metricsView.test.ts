import { describe, expect, it } from "vitest";
import type { FinancialMetric } from "../types";
import { groupByFiscalYear, metricValueKind } from "./metricsView";

function metric(code: string, fiscalYear: number | null, periodType: string | null = "ANNUAL"): FinancialMetric {
  return {
    id: `${code}-${fiscalYear}`, company_id: "c", period_id: `p${fiscalYear}`, metric_code: code, display_name: code,
    value: "1", unit: "%", status: "AVAILABLE", reason: null, warnings: null, formula_version: 1,
    calculated_at: "2026-10-23", created_at: "2026-10-23", fiscal_year: fiscalYear, period_type: periodType,
    period_end: fiscalYear === null ? null : `${fiscalYear}-12-31`, source_tier: "vendor", provisional: true,
    methodology_version: "metrics-stmt-1.0", inputs: [],
  };
}

describe("groupByFiscalYear", () => {
  it("groups by year, newest first, rows in display order", () => {
    const groups = groupByFiscalYear([
      metric("eps", 2024),
      metric("roe", 2025),
      metric("revenue_growth_yoy", 2025),
      metric("roa", 2024),
    ]);
    expect(groups.map((g) => g.fiscalYear)).toEqual([2025, 2024]);
    expect(groups[0]?.rows.map((r) => r.metric_code)).toEqual(["revenue_growth_yoy", "roe"]);
    expect(groups[1]?.rows.map((r) => r.metric_code)).toEqual(["roa", "eps"]);
    expect(groups[0]?.periodEnd).toBe("2025-12-31");
  });
  it("puts rows without a fiscal year last in one group", () => {
    const groups = groupByFiscalYear([metric("roe", null), metric("roe", 2025), metric("eps", null)]);
    expect(groups.map((g) => g.fiscalYear)).toEqual([2025, null]);
    expect(groups[1]?.rows).toHaveLength(2);
  });
  it("is empty for no metrics", () => {
    expect(groupByFiscalYear([])).toEqual([]);
  });
  it("sorts unknown metric codes after known ones", () => {
    const g = groupByFiscalYear([metric("zzz", 2025), metric("roe", 2025)]);
    expect(g[0]?.rows.map((r) => r.metric_code)).toEqual(["roe", "zzz"]);
  });
});

describe("metricValueKind", () => {
  it("reads the backend unit", () => {
    expect(metricValueKind("%")).toBe("pct");
    expect(metricValueKind("ratio")).toBe("ratio");
    expect(metricValueKind("currency per share")).toBe("perShare");
    expect(metricValueKind("currency")).toBe("currency");
    expect(metricValueKind("days")).toBe("plain");
  });
});
