import { describe, it, expect } from "vitest";
import { SHORT_COPY, t } from "./dict";

describe("i18n", () => {
  it("resolves all keys", () => {
    for (const key of Object.keys(SHORT_COPY)) {
      expect(t(key, "en")).toBeTruthy();
      expect(t(key, "ar")).toBeTruthy();
    }
  });
  it("throws on missing key", () => {
    expect(() => t("nope", "en")).toThrow();
  });
});
