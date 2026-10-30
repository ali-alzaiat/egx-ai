import type { ReactNode } from "react";
import { Badge } from "@/components/shadcn/badge";
import { useLang } from "../../i18n/useLang";
import { fmtCycle } from "../../lib/format";
import type { ShariahStatus } from "../../types";
import { BarIcon, TriangleDownIcon, TriangleUpIcon } from "./icons";

/** Neutral tag: "Provisional", "Low liquidity", "EGX33 member", tiers (spec 3.7). */
export function Tag({ children, title }: { children: ReactNode; title?: string }) {
  return <Badge title={title}>{children}</Badge>;
}

export type StanceCode = "buy" | "hold" | "reduce";

/**
 * "Not assessed" when no stance exists, when coverage is zero, or when the API
 * returned the default hold with no confidence and no reasons (QA F5).
 */
export function isNotAssessed(
  stance: StanceCode | null | undefined,
  confidence: number | null | undefined,
  reasonsCount: number | null | undefined,
): boolean {
  if (!stance) return true;
  return confidence === 0 && reasonsCount === 0;
}

const STANCE_VIEW = {
  buy: { key: "stance_buy", variant: "gain", Icon: TriangleUpIcon },
  hold: { key: "stance_hold", variant: "neutral", Icon: BarIcon },
  reduce: { key: "stance_reduce", variant: "loss", Icon: TriangleDownIcon },
} as const;

/**
 * Stance as a shape plus a word that never reads as an instruction (spec 5.1).
 * The internal codes and R42 thresholds are untouched; only labels differ.
 */
export function StanceBadge({
  stance,
  confidence,
  reasonsCount,
  rules,
}: {
  stance: StanceCode | null | undefined;
  confidence?: number | null;
  reasonsCount?: number | null;
  rules?: string | null;
}) {
  const { t } = useLang();
  if (!stance || isNotAssessed(stance, confidence, reasonsCount)) {
    return (
      <Badge variant="none" title={t("stance_not_assessed_tooltip")}>
        {t("stance_not_assessed")}
      </Badge>
    );
  }
  const view = STANCE_VIEW[stance];
  const title = t("stance_tooltip", { rules: rules ?? "", c: confidence ?? 0 });
  return (
    <Badge variant={view.variant} title={title}>
      <view.Icon size={12} />
      {t(view.key)}
    </Badge>
  );
}

const VERDICT_VIEW = {
  COMPLIANT: { key: "shariah_compliant", variant: "accent" },
  NON_COMPLIANT: { key: "shariah_non_compliant", variant: "warn" },
  INSUFFICIENT_DATA: { key: "shariah_insufficient", variant: "muted" },
  NOT_SCREENED: { key: "shariah_not_screened", variant: "outline" },
} as const;

/** Our verdict. Never gain/loss colours, so a pass is not read as a price gain (spec 5.2). */
export function ShariahBadge({
  verdict,
  provisional = false,
}: {
  verdict: ShariahStatus["verdict"];
  provisional?: boolean;
}) {
  const { t } = useLang();
  const view = VERDICT_VIEW[verdict];
  return (
    <span className="shariah-pair">
      <Badge variant={view.variant}>{t(view.key)}</Badge>
      {provisional && <Tag>{t("shariah_provisional")}</Tag>}
    </span>
  );
}

/** EGX33 membership line, shown beside (never merged with) our verdict. */
export function Egx33Note({ shariah }: { shariah: ShariahStatus }) {
  const { t, locale } = useLang();
  if (shariah.egx33 === "member") {
    const cycle = fmtCycle(locale, shariah.egx33_review_cycle) ?? shariah.egx33_review_cycle ?? "";
    return <Tag>{t("shariah_egx33_member", { cycle })}</Tag>;
  }
  if (shariah.egx33 === "not_member") return <span className="text-note">{t("shariah_egx33_not_member")}</span>;
  return <span className="text-note">{t("shariah_egx33_unknown")}</span>;
}

/** Compact form for tables and the hub header: "{our verdict} · EGX33 {member|—}". */
export function ShariahPair({ shariah }: { shariah: ShariahStatus | null | undefined }) {
  const { t } = useLang();
  if (!shariah) return <ShariahBadge verdict="NOT_SCREENED" />;
  const egx33 =
    shariah.egx33 === "member" ? (
      <span>EGX33 {t("shariah_member")}</span>
    ) : (
      <span
        title={shariah.egx33 === "not_member" ? t("shariah_egx33_not_member") : t("shariah_egx33_unknown")}
      >
        EGX33 —
      </span>
    );
  return (
    <span className="shariah-pair">
      <ShariahBadge verdict={shariah.verdict} />
      <span className="text-note">·</span>
      <span className="text-note">{egx33}</span>
    </span>
  );
}
