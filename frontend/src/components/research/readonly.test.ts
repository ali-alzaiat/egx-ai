import { describe, expect, it } from "vitest";

/*
 * R43 AC-1 for the research tabs (Valuation, Shariah, Peers, Thesis & filings):
 * they compute on read, so they must not import any write call or render a
 * form control. The only control is the Disclosures comparison selector.
 */

const FILES = [
  "pages/Valuation.tsx",
  "pages/InvestmentScore.tsx",
  "pages/ShariahScreening.tsx",
  "pages/Peers.tsx",
  "pages/Thesis.tsx",
  "pages/Disclosures.tsx",
  "FairValueCard.tsx",
  "SensitivityTable.tsx",
  "PeersTab.tsx",
  "AssumptionsTable.tsx",
  "parts.tsx",
  "reasons.tsx",
] as const;

/** Keyed by path relative to the nearest folder: "pages/Thesis.tsx", "PeersTab.tsx", "parts.tsx". */
const SOURCES: Record<string, string> = Object.fromEntries(
  Object.entries(
    import.meta.glob<string>(["../../pages/*.tsx", "../*.tsx", "./*.tsx"], {
      query: "?raw",
      import: "default",
      eager: true,
    }),
  ).map(([path, text]) => [path.replace(/^(\.\.\/|\.\/)+/, ""), text]),
);

const WRITE_CALLS = [
  "calculateValuations",
  "calculateIndicators",
  "calculateMetrics",
  "assessScore",
  "assessThesis",
  "updateThesis",
  "screenCompany",
  "estimatePurification",
  "recordEgxMembership",
  "putPeerOverride",
  "registerFiling",
  "uploadFiling",
  "parseFiling",
  "startMarketRefresh",
  "runSignals",
  "recordManualFiling",
];

describe("research tabs are read-only (R43 AC-1)", () => {
  it.each(FILES)("%s exists in the glob", (file) => {
    expect(SOURCES[file], `${file} not found`).toBeDefined();
  });

  it.each(FILES)("%s imports no write call", (file) => {
    const text = SOURCES[file] ?? "";
    for (const name of WRITE_CALLS) expect(text, `${file} uses ${name}`).not.toContain(name);
  });

  it.each(FILES)("%s renders no form control except the comparison selector", (file) => {
    const text = SOURCES[file] ?? "";
    expect(text).not.toMatch(/<(input|textarea|form|button)\b/);
    if (file !== "pages/Disclosures.tsx") expect(text).not.toMatch(/<select\b/);
  });
});
