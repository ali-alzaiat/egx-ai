import { describe, it, expect } from "vitest";
import { sortRadarRows } from "./radarSort";

describe("sortRadarRows", () => {
  const numericRows = [
    { ticker: "COMI", score: 72.5 },
    { ticker: "HRHO", score: 61 },
    { ticker: "TMGH", score: 80 },
    { ticker: "CIRA", score: null },
  ];

  it("sorts numeric values ascending with blanks last", () => {
    const sorted = sortRadarRows(numericRows, "score", "asc");
    expect(sorted.map((r) => r.ticker)).toEqual(["HRHO", "COMI", "TMGH", "CIRA"]);
  });

  it("sorts numeric values descending with blanks still last", () => {
    const sorted = sortRadarRows(numericRows, "score", "desc");
    expect(sorted.map((r) => r.ticker)).toEqual(["TMGH", "COMI", "HRHO", "CIRA"]);
  });

  it("compares numeric strings by value, not by text", () => {
    const rows = [
      { ticker: "A", score: "9.5" },
      { ticker: "B", score: "10" },
      { ticker: "C", score: "2" },
    ];
    expect(sortRadarRows(rows, "score", "asc").map((r) => r.ticker)).toEqual([
      "C",
      "A",
      "B",
    ]);
    expect(sortRadarRows(rows, "score", "desc").map((r) => r.ticker)).toEqual([
      "B",
      "A",
      "C",
    ]);
  });

  it("treats empty strings as blanks that sort last", () => {
    const rows = [
      { ticker: "A", stance: "hold" },
      { ticker: "B", stance: null },
      { ticker: "C", stance: "buy" },
      { ticker: "D", stance: "" },
    ];
    const sorted = sortRadarRows(rows, "stance", "desc");
    expect(sorted.map((r) => r.ticker)).toEqual(["A", "C", "B", "D"]);
  });

  it("sorts string columns alphabetically for asc and desc", () => {
    const rows = [
      { ticker: "COMI", name: "Commercial International Bank" },
      { ticker: "HRHO", name: "EFG Holding" },
      { ticker: "TMGH", name: "Talaat Moustafa Group" },
    ];
    expect(sortRadarRows(rows, "name", "asc").map((r) => r.ticker)).toEqual([
      "COMI",
      "HRHO",
      "TMGH",
    ]);
    expect(sortRadarRows(rows, "name", "desc").map((r) => r.ticker)).toEqual([
      "TMGH",
      "HRHO",
      "COMI",
    ]);
  });

  it("defaults direction to ascending", () => {
    const rows = [
      { ticker: "B", score: 2 },
      { ticker: "A", score: 1 },
    ];
    expect(sortRadarRows(rows, "ticker").map((r) => r.ticker)).toEqual(["A", "B"]);
  });

  it("treats a missing key as a blank (sorts last)", () => {
    const rows = [{ ticker: "A" }, { ticker: "B" }];
    const sorted = sortRadarRows(rows, "score", "asc");
    expect(sorted.map((r) => r.ticker)).toEqual(["A", "B"]);
  });

  it("does not mutate the input array", () => {
    const rows = [
      { ticker: "B", score: 2 },
      { ticker: "A", score: 1 },
    ];
    const before = rows.map((r) => r.ticker);
    sortRadarRows(rows, "ticker", "asc");
    expect(rows.map((r) => r.ticker)).toEqual(before);
  });

  it("keeps an empty list empty", () => {
    expect(sortRadarRows([], "score", "desc")).toEqual([]);
  });
});
