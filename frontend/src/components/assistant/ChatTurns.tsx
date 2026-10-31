import { memo } from "react";
import { Link } from "react-router-dom";
import { Alert } from "@/components/shadcn/alert";
import { Badge } from "@/components/shadcn/badge";
import { useLang } from "../../i18n/useLang";
import { parseAnswer, type Inline } from "../../lib/answerText";
import { assistantErrorCopy, sourceHref, toolKey, uniqueSources } from "../../lib/assistant";
import type { ChatTurn } from "../../lib/assistantChat";
import type { AssistantSource } from "../../types";
import { ForeignText } from "../../pages/shared/ForeignText";
import { CheckIcon, WarningIcon } from "../ui/icons";

function Inlines({ items }: { items: readonly Inline[] }) {
  return (
    <>
      {items.map((part, i) => (part.bold ? <strong key={i}>{part.text}</strong> : <span key={i}>{part.text}</span>))}
    </>
  );
}

/** Model text as paragraphs, lists and bold; built from React elements, never from HTML. */
function AnswerBody({ text }: { text: string }) {
  return (
    <div className="flex flex-col gap-2 text-ui text-foreground">
      {parseAnswer(text).map((block, i) => {
        switch (block.kind) {
          case "h":
            return (
              <p key={i} dir="auto" className="font-semibold">
                <Inlines items={block.inlines} />
              </p>
            );
          case "ul":
            return (
              <ul key={i} dir="auto" className="list-disc ps-5">
                {block.items.map((item, j) => (
                  <li key={j}>
                    <Inlines items={item} />
                  </li>
                ))}
              </ul>
            );
          case "ol":
            return (
              <ol key={i} dir="auto" className="list-decimal ps-5">
                {block.items.map((item, j) => (
                  <li key={j}>
                    <Inlines items={item} />
                  </li>
                ))}
              </ol>
            );
          case "p":
            return (
              <p key={i} dir="auto" className="whitespace-pre-line">
                <Inlines items={block.inlines} />
              </p>
            );
        }
      })}
    </div>
  );
}

function SourceChips({ sources, onNavigate }: { sources: readonly AssistantSource[]; onNavigate?: () => void }) {
  const { t } = useLang();
  const unique = uniqueSources(sources);
  if (unique.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-meta text-muted-foreground">{t("assistant_sources")}</span>
      {unique.map((source) => {
        const key = toolKey(source.tool);
        const name = key ? t(key) : source.tool;
        const label = (
          <>
            {name}
            {source.ticker ? <span dir="ltr"> · {source.ticker}</span> : null}
          </>
        );
        const href = sourceHref(source);
        const chip =
          "inline-flex min-h-8 items-center rounded-full border border-border bg-secondary px-3 text-meta text-text-2 no-underline";
        return href ? (
          <Link key={`${source.tool}|${source.ticker ?? ""}`} to={href} onClick={onNavigate} className={`${chip} hover:bg-accent hover:text-foreground`}>
            {label}
          </Link>
        ) : (
          <span key={`${source.tool}|${source.ticker ?? ""}`} className={chip}>
            {label}
          </span>
        );
      })}
    </div>
  );
}

function CheckedNote({ checked }: { checked: number | null }) {
  const { t } = useLang();
  if (checked === null) return null;
  return checked > 0 ? (
    <p className="flex items-center gap-1.5 text-meta text-gain">
      <CheckIcon size={14} />
      <span>{t("assistant_checked", { n: checked })}</span>
    </p>
  ) : (
    <p className="text-meta text-muted-foreground">{t("assistant_checked_none")}</p>
  );
}

function ErrorTurn({ code, detail, onNavigate }: { code: string; detail: string | null; onNavigate?: () => void }) {
  const { t } = useLang();
  const copy = assistantErrorCopy(code);
  const showDetail = detail !== null && detail.trim() !== "" && !copy.settings;
  return (
    <Alert variant={copy.settings ? "warning" : "destructive"} role="alert">
      <WarningIcon size={20} />
      <div className="flex min-w-0 flex-col gap-2">
        <p dir="auto">{t(copy.key)}</p>
        {copy.settings && (
          <Link to="/admin/ai" onClick={onNavigate} className="font-semibold text-primary">
            {t("assistant_open_settings")}
          </Link>
        )}
        {showDetail && (
          <details className="text-meta text-text-2">
            <summary className="cursor-pointer">{t("assistant_error_details")}</summary>
            <p className="mt-1 break-words">
              <ForeignText>{detail.trim().slice(0, 300)}</ForeignText>
            </p>
          </details>
        )}
      </div>
    </Alert>
  );
}

/** One entry of the conversation. Memoised: turns are immutable, so a progress tick rerenders none of them. */
export const TurnView = memo(function TurnView({ turn, onNavigate }: { turn: ChatTurn; onNavigate?: () => void }) {
  const { t } = useLang();
  switch (turn.kind) {
    case "user":
      return (
        <div dir="auto" className="max-w-[88%] self-end whitespace-pre-wrap break-words rounded-md bg-brand-bg px-3 py-2 text-ui text-foreground">
          {turn.text}
        </div>
      );
    case "answer":
      return (
        <article className="flex flex-col gap-3 rounded-md border border-border bg-card p-3" aria-label={t("assistant_assistant")}>
          <AnswerBody text={turn.text} />
          <CheckedNote checked={turn.checked} />
          <SourceChips sources={turn.sources} onNavigate={onNavigate} />
        </article>
      );
    case "unverified":
      return (
        <Alert variant="warning" role="alert">
          <WarningIcon size={20} />
          <div className="flex min-w-0 flex-col gap-2">
            <p className="font-semibold">{t("assistant_unverified_title")}</p>
            <p>{t("assistant_unverified_body")}</p>
            {turn.unverified.length > 0 && (
              <p className="text-meta">
                {t("assistant_unverified_list")}{" "}
                <span dir="ltr" className="font-semibold">
                  {turn.unverified.join(", ")}
                </span>
              </p>
            )}
            <SourceChips sources={turn.sources} onNavigate={onNavigate} />
          </div>
        </Alert>
      );
    case "error":
      return <ErrorTurn code={turn.code} detail={turn.detail} onNavigate={onNavigate} />;
    case "stopped":
      return <Badge variant="muted" className="self-start">{t("assistant_stopped")}</Badge>;
  }
});
