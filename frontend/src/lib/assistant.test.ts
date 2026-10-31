import { describe, expect, it } from "vitest";
import { t } from "../i18n/dict";
import {
  assistantErrorCopy,
  decodeAssistantEvent,
  httpErrorCode,
  newsNoteKey,
  parseApiErrorBody,
  capInputValue,
  parseCapInput,
  pickModel,
  sourceHref,
  tickerFromPath,
  toolKey,
  safeWebUrl,
  sourceDomain,
  uniqueSources,
  webSources,
} from "./assistant";

describe("decodeAssistantEvent", () => {
  it("decodes meta, status, answer, unverified, error and done", () => {
    expect(decodeAssistantEvent({ event: "meta", data: '{"conversation_id":"c1","model":"claude-sonnet-5-5"}' })).toEqual({
      type: "meta",
      conversation_id: "c1",
      model: "claude-sonnet-5-5",
      web_search: null,
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
      general: false,
      news: null,
    });
    expect(decodeAssistantEvent({ event: "unverified", data: '{"checked":2,"unverified":["12%",4],"sources":[]}' })).toEqual({
      type: "unverified",
      checked: 2,
      unverified: ["12%"],
      sources: [],
      news: null,
    });
    expect(decodeAssistantEvent({ event: "error", data: '{"code":"NO_KEY","detail":"no key"}' })).toEqual({
      type: "error",
      code: "NO_KEY",
      detail: "no key",
      reason: null,
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

  it("decodes web_search, general and web sources, dropping unsafe URLs", () => {
    expect(decodeAssistantEvent({ event: "meta", data: '{"conversation_id":"c1","model":"m","web_search":true}' })).toEqual({
      type: "meta",
      conversation_id: "c1",
      model: "m",
      web_search: true,
    });
    expect(decodeAssistantEvent({ event: "meta", data: '{"web_search":"yes"}' })).toMatchObject({ web_search: null });
    const answer = decodeAssistantEvent({
      event: "answer",
      data: JSON.stringify({
        text: "t",
        checked: 0,
        general: true,
        news: null,
        sources: [
          { tool: "valuation", ticker: "COMI" },
          { tool: "web", url: "https://www.reuters.com/markets/x", title: "Egypt rate decision" },
          { tool: "web", url: "javascript:alert(1)", title: "bad" },
          { tool: "web", url: "data:text/html,<b>x</b>", title: "bad" },
          { tool: "web", url: "/relative", title: "bad" },
          { tool: "web", title: "no url" },
          { tool: "web", url: "http://example.com/a", title: 5 },
        ],
      }),
    });
    expect(answer).toEqual({
      type: "answer",
      text: "t",
      checked: 0,
      general: true,
      news: null,
      sources: [
        { tool: "valuation", ticker: "COMI" },
        { tool: "web", url: "https://www.reuters.com/markets/x", title: "Egypt rate decision" },
        { tool: "web", url: "http://example.com/a", title: "" },
      ],
    });
  });

  it("decodes news and the provider reason defensively", () => {
    for (const news of ["searched", "not_offered", "unsupported", "refused"]) {
      expect(decodeAssistantEvent({ event: "answer", data: JSON.stringify({ text: "t", news }) })).toMatchObject({ news });
      expect(decodeAssistantEvent({ event: "unverified", data: JSON.stringify({ news }) })).toMatchObject({ news });
    }
    expect(decodeAssistantEvent({ event: "answer", data: '{"text":"t","news":"maybe"}' })).toMatchObject({ news: null });
    expect(decodeAssistantEvent({ event: "answer", data: '{"text":"t","news":5}' })).toMatchObject({ news: null });
    expect(decodeAssistantEvent({ event: "answer", data: '{"text":"t"}' })).toMatchObject({ news: null });
    expect(decodeAssistantEvent({ event: "error", data: '{"code":"PROVIDER_ERROR","detail":"d","reason":"quota"}' })).toEqual({
      type: "error",
      code: "PROVIDER_ERROR",
      detail: "d",
      reason: "quota",
    });
    expect(decodeAssistantEvent({ event: "error", data: '{"code":"PROVIDER_ERROR","reason":"weird"}' })).toMatchObject({ reason: null });
    expect(decodeAssistantEvent({ event: "error", data: '{"code":"PROVIDER_ERROR"}' })).toMatchObject({ reason: null });
  });

  it("general is true only for a real true", () => {
    expect(decodeAssistantEvent({ event: "answer", data: '{"text":"t","general":"true"}' })).toMatchObject({ general: false });
    expect(decodeAssistantEvent({ event: "answer", data: '{"text":"t"}' })).toMatchObject({ general: false });
  });

  it("keeps a missing error code visible as UNKNOWN instead of guessing", () => {
    expect(decodeAssistantEvent({ event: "error", data: "{}" })).toEqual({ type: "error", code: "UNKNOWN", detail: null, reason: null });
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

  it("gives a provider error its reason-specific line, and never says try again for quota", () => {
    expect(assistantErrorCopy("PROVIDER_ERROR", "quota")).toEqual({ key: "assistant_err_prov_quota", settings: true });
    expect(assistantErrorCopy("PROVIDER_ERROR", "rate_limit")).toEqual({ key: "assistant_err_prov_rate_limit", settings: false });
    expect(assistantErrorCopy("PROVIDER_ERROR", "auth")).toEqual({ key: "assistant_err_prov_auth", settings: true });
    expect(assistantErrorCopy("PROVIDER_ERROR", "unavailable").key).toBe("assistant_err_prov_unavailable");
    expect(assistantErrorCopy("PROVIDER_ERROR", "bad_request").key).toBe("assistant_err_prov_bad_request");
    expect(t("assistant_err_prov_quota", "en").toLowerCase()).not.toContain("try again");
    expect(t("assistant_err_prov_rate_limit", "en")).toContain("Try again");
  });

  it("uses the generic provider copy when the reason is missing or unknown", () => {
    expect(assistantErrorCopy("PROVIDER_ERROR", null).key).toBe("assistant_err_provider");
    expect(assistantErrorCopy("PROVIDER_ERROR").key).toBe("assistant_err_provider");
    expect(assistantErrorCopy("PROVIDER_ERROR", "unknown").key).toBe("assistant_err_provider");
    expect(assistantErrorCopy("NO_KEY", "quota").key).toBe("assistant_err_no_key");
  });

  it("picks the news note from the news field only", () => {
    expect(newsNoteKey("unsupported")).toBe("assistant_news_not_checked");
    expect(newsNoteKey("refused")).toBe("assistant_news_refused");
    for (const quiet of ["searched", "not_offered", null] as const) expect(newsNoteKey(quiet)).toBeNull();
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

describe("web sources", () => {
  it("accepts only absolute http(s) URLs", () => {
    expect(safeWebUrl("https://a.com/x?y=1")).toBe("https://a.com/x?y=1");
    expect(safeWebUrl("  http://a.com ")).toBe("http://a.com/");
    for (const bad of ["javascript:alert(1)", "data:text/plain,x", "ftp://a.com", "//a.com", "a.com", "", "  ", null, 5, {}]) {
      expect(safeWebUrl(bad)).toBeNull();
    }
  });

  it("shows the site's domain without www", () => {
    expect(sourceDomain("https://www.reuters.com/markets/x")).toBe("reuters.com");
    expect(sourceDomain("https://news.Example.co.uk:8443/a?b=c")).toBe("news.example.co.uk");
    expect(sourceDomain("http://WWW.ahram.org.eg/x")).toBe("ahram.org.eg");
    expect(sourceDomain("javascript:alert(1)")).toBeNull();
    expect(sourceDomain("not a url")).toBeNull();
  });

  it("splits data chips from web chips and dedupes each", () => {
    const sources = [
      { tool: "valuation", ticker: "COMI" },
      { tool: "web" as const, url: "https://a.com/1", title: "A" },
      { tool: "valuation", ticker: "COMI" },
      { tool: "web" as const, url: "https://a.com/1", title: "A again" },
      { tool: "web" as const, url: "https://b.com/2", title: "B" },
    ];
    expect(uniqueSources(sources)).toEqual([{ tool: "valuation", ticker: "COMI" }]);
    expect(webSources(sources).map((s) => s.url)).toEqual(["https://a.com/1", "https://b.com/2"]);
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
