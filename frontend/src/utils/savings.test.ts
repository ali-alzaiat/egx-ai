import { describe, it, expect } from "vitest";
import { projectSavings } from "./savings";

describe("projectSavings", () => {
  it("compounds monthly", () => {
    const r = projectSavings(1000, 2, 12);
    expect(r).toHaveLength(2);
    expect(r[0]!.balance).toBeCloseTo(1000, 1);
  });
  it("zero rate", () => {
    const r = projectSavings(100, 3, 0);
    expect(r[2]!.balance).toBe(300);
  });
  it("single month", () => {
    const r = projectSavings(50, 1, 0);
    expect(r[0]!).toEqual({ month: 1, balance: 50 });
  });
});
