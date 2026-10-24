import ts from "typescript";
import { describe, expect, it } from "vitest";

/*
 * Guard against hard-coded English in the UI: every visible string goes
 * through t(). Parses each .tsx file and flags JSX text and user-facing
 * string attributes that contain Latin words. All-caps codes that stay Latin
 * in Arabic (tickers, EGX33, ATR, RSI) and URLs pass; other exceptions are
 * listed in ALLOWED.
 */

const VISIBLE_ATTRS = new Set(["title", "placeholder", "aria-label", "alt", "label"]);
const ALLOWED = new Set(["Ctrl K"]);
/** A word with a lowercase letter: "Open", "of"; not "ATR" or "EGX33". */
const LATIN_WORD = /[A-Z]?[a-z]{2,}/;

/** Hub tab files not yet migrated (Lane B). Remove each entry as it is translated; the list must end empty. */
const PENDING = new Set<string>([
  "components/DataQualityCard.tsx",
  "components/FairValueCard.tsx",
  "components/PeersTab.tsx",
  "components/SensitivityTable.tsx",
  "pages/CompanyDetail.tsx",
  "pages/Disclosures.tsx",
  "pages/FinancialData.tsx",
  "pages/FinancialMetrics.tsx",
  "pages/InvestmentScore.tsx",
  "pages/Peers.tsx",
  "pages/ShariahScreening.tsx",
  "pages/TechnicalAnalysis.tsx",
  "pages/Thesis.tsx",
  "pages/Valuation.tsx",
]);

/** Every .tsx source under src/, keyed "pages/Foo.tsx", read as raw text by Vite. */
const SOURCES: Record<string, string> = Object.fromEntries(
  Object.entries(
    import.meta.glob<string>(["../**/*.tsx", "!../**/*.test.tsx"], { query: "?raw", import: "default", eager: true }),
  ).map(([path, text]) => [path.replace(/^\.\.\//, ""), text]),
);

function findings(file: string): string[] {
  const source = ts.createSourceFile(file, SOURCES[file] ?? "", ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const out: string[] = [];
  const report = (node: ts.Node, text: string): void => {
    const trimmed = text.replace(/\s+/g, " ").trim();
    if (!LATIN_WORD.test(trimmed) || ALLOWED.has(trimmed) || /^https?:\/\//.test(trimmed)) return;
    const { line } = source.getLineAndCharacterOfPosition(node.getStart());
    out.push(`${line + 1}: ${trimmed.slice(0, 60)}`);
  };
  const visit = (node: ts.Node): void => {
    if (ts.isJsxText(node)) report(node, node.getText());
    if (
      ts.isJsxAttribute(node) &&
      VISIBLE_ATTRS.has(node.name.getText()) &&
      node.initializer &&
      ts.isStringLiteral(node.initializer)
    ) {
      report(node, node.initializer.text);
    }
    ts.forEachChild(node, visit);
  };
  visit(source);
  return out;
}

describe("no hard-coded English in the UI", () => {
  const files = Object.keys(SOURCES);

  it.each(files.filter((f) => !PENDING.has(f)))("%s", (file) => {
    expect(findings(file)).toEqual([]);
  });

  it("the pending list only names files that still need translating", () => {
    for (const file of PENDING) {
      expect(files, `${file} no longer exists`).toContain(file);
      expect(findings(file).length, `${file} is clean: remove it from PENDING`).toBeGreaterThan(0);
    }
  });
});
