import { describe, expect, it } from "vitest";
import { t } from "../../i18n";
import { describeError, statusOf } from "./apiError";

const en = (key: Parameters<typeof t>[0]): string => t(key, "en");

describe("apiError", () => {
  it("reads the status out of the client's error message", () => {
    expect(statusOf(new Error("API error: 422"))).toBe(422);
    expect(statusOf(new Error("boom"))).toBeNull();
    expect(statusOf("API error: 422")).toBeNull();
  });

  it("maps known statuses to localized sentences without leaking the code", () => {
    const view = describeError(new Error("API error: 409"), en, "err_generic");
    expect(view.text).toBe(t("err_conflict", "en"));
    expect(view.detail).toBeNull();
    expect(describeError(new Error("API error: 503"), en, "err_generic").text).toBe(t("err_server", "en"));
  });

  it("uses the fallback for unmapped statuses", () => {
    expect(describeError(new Error("API error: 418"), en, "err_generic").text).toBe(t("err_generic", "en"));
  });

  it("keeps a server detail separate from the headline", () => {
    const view = describeError(new Error("Every value needs a page"), en, "err_generic");
    expect(view.text).toBe(t("err_generic", "en"));
    expect(view.detail).toBe("Every value needs a page");
  });

  it("handles non-Error throws", () => {
    expect(describeError(undefined, en, "err_generic")).toEqual({ text: t("err_generic", "en"), detail: null });
  });
});
