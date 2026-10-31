import { useCallback, useEffect, useMemo, useReducer, useRef } from "react";
import { AssistantApiError, streamAssistant, useRefreshAssistantData } from "../../api/client";
import { httpErrorCode } from "../../lib/assistant";
import { INITIAL_CHAT, chatReducer, type ChatState, type ChatTurn } from "../../lib/assistantChat";
import type { AssistantCard, AssistantChatRequest, AssistantExplainRequest, AssistantLang } from "../../types";

export interface ChatOptions {
  /** Company the chat is scoped to; null for general questions. */
  ticker: string | null;
  lang: AssistantLang;
  /** Chosen model id; null lets the server use its default. */
  model: string | null;
}

export interface ChatInitial {
  turns: ChatTurn[];
  conversationId: string | null;
}

export interface AssistantChat {
  state: ChatState;
  send: (text: string) => void;
  /** Run an Explain card; `label` is the line shown as the question. */
  explain: (ticker: string, card: AssistantCard, label: string) => void;
  stop: () => void;
  reset: () => void;
}

/**
 * One assistant conversation: folds the SSE stream into `ChatState`. Callbacks are stable (they read the latest
 * options from a ref), so buttons that only start a request never rerender while an answer streams. Only the
 * newest request may change state; an older stream that is still closing is ignored.
 */
export function useAssistantChat(options: ChatOptions, initial?: ChatInitial): AssistantChat {
  const [state, dispatch] = useReducer(chatReducer, initial, (init) =>
    init ? chatReducer(INITIAL_CHAT, { type: "load", turns: init.turns, conversationId: init.conversationId }) : INITIAL_CHAT,
  );
  const refresh = useRefreshAssistantData();

  const latest = useRef({ options, conversationId: state.conversationId, refresh });
  useEffect(() => {
    latest.current = { options, conversationId: state.conversationId, refresh };
  });
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      controllerRef.current?.abort();
      controllerRef.current = null;
    },
    [],
  );

  const run = useCallback((path: "/chat" | "/explain", body: AssistantChatRequest | AssistantExplainRequest, question: string): void => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const live = (): boolean => controllerRef.current === controller;
    dispatch({ type: "send", text: question });
    streamAssistant(
      path,
      body,
      (event) => {
        if (!live()) return;
        dispatch({ type: "event", event });
        if (event.type === "done") latest.current.refresh();
      },
      controller.signal,
    )
      .then(() => {
        if (live()) dispatch({ type: "closed" });
      })
      .catch((err: unknown) => {
        if (!live()) return;
        if (err instanceof AssistantApiError) {
          dispatch({ type: "failed", code: httpErrorCode(err.status, err.code), detail: err.detail });
        } else {
          dispatch({ type: "failed", code: "NETWORK", detail: null });
        }
      });
  }, []);

  const send = useCallback(
    (text: string): void => {
      const message = text.trim();
      if (message === "") return;
      const { options: o, conversationId } = latest.current;
      const body: AssistantChatRequest = { message, lang: o.lang };
      if (conversationId) body.conversation_id = conversationId;
      if (o.model) body.model = o.model;
      if (o.ticker) body.ticker = o.ticker;
      run("/chat", body, message);
    },
    [run],
  );

  const explain = useCallback(
    (ticker: string, card: AssistantCard, label: string): void => {
      const { options: o } = latest.current;
      const body: AssistantExplainRequest = { ticker, card, lang: o.lang };
      if (o.model) body.model = o.model;
      run("/explain", body, label);
    },
    [run],
  );

  const stop = useCallback((): void => {
    if (controllerRef.current === null) return;
    controllerRef.current.abort();
    controllerRef.current = null;
    dispatch({ type: "stopped" });
  }, []);

  const reset = useCallback((): void => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    dispatch({ type: "reset" });
  }, []);

  return useMemo(() => ({ state, send, explain, stop, reset }), [state, send, explain, stop, reset]);
}
