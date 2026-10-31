/**
 * A deliberately small reader for the markdown-ish text models answer with: paragraphs,
 * "-" / "*" bullets, "1." lists, "#" headings and **bold**. Everything else stays literal
 * text, and the result is rendered as React elements (never as HTML).
 */

export interface Inline {
  text: string;
  bold: boolean;
}

export type AnswerBlock =
  | { kind: "p"; inlines: Inline[] }
  | { kind: "h"; inlines: Inline[] }
  | { kind: "ul"; items: Inline[][] }
  | { kind: "ol"; items: Inline[][] };

/** A pair of backticks around at least one character. A lone backtick has no pair and stays literal. */
const CODE_SPAN = /`([^`]+)`/g;
const MASK_OPEN = "";
const MASK_CLOSE = "";
const MASK = new RegExp(`${MASK_OPEN}(\\d+)${MASK_CLOSE}`, "g");

export function parseInline(text: string): Inline[] {
  // Backticked text is shown as plain text without the backticks (the prompt asks models for plain words, but some
  // still quote names). Its content is masked while ** is read, so a marker inside it stays literal.
  const spans: string[] = [];
  const masked = text.replace(CODE_SPAN, (_match, content: string) => `${MASK_OPEN}${spans.push(content) - 1}${MASK_CLOSE}`);
  const parts = masked.split("**");
  const out: Inline[] = [];
  parts.forEach((part, i) => {
    if (part === "") return;
    // An odd count of ** leaves the last marker literal rather than bolding the rest.
    const closed = i < parts.length - 1 || parts.length % 2 === 1;
    const bold = i % 2 === 1 && closed;
    const raw = !bold && i % 2 === 1 ? `**${part}` : part;
    out.push({ text: raw.replace(MASK, (match, index: string) => spans[Number(index)] ?? match), bold });
  });
  return out;
}

const HEADING = /^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$/;
const BULLET = /^\s*[-*•]\s+(.*)$/;
const ORDERED = /^\s*\d{1,3}[.)]\s+(.*)$/;

export function parseAnswer(text: string): AnswerBlock[] {
  const blocks: AnswerBlock[] = [];
  let paragraph: string[] = [];
  const flush = (): void => {
    if (paragraph.length > 0) blocks.push({ kind: "p", inlines: parseInline(paragraph.join("\n")) });
    paragraph = [];
  };
  const list = (kind: "ul" | "ol", item: string): void => {
    flush();
    const last = blocks[blocks.length - 1];
    if (last && last.kind === kind) last.items.push(parseInline(item));
    else blocks.push({ kind, items: [parseInline(item)] });
  };

  for (const raw of text.replace(/\r\n?/g, "\n").split("\n")) {
    if (raw.trim() === "") {
      flush();
      continue;
    }
    const heading = HEADING.exec(raw);
    if (heading?.[1]) {
      flush();
      blocks.push({ kind: "h", inlines: parseInline(heading[1]) });
      continue;
    }
    const bullet = BULLET.exec(raw);
    if (bullet?.[1] !== undefined) {
      list("ul", bullet[1]);
      continue;
    }
    const ordered = ORDERED.exec(raw);
    if (ordered?.[1] !== undefined) {
      list("ol", ordered[1]);
      continue;
    }
    paragraph.push(raw.trim());
  }
  flush();
  return blocks;
}
