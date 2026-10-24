import "../components/hub/hubPages.css";

import { useParams } from "react-router-dom";
import { useRatios } from "../api/client";
import { ReasonText } from "../components/hub/Reason";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import type { CopyKey } from "../i18n";
import { SHORT_COPY } from "../i18n/dict";
import { useLang } from "../i18n/useLang";
import { fmtPct, fmtPrice, fmtRatio } from "../lib/format";
import { lineFallback } from "../lib/reasons";
import type { RatioResult } from "../types";

type RatioKind = "pct" | "multiple" | "price";

const KIND: Record<string, RatioKind> = {
  gross_margin: "pct",
  operating_margin: "pct",
  net_margin: "pct",
  roe: "pct",
  roa: "pct",
  revenue_growth_yoy: "pct",
  net_income_growth_yoy: "pct",
  leverage: "multiple",
  current_ratio: "multiple",
  eps: "price",
};

function ratioLabel(code: string, t: (key: CopyKey) => string): string {
  const key = `ratio_${code}`;
  return key in SHORT_COPY ? t(key as CopyKey) : lineFallback(code);
}

function RatioValue({ ratio }: { ratio: RatioResult }) {
  const { locale } = useLang();
  const kind = KIND[ratio.code] ?? "multiple";
  const text =
    ratio.value === null || ratio.status !== "AVAILABLE"
      ? null
      : kind === "pct"
        ? fmtPct(locale, ratio.value)
        : kind === "price"
          ? fmtPrice(locale, ratio.value)
          : fmtRatio(locale, ratio.value);
  if (text === null) return null;
  return <>{kind === "multiple" ? `${text}×` : text}</>;
}

/** Financials › Ratios (spec 4.4.3): Ratio, Value, Note. The note is empty when the ratio is available. */
export default function Ratios() {
  const { ticker = "" } = useParams<{ ticker: string }>();
  const { t } = useLang();
  const { data, isLoading, error, refetch } = useRatios(ticker);

  if (isLoading) return <LoadingState thing={t("ratios_title")} />;
  if (error || !data) return <ErrorState thing={t("ratios_title")} onRetry={() => void refetch()} />;
  if (data.ratios.length === 0) return <EmptyState>{t("ratios_empty")}</EmptyState>;

  return (
    <div className="page">
      <p className="table-meta">
        {t("fn_ratios_meta", { year: data.fiscal_year ?? "—" })} <bdi dir="ltr">{data.ratios_version}</bdi>
      </p>
      <div className="table-wrap">
        <table aria-label={t("ratios_title")}>
          <thead>
            <tr>
              <th scope="col">{t("col_ratio")}</th>
              <th scope="col" className="num" dir="ltr">
                {t("col_value")}
              </th>
              <th scope="col">{t("fn_col_note")}</th>
            </tr>
          </thead>
          <tbody>
            {data.ratios.map((r) => {
              const available = r.status === "AVAILABLE" && r.value !== null;
              return (
                <tr key={r.code}>
                  <th scope="row">{ratioLabel(r.code, t)}</th>
                  <td className="num" dir="ltr">
                    {available ? <RatioValue ratio={r} /> : <span className="missing">—</span>}
                  </td>
                  <td className="note-cell">{available ? null : <ReasonText ticker={ticker} reason={r.reason} />}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
