import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { Alert } from "@/components/shadcn/alert";
import { Button } from "@/components/shadcn/button";
import { useAssistantModels } from "../../api/client";
import { useLang } from "../../i18n/useLang";
import { pickModel, toolKey } from "../../lib/assistant";
import type { ChatProgress } from "../../lib/assistantChat";
import { SparkleIcon } from "../ui/icons";
import { TurnView } from "./ChatTurns";
import type { AssistantChat } from "./useAssistantChat";

export interface ChatViewProps {
  chat: AssistantChat;
  /** Company the chat is about; null for general questions. */
  ticker: string | null;
  modelChoice: string | null;
  /** The user picked a model (persist it). */
  onModelPick: (id: string) => void;
  /** The model in use was resolved from the server list (do not persist). */
  onModelResolved: (id: string) => void;
  /** A link inside the chat was followed (the phone panel closes to show the page). */
  onNavigate?: () => void;
  /** Autofocus the question box when the view appears. */
  autoFocus?: boolean;
  className?: string;
}

function ProgressLine({ progress }: { progress: ChatProgress }) {
  const { t } = useLang();
  let text: string;
  switch (progress.stage) {
    case "tool": {
      const key = progress.tool ? toolKey(progress.tool) : null;
      text = key ? t("assistant_progress_tool", { tool: t(key) }) : t("assistant_progress_tool_plain");
      break;
    }
    case "verifying":
      text = t("assistant_progress_verifying");
      break;
    case "retrying":
      text = t("assistant_progress_retrying");
      break;
    default:
      text = t("assistant_progress_thinking");
  }
  return (
    <p role="status" className="flex items-center gap-2 text-table text-text-2">
      <span aria-hidden="true" className="size-2 animate-pulse rounded-full bg-primary motion-reduce:animate-none" />
      <span>{text}</span>
    </p>
  );
}

/** The chat itself, shared by the side panel and the /assistant page. */
export function ChatView({ chat, ticker, modelChoice, onModelPick, onModelResolved, onNavigate, autoFocus = false, className = "" }: ChatViewProps) {
  const { t } = useLang();
  const { state, send, stop } = chat;
  const modelsQuery = useAssistantModels();
  const models = modelsQuery.data;
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const modelId = useId();

  const selected = models ? pickModel(models.models, models.default_model, modelChoice) : modelChoice;
  const available = models ? models.models.filter((m) => m.available) : [];
  const noModels = models !== undefined && available.length === 0;

  useEffect(() => {
    if (selected !== null && selected !== modelChoice) onModelResolved(selected);
  }, [selected, modelChoice, onModelResolved]);

  useEffect(() => {
    if (autoFocus) inputRef.current?.focus();
  }, [autoFocus]);

  // Keep the newest turn in view: the start of an answer (so it reads from the top), the end for everything else.
  const turnCount = state.turns.length;
  const lastKind = state.turns[turnCount - 1]?.kind;
  useEffect(() => {
    const last = listRef.current?.lastElementChild;
    if (turnCount === 0 || !(last instanceof HTMLElement)) return;
    last.scrollIntoView({ block: lastKind === "user" ? "end" : "start" });
  }, [turnCount, lastKind]);

  const submit = (): void => {
    if (state.running || noModels || draft.trim() === "") return;
    send(draft);
    setDraft("");
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>): void => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className={`flex min-h-0 flex-1 flex-col gap-3 ${className}`}>
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor={modelId} className="text-table font-medium text-text-2">
          {t("assistant_model")}
        </label>
        <select
          id={modelId}
          value={selected ?? ""}
          disabled={available.length === 0}
          onChange={(e) => onModelPick(e.target.value)}
          className="h-11 min-w-0 max-w-full flex-1 rounded-sm border border-input bg-card px-3 text-ui text-foreground disabled:opacity-60"
        >
          {available.length === 0 && <option value="">{t("assistant_model_none")}</option>}
          {available.map((m) => (
            <option key={m.id} value={m.id}>
              {m.web_search ? t("assistant_model_searches", { label: m.label }) : m.label}
            </option>
          ))}
        </select>
      </div>

      {noModels && (
        <Alert variant="warning" role="note">
          <div className="flex flex-col gap-2">
            <p>{t("assistant_no_models")}</p>
            <Link to="/admin/ai" onClick={onNavigate} className="font-semibold text-primary">
              {t("assistant_set_key")}
            </Link>
          </div>
        </Alert>
      )}
      {modelsQuery.isError && <p className="text-meta text-muted-foreground">{t("assistant_models_error")}</p>}

      <div
        ref={listRef}
        role="log"
        aria-live="polite"
        aria-label={t("assistant_title")}
        className="flex min-h-40 flex-1 flex-col gap-3 overflow-y-auto overscroll-contain pe-1"
      >
        {state.turns.length === 0 ? (
          <div className="m-auto flex max-w-sm flex-col items-center gap-2 py-6 text-center text-text-2">
            <SparkleIcon size={24} />
            <p className="font-semibold text-foreground">{t("assistant_empty_title")}</p>
            <p className="text-table">
              {ticker ? t("assistant_empty_company", { ticker }) : t("assistant_empty_general")}
            </p>
          </div>
        ) : (
          state.turns.map((turn) => <TurnView key={turn.id} turn={turn} onNavigate={onNavigate} />)
        )}
      </div>

      {state.progress && <ProgressLine progress={state.progress} />}

      <form
        className="flex flex-col gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <label htmlFor={`${modelId}-q`} className="sr-only">
          {t("assistant_input_label")}
        </label>
        <textarea
          id={`${modelId}-q`}
          ref={inputRef}
          value={draft}
          rows={2}
          maxLength={4000}
          disabled={noModels}
          dir="auto"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={ticker ? t("assistant_input_placeholder_company", { ticker }) : t("assistant_input_placeholder")}
          className="min-h-11 w-full resize-none rounded-sm border border-input bg-card px-3 py-2 text-ui text-foreground placeholder:text-muted-foreground disabled:opacity-60"
        />
        <div className="flex items-center justify-between gap-3">
          <p className="text-meta text-muted-foreground">{t("assistant_disclaimer")}</p>
          {state.running ? (
            <Button variant="outline" onClick={stop}>
              {t("assistant_stop")}
            </Button>
          ) : (
            <Button type="submit" disabled={noModels || draft.trim() === ""}>
              {t("assistant_send")}
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}
