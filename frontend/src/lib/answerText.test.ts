import { describe, expect, it } from "vitest";
import { parseAnswer, parseInline } from "./answerText";

describe("parseInline", () => {
  it("bolds paired markers", () => {
    expect(parseInline("a **b** c")).toEqual([
      { text: "a ", bold: false },
      { text: "b", bold: true },
      { text: " c", bold: false },
    ]);
  });

  it("leaves an unpaired marker literal", () => {
    expect(parseInline("a **b")).toEqual([
      { text: "a ", bold: false },
      { text: "**b", bold: false },
    ]);
  });

  it("keeps numbers and Arabic text untouched", () => {
    expect(parseInline("الإجمالي 72.5% من 100")).toEqual([{ text: "الإجمالي 72.5% من 100", bold: false }]);
  });
});

describe("parseAnswer", () => {
  it("splits paragraphs on blank lines and keeps single line breaks", () => {
    expect(parseAnswer("one\ntwo\n\nthree")).toEqual([
      { kind: "p", inlines: [{ text: "one\ntwo", bold: false }] },
      { kind: "p", inlines: [{ text: "three", bold: false }] },
    ]);
  });

  it("groups bullets and numbered lines", () => {
    const blocks = parseAnswer("Intro\n- a\n* b\n1. c\n2) d");
    expect(blocks.map((b) => b.kind)).toEqual(["p", "ul", "ol"]);
    expect(blocks[1]).toMatchObject({ kind: "ul", items: [[{ text: "a" }], [{ text: "b" }]] });
    expect(blocks[2]).toMatchObject({ kind: "ol", items: [[{ text: "c" }], [{ text: "d" }]] });
  });

  it("reads headings and strips the hashes", () => {
    expect(parseAnswer("## Valuation")).toEqual([{ kind: "h", inlines: [{ text: "Valuation", bold: false }] }]);
  });

  it("does not turn a negative number or a hyphenated word into a bullet", () => {
    expect(parseAnswer("-5% change")[0]).toMatchObject({ kind: "p" });
    expect(parseAnswer("well-known")[0]).toMatchObject({ kind: "p" });
  });

  it("never produces markup from angle brackets", () => {
    expect(parseAnswer("<script>x</script>")).toEqual([{ kind: "p", inlines: [{ text: "<script>x</script>", bold: false }] }]);
  });
});
