import { useParams } from "react-router-dom";
import { useMemo, useState, type ReactNode } from "react";
import { useCompanyByTicker } from "../../api/client";
import { useLang } from "../../i18n/useLang";
import { fmtDate, fmtEgpCompact, fmtInt, fmtPrice } from "../../lib/format";
import DataTable, { type Column } from "../ui/DataTable";
import { Missing } from "../ui/Missing";
import { ChevronIcon } from "../ui/icons";
import { ErrorState } from "../ui/States";
import { useYearPrices } from "./priceData";
import type { DailyPrice } from "../../types";

const PAGE_SIZE = 20;

/** Daily prices (spec 4.4.2 item 8): Date, OHLC, Volume, Value traded; 20 rows per page. */
export default function DailyPrices() {
  const { ticker = "" } = useParams<{ ticker: string }>();
  const { t, locale } = useLang();
  const { data: company } = useCompanyByTicker(ticker);
  const { query, bars } = useYearPrices(company?.id);
  // Page belongs to a ticker: switching company starts at page 1 without an effect.
  const [pageState, setPageState] = useState({ ticker, page: 1 });
  const page = pageState.ticker === ticker ? pageState.page : 1;
  const setPage = (next: number): void => setPageState({ ticker, page: next });

  const totalPages = Math.max(1, Math.ceil(bars.length / PAGE_SIZE));
  const current = Math.min(page, totalPages);
  const rows = useMemo(() => bars.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE), [bars, current]);
  const hidden = (query.data?.items.length ?? 0) - bars.length;

  const missing = <Missing localized={t("ov_not_in_data")} />;
  const price = (pick: (p: DailyPrice) => string): ((p: DailyPrice) => ReactNode) => (p) =>
    fmtPrice(locale, pick(p)) ?? missing;
  const columns: Column<DailyPrice>[] = [
    { id: "date", header: t("px_col_date"), cell: (p) => fmtDate(locale, p.date) ?? missing },
    { id: "open", header: t("ov_open"), type: "num", cell: price((p) => p.open) },
    { id: "high", header: t("ov_high"), type: "num", cell: price((p) => p.high) },
    { id: "low", header: t("ov_low"), type: "num", cell: price((p) => p.low) },
    { id: "close", header: t("px_col_close"), type: "num", cell: price((p) => p.close) },
    { id: "volume", header: t("ov_volume"), type: "num", cell: (p) => fmtInt(locale, p.volume) ?? missing },
    { id: "value", header: t("ov_value_traded"), type: "num", cell: (p) => fmtEgpCompact(locale, p.value_traded) ?? missing },
  ];

  if (query.error) return <ErrorState thing={t("px_prices_title")} onRetry={() => void query.refetch()} />;

  return (
    <section>
      <h2 className="section-title">{t("px_prices_title")}</h2>
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(p) => p.id}
        caption={t("px_prices_title")}
        loading={query.isLoading}
        loadingThing={t("px_prices_title")}
        meta={t("px_prices_meta", { n: new Intl.NumberFormat(locale).format(bars.length) })}
        footnote={hidden > 0 ? t("px_prices_hidden_note") : undefined}
        empty={<p className="empty">{t("px_prices_empty", { ticker })}</p>}
        cardFields={["close", "volume", "high", "low"]}
        hideDensityToggle
      />
      {totalPages > 1 && (
        <nav className="pagination" aria-label={t("page_aria")}>
          <button type="button" className="pagination-btn pagination-prev" disabled={current <= 1} onClick={() => setPage(current - 1)}>
            <ChevronIcon size={12} />
            {t("page_prev")}
          </button>
          <span className="pagination-info">
            {t("px_prices_page_info", {
              page: new Intl.NumberFormat(locale).format(current),
              pages: new Intl.NumberFormat(locale).format(totalPages),
            })}
          </span>
          <button
            type="button"
            className="pagination-btn pagination-next"
            disabled={current >= totalPages}
            onClick={() => setPage(current + 1)}
          >
            {t("page_next")}
            <ChevronIcon size={12} />
          </button>
        </nav>
      )}
    </section>
  );
}
