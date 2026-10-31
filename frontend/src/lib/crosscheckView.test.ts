import { describe, expect, it } from "vitest";
import { t as translate } from "../i18n/dict";
import type { CrossCheck } from "../types";
import { describeCheck } from "./crosscheckView";

const en = (key: Parameters<typeof translate>[0], params?: Parameters<typeof translate>[2]): string => translate(key, "en", params);
const ar = (key: Parameters<typeof translate>[0], params?: Parameters<typeof translate>[2]): string => translate(key, "ar", params);

function check(code: string, status: CrossCheck["status"], evidence: unknown): CrossCheck {
  return { code, status, detail: "BACKEND ENGLISH DETAIL", evidence };
}

function rowsOf(view: ReturnType<typeof describeCheck>): Record<string, string> {
  return Object.fromEntries((view?.rows ?? []).map((r) => [r.label, r.value]));
}

describe("describeCheck: provenance", () => {
  const evidence = { lines: 40, filing_backed: 0, vendor_only: 40, other: 0, filing_backed_share: "0.0000" };

  it("says in words that vendor-only figures are unconfirmed, with translated labels and a % share", () => {
    const view = describeCheck(check("provenance", "warn", evidence), "en", en);
    expect(view?.summary).toBe("None of the 40 approved statement lines is confirmed by a filing yet; the figures come from vendor files.");
    expect(rowsOf(view)).toEqual({
      "Lines checked": "40",
      "Backed by a filing": "0",
      "Vendor files only": "40",
      "No filing or vendor source": "0",
      "Filing-backed share": "0.0%",
    });
    expect(JSON.stringify(view)).not.toMatch(/vendor_only|filing_backed|0\.0000/);
  });

  it("reports a partial share", () => {
    const view = describeCheck(check("provenance", "pass", { lines: 10, filing_backed: 9, vendor_only: 1, other: 0, filing_backed_share: "0.9000" }), "en", en);
    expect(view?.summary).toBe("9 of 10 approved statement lines are backed by a filing (90.0%).");
  });

  it("says when nothing has a source", () => {
    const view = describeCheck(check("provenance", "fail", { lines: 3, filing_backed: 0, vendor_only: 0, other: 3, filing_backed_share: "0.0000" }), "en", en);
    expect(view?.summary).toContain("has a source: no filing and no vendor file");
  });

  it("is translated to Arabic with Western digits", () => {
    const view = describeCheck(check("provenance", "warn", evidence), "ar-EG-u-nu-latn", ar);
    expect(view?.summary).toContain("40");
    expect(view?.summary).toMatch(/[؀-ۿ]/);
    expect(view?.rows[0]).toEqual({ label: "الأسطر المفحوصة", value: "40" });
  });

  it("falls back (null) when the evidence is incomplete", () => {
    expect(describeCheck(check("provenance", "warn", { lines: 3 }), "en", en)).toBeNull();
  });
});

describe("describeCheck: price_sanity", () => {
  it("passes with empty lists shown as none", () => {
    const view = describeCheck(
      check("price_sanity", "pass", { closes_checked: 250, non_positive_closes: [], limit_breaches: [], possible_splits: [], gaps: [] }),
      "en",
      en,
    );
    expect(view?.summary).toBe("250 closes in the last year are positive, within the daily limit and without long gaps.");
    expect(rowsOf(view)).toMatchObject({
      "Closes checked": "250",
      "Non-positive closes": "None",
      "Moves beyond the daily limit": "None",
      "Possible splits": "None",
      "Gaps in the price history": "None",
    });
  });

  it("describes gaps, breaches and splits with localised dates", () => {
    const view = describeCheck(
      check("price_sanity", "fail", {
        closes_checked: 200,
        non_positive_closes: ["2026-03-02"],
        limit_breaches: [{ date: "2026-04-05", change: "0.2500" }],
        possible_splits: [{ date: "2026-05-05", change: "-0.5000" }],
        gaps: [{ from: "2026-01-05", to: "2026-01-20", missing_days: 8 }],
      }),
      "en",
      en,
    );
    expect(view?.summary).toBe(
      "Non-positive closes: 1. One-day moves beyond the daily limit without a split: 1. Gaps in the price history: 1. Possible splits noted: 1.",
    );
    const rows = rowsOf(view);
    expect(rows["Non-positive closes"]).toBe("2 Mar 2026");
    expect(rows["Moves beyond the daily limit"]).toBe("5 Apr 2026: 25.0%");
    expect(rows["Gaps in the price history"]).toBe("5 Jan 2026 to 20 Jan 2026: 8 trading days missing");
    expect(rows["Possible splits"]).toContain("5 May 2026");
  });

  it("falls back when a list is not a list", () => {
    expect(describeCheck(check("price_sanity", "pass", { closes_checked: 5, gaps: "x" }), "en", en)).toBeNull();
  });
});

