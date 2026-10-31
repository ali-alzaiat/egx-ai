import { useEffect, useRef, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { Badge } from "@/components/shadcn/badge";
import { Button } from "@/components/shadcn/button";
import { useLang } from "../../i18n/useLang";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { CloseIcon, SparkleIcon } from "../ui/icons";
import { useAssistantPanel } from "./assistantContext";
import { ChatView } from "./ChatView";

/** The non-modal side panel (inline-end edge; full screen on phones). Loaded on first open. */
export default function AssistantPanel({ onClose, visible }: { onClose: () => void; visible: boolean }) {
  const { t } = useLang();
  const { ticker, chat, modelChoice, pickModel, resolveModel } = useAssistantPanel();
  const phone = useMediaQuery("(max-width: 767px)");
  const rootRef = useRef<HTMLDivElement>(null);
  const wasVisible = useRef(false);

  // Move focus into the panel when it opens, so keyboard users land on the question box.
  useEffect(() => {
    if (visible && !wasVisible.current) rootRef.current?.querySelector<HTMLElement>("textarea")?.focus();
    wasVisible.current = visible;
  }, [visible]);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>): void => {
    if (e.key === "Escape" && !e.defaultPrevented) {
      e.stopPropagation();
      onClose();
    }
  };

  return (
    <div
      ref={rootRef}
      role="dialog"
      aria-modal="false"
      aria-label={t("assistant_panel_aria")}
      onKeyDown={onKeyDown}
      className={`${visible ? "flex" : "hidden"} fixed inset-y-0 end-0 z-[35] w-full flex-col gap-3 border-s border-border bg-background p-4 pb-[max(1rem,env(safe-area-inset-bottom))] shadow-pop md:w-[420px]`}
    >
      <div className="flex items-center gap-2">
        <SparkleIcon size={18} />
        <h2 className="flex-1 text-h3 font-semibold">{t("assistant_title")}</h2>
        <Button variant="ghost" size="sm" onClick={chat.reset} disabled={chat.state.turns.length === 0 && !chat.state.running}>
          {t("assistant_new_chat")}
        </Button>
        <Button variant="ghost" size="icon" className="size-9" aria-label={t("assistant_close")} onClick={onClose}>
          <CloseIcon size={18} />
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={ticker ? "accent" : "muted"}>
          {ticker ? <span dir="auto">{t("assistant_scope", { ticker })}</span> : t("assistant_scope_none")}
        </Badge>
        <Link to="/assistant" onClick={onClose} className="text-meta font-semibold text-primary">
          {t("assistant_open_page")}
        </Link>
      </div>
      <ChatView
        chat={chat}
        ticker={ticker}
        modelChoice={modelChoice}
        onModelPick={pickModel}
        onModelResolved={resolveModel}
        // On a phone the panel covers the page, so following a link closes it; on a wide screen it stays beside the page.
        onNavigate={phone ? onClose : undefined}
        autoFocus={false}
      />
    </div>
  );
}
