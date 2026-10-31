import { createContext, useContext } from "react";
import type { AssistantCard } from "../../types";
import type { AssistantChat } from "./useAssistantChat";

/**
 * Two contexts on purpose. Actions never change while an answer streams, so the Explain buttons on the cards
 * subscribe only to them; the panel state (open flag, chat) changes often and only the launcher and panel read it.
 */
export interface AssistantActions {
  /** Open the side panel and run Explain for a card of the company page. */
  requestExplain: (ticker: string, card: AssistantCard) => void;
}

export interface AssistantPanelState {
  open: boolean;
  setOpen: (open: boolean) => void;
  /** Ticker of the company page the user is on; the panel chat is scoped to it. */
  ticker: string | null;
  chat: AssistantChat;
  /** Model sent with requests (null = let the server pick its default). */
  modelChoice: string | null;
  /** The user picked a model: use it and remember it. */
  pickModel: (id: string) => void;
  /** The model list resolved a model: use it without remembering it, so a later change of the default still applies. */
  resolveModel: (id: string) => void;
}

export const AssistantActionsContext = createContext<AssistantActions | null>(null);
export const AssistantPanelContext = createContext<AssistantPanelState | null>(null);
/** Only whether the panel is open, for the page layout: it must not re-render with every streamed word of an answer. */
export const AssistantOpenContext = createContext<boolean>(false);

export function useAssistantOpen(): boolean {
  return useContext(AssistantOpenContext);
}

export function useAssistantActions(): AssistantActions {
  const ctx = useContext(AssistantActionsContext);
  if (!ctx) throw new Error("useAssistantActions must be used inside <AssistantProvider>");
  return ctx;
}

export function useAssistantPanel(): AssistantPanelState {
  const ctx = useContext(AssistantPanelContext);
  if (!ctx) throw new Error("useAssistantPanel must be used inside <AssistantProvider>");
  return ctx;
}
