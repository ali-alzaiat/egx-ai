import { describe, expect, it } from "vitest";
import { crossCheckNameKey, crossCheckStatus, evidenceRows } from "./crosschecks";

describe("crossCheckStatus", () => {
  it("maps each status to a tone and a word key", () => {
    expect(crossCheckStatus("pass")).toEqual({ tone: "gain", key: "xc_status_pass" });
    expect(crossCheckStatus("warn")).toEqual({ tone: "warn", key: "xc_status_warn" });
    expect(crossCheckStatus("fail")).toEqual({ tone: "loss", key: "xc_status_fail" });
    expect(crossCheckStatus("insufficient_data")).toEqual({ tone: "muted", key: "xc_status_insufficient" });
  });

  it("never reads an unknown status as a pass", () => {
    expect(crossCheckStatus("great")).toEqual({ tone: "muted", key: "xc_status_insufficient" });
  });
});

describe("crossCheckNameKey", () => {
  it("names the five known checks and returns null for others", () => {
    expect(crossCheckNameKey("provenance")).toBe("xc_check_provenance");
    expect(crossCheckNameKey("cross_source")).toBe("xc_check_cross_source");
    expect(crossCheckNameKey("freshness")).toBe("xc_check_freshness");
    expect(crossCheckNameKey("new_check")).toBeNull();
  });
});

describe("evidenceRows", () => {
  it("flattens an object into key/value text", () => {
    expect(evidenceRows({ share: 0.75, period: "2026-Q2", ok: true, missing: null }, "provenance")).toEqual([
      { key: "share", value: "0.75" },
      { key: "period", value: "2026-Q2" },
      { key: "ok", value: "true" },
      { key: "missing", value: "—" },
    ]);
  });

  it("flattens nested objects and lists", () => {
    expect(evidenceRows({ periods: ["2026-Q1", "2026-Q2"], band: { low: 1, high: 5 } }, "x")).toEqual([
      { key: "periods", value: "2026-Q1, 2026-Q2" },
      { key: "band.low", value: "1" },
      { key: "band.high", value: "5" },
    ]);
  });

  it("returns nothing for empty evidence and treats markup as plain text", () => {
    expect(evidenceRows(null, "x")).toEqual([]);
    expect(evidenceRows(undefined, "x")).toEqual([]);
    expect(evidenceRows({ note: "<img src=x onerror=alert(1)>" }, "x")).toEqual([
      { key: "note", value: "<img src=x onerror=alert(1)>" },
    ]);
  });

  it("accepts a bare scalar and caps rows and value length", () => {
    expect(evidenceRows("just text", "x")).toEqual([{ key: "value", value: "just text" }]);
    const big = Object.fromEntries(Array.from({ length: 60 }, (_, i) => [`k${i}`, i]));
    expect(evidenceRows(big, "x")).toHaveLength(24);
    expect(evidenceRows({ long: "a".repeat(500) }, "x")[0]?.value).toHaveLength(201);
  });

  it("never shows vendor values for the cross-source check", () => {
    const rows = evidenceRows({ band: "1-5%", our_value: 100, vendor_value: 104, nested: { vendor_figure: 9 } }, "cross_source");
    expect(rows).toEqual([
      { key: "band", value: "1-5%" },
      { key: "our_value", value: "100" },
    ]);
    expect(evidenceRows({ vendor_only_lines: 3 }, "provenance")).toEqual([{ key: "vendor_only_lines", value: "3" }]);
  });
});