describe("describeCheck: freshness", () => {
  it("renders dates and counts", () => {
    const view = describeCheck(
      check("freshness", "warn", {
        as_of: "2026-10-31",
        last_close: "2026-10-28",
        price_age_trading_days: 3,
        latest_period_end: "2026-03-31",
        quarters_behind: 2,
      }),
      "en",
      en,
    );
    expect(view?.summary).toBe("Last close on 28 Oct 2026; trading days since: 3. Latest reported period ended 31 Mar 2026; quarters behind: 2.");
    expect(rowsOf(view)).toMatchObject({ "Checked as of": "31 Oct 2026", "Quarters behind": "2", "Price age (trading days)": "3" });
  });

  it("says when there is no price or period", () => {
    const view = describeCheck(check("freshness", "insufficient_data", { as_of: "2026-10-31", last_close: null, latest_period_end: null }), "en", en);
    expect(view?.summary).toBe("No stored price. No reported period.");
    expect(rowsOf(view)).toMatchObject({ "Last close": "None", "Latest reported period ends": "None" });
  });
});

describe("describeCheck: cross_source", () => {
  it("shows bands and our value only", () => {
    const view = describeCheck(
      check("cross_source", "fail", {
        compared: 12,
        within_1_percent: 9,
        from_1_to_5_percent: 2,
        over_5_percent: 1,
        items: [{ period: "2025-12-31", ontology_code: "revenue", band: "over_5_percent", our_value: "1234567.50" }],
      }),
      "en",
      en,
    );
    expect(view?.summary).toBe("3 of 12 compared figures differ from the vendor files by 1% or more.");
    const rows = rowsOf(view);
    expect(rows["Within 1%"]).toBe("9");
    expect(rows["Differing figures"]).toBe("2025-12-31 · revenue: more than 5% apart (our value 1,234,567.5)");
    expect(JSON.stringify(view)).not.toMatch(/vendor_value|within_1_percent|over_5_percent/);
  });

  it("passes with no differing figures listed", () => {
    const view = describeCheck(
      check("cross_source", "pass", { compared: 4, within_1_percent: 4, from_1_to_5_percent: 0, over_5_percent: 0, items: [] }),
      "en",
      en,
    );
    expect(view?.summary).toBe("All 4 compared figures agree with the vendor files within 1%.");
    expect(rowsOf(view)["Differing figures"]).toBe("None");
  });
});

describe("describeCheck: accounting_identity", () => {
  it("translates the identity name and shows both sides when sent", () => {
    const view = describeCheck(
      check("accounting_identity", "warn", {
        evaluated: 8,
        off: 1,
        items: [
          {
            period: "2025-12-31",
            identity: "assets = liabilities + equity",
            relative_difference: "0.0100",
            left: "1000",
            right: "990",
          },
        ],
      }),
      "en",
      en,
    );
    expect(view?.summary).toBe("1 of 8 accounting identity checks are off by more than the tolerance.");
    expect(rowsOf(view)["Identities that are off"]).toBe(
      "2025-12-31 · Assets = liabilities + equity: off by 1.0% (left side 1,000, right side 990)",
    );
  });

  it("shows the difference alone when no sides are sent, and an unknown identity name as given", () => {
    const view = describeCheck(
      check("accounting_identity", "fail", {
        evaluated: 2,
        off: 1,
        items: [{ period: "2025-12-31", identity: "a = b", relative_difference: "0.0300" }],
      }),
      "en",
      en,
    );
    expect(rowsOf(view)["Identities that are off"]).toBe("2025-12-31 · a = b: off by 3.0%");
  });

  it("passes with none listed", () => {
    const view = describeCheck(check("accounting_identity", "pass", { evaluated: 5, off: 0, items: [] }), "en", en);
    expect(view?.summary).toBe("All 5 accounting identity checks hold within tolerance.");
    expect(rowsOf(view)["Identities that are off"]).toBe("None");
  });
});

describe("describeCheck: fallbacks", () => {
  it("returns null for an unknown code so the backend detail is used", () => {
    expect(describeCheck(check("brand_new", "pass", { a: 1 }), "en", en)).toBeNull();
  });

  it("explains an insufficient-data check with empty evidence in words", () => {
    expect(describeCheck(check("provenance", "insufficient_data", {}), "en", en)?.summary).toBe(
      "There are no approved statement lines for this company.",
    );
    expect(describeCheck(check("cross_source", "insufficient_data", {}), "en", en)?.summary).toContain("No period and line");
    expect(describeCheck(check("accounting_identity", "insufficient_data", {}), "en", en)?.rows).toEqual([]);
    expect(describeCheck(check("price_sanity", "insufficient_data", {}), "en", en)?.summary).toContain("fewer than two closes");
  });

  it("returns null for evidence that is not an object", () => {
    expect(describeCheck(check("provenance", "pass", null), "en", en)).toBeNull();
    expect(describeCheck(check("provenance", "pass", "x"), "en", en)).toBeNull();
    expect(describeCheck(check("provenance", "pass", [1]), "en", en)).toBeNull();
  });
});
