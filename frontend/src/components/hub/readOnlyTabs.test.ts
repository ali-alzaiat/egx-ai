import ts from "typescript";
import { describe, expect, it } from "vitest";

/*
 * R43 AC-1 for the Overview, Price & signals and Financials tabs: they only
 * read. No write-path client function is imported, and no form control is
 * rendered. Buttons are limited to view selectors, pagination, retry and the
 * info popover (checked by the file list below, which names every file that
 * renders a button).
 */

const FILES = [
  "pages/CompanyDetail.tsx",
  "pages/Signals.tsx",
  "pages/TechnicalAnalysis.tsx",
  "pages/Statements.tsx",
  "pages/Ratios.tsx",
  "pages/FinancialMetrics.tsx",
  "components/DataQualityCard.tsx",
  "components/hub/DailyPrices.tsx",
  "components/hub/Reason.tsx",
  "components/hub/priceData.ts",
  "components/ui/PriceChart.tsx",
  "components/ui/InfoPopover.tsx",
];

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

const FORM_TAGS = new Set(["input", "select", "textarea", "form"]);
/** Files where a raw `<button>` is allowed, and why. */
const BUTTONS_ALLOWED = new Set([
  "components/ui/InfoPopover.tsx", // opens a definition
  "components/hub/DailyPrices.tsx", // pagination
]);

const SOURCES = import.meta.glob<string>(["../../pages/*.tsx", "../../components/*.tsx", "../../components/*/*.ts", "../../components/*/*.tsx"], {
  query: "?raw",
  import: "default",
  eager: true,
});

function sourceOf(file: string): string {
  // Glob keys are relative to this folder ("../ui/X.tsx"), so match on the file name.
  const name = file.slice(file.lastIndexOf("/") + 1);
  const entry = Object.entries(SOURCES).find(([path]) => path.endsWith(`/${name}`));
  if (!entry) throw new Error(`${file} not found`);
  return entry[1];
}

function jsxTags(file: string): string[] {
  const source = ts.createSourceFile(file, sourceOf(file), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const tags: string[] = [];
  const visit = (node: ts.Node): void => {
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) tags.push(node.tagName.getText());
    ts.forEachChild(node, visit);
  };
  visit(source);
  return tags;
}

describe("read-only hub tabs (R43 AC-1)", () => {
  it.each(FILES)("%s imports no write-path client function", (file) => {
    const text = sourceOf(file);
    for (const name of WRITE_CALLS) expect(text, `${file} uses ${name}`).not.toMatch(new RegExp(`\\b${name}\\b`));
  });

  it.each(FILES.filter((f) => f.endsWith(".tsx")))("%s renders no form control", (file) => {
    expect(jsxTags(file).filter((tag) => FORM_TAGS.has(tag))).toEqual([]);
  });

  it.each(FILES.filter((f) => f.endsWith(".tsx")))("%s renders buttons only where allowed", (file) => {
    const buttons = jsxTags(file).filter((tag) => tag === "button");
    if (!BUTTONS_ALLOWED.has(file)) expect(buttons).toEqual([]);
  });
});
