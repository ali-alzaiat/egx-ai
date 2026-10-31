import { describe, expect, it } from "vitest";
import { INITIAL_CHAT, chatReducer, turnsFromConversation, type ChatAction, type ChatState } from "./assistantChat";

function run(actions: readonly ChatAction[], from: ChatState = INITIAL_CHAT): ChatState {
  return actions.reduce(chatReducer, from);
}

describe("chatReducer", () => {
  it("send adds the question and starts the progress line", () => {
    const s = run([{ type: "send", text: "How is COMI?" }]);
    expect(s.running).toBe(true);
    expect(s.progress).toEqual({ stage: "thinking", tool: null });
    expect(s.turns).toEqual([{ id: 1, kind: "user", text: "How is COMI?" }]);
  });

  it("folds meta, status and a verified answer", () => {
    const s = run([
      { type: "send", text: "q" },
      { type: "event", event: { type: "meta", conversation_id: "c1", model: "m1", web_search: null } },
      { type: "event", event: { type: "status", stage: "tool", tool: "valuation" } },
    ]);
    expect(s.conversationId).toBe("c1");
    expect(s.progress).toEqual({ stage: "tool", tool: "valuation" });
    const done = run(
      [
        { type: "event", event: { type: "answer", text: "A", checked: 4, sources: [{ tool: "valuation", ticker: "COMI" }], general: false, news: null } },
        { type: "event", event: { type: "done", input_tokens: 1, output_tokens: 1, cost_usd: null, month_spend_usd: null } },
      ],
      s,
    );
    expect(done.running).toBe(false);
    expect(done.progress).toBeNull();
    expect(done.turns[1]).toMatchObject({ kind: "answer", text: "A", checked: 4, model: "m1" });
  });

  it("an unverified event withholds the answer and settles", () => {
    const s = run([
      { type: "send", text: "q" },
      { type: "event", event: { type: "unverified", checked: 2, unverified: ["12%"], sources: [], news: null } },
    ]);
    expect(s.running).toBe(false);
    expect(s.turns[1]).toMatchObject({ kind: "unverified", unverified: ["12%"] });
  });

  it("an error event settles with its code", () => {
    const s = run([
      { type: "send", text: "q" },
      { type: "event", event: { type: "error", code: "NO_KEY", detail: null, reason: null } },
    ]);
    expect(s.running).toBe(false);
    expect(s.turns[1]).toMatchObject({ kind: "error", code: "NO_KEY" });
  });

  it("a stream that closes with no outcome becomes an interrupted error, not an endless spinner", () => {
    const s = run([{ type: "send", text: "q" }, { type: "closed" }]);
    expect(s.running).toBe(false);
    expect(s.turns[1]).toMatchObject({ kind: "error", code: "STREAM_INTERRUPTED" });
  });

  it("closing after an answer adds nothing", () => {
    const s = run([
      { type: "send", text: "q" },
      { type: "event", event: { type: "answer", text: "A", checked: 1, sources: [], general: false, news: null } },
      { type: "closed" },
    ]);
    expect(s.turns).toHaveLength(2);
  });

  it("stop notes the interruption once", () => {
    const s = run([{ type: "send", text: "q" }, { type: "stopped" }, { type: "stopped" }]);
    expect(s.turns.map((t) => t.kind)).toEqual(["user", "stopped"]);
    expect(s.running).toBe(false);
  });

  it("status events after the outcome are ignored", () => {
    const s = run([
      { type: "send", text: "q" },
      { type: "event", event: { type: "answer", text: "A", checked: 1, sources: [], general: false, news: null } },
      { type: "event", event: { type: "status", stage: "verifying", tool: null } },
    ]);
    expect(s.progress).toBeNull();
  });

  it("a request failure before the stream records the code", () => {
    const s = run([{ type: "send", text: "q" }, { type: "failed", code: "HTTP_404", detail: null }]);
    expect(s.turns[1]).toMatchObject({ kind: "error", code: "HTTP_404" });
  });

  it("keeps the conversation id across turns and clears it on reset", () => {
    const s = run([
      { type: "send", text: "q" },
      { type: "event", event: { type: "meta", conversation_id: "c1", model: null, web_search: null } },
      { type: "event", event: { type: "answer", text: "A", checked: 0, sources: [], general: false, news: null } },
      { type: "send", text: "q2" },
    ]);
    expect(s.conversationId).toBe("c1");
    expect(s.turns.map((t) => t.id)).toEqual([1, 2, 3]);
    expect(chatReducer(s, { type: "reset" })).toEqual(INITIAL_CHAT);
  });

  it("a meta event without a conversation id (explain) keeps the current one", () => {
    const s = run([
      { type: "event", event: { type: "meta", conversation_id: "c1", model: null, web_search: null } },
      { type: "event", event: { type: "meta", conversation_id: null, model: "m", web_search: null } },
    ]);
    expect(s.conversationId).toBe("c1");
  });
});

