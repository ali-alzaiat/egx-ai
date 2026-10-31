import { describe, expect, it } from "vitest";
import {
  assistantErrorCopy,
  decodeAssistantEvent,
  httpErrorCode,
  parseApiErrorBody,
  capInputValue,
  parseCapInput,
  pickModel,
  sourceHref,
  tickerFromPath,
  toolKey,
  uniqueSources,
} from "./assistant";

describe("decodeAssistantEvent", () => {
  it("decodes meta, status, answer, unverified, error and done", () => {
    expect(decodeAssistantEvent({ event: "meta", data: '{"conversation_id":"c1","model":"claude-sonnet-5-5"}' })).toEqual({
      type: "meta",
      conversation_id: "c1",
      model: "claude-sonnet-5-5",
    });
    expect(decodeAssistantEvent({ event: "status", data: '{"stage":"tool","tool":"valuation"}' })).toEqual({
      type: "status",
      stage: "tool",
      tool: "valuation",
    });
    expect(
      decodeAssistantEvent({
        event: "answer",
        data: '{"text":"Score 72.5","verified":true,"checked":3,"sources":[{"tool":"investment_score","ticker":"COMI"},{"tool":"search_companies"},{"nope":1}]}',
      }),
    ).toEqual({
      type: "answer",
      text: "Score 72.5",
      checked: 3,
      sources: [
        { tool: "investment_score", ticker: "COMI" },
        { tool: "search_companies", ticker: null },
      ],
    });
    expect(decodeAssistantEvent({ event: "unverified", data: '{"checked":2,"unverified":["12%",4],"sources":[]}' })).toEqual({
      type: "unverified",
      checked: 2,
      unverified: ["12%"],
      sources: [],
    });
    expect(decodeAssistantEvent({ event: "error", data: '{"code":"NO_KEY","detail":"no key"}' })).toEqual({
      type: "error",
      code: "NO_KEY",
      detail: "no key",
    });
    expect(
      decodeAssistantEvent({ event: "done", data: '{"input_tokens":10,"output_tokens":5,"cost_usd":"0.0123","month_spend_usd":1.5}' }),
    ).toEqual({ type: "done", input_tokens: 10, output_tokens: 5, cost_usd: "0.0123", month_spend_usd: 1.5 });
  });

  it("returns null for malformed JSON, unknown events and unknown stages", () => {
    expect(decodeAssistantEvent({ event: "answer", data: "{oops" })).toBeNull();
    expect(decodeAssistantEvent({ event: "mystery", data: "{}" })).toBeNull();
    expect(decodeAssistantEvent({ event: "status", data: '{"stage":"dreaming"}' })).toBeNull();
    expect(decodeAssistantEvent({ event: "answer", data: "[1]" })).toBeNull();
    expect(decodeAssistantEvent({ event: "answer", data: '{"verified":true}' })).toBeNull();
  });

  it("keeps a missing error code visible as UNKNOWN instead of guessing", () => {
    expect(decodeAssistantEvent({ event: "error", data: "{}" })).toEqual({ type: "error", code: "UNKNOWN", detail: null });
  });
});

describe("parseApiErrorBody", () => {
  it("reads the code from every shape the backend may use", () => {
    expect(parseApiErrorBody({ detail: "KEY_REJECTED" })).toEqual({ code: "KEY_REJECTED", detail: null });
    expect(parseApiErrorBody({ detail: { code: "AI_SECRETS_KEY_MISSING", detail: "set it" } })).toEqual({
      code: "AI_SECRETS_KEY_MISSING",
      detail: "set it",
    });
    expect(parseApiErrorBody({ code: "INSECURE_TRANSPORT", detail: "use https" })).toEqual({
      code: "INSECURE_TRANSPORT",
      detail: "use https",
    });
    expect(parseApiErrorBody({ detail: [{ msg: "too short" }] })).toEqual({ code: null, detail: "too short" });
    expect(parseApiErrorBody({ detail: "Key was refused by the provider" })).toEqual({
      code: null,
      detail: "Key was refused by the provider",
    });
  });

  it("tolerates non-objects", () => {
    expect(parseApiErrorBody(null)).toEqual({ code: null, detail: null });
    expect(parseApiErrorBody("x")).toEqual({ code: null, detail: null });
  });
});

