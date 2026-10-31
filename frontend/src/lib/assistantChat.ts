import type {
  AssistantConversation,
  AssistantNews,
  AssistantProviderReason,
  AssistantSource,
  AssistantStage,
  AssistantStreamEvent,
} from "../types";
import { newsOf } from "./assistant";

/** Pure chat state for the assistant view (R49): the stream events fold into a list of turns. */

export type ChatTurn =
  | { id: number; kind: "user"; text: string }
  | {
      id: number;
      kind: "answer";
      text: string;
      checked: number | null;
      sources: AssistantSource[];
      model: string | null;
      /** General information, not checked against our data. */
      general: boolean;
      /** Whether news was checked (R50 B16); null when unknown (stored conversations). */
      news: AssistantNews | null;
    }
  | { id: number; kind: "unverified"; checked: number | null; unverified: string[]; sources: AssistantSource[]; news: AssistantNews | null }
  | { id: number; kind: "error"; code: string; detail: string | null; reason: AssistantProviderReason | null }
  | { id: number; kind: "stopped" };

export interface ChatProgress {
  stage: AssistantStage;
  tool: string | null;
}

export interface ChatState {
  turns: ChatTurn[];
  conversationId: string | null;
  /** Model the server reported for the running request. */
  model: string | null;
  /** True from send until the answer, unverified notice, error or Stop. */
  running: boolean;
  progress: ChatProgress | null;
  nextId: number;
}

export type ChatAction =
  | { type: "send"; text: string }
  | { type: "event"; event: AssistantStreamEvent }
  | { type: "failed"; code: string; detail: string | null }
  | { type: "closed" }
  | { type: "stopped" }
  | { type: "reset" }
  | { type: "load"; turns: ChatTurn[]; conversationId: string | null };

export const INITIAL_CHAT: ChatState = {
  turns: [],
  conversationId: null,
  model: null,
  running: false,
  progress: null,
  nextId: 1,
};

function push(state: ChatState, turn: (id: number) => ChatTurn): ChatState {
  return { ...state, turns: [...state.turns, turn(state.nextId)], nextId: state.nextId + 1 };
}

function settle(state: ChatState): ChatState {
  return { ...state, running: false, progress: null };
}

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "send":
      return {
        ...push(state, (id) => ({ id, kind: "user", text: action.text })),
        running: true,
        progress: { stage: "thinking", tool: null },
        model: null,
      };
    case "event": {
      const e = action.event;
      switch (e.type) {
        case "meta":
          return {
            ...state,
            conversationId: e.conversation_id ?? state.conversationId,
            model: e.model ?? state.model,
          };
        case "status":
          return state.running ? { ...state, progress: { stage: e.stage, tool: e.tool } } : state;
        case "answer":
          return settle(
            push(state, (id) => ({
              id,
              kind: "answer",
              text: e.text,
              checked: e.checked,
              sources: e.sources,
              model: state.model,
              general: e.general,
              news: e.news,
            })),
          );
        case "unverified":
          return settle(
            push(state, (id) => ({ id, kind: "unverified", checked: e.checked, unverified: e.unverified, sources: e.sources, news: e.news })),
          );
        case "error":
          return settle(push(state, (id) => ({ id, kind: "error", code: e.code, detail: e.detail, reason: e.reason })));
        case "done":
          return state;
      }
      return state;
    }
    case "failed":
      return settle(push(state, (id) => ({ id, kind: "error", code: action.code, detail: action.detail, reason: null })));
    case "closed":
      // The stream ended without an answer, notice or error: never leave the view waiting.
      return state.running ? settle(push(state, (id) => ({ id, kind: "error", code: "STREAM_INTERRUPTED", detail: null, reason: null }))) : state;
    case "stopped":
      return state.running ? settle(push(state, (id) => ({ id, kind: "stopped" }))) : state;
    case "reset":
      return INITIAL_CHAT;
    case "load":
      return {
        ...INITIAL_CHAT,
        turns: action.turns,
        conversationId: action.conversationId,
        nextId: action.turns.reduce((max, t) => Math.max(max, t.id), 0) + 1,
      };
  }
}

function isRec(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** Stored verification JSON is backend-owned: read what is there, assume nothing. */
function verificationOf(v: unknown): { checked: number | null; unverified: string[]; general: boolean; news: AssistantNews | null } {
  if (!isRec(v)) return { checked: null, unverified: [], general: false, news: null };
  const checked = typeof v.checked === "number" && Number.isFinite(v.checked) ? v.checked : null;
  const unverified = Array.isArray(v.unverified) ? v.unverified.filter((x): x is string => typeof x === "string") : [];
  return { checked, unverified, general: v.general === true, news: newsOf(v.news) };
}

/** Turns for a stored conversation (GET /conversations/{id}). */
export function turnsFromConversation(conversation: AssistantConversation): ChatTurn[] {
  return conversation.messages.map((m, i): ChatTurn => {
    const id = i + 1;
    if (m.role === "user") return { id, kind: "user", text: m.content };
    const v = verificationOf(m.verification);
    if (m.status === "unverified") return { id, kind: "unverified", checked: v.checked, unverified: v.unverified, sources: [], news: v.news };
    if (m.status === "cap_reached") return { id, kind: "error", code: "CAP_REACHED", detail: null, reason: null };
    if (m.status === "error") return { id, kind: "error", code: "PROVIDER_ERROR", detail: null, reason: null };
    return { id, kind: "answer", text: m.content, checked: v.checked, sources: [], model: m.model, general: v.general, news: v.news };
  });
}