describe("general answers, news and provider reasons", () => {
  it("carries general, news and sources onto the answer turn", () => {
    const s = run([
      { type: "send", text: "q" },
      {
        type: "event",
        event: {
          type: "answer",
          text: "A",
          checked: 0,
          general: true,
          news: "refused",
          sources: [{ tool: "web", url: "https://a.com/x", title: "A" }],
        },
      },
    ]);
    expect(s.turns[1]).toMatchObject({ kind: "answer", general: true, news: "refused" });
    expect(s.turns[1]).toMatchObject({ sources: [{ tool: "web", url: "https://a.com/x" }] });
  });

  it("carries news onto an unverified notice", () => {
    const s = run([
      { type: "send", text: "q" },
      { type: "event", event: { type: "unverified", checked: 1, unverified: ["9%"], sources: [], news: "unsupported" } },
    ]);
    expect(s.turns[1]).toMatchObject({ kind: "unverified", news: "unsupported" });
  });

  it("keeps the provider reason on an error turn", () => {
    const s = run([
      { type: "send", text: "q" },
      { type: "event", event: { type: "error", code: "PROVIDER_ERROR", detail: "model x", reason: "quota" } },
    ]);
    expect(s.turns[1]).toMatchObject({ kind: "error", code: "PROVIDER_ERROR", reason: "quota" });
  });

  it("stored answers read general and news from the verification JSON", () => {
    const turns = turnsFromConversation({
      id: "c1",
      title: "t",
      ticker: null,
      messages: [
        { role: "assistant", content: "A", status: "answered", model: "m", verification: { general: true }, created_at: "x" },
        { role: "assistant", content: "B", status: "answered", model: "m", verification: { general: "yes", news: "maybe" }, created_at: "x" },
        { role: "assistant", content: "C", status: "answered", model: "m", verification: { checked: 1, news: "refused" }, created_at: "x" },
        { role: "assistant", content: "", status: "unverified", model: "m", verification: { news: "unsupported" }, created_at: "x" },
      ],
    });
    expect(turns[0]).toMatchObject({ general: true, news: null, checked: null });
    expect(turns[1]).toMatchObject({ general: false, news: null });
    expect(turns[2]).toMatchObject({ news: "refused" });
    expect(turns[3]).toMatchObject({ kind: "unverified", news: "unsupported" });
  });
});

describe("turnsFromConversation", () => {
  it("maps stored messages by status", () => {
    const turns = turnsFromConversation({
      id: "c1",
      title: "t",
      ticker: "COMI",
      messages: [
        { role: "user", content: "q", status: null, model: null, verification: null, created_at: "2026-10-30T10:00:00Z" },
        {
          role: "assistant",
          content: "A",
          status: "answered",
          model: "m",
          verification: { verified: true, checked: 5 },
          created_at: "2026-10-30T10:00:01Z",
        },
        { role: "assistant", content: "", status: "unverified", model: "m", verification: { unverified: ["9%"] }, created_at: "x" },
        { role: "assistant", content: "", status: "cap_reached", model: null, verification: null, created_at: "x" },
        { role: "assistant", content: "", status: "error", model: null, verification: "weird", created_at: "x" },
      ],
    });
    expect(turns.map((t) => t.kind)).toEqual(["user", "answer", "unverified", "error", "error"]);
    expect(turns[1]).toMatchObject({ checked: 5, model: "m" });
    expect(turns[2]).toMatchObject({ unverified: ["9%"] });
    expect(turns[3]).toMatchObject({ code: "CAP_REACHED" });
    expect(turns.map((t) => t.id)).toEqual([1, 2, 3, 4, 5]);
  });

  it("load continues numbering after the stored turns", () => {
    const s = chatReducer(INITIAL_CHAT, { type: "load", turns: [{ id: 1, kind: "user", text: "q" }], conversationId: "c1" });
    expect(s.nextId).toBe(2);
    expect(s.conversationId).toBe("c1");
  });
});
