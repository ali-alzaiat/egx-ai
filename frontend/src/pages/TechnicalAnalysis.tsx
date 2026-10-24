import "../components/hub/hubPages.css";

import { useParams } from "react-router-dom";
import { useCompanyByTicker, useTechnicalIndicators } from "../api/client";
import { Missing } from "../components/ui/Missing";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import type { CopyKey } from "../i18n";
import { useLang } from "../i18n/useLang";
import { fmtDate, fmtInt, fmtRatio, toNumber } from "../lib/format";
import { isIndicatorType, type IndicatorType } from "../lib/stanceModel";
import type { TechnicalIndicator } from "../types";

const INDICATOR_KEY: Record<IndicatorType, CopyKey> = {
  sma: "px_ind_sma",
  ema: "px_ind_ema",
  rsi: "px_ind_rsi",
  macd: "px_ind_macd",
  bollinger: "px_ind_bollinger",
  obv: "px_ind_obv",
  vwap: "px_ind_vwap",
  atr: "px_ind_atr",
};

/** The look-back period when the indicator carries one ("SMA 20"). */
function periodOf(ind: TechnicalIndicator): number | null {
  const period = ind.parameters?.["period"];
  return typeof period === "number" && Number.isFinite(period) ? period : null;
}

function IndicatorRow({ ind }: { ind: TechnicalIndicator }) {
  const { t, locale } = useLang();
  const type = ind.indicator_type.toLowerCase();
  const period = periodOf(ind);
  const value = ind.status === "AVAILABLE" ? (type === "obv" ? fmtInt(locale, ind.value) : fmtRatio(locale, ind.value)) : null;
  const asOf = fmtDate(locale, ind.price_as_of ?? ind.calculated_at);
  return (
    <tr>
      <td className="text-cell">
        {isIndicatorType(type) ? t(INDICATOR_KEY[type]) : <bdi dir="ltr">{type.toUpperCase()}</bdi>}
        {period !== null && <span dir="ltr"> {period}</span>}
      </td>
      <td className="num" dir="ltr">
        {value ?? <Missing reason={toNumber(ind.value) === null ? ind.reason : null} />}
      </td>
      <td className="num" dir="ltr">
        {asOf ?? <Missing />}
      </td>
    </tr>
  );
}

/**
 * Technical indicators (spec 4.4.2 item 6): read-only. The server computes
 * them from stored prices (R43), so there is no Calculate button.
 */
export default function TechnicalAnalysis() {
  const { ticker = "" } = useParams<{ ticker: string }>();
  const { t } = useLang();
  const { data: company } = useCompanyByTicker(ticker);
  const { data, isLoading, error, refetch } = useTechnicalIndicators(company?.id);

  return (
    <section>
      <h2 className="section-title">{t("px_tech_title")}</h2>
      {isLoading && <LoadingState thing={t("px_tech_title")} />}
      {error && <ErrorState thing={t("px_tech_title")} onRetry={() => void refetch()} />}
      {data && data.length === 0 && <EmptyState>{t("px_tech_empty", { ticker })}</EmptyState>}
      {data && data.length > 0 && (
        <div className="table-wrap">
          <table aria-label={t("px_tech_title")}>
            <thead>
              <tr>
                <th scope="col">{t("px_tech_col_indicator")}</th>
                <th scope="col" className="num" dir="ltr">
                  {t("col_value")}
                </th>
                <th scope="col" className="num" dir="ltr">
                  {t("px_tech_col_as_of")}
                </th>
              </tr>
            </thead>
            <tbody>
              {data.map((ind) => (
                <IndicatorRow key={ind.id} ind={ind} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