describe("error codes", () => {
  it("links key and cap problems to settings", () => {
    expect(assistantErrorCopy("NO_KEY").settings).toBe(true);
    expect(assistantErrorCopy("CAP_REACHED").settings).toBe(true);
    expect(assistantErrorCopy("PROVIDER_ERROR").settings).toBe(false);
  });

  it("falls back to generic copy for a code it does not know", () => {
    expect(assistantErrorCopy("SOMETHING_NEW").key).toBe("assistant_err_generic");
  });

  it("maps pre-stream HTTP failures", () => {
    expect(httpErrorCode(404, null)).toBe("HTTP_404");
    expect(httpErrorCode(502, null)).toBe("HTTP_5XX");
    expect(httpErrorCode(422, "NO_KEY")).toBe("NO_KEY");
    expect(httpErrorCode(422, "OTHER")).toBe("HTTP_422");
  });
});

describe("sources", () => {
  it("links each tool to the tab that shows the same figures", () => {
    expect(sourceHref({ tool: "investment_score", ticker: "COMI" })).toBe("/companies/COMI/valuation#score");
    expect(sourceHref({ tool: "valuation", ticker: "COMI" })).toBe("/companies/COMI/valuation");
    expect(sourceHref({ tool: "stance", ticker: "COMI" })).toBe("/companies/COMI/price");
    expect(sourceHref({ tool: "shariah_status", ticker: "COMI" })).toBe("/companies/COMI/shariah");
    expect(sourceHref({ tool: "financial_metrics", ticker: "COMI" })).toBe("/companies/COMI/financials/metrics");
    expect(sourceHref({ tool: "company_overview", ticker: "COMI" })).toBe("/companies/COMI");
  });

  it("has no link without a ticker, and escapes the ticker", () => {
    expect(sourceHref({ tool: "screen_companies" })).toBeNull();
    expect(sourceHref({ tool: "valuation", ticker: " " })).toBeNull();
    expect(sourceHref({ tool: "valuation", ticker: "A/B" })).toBe("/companies/A%2FB/valuation");
  });

  it("de-duplicates tool and ticker pairs in first-seen order", () => {
    expect(
      uniqueSources([
        { tool: "valuation", ticker: "COMI" },
        { tool: "stance", ticker: "COMI" },
        { tool: "valuation", ticker: "COMI" },
        { tool: "valuation", ticker: "SWDY" },
      ]),
    ).toEqual([
      { tool: "valuation", ticker: "COMI" },
      { tool: "stance", ticker: "COMI" },
      { tool: "valuation", ticker: "SWDY" },
    ]);
  });

  it("names the known tools only", () => {
    expect(toolKey("valuation")).toBe("assistant_tool_valuation");
    expect(toolKey("drop_tables")).toBeNull();
  });
});

describe("tickerFromPath", () => {
  it("reads the ticker on company pages only", () => {
    expect(tickerFromPath("/companies/COMI/price")).toBe("COMI");
    expect(tickerFromPath("/companies/COMI")).toBe("COMI");
    expect(tickerFromPath("/companies")).toBeNull();
    expect(tickerFromPath("/assistant")).toBeNull();
    expect(tickerFromPath("/companies/A%2FB")).toBe("A/B");
  });
});

describe("capInputValue", () => {
  it("drops padding zeros so a saved cap stays valid in the form", () => {
    expect(capInputValue(null)).toBe("");
    expect(capInputValue("0.0000")).toBe("0");
    expect(capInputValue("12.5000")).toBe("12.5");
    expect(capInputValue("25")).toBe("25");
    expect(parseCapInput(capInputValue("0.0000"))).toEqual({ ok: true, value: "0" });
  });
});

describe("parseCapInput", () => {
  it("accepts empty (off) and non-negative decimals", () => {
    expect(parseCapInput("")).toEqual({ ok: true, value: null });
    expect(parseCapInput(" 25 ")).toEqual({ ok: true, value: "25" });
    expect(parseCapInput("12.50")).toEqual({ ok: true, value: "12.50" });
    expect(parseCapInput("0")).toEqual({ ok: true, value: "0" });
  });

  it("rejects negatives, text and too many decimals", () => {
    expect(parseCapInput("-1")).toEqual({ ok: false });
    expect(parseCapInput("abc")).toEqual({ ok: false });
    expect(parseCapInput("1.234")).toEqual({ ok: false });
    expect(parseCapInput("1e3")).toEqual({ ok: false });
  });
});

describe("pickModel", () => {
  const models = [
    { id: "a", available: false },
    { id: "b", available: true },
    { id: "c", available: true },
  ];

  it("prefers the saved choice, then the default, then the first available", () => {
    expect(pickModel(models, "b", "c")).toBe("c");
    expect(pickModel(models, "c", "a")).toBe("c");
    expect(pickModel(models, "a", null)).toBe("b");
  });

  it("is null when no provider has a key", () => {
    expect(pickModel([{ id: "a", available: false }], "a", "a")).toBeNull();
    expect(pickModel([], null, null)).toBeNull();
  });
});
