/** Pure shaping of the statements bundle into a lines-by-periods matrix (spec 4.4.3). */

import type { PeriodStatements, StatementLineRead } from "../types";

export type StatementField = "income" | "balance" | "cash_flow";
export const STATEMENT_FIELDS: readonly StatementField[] = ["income", "balance", "cash_flow"];
export const MAX_PERIODS = 5;

export interface MatrixColumn {
  periodId: string;
  fiscalYear: number;
  periodType: string;
  /** Vendor if any line is vendor data; filing if the lines are official; null when no line has a value. */
  source: "vendor" | "filing" | null;
  /** First official filing link among the period's lines. */
  documentUrl: string | null;
}

export interface MatrixRow {
  code: string;
  labelEn: string;
  labelAr: string;
  /** One entry per column; null when the period has no such line. */
  cells: (StatementLineRead | null)[];
}

export interface Matrix {
  columns: MatrixColumn[];
  rows: MatrixRow[];
}

const PERIOD_ORDER: Record<string, number> = { ANNUAL: 0, Q4: 1, Q3: 2, Q2: 3, Q1: 4, SEMI_ANNUAL: 5, INTERIM: 6 };

/** Newest first: fiscal year descending, then the longer period before the shorter one. */
export function sortPeriods(periods: readonly PeriodStatements[]): PeriodStatements[] {
  return [...periods].sort(
    (a, b) => b.fiscal_year - a.fiscal_year || (PERIOD_ORDER[a.period_type] ?? 9) - (PERIOD_ORDER[b.period_type] ?? 9),
  );
}

function allLines(p: PeriodStatements): StatementLineRead[] {
  return [...p.income, ...p.balance, ...p.cash_flow];
}

export function periodSource(p: PeriodStatements): Pick<MatrixColumn, "source" | "documentUrl"> {
  const withValue = allLines(p).filter((l) => l.value !== null);
  if (withValue.some((l) => l.source_tier === "vendor")) return { source: "vendor", documentUrl: null };
  const filing = withValue.filter((l) => l.source_tier === "filing");
  if (filing.length === 0) return { source: null, documentUrl: null };
  return { source: "filing", documentUrl: filing.find((l) => l.document_url)?.document_url ?? null };
}

export function buildMatrix(periods: readonly PeriodStatements[], field: StatementField, max = MAX_PERIODS): Matrix {
  const chosen = sortPeriods(periods).slice(0, max);
  const columns: MatrixColumn[] = chosen.map((p) => ({
    periodId: p.period_id,
    fiscalYear: p.fiscal_year,
    periodType: p.period_type,
    ...periodSource(p),
  }));

  const order: string[] = [];
  const meta = new Map<string, { labelEn: string; labelAr: string }>();
  for (const p of chosen) {
    for (const line of p[field]) {
      if (!meta.has(line.ontology_code)) {
        order.push(line.ontology_code);
        meta.set(line.ontology_code, { labelEn: line.label_en, labelAr: line.label_ar });
      }
    }
  }
  const rows: MatrixRow[] = order.map((code) => ({
    code,
    labelEn: meta.get(code)?.labelEn ?? code,
    labelAr: meta.get(code)?.labelAr ?? "",
    cells: chosen.map((p) => p[field].find((l) => l.ontology_code === code) ?? null),
  }));
  return { columns, rows };
}

/** True when every column is a full-year period (the meta line then says "Annual"). */
export function allAnnual(columns: readonly MatrixColumn[]): boolean {
  return columns.length > 0 && columns.every((c) => c.periodType === "ANNUAL");
}

/** True when any period of the bundle carries vendor data. */
export function anyVendor(periods: readonly PeriodStatements[]): boolean {
  return periods.some((p) => periodSource(p).source === "vendor");
}

export type LineUnit = NonNullable<StatementLineRead["unit"]>;

/** Unit of an ontology line when the payload does not say (payloads before R43 lack `unit`). */
export function unitForCode(code: string): LineUnit {
  if (code === "eps") return "currency_per_share";
  if (code === "shares_outstanding" || code === "weighted_avg_shares_basic") return "shares";
  return "currency";
}

export function lineUnit(line: Pick<StatementLineRead, "unit" | "ontology_code">): LineUnit {
  return line.unit ?? unitForCode(line.ontology_code);
}
