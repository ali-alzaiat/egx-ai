import { describe, expect, it } from "vitest";
import type { FairValueInputs } from "../types";
import { scalarInput, scalarInputEntries } from "./fairValue";

const inputs: FairValueInputs = {
  discount_rate: "0.2833",
  growth_rate: null,
  affo: "",
  fcfe_base: { method: "m", years_required: 3, status: "AVAILABLE", reason: null, mean: "1", years: [] },
};

describe("scalarInput", () => {
  it("returns decimal strings and nothing else", () => {
    expect(scalarInput(inputs, "discount_rate")).toBe("0.2833");
    expect(scalarInput(inputs, "growth_rate")).toBeNull();
    expect(scalarInput(inputs, "affo")).toBeNull();
    expect(scalarInput(inputs, "missing")).toBeNull();
    expect(scalarInput(inputs, "fcfe_base")).toBeNull();
  });
});

describe("scalarInputEntries", () => {
  it("keeps only inputs with a value and drops the structured FCFE base", () => {
    expect(scalarInputEntries(inputs)).toEqual([["discount_rate", "0.2833"]]);
  });
});
