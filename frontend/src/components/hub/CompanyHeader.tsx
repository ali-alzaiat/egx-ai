import { useMemo } from "react";
import { useCompanyPrices, useStance } from "../../api/client";
import { useLang } from "../../i18n/useLang";
import { fmtChange, fmtDate, fmtPrice, toNumber } from "../../lib/format";
import type { Company, DailyPrice } from "../../types";
import { ShariahPair, StanceBadge } from "../ui/Badges";
import { CompanyName } from "../ui/CompanyName";
import { TriangleDownIcon, TriangleUpIcon } from "../ui/icons";
import { Missing } from "../ui/Missing";
import { StatStrip, type StatItem } from "../ui/StatStrip";

/** Placeholder bars (O=H=L=C and zero volume) are not trading days. */
function isPlaceholderBar(p: DailyPrice): boolean {
  return p.open === p.high && p.high === p.low && p.low === p.close && p.volume === 0;
}

/** The two most recent real bars, newest first. */
export function latestTwoBars(items: readonly DailyPrice[]): DailyPrice[] {
  return items
    .filter((p) => !isPlaceholderBar(p))
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0))
    .slice(0, 2);
}

function Skeleton() {
  return <span className="skeleton-bar" style={{ width: "6ch" }} />;
}

/**
 * Hub header, rendered once by the hub layout route (spec 1.4): ticker, name,
 * a four-item stat strip and the as-of line. Change is computed client-side
 * from the two latest real bars of the one-year prices query.
 */
export default function CompanyHeader({ company }: { company: Company }) {
  const { t, locale } = useLang();
  const startDate = useMemo(() => {
    const d = new Date();
    d.setFullYear(d.getFullYear() - 1);
    return d.toISOString().split("T")[0]!;
  }, []);
  const prices = useCompanyPrices(company.id, { start_date: startDate, page_size: 300 });
  const stance = useStance(company.ticker);

  const bars = useMemo(() => latestTwoBars(prices.data?.items ?? []), [prices.data]);
  const [latest, previous] = bars;

  const lastClose = latest ? fmtPrice(locale, latest.close) : null;
  const prevClose = previous ? toNumber(previous.close) : null;
  const latestClose = latest ? toNumber(latest.close) : null;
  const abs = prevClose !== null && latestClose !== null ? latestClose - prevClose : null;
  const pct = abs !== null && prevClose !== null && prevClose !== 0 ? abs / prevClose : null;
  const changeText = fmtChange(locale, abs, pct);
  const dir = abs === null ? "flat" : abs > 0 ? "up" : abs < 0 ? "down" : "flat";
  const asOf = latest ? fmtDate(locale, latest.date) : null;

  const s = stance.data;
  const items: StatItem[] = [
    {
      id: "close",
      label: t("hub_last_close"),
      hero: true,
      numeric: true,
      value: prices.isLoading ? (
        <Skeleton />
      ) : lastClose ? (
        <>
          {lastClose} <span className="stat-sub">{t("egp")}</span>
        </>
      ) : (
        <Missing />
      ),
    },
    {
      id: "change",
      label: t("hub_change"),
      numeric: true,
      value: prices.isLoading ? (
        <Skeleton />
      ) : changeText ? (
        <span className="hub-change" data-dir={dir}>
          {dir === "up" && <TriangleUpIcon size={12} />}
          {dir === "down" && <TriangleDownIcon size={12} />} {changeText}
        </span>
      ) : (
        <Missing localized={t("not_enough_history")} />
      ),
      sub: changeText && latest ? t("hub_vs_prev", { date: fmtDate(locale, latest.date) ?? "" }) : undefined,
    },
    {
      id: "stance",
      label: t("hub_stance"),
      value: stance.isLoading ? (
        <Skeleton />
      ) : s ? (
        <StanceBadge stance={s.stance} confidence={s.confidence} reasonsCount={s.reasons.length} rules={s.rules_version} />
      ) : (
        <Missing />
      ),
      sub: s && s.confidence > 0 ? t("stance_confidence", { c: s.confidence }) : undefined,
    },
    {
      id: "shariah",
      label: t("hub_shariah"),
      value: stance.isLoading ? <Skeleton /> : s ? <ShariahPair shariah={s.shariah} /> : <Missing />,
    },
  ];

  return (
    <header className="hub-header">
      <div className="hub-title">
        <span className="hub-ticker" dir="ltr">
          {company.ticker}
        </span>
        <h1>
          <CompanyName name={company.name} nameAr={company.name_ar} />
        </h1>
      </div>
      <StatStrip items={items} label={company.ticker} />
      {asOf && (
        <p className="hub-asof">
          {s?.rules_version
            ? t("hub_prices_as_of", { date: asOf, rules: s.rules_version })
            : t("hub_prices_as_of_only", { date: asOf })}
        </p>
      )}
    </header>
  );
}
