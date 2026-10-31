import { useEffect, useState } from "react";
import { Button } from "@/components/shadcn/button";
import { Badge } from "@/components/shadcn/badge";
import { useConversation, useConversations, useDeleteConversation } from "../api/client";
import { ChatView } from "../components/assistant/ChatView";
import { useAssistantChat } from "../components/assistant/useAssistantChat";
import { useModelChoice } from "../components/assistant/useModelChoice";
import { PageHeader } from "../components/ui/PageHeader";
import { PageTitle } from "../components/ui/PageTitle";
import { ErrorState, LoadingState } from "../components/ui/States";
import { useLang } from "../i18n/useLang";
import { turnsFromConversation } from "../lib/assistantChat";
import { fmtDate } from "../lib/format";
import type { AssistantConversation } from "../types";
import { FormMessage } from "./shared/FormMessage";

/** One chat. Remounted (by key) whenever the user starts a new chat or opens a saved one. */
function ChatSession({
  conversation,
  onConversationId,
}: {
  conversation: AssistantConversation | null;
  onConversationId: (id: string | null) => void;
}) {
  const { lang } = useLang();
  const { modelChoice, pick, resolve } = useModelChoice();
  const chat = useAssistantChat(
    { ticker: conversation?.ticker ?? null, lang, model: modelChoice },
    conversation ? { turns: turnsFromConversation(conversation), conversationId: conversation.id } : undefined,
  );
  const conversationId = chat.state.conversationId;
  useEffect(() => {
    onConversationId(conversationId);
  }, [conversationId, onConversationId]);

  return (
    <ChatView
      chat={chat}
      ticker={conversation?.ticker ?? null}
      modelChoice={modelChoice}
      onModelPick={pick}
      onModelResolved={resolve}
      autoFocus
    />
  );
}

/** Opens a saved conversation: loads it, then hands it to a ChatSession. */
function SavedChat({ id, onConversationId }: { id: string; onConversationId: (id: string | null) => void }) {
  const { t } = useLang();
  const query = useConversation(id);
  if (query.isLoading) return <LoadingState thing={t("assistant_conversation_loading")} />;
  if (query.isError || !query.data) {
    return <ErrorState thing={t("assistant_conversation_loading")} onRetry={() => void query.refetch()} />;
  }
  return <ChatSession conversation={query.data} onConversationId={onConversationId} />;
}

function ConversationList({
  activeId,
  onOpen,
  onDeleted,
}: {
  activeId: string | null;
  onOpen: (id: string) => void;
  onDeleted: (id: string) => void;
}) {
  const { t, locale } = useLang();
  const query = useConversations();
  const remove = useDeleteConversation();

  if (query.isLoading) return <LoadingState thing={t("assistant_conversations_thing")} />;
  if (query.isError) return <ErrorState thing={t("assistant_conversations_thing")} onRetry={() => void query.refetch()} />;
  const items = query.data ?? [];
  if (items.length === 0) return <p className="empty">{t("assistant_conversations_empty")}</p>;

  return (
    <div className="flex flex-col gap-2">
      {remove.isError && <FormMessage kind="error" text={t("assistant_delete_failed")} />}
      <ul className="flex flex-col gap-1">
        {items.map((c) => {
          const title = c.title.trim() === "" ? t("assistant_untitled") : c.title;
          const date = fmtDate(locale, c.updated_at);
          return (
            <li key={c.id} className="flex items-stretch gap-1">
              <button
                type="button"
                onClick={() => onOpen(c.id)}
                aria-current={c.id === activeId ? "true" : undefined}
                className="flex min-h-11 min-w-0 flex-1 flex-col items-start justify-center rounded-sm border-0 bg-transparent px-3 py-1.5 text-start hover:bg-accent aria-[current=true]:bg-brand-bg"
              >
                <span dir="auto" className="w-full truncate text-table font-medium text-foreground">
                  {title}
                </span>
                <span className="flex items-center gap-2 text-meta text-muted-foreground">
                  {c.ticker && <Badge variant="muted" className="h-5 px-2">{c.ticker}</Badge>}
                  {date}
                </span>
              </button>
              <Button
                variant="ghost"
                size="sm"
                className="h-auto min-h-11"
                aria-label={t("assistant_delete_aria", { title })}
                disabled={remove.isPending}
                onClick={() => {
                  if (window.confirm(t("assistant_delete_confirm"))) remove.mutate(c.id, { onSuccess: () => onDeleted(c.id) });
                }}
              >
                {t("assistant_delete")}
              </Button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** `/assistant`: general questions across all companies, with the saved conversations beside the chat. */
export default function Assistant() {
  const { t } = useLang();
  const count = useConversations().data?.length ?? 0;
  const [session, setSession] = useState<{ key: number; loadId: string | null }>({ key: 0, loadId: null });
  const [activeId, setActiveId] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);

  const startNew = (): void => {
    setSession((s) => ({ key: s.key + 1, loadId: null }));
    setActiveId(null);
    setHistoryOpen(false);
  };
  const open = (id: string): void => {
    setSession((s) => ({ key: s.key + 1, loadId: id }));
    setActiveId(id);
    setHistoryOpen(false);
  };

  return (
    <div className="page">
      <PageTitle parts={[t("nav_assistant")]} />
      <PageHeader
        title={t("assistant_title")}
        subtitle={t("assistant_page_subtitle")}
        actions={<Button variant="outline" onClick={startNew}>{t("assistant_new_chat")}</Button>}
      />
      <div className="grid min-w-0 gap-4 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <aside aria-label={t("assistant_conversations")} className="flex min-w-0 flex-col gap-2">
          <Button
            variant="outline"
            className="lg:hidden"
            aria-expanded={historyOpen}
            onClick={() => setHistoryOpen((v) => !v)}
          >
            {t("assistant_conversations_count", { n: count })}
          </Button>
          <div className={`${historyOpen ? "block" : "hidden"} lg:block`}>
            <h2 className="mb-2 hidden text-h3 font-semibold lg:block">{t("assistant_conversations")}</h2>
            <ConversationList
              activeId={activeId}
              onOpen={open}
              onDeleted={(id) => {
                if (id === activeId) startNew();
              }}
            />
          </div>
        </aside>
        <section className="flex h-[70dvh] min-h-[28rem] min-w-0 flex-col rounded-md border border-border bg-card p-4">
          {session.loadId ? (
            <SavedChat key={session.key} id={session.loadId} onConversationId={setActiveId} />
          ) : (
            <ChatSession key={session.key} conversation={null} onConversationId={setActiveId} />
          )}
        </section>
      </div>
    </div>
  );
}
