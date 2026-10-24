import { describe, expect, it } from "vitest";
import { t as translate } from "../../i18n";
import type { AlertRule } from "../../types";
import { buildParams, firedSummary, resolveScope, ruleSummary, snapshotEntries } from "./alertsFormat";
import { fmtDateTime } from "./dateTime";

type Key = Parameters<typeof translate>[0];
type Params = Parameters<typeof translate>[2];
const en = (key: Key, params?: Params): string => translate(key, "en", params);
const ar = (key: Key, params?: Params): string => translate(key, "ar", params);

const inputs = { threshold: "", direction: "above" as const, gapPct: "", thresholdPct: "" };

describe("buildParams", () => {
  it("requires a numeric price threshold and keeps the direction", () => {
    expect(buildParams("price", { ...inputs, threshold: "42.5", direction: "below" })).toEqual({
      ok: true,
      params: { threshold: 42.5, direction: "below" },
    });
    expect(buildParams("price", inputs)).toEqual({ ok: false, error: "al_err_price" });
  });

  it("rejects zero and negative percentages instead of defaulting them", () => {
    expect(buildParams("valuation_gap", { ...inputs, gapPct: "0" })).toEqual({ ok: false, error: "al_err_gap" });
    expect(buildParams("score_change", { ...inputs, thresholdPct: "-3" })).toEqual({ ok: false, error: "al_err_score" });
    expect(buildParams("score_change", { ...inputs, thresholdPct: "10" })).toEqual({
      ok: true,
      params: { threshold_pct: 10 },
    });
  });

  it("document rules carry no parameters", () => {
    expect(buildParams("document", inputs)).toEqual({ ok: true, params: {} });
  });
});

describe("resolveScope", () => {
  it("document rules always need a list", () => {
    expect(resolveScope("document", "universe", null, "")).toEqual({ ok: false, error: "al_err_document_list" });
    expect(resolveScope("document", "company", null, " L1 ")).toEqual({ ok: true, watchlistId: "L1" });
  });

  it("company scope needs a picked company; universe needs nothing", () => {
    expect(resolveScope("price", "company", null, "")).toEqual({ ok: false, error: "al_err_company" });
    expect(resolveScope("price", "company", { id: "C1" }, "")).toEqual({ ok: true, companyId: "C1" });
    expect(resolveScope("price", "universe", null, "")).toEqual({ ok: true });
  });
});

describe("summaries", () => {
  const rule = (family: string, params: Record<string, unknown>): AlertRule => ({
    id: "r",
    user_id: "u",
    watchlist_id: null,
    company_id: null,
    family,
    params,
    methodology_version: "1",
    enabled: true,
    created_at: "2026-10-01T00:00:00Z",
  });

  it("describes a price rule in words, in both languages", () => {
    expect(ruleSummary(rule("price", { threshold: 42.5, direction: "below" }), en, "en")).toBe("Crosses below 42.50");
    expect(ruleSummary(rule("price", { threshold: 42.5, direction: "below" }), ar, "ar-EG-u-nu-latn")).toContain("42.50");
  });

  it("shows a dash, never zero, when a snapshot number is missing", () => {
    const text = firedSummary("price", { direction: "above" }, en, "en");
    expect(text).toContain("—");
    expect(text).not.toContain("0.00");
  });

  it("does not print fact ids for document alerts", () => {
    const text = firedSummary("document", { fact_ids: ["aaaaaaaa-1111", "bbbbbbbb-2222"] }, en, "en");
    expect(text).toContain("2");
    expect(text).not.toContain("aaaaaaaa");
  });

  it("stringifies snapshot entries for the details fold", () => {
    expect(snapshotEntries({ a: null, b: 3, c: { x: 1 } })).toEqual([
      ["a", "—"],
      ["b", "3"],
      ["c", '{"x":1}'],
    ]);
  });
});

describe("fmtDateTime", () => {
  it("formats with Western digits in Arabic and rejects garbage", () => {
    expect(fmtDateTime("ar-EG-u-nu-latn", "2026-10-22T14:05:00Z")).toMatch(/14:05/);
    expect(fmtDateTime("ar-EG-u-nu-latn", "2026-10-22T14:05:00Z")).not.toMatch(/[٠-٩]/);
    expect(fmtDateTime("en", "nope")).toBeNull();
    expect(fmtDateTime("en", null)).toBeNull();
  });
});
