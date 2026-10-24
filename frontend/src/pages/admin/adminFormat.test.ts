import { describe, expect, it } from "vitest";
import { t as translate } from "../../i18n";
import type { DisclosureFact, DisclosureFiling, ThesisCatalyst, ThesisInvalidation } from "../../types";
import {
  ACCOUNTING_BASES,
  CLASSIFICATION_KEY,
  FILING_TYPES,
  FILING_TYPE_KEY,
  LEDGER_CLASSIFICATIONS,
  addPeer,
  changedCatalysts,
  changedInvalidations,
  enumLabel,
  filingParseState,
  optionalFields,
  parseOutcome,
  peersChanged,
  removePeer,
  shortUrl,
} from "./adminFormat";

const filing = (over: Partial<DisclosureFiling>): DisclosureFiling => ({
  id: "f1",
  company_id: "c1",
  filing_url: "https://example.test/a.pdf",
  bulletin_id: null,
  report_date: "2026-06-30",
  filing_type: "Q",
  accounting_basis: "EAS",
  content_hash: null,
  byte_size: 10,
  storage_path: null,
  has_bytes: true,
  downloaded_at: "2026-07-01T00:00:00Z",
  created_at: "2026-07-01T00:00:00Z",
  ...over,
});

const fact = (filingUrl: string | null): DisclosureFact => ({ source: { filing_url: filingUrl } }) as unknown as DisclosureFact;

describe("filingParseState", () => {
  it("separates parsed, stored-without-facts and reference-only filings", () => {
    const f = filing({});
    expect(filingParseState(f, [fact(f.filing_url)])).toBe("parsed");
    expect(filingParseState(f, [fact("https://other.test/b.pdf")])).toBe("no_facts");
    expect(filingParseState(f, [])).toBe("no_facts");
    expect(filingParseState(filing({ has_bytes: false }), [])).toBe("reference");
  });
});

describe("parseOutcome", () => {
  it("reads the upload response's parse block", () => {
    expect(parseOutcome({ parse: { status: "OK", facts: [{}, {}] } })).toEqual({ status: "ok", facts: 2, reason: null });
    expect(parseOutcome({ parse: { status: "UNKNOWN", reason: "scanned-needs-OCR", facts: [] } })).toEqual({
      status: "failed",
      facts: 0,
      reason: "scanned-needs-OCR",
    });
    expect(parseOutcome({ parse: null })).toEqual({ status: "none", facts: 0, reason: null });
    expect(parseOutcome(undefined)).toEqual({ status: "none", facts: 0, reason: null });
  });
});

describe("optionalFields", () => {
  it("drops blanks and trims the rest", () => {
    expect(optionalFields({ a: " x ", b: "  ", c: "" })).toEqual({ a: "x" });
  });
});

describe("peer list editing", () => {
  const peerA = { id: "a", ticker: "AAA", name: "A Co" };
  const peerB = { id: "b", ticker: "BBB", name: "B Co" };

  it("refuses the company itself and repeats", () => {
    expect(addPeer([peerA], "self", { id: "self", ticker: "SLF", name: "Self" }).issue).toBe("self");
    expect(addPeer([peerA], "self", peerA).issue).toBe("duplicate");
    const added = addPeer([peerA], "self", peerB);
    expect(added.issue).toBeNull();
    expect(added.draft.map((p) => p.ticker)).toEqual(["AAA", "BBB"]);
  });

  it("detects a changed list regardless of order", () => {
    expect(peersChanged([peerA, peerB], [peerB, peerA])).toBe(false);
    expect(peersChanged([peerA], [peerA, peerB])).toBe(true);
    expect(peersChanged([peerA, peerB], removePeer([peerA, peerB], "a"))).toBe(true);
  });
});

describe("thesis update payloads", () => {
  const inv = (metric: string, status: string): ThesisInvalidation => ({ metric, status }) as ThesisInvalidation;
  const cat = (id: string, outcome: string): ThesisCatalyst => ({ id, outcome }) as ThesisCatalyst;

  it("sends only the rows the reviewer changed", () => {
    expect(changedInvalidations([inv("m1", "Active"), inv("m2", "Active")], { m1: "Active", m2: "Triggered" })).toEqual([
      { metric: "m2", status: "Triggered" },
    ]);
    expect(changedCatalysts([cat("c1", "Pending")], { c1: "Hit" })).toEqual([{ catalyst_id: "c1", outcome: "Hit" }]);
    expect(changedCatalysts([cat("c1", "Pending")], {})).toEqual([]);
  });
});

describe("labels", () => {
  it("localizes every pinned enum in both languages", () => {
    const en = (key: Parameters<typeof translate>[0]): string => translate(key, "en");
    const ar = (key: Parameters<typeof translate>[0]): string => translate(key, "ar");
    for (const type of FILING_TYPES) expect(enumLabel(type, FILING_TYPE_KEY, ar)).not.toBe(enumLabel(type, FILING_TYPE_KEY, en));
    for (const c of LEDGER_CLASSIFICATIONS) expect(enumLabel(c, CLASSIFICATION_KEY, en)).not.toBe("");
    expect(enumLabel("Something", CLASSIFICATION_KEY, en)).toBe("Something");
    expect(ACCOUNTING_BASES).toContain("IFRS");
  });

  it("shortens long URLs", () => {
    expect(shortUrl("https://a.test/x")).toBe("https://a.test/x");
    expect(shortUrl("x".repeat(80)).length).toBe(48);
  });
});
