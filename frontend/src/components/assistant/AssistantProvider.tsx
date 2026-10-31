import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { useLang } from "../../i18n/useLang";
import { tickerFromPath } from "../../lib/assistant";
import type { AssistantCard } from "../../types";
import {
  AssistantActionsContext,
  AssistantPanelContext,
  type AssistantActions,
  type AssistantPanelState,
} from "./assistantContext";
import { useAssistantChat } from "./useAssistantChat";
import { useModelChoice } from "./useModelChoice";

const PROMPT_KEY = {
  score: "assistant_explain_prompt_score",
  valuation: "assistant_explain_prompt_valuation",
  stance: "assistant_explain_prompt_stance",
  shariah: "assistant_explain_prompt_shariah",
} as const satisfies Record<AssistantCard, string>;

/**
 * Owns the side-panel chat. It lives above the routes so the conversation survives navigation between tabs and
 * a running answer is not cut off when the panel is closed. Moving to another company starts a fresh chat,
 * because the panel is scoped to the company on screen.
 */
export function AssistantProvider({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const { lang, t } = useLang();
  const ticker = tickerFromPath(pathname);
  const [open, setOpen] = useState(false);
  const { modelChoice, pick: pickModel, resolve: resolveModel } = useModelChoice();

  const chat = useAssistantChat({ ticker, lang, model: modelChoice });
  const { reset, explain } = chat;

  useEffect(() => {
    reset();
  }, [ticker, reset]);

  const requestExplain = useCallback(
    (forTicker: string, card: AssistantCard): void => {
      setOpen(true);
      explain(forTicker, card, t(PROMPT_KEY[card], { ticker: forTicker }));
    },
    [explain, t],
  );

  const actions = useMemo<AssistantActions>(() => ({ requestExplain }), [requestExplain]);
  const panel = useMemo<AssistantPanelState>(
    () => ({ open, setOpen, ticker, chat, modelChoice, pickModel, resolveModel }),
    [open, ticker, chat, modelChoice, pickModel, resolveModel],
  );

  return (
    <AssistantActionsContext.Provider value={actions}>
      <AssistantPanelContext.Provider value={panel}>{children}</AssistantPanelContext.Provider>
    </AssistantActionsContext.Provider>
  );
}
