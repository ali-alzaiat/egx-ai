import { memo } from "react";
import { Button } from "@/components/shadcn/button";
import { useLang } from "../../i18n/useLang";
import type { AssistantCard } from "../../types";
import { SparkleIcon } from "../ui/icons";
import { useAssistantActions } from "./assistantContext";

const CARD_KEY = {
  score: "assistant_card_score",
  valuation: "assistant_card_valuation",
  stance: "assistant_card_stance",
  shariah: "assistant_card_shariah",
  data_check: "assistant_card_data_check",
} as const satisfies Record<AssistantCard, string>;

/** "Explain this" on a result card: opens the side panel and asks the assistant to explain that card's figures. */
export const ExplainButton = memo(function ExplainButton({ card, ticker }: { card: AssistantCard; ticker: string }) {
  const { t } = useLang();
  const { requestExplain } = useAssistantActions();
  return (
    <Button
      variant="outline"
      size="sm"
      className="self-start"
      aria-label={t("assistant_explain_aria", { card: t(CARD_KEY[card]) })}
      onClick={() => requestExplain(ticker, card)}
    >
      <SparkleIcon size={14} />
      {t("assistant_explain")}
    </Button>
  );
});
