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

export function parseInline(text: string): Inline[] {
  const parts = text.split("**");
  const out: Inline[] = [];
  parts.forEach((part, i) => {
    if (part === "") return;
    // An odd count of ** leaves the last marker literal rather than bolding the rest.
    const closed = i < parts.length - 1 || parts.length % 2 === 1;
    const bold = i % 2 === 1 && closed;
    out.push({ text: !bold && i % 2 === 1 ? `**${part}` : part, bold });
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
