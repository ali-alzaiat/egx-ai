/*
 * Pieces shared by the market pages (Dashboard, Recommendations, Companies,
 * Rankings, Shariah list). Visual styling lives in tokens and components/ui;
 * nothing here sets a colour, size or radius.
 */

import { Fragment, type ReactNode } from "react";
import { CompanyName } from "../../components/ui/CompanyName";
import { StanceBadge, Tag, isNotAssessed, type StanceCode } from "../../components/ui/Badges";
import { StockCell, type Column } from "../../components/ui/DataTable";
import { ChevronIcon } from "../../components/ui/icons";
import { useLang } from "../../i18n/useLang";
import { fmtSignedPct, plural } from "../../lib/format";
import { useMediaQuery } from "../../lib/useMediaQuery";
import type { SignalTier } from "../../types";

type Translate = ReturnType<typeof useLang>["t"];

/** Plural noun sets defined in i18n/dict/markets.ts as `<base>_one` … `<base>_other`. */
export type PluralBase =
  | "stocks_count"
  | "matches_count"
  | "no_history_count"
  | "watchlists_count"
  | "unacked_alerts_count"
  | "factors_missing"
  | "hidden_results";

/** "4 stocks" / "سهمان": the right plural form for the active language. */
export function countText(t: Translate, locale: string, n: number, base: PluralBase): string {
  return plural(locale, n, {
    one: t(`${base}_one` as const),
    two: t(`${base}_two` as const),
    few: t(`${base}_few` as const),
    many: t(`${base}_many` as const),
    other: t(`${base}_other` as const),
  });
}

/**
 * Splits a translated sentence at `{name}` markers and puts a node in each
 * marker's place, so word order stays the translator's (links inside prose).
 */
export function RichText({ text, parts }: { text: string; parts: Readonly<Record<string, ReactNode>> }) {
  const pieces = text.split(/(\{\w+\})/g);
  return (
    <>
      {pieces.map((piece, i) => {
        const name = /^\{(\w+)\}$/.exec(piece)?.[1];
        const node = name !== undefined ? parts[name] : undefined;
        return <Fragment key={i}>{node !== undefined ? node : piece}</Fragment>;
      })}
    </>
  );
}

/**
 * On phones the first column becomes line 1 of each card, so the stock column
 * must lead there even when a rank column leads on desktop.
 */
export function stockFirst<T>(columns: readonly Column<T>[], narrow: boolean, stockId = "stock"): Column<T>[] {
  if (!narrow) return [...columns];
  const stock = columns.find((c) => c.id === stockId);
  return stock ? [stock, ...columns.filter((c) => c.id !== stockId)] : [...columns];
}

/** Ticker plus name on one line, linking to `href`. */
export function Stock({
  ticker,
  name,
  nameAr,
  href,
  cardLinked = false,
}: {
  ticker: string;
  name: string;
  nameAr?: string | null;
  href: string;
  /** The table renders phone cards that are links themselves: no nested link there. */
  cardLinked?: boolean;
}) {
  const phone = useMediaQuery("(max-width: 767px)");
  return (
    <StockCell
      ticker={ticker}
      name={<CompanyName name={name} nameAr={nameAr} />}
      href={cardLinked && phone ? undefined : href}
    />
  );
}

/**
 * The stance to display, or null for "Not assessed": no stance, or the
 * zero-confidence default hold that no engine produced (QA F5).
 */
export function assessedStance(
  stance: StanceCode | null | undefined,
  confidence: number | null | undefined,
): StanceCode | null {
  return stance && confidence !== 0 ? stance : null;
}

const TIER_KEY = {
  STRONGEST: "tier_strongest",
  STRONG: "tier_strong",
  NEUTRAL: "tier_neutral",
  WEAK: "tier_weak",
  WEAKEST: "tier_weakest",
} as const satisfies Record<SignalTier, string>;

/** Momentum tier as a neutral, sentence-case tag. */
export function TierTag({ tier }: { tier: SignalTier }) {
  const { t } = useLang();
  return <Tag>{t(TIER_KEY[tier])}</Tag>;
}

export function tierLabel(t: Translate, tier: SignalTier): string {
  return t(TIER_KEY[tier]);
}

/** Stance badge with "28/100" confidence beside it (never a bare number). */
export function StanceWithConfidence({
  stance,
  confidence,
  reasonsCount,
  rules,
}: {
  stance: StanceCode | null | undefined;
  confidence: number | null | undefined;
  reasonsCount?: number | null;
  rules?: string | null;
}) {
  const assessed = !isNotAssessed(stance, confidence, reasonsCount);
  return (
    <span className="shariah-pair">
      <StanceBadge stance={stance} confidence={confidence} reasonsCount={reasonsCount} rules={rules} />
      {assessed && confidence !== null && confidence !== undefined && (
        <span className="text-note" dir="ltr">
          {confidence}/100
        </span>
      )}
    </span>
  );
}

/** Previous / Next with "Page 1 of 5 (234 companies)"; chevrons follow the reading direction. */
export function Pagination({
  page,
  totalPages,
  total,
  onPage,
}: {
  page: number;
  totalPages: number;
  total: number;
  onPage: (page: number) => void;
}) {
  const { t, locale } = useLang();
  if (totalPages <= 1) return null;
  const n = new Intl.NumberFormat(locale);
  return (
    <nav className="pagination" aria-label={t("page_aria")}>
      <button type="button" className="pagination-btn pagination-prev" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        <ChevronIcon size={12} />
        {t("page_prev")}
      </button>
      <span className="pagination-info">
        {t("page_info", { page: n.format(page), pages: n.format(totalPages), total: n.format(total) })}
      </span>
      <button
        type="button"
        className="pagination-btn pagination-next"
        disabled={page >= totalPages}
        onClick={() => onPage(page + 1)}
      >
        {t("page_next")}
        <ChevronIcon size={12} />
      </button>
    </nav>
  );
}

/** A return as a signed percentage, green for a gain and red for a loss. */
export function ReturnText({ value }: { value: number | null }) {
  const { locale } = useLang();
  const text = fmtSignedPct(locale, value);
  if (text === null || value === null) return null;
  return <span className={value > 0 ? "positive" : value < 0 ? "negative" : undefined}>{text}</span>;
}

/** Signed two-decimal number for a -1 to +1 scale: "+1.00", "−0.25". */
export function fmtSigned2(locale: string, value: number): string {
  const body = new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Math.abs(value));
  if (value > 0) return `+${body}`;
  if (value < 0) return `−${body}`;
  return body;
}

/** One-decimal number: 85.7. */
export function fmt1(locale: string, value: number): string {
  return new Intl.NumberFormat(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(value);
}
