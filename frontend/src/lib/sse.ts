/**
 * Server-sent events parser (WHATWG "Parsing an event stream"), pure and
 * chunk-agnostic: bytes may be split anywhere, including inside a field name,
 * a multi-byte character (the caller decodes with `stream: true`) or between
 * the CR and LF of a CRLF pair.
 */

export interface SseMessage {
  /** The `event:` name; "message" when the server sent none. */
  event: string;
  /** The `data:` lines joined with "\n". */
  data: string;
}

export interface SseParser {
  /** Feed the next chunk of decoded text; returns the events it completed. */
  push(chunk: string): SseMessage[];
  /** The stream ended: dispatch an event the server left without its closing blank line. */
  flush(): SseMessage[];
}

export function createSseParser(): SseParser {
  let buffer = "";
  let started = false;
  let eventName = "";
  let dataLines: string[] = [];

  const dispatch = (out: SseMessage[]): void => {
    if (dataLines.length > 0) out.push({ event: eventName === "" ? "message" : eventName, data: dataLines.join("\n") });
    eventName = "";
    dataLines = [];
  };

  const line = (raw: string, out: SseMessage[]): void => {
    if (raw === "") {
      dispatch(out);
      return;
    }
    if (raw.startsWith(":")) return; // comment / keep-alive
    const colon = raw.indexOf(":");
    const field = colon === -1 ? raw : raw.slice(0, colon);
    let value = colon === -1 ? "" : raw.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") eventName = value;
    else if (field === "data") dataLines.push(value);
    // id and retry are not used by this app
  };

  return {
    push(chunk) {
      let text = buffer + chunk;
      if (!started && text.length > 0) {
        started = true;
        if (text.startsWith("﻿")) text = text.slice(1);
      }
      // A trailing CR may be the first half of CRLF: keep it until the next chunk.
      const held = text.endsWith("\r") ? "\r" : "";
      const body = held ? text.slice(0, -1) : text;
      const lines = body.replace(/\r\n|\r/g, "\n").split("\n");
      buffer = (lines.pop() ?? "") + held;
      const out: SseMessage[] = [];
      for (const l of lines) line(l, out);
      return out;
    },
    flush() {
      const out: SseMessage[] = [];
      const rest = buffer.replace(/\r$/, "");
      buffer = "";
      if (rest !== "") line(rest, out);
      dispatch(out);
      return out;
    },
  };
}
