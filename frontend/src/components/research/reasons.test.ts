import { describe, expect, it } from "vitest";
import { t } from "../../i18n/dict";
import { localizeReason } from "./reasons";

const en = (reason: string): string | null => localizeReason(reason, (key, params) => t(key, "en", params), "en");
const ar = (reason: string): string | null => localizeReason(reason, (key, params) => t(key, "ar", params), "ar");

describe("localizeReason: fair-value reasons (R46)", () => {
  it("localizes the implied-growth bound reasons with the bound from the text", () => {
    const over = "price is above the model value at 100% stage-1 growth: implied growth is over 100%";
    expect(en(over)).toBe(
      "The price is above the model value even at 100.0% stage-1 growth, so the implied growth is over 100.0%",
    );
    const under = "price is below the model value at -50% stage-1 growth: implied growth is under -50%";
    expect(en(under)).toContain("−50.0%");
    expect(ar(over)).toContain("100.0%");
  });
  it("localizes a missing price and a missing annual period", () => {
    expect(en("no positive current price to compare with")).toBe("There is no positive current price to compare with");
    expect(en("no approved annual period FY2023")).toBe("No approved annual statement for FY2023");
    expect(ar("no approved annual period FY2023")).toContain("2023");
  });
  it("localizes the cash-flow fallback reason", () => {
    expect(en("Free cash flow must be positive for FCFE valuation")).toBe("The average cash flow before financing is not positive");
    expect(ar("Free cash flow must be positive for FCFE valuation")).toContain("التدفق");
  });
  it("names the new statement lines instead of showing the code", () => {
    expect(en("missing statement line: net_borrowing (FY2024)")).toBe("Missing line: Net borrowing (FY2024)");
  });
  it("leaves unknown text to the caller", () => {
    expect(en("parent share undefined: net income incl. minorities is not positive (FY2023)")).toBeNull();
  });
});
