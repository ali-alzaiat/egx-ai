import type { ReactNode } from "react";
import { useLatestPrice } from "../../api/client";
import { useLang } from "../../i18n/useLang";
import { fmtChange, fmtDate, fmtInt, fmtPrice, toNumber } from "../../lib/format";
import { BackendText } from "../ui/BackendText";
import { TriangleDownIcon, TriangleUpIcon } from "../ui/icons";
import { Missing } from "../ui/Missing";
import { ErrorState, LoadingState } from "../ui/States";

/**
 * Day view (R47 P1): the last stored session as figures, not a line. End-of-day
 * data only; the change is against the previous stored session, with its date.
 */
export default function SessionSummary({ companyId }: { companyId: string }) {
  const { t, locale } = useLang();
  const query = useLatestPrice(companyId);
  const price = query.data;

  if (query.isLoading) return <LoadingState thing={t("pxf_range_1D")} />;
  if (query.error || !price) return <ErrorState thing={t("pxf_range_1D")} onRetry={() => void query.refetch()} />;
  if (price.status !== "AVAILABLE") {
    return (
      <div>
        <p className="empty">{t("pxf_day_empty")}</p>
        <p className="price-panel-note">
          <BackendText>{price.reason}</BackendText>
        </p>
      </div>
    );
  }

  const abs = toNumber(price.change);
  const pct = toNumber(price.change_pct);
  const dir = abs === null ? "flat" : abs > 0 ? "up" : abs < 0 ? "down" : "flat";
  // change_pct is already a percent; the formatters take a decimal.
  const change =
    abs !== null && pct !== null ? fmtChange(locale, abs, pct / 100) : abs !== null ? fmtPrice(locale, abs) : null;

  const cells: { id: string; label: string; value: ReactNode }[] = [
    { id: "open", label: t("ov_open"), value: fmtPrice(locale, price.open) },
    { id: "high", label: t("ov_high"), value: fmtPrice(locale, price.high) },
    { id: "low", label: t("ov_low"), value: fmtPrice(locale, price.low) },
    { id: "close", label: t("pxf_day_close"), value: fmtPrice(locale, price.close) },
    {
      id: "change",
      label: t("pxf_day_change"),
      value:
        change ? (
          <span className="hub-change" data-dir={dir}>
            {dir === "up" && <TriangleUpIcon size={12} />}
            {dir === "down" && <TriangleDownIcon size={12} />} {change}
          </span>
        ) : (
          <Missing reason={price.change_reason} />
        ),
    },
    { id: "volume", label: t("ov_volume"), value: fmtInt(locale, price.volume) },
  ];

  return (
    <div className="session-summary">
      <h3 className="price-panel-title">{t("pxf_day_title", { date: fmtDate(locale, price.date) ?? "" })}</h3>
      <dl className="session-grid">
        {cells.map((c) => (
          <div key={c.id} className="session-cell">
            <dt>{c.label}</dt>
            <dd>{c.value ?? <Missing />}</dd>
          </div>
        ))}
      </dl>
      {price.previous_close && price.previous_date && (
        <p className="price-panel-note">
          {t("pxf_day_vs_prev", {
            price: fmtPrice(locale, price.previous_close) ?? "",
            date: fmtDate(locale, price.previous_date) ?? "",
          })}
        </p>
      )}
      <p className="price-panel-note">{t("pxf_day_note")}</p>
    </div>
  );
}
