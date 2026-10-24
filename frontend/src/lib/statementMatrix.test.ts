import { describe, expect, it } from "vitest";
import type { PeriodStatements, StatementLineRead } from "../types";
import { allAnnual, anyVendor, buildMatrix, lineUnit, periodSource, sortPeriods, unitForCode } from "./statementMatrix";

function line(code: string, value: string | null, tier: "filing" | "vendor" | null, url: string | null = null): StatementLineRead {
  return {
    ontology_code: code, label_en: code, label_ar: "", value, status: value === null ? "INSUFFICIENT_DATA" : "AVAILABLE",
    currency: "EGP", source_label_reported: null, source_page: null, published_date: null, document_url: url,
    source_tier: tier, provisional: tier === "vendor",
  };
}

function period(year: number, type: string, income: StatementLineRead[], balance: StatementLineRead[] = []): PeriodStatements {
  return { period_id: `${year}-${type}`, fiscal_year: year, period_type: type, published_date: null, income, balance, cash_flow: [] };
}

const p2024 = period(2024, "ANNUAL", [line("revenue", "100", "vendor"), line("net_income", null, null)]);
const p2025 = period(2025, "ANNUAL", [line("revenue", "120", "vendor"), line("net_income", "30", "vendor")]);
const p2023 = period(2023, "ANNUAL", [line("revenue", "90", "filing", "https://x/f.pdf")]);

describe("sortPeriods", () => {
  it("puts the newest year first", () => {
    expect(sortPeriods([p2023, p2025, p2024]).map((p) => p.fiscal_year)).toEqual([2025, 2024, 2023]);
  });
  it("puts the full year before interim periods of the same year", () => {
    const q2 = period(2025, "Q2", []);
    expect(sortPeriods([q2, p2025]).map((p) => p.period_type)).toEqual(["ANNUAL", "Q2"]);
  });
});

describe("periodSource", () => {
  it("is vendor when any value comes from the vendor", () => {
    expect(periodSource(p2025).source).toBe("vendor");
  });
  it("is filing with its link for official lines", () => {
    expect(periodSource(p2023)).toEqual({ source: "filing", documentUrl: "https://x/f.pdf" });
  });
  it("is null when no line has a value", () => {
    expect(periodSource(period(2022, "ANNUAL", [line("revenue", null, null)])).source).toBeNull();
  });
});

describe("buildMatrix", () => {
  it("lines up rows by code across periods, newest column first", () => {
    const m = buildMatrix([p2023, p2024, p2025], "income");
    expect(m.columns.map((c) => c.fiscalYear)).toEqual([2025, 2024, 2023]);
    expect(m.rows.map((r) => r.code)).toEqual(["revenue", "net_income"]);
    expect(m.rows[1]?.cells.map((c) => c?.value ?? null)).toEqual(["30", null, null]);
  });
  it("keeps at most five periods", () => {
    const many = [2018, 2019, 2020, 2021, 2022, 2023].map((y) => period(y, "ANNUAL", [line("revenue", "1", "vendor")]));
    expect(buildMatrix(many, "income").columns).toHaveLength(5);
  });
  it("is empty for no periods", () => {
    expect(buildMatrix([], "income")).toEqual({ columns: [], rows: [] });
  });
});

describe("helpers", () => {
  it("reports annual-only and vendor presence", () => {
    expect(allAnnual(buildMatrix([p2025], "income").columns)).toBe(true);
    expect(allAnnual(buildMatrix([period(2025, "Q1", [])], "income").columns)).toBe(false);
    expect(anyVendor([p2023])).toBe(false);
    expect(anyVendor([p2023, p2025])).toBe(true);
  });
});

describe("lineUnit", () => {
  it("prefers the payload unit and otherwise reads the code", () => {
    expect(lineUnit({ unit: "shares", ontology_code: "revenue" })).toBe("shares");
    expect(lineUnit({ ontology_code: "eps" })).toBe("currency_per_share");
    expect(unitForCode("weighted_avg_shares_basic")).toBe("shares");
    expect(unitForCode("revenue")).toBe("currency");
  });
});
