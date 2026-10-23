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
  // Golden table: 1000 EGP/month × 12 months @ 12% annual (1%/month),
  // balance after the m-th deposit: 1000 × (1.01^m − 1) / 0.01.
  it("golden 1000/mo × 12 @ 12%", () => {
    const r = projectSavings(1000, 12, 12);
    const expected = [1000, 2010, 3030.1, 4060.4, 5101.01, 6152.02, 7213.54, 8285.67, 9368.53, 10462.21, 11566.83, 12682.5];
    expect(r.map((row) => row.month)).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]);
    expected.forEach((value, i) => {
      expect(r[i]!.balance).toBeCloseTo(value, 1);
    });
    // interest actually accrues: final balance above 12000 pure-deposit sum
    expect(r[r.length - 1]!.balance).toBeGreaterThan(12000);
  });
  it("balances grow monotonically", () => {
    const r = projectSavings(500, 6, 9);
    for (let i = 1; i < r.length; i++) {
      expect(r[i]!.balance).toBeGreaterThan(r[i - 1]!.balance);
    }
  });
});

