import { describe, expect, it } from "vitest";
import { t as translate } from "../../i18n";
import { EVENT_TYPES, EMPTY_FILTERS, eventTypeLabel, hasFilters, snapshotHighlights, toQueryParams } from "./eventFormat";

type Key = Parameters<typeof translate>[0];
type Params = Parameters<typeof translate>[2];
const en = (key: Key, params?: Params): string => translate(key, "en", params);
const ar = (key: Key, params?: Params): string => translate(key, "ar", params);

describe("event filters", () => {
  it("sends only the filters that are set", () => {
    expect(toQueryParams(EMPTY_FILTERS)).toEqual({});
    expect(toQueryParams({ ...EMPTY_FILTERS, symbol: "C1", date_from: "2026-01-01" })).toEqual({
      symbol: "C1",
      date_from: "2026-01-01",
    });
    expect(hasFilters(EMPTY_FILTERS)).toBe(false);
    expect(hasFilters({ ...EMPTY_FILTERS, type: "alert.fired" })).toBe(true);
  });
});

describe("event labels", () => {
  it("has an English and an Arabic label for every ledger type, never the raw code", () => {
    for (const type of EVENT_TYPES) {
      expect(eventTypeLabel(type, en)).not.toBe(type);
      expect(eventTypeLabel(type, ar)).not.toBe(eventTypeLabel(type, en));
    }
  });

  it("makes an unknown type readable", () => {
    expect(eventTypeLabel("price.crossed", en)).toBe("Price crossed");
  });
});

describe("snapshotHighlights", () => {
  it("counts fact ids instead of listing them", () => {
    const out = snapshotHighlights({ fact_ids: ["aaaaaaaa-1", "bbbbbbbb-2"], methodology_version: "1.2" }, en, "en");
    expect(out.join(" ")).not.toContain("aaaaaaaa");
    expect(out.some((line) => line.includes("2"))).toBe(true);
    expect(out.some((line) => line.includes("1.2"))).toBe(true);
  });

  it("returns nothing for an empty snapshot", () => {
    expect(snapshotHighlights({}, en, "en")).toEqual([]);
  });
});
