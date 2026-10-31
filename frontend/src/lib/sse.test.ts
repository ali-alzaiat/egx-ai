import { describe, expect, it } from "vitest";
import { createSseParser, type SseMessage } from "./sse";

function parseAll(chunks: readonly string[]): SseMessage[] {
  const p = createSseParser();
  const out: SseMessage[] = [];
  for (const c of chunks) out.push(...p.push(c));
  out.push(...p.flush());
  return out;
}

describe("createSseParser", () => {
  it("parses a named event with JSON data", () => {
    expect(parseAll(['event: meta\ndata: {"a":1}\n\n'])).toEqual([{ event: "meta", data: '{"a":1}' }]);
  });

  it("defaults the event name to message", () => {
    expect(parseAll(["data: hi\n\n"])).toEqual([{ event: "message", data: "hi" }]);
  });

  it("joins multiple data lines with a newline", () => {
    expect(parseAll(["event: x\ndata: a\ndata: b\n\n"])).toEqual([{ event: "x", data: "a\nb" }]);
  });

  it("strips exactly one leading space from a value", () => {
    expect(parseAll(["data:  two\n\ndata:none\n\n"])).toEqual([
      { event: "message", data: " two" },
      { event: "message", data: "none" },
    ]);
  });

  it("handles CRLF and bare CR line endings", () => {
    expect(parseAll(["event: a\r\ndata: 1\r\n\r\nevent: b\rdata: 2\r\r"])).toEqual([
      { event: "a", data: "1" },
      { event: "b", data: "2" },
    ]);
  });

  it("is independent of where the chunks are split", () => {
    const whole = 'event: status\ndata: {"stage":"tool"}\n\nevent: done\ndata: {}\n\n';
    const expected = parseAll([whole]);
    expect(expected).toHaveLength(2);
    for (let i = 1; i < whole.length; i++) {
      expect(parseAll([whole.slice(0, i), whole.slice(i)])).toEqual(expected);
    }
    expect(parseAll(whole.split(""))).toEqual(expected);
  });

  it("keeps a CR at the end of a chunk until the LF arrives", () => {
    expect(parseAll(["event: a\r", "\ndata: 1\r", "\n\r", "\n"])).toEqual([{ event: "a", data: "1" }]);
  });

  it("ignores comments and keep-alives", () => {
    expect(parseAll([": ping\n\nevent: a\n: note\ndata: 1\n\n"])).toEqual([{ event: "a", data: "1" }]);
  });

  it("does not dispatch an event with no data", () => {
    expect(parseAll(["event: a\n\n", "data: 1\n\n"])).toEqual([{ event: "message", data: "1" }]);
  });

  it("resets the event name between events", () => {
    expect(parseAll(["event: a\ndata: 1\n\ndata: 2\n\n"])).toEqual([
      { event: "a", data: "1" },
      { event: "message", data: "2" },
    ]);
  });

  it("drops a leading byte-order mark", () => {
    expect(parseAll(["﻿data: 1\n\n"])).toEqual([{ event: "message", data: "1" }]);
  });

  it("keeps Arabic text and colons inside the data", () => {
    expect(parseAll(["data: النتيجة: 72.5\n\n"])).toEqual([{ event: "message", data: "النتيجة: 72.5" }]);
  });

  it("flush dispatches an event missing its closing blank line, and nothing twice", () => {
    const p = createSseParser();
    expect(p.push("event: done\ndata: {}\n")).toEqual([]);
    expect(p.flush()).toEqual([{ event: "done", data: "{}" }]);
    expect(p.flush()).toEqual([]);
  });

  it("treats a field without a colon as an empty value", () => {
    expect(parseAll(["data\n\n"])).toEqual([{ event: "message", data: "" }]);
  });
});
