/** Pure shaping of stored metrics for the Financials › Metrics table. */

import type { FinancialMetric } from "../types";

/** Display order inside a fiscal year: growth, margins, returns, leverage, liquidity, cash flow, per share. */
export const METRIC_ORDER: readonly string[] = [
  "revenue_growth_yoy",
  "net_income_growth_yoy",
  "eps_growth_yoy",
  "gross_margin",
  "operating_margin",
  "net_margin",
  "roe",
  "roa",
  "debt_to_equity",
  "debt_to_assets",
  "current_ratio",
  "quick_ratio",
  "operating_cash_flow_margin",
  "free_cash_flow",
  "free_cash_flow_margin",
  "eps",
  "book_value_per_share",
];

export type MetricValueKind = "pct" | "ratio" | "perShare" | "currency" | "plain";

/** How to format a metric value, from the backend `unit` ("%" values are percentage points, not fractions). */
export function metricValueKind(unit: string): MetricValueKind {
  switch (unit) {
    case "%":
      return "pct";
    case "ratio":
      return "ratio";
    case "currency per share":
      return "perShare";
    case "currency":
      return "currency";
    default:
      return "plain";
  }
}

export interface MetricYear {
  /** Fiscal year, or null for rows from before periods were attached. */
  fiscalYear: number | null;
  periodType: string | null;
  periodEnd: string | null;
  rows: FinancialMetric[];
}

function orderIndex(code: string): number {
  const i = METRIC_ORDER.indexOf(code);
  return i === -1 ? METRIC_ORDER.length : i;
}

/** Metrics grouped by fiscal year, newest year first; rows in display order. */
export function groupByFiscalYear(metrics: readonly FinancialMetric[]): MetricYear[] {
  const groups = new Map<string, MetricYear>();
  for (const m of metrics) {
    const key = m.fiscal_year === null || m.fiscal_year === undefined ? "none" : `${m.fiscal_year}:${m.period_type ?? ""}`;
    let group = groups.get(key);
    if (!group) {
      group = {
        fiscalYear: m.fiscal_year ?? null,
        periodType: m.period_type ?? null,
        periodEnd: m.period_end ?? null,
        rows: [],
      };
      groups.set(key, group);
    }
    group.rows.push(m);
  }
  const out = [...groups.values()];
  for (const g of out) g.rows.sort((a, b) => orderIndex(a.metric_code) - orderIndex(b.metric_code));
  return out.sort((a, b) => (b.fiscalYear ?? -Infinity) - (a.fiscalYear ?? -Infinity));
}
