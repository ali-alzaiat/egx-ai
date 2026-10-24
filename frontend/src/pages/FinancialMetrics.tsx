import "../components/hub/hubPages.css";

import type { ReactNode } from "react";
import { useParams } from "react-router-dom";
import { useCompanyByTicker, useCompanyMetrics } from "../api/client";
import { ReasonText, useLineLabel } from "../components/hub/Reason";
import { Tag } from "../components/ui/Badges";
import { InfoPopover } from "../components/ui/InfoPopover";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import type { CopyKey } from "../i18n";
import { SHORT_COPY } from "../i18n/dict";
import { useLang } from "../i18n/useLang";
import { fmtDate, fmtEgpMillions, fmtInt, fmtPct, fmtPrice, fmtRatio } from "../lib/format";
import { groupByFiscalYear, metricValueKind, type MetricYear } from "../lib/metricsView";
import { lineFallback } from "../lib/reasons";
import { unitForCode } from "../lib/statementMatrix";
import type { FinancialMetric } from "../types";

function metricLabel(code: string, t: (key: CopyKey) => string): string {
  const key = `fn_metric_${code}`;
  return key in SHORT_COPY ? t(key as CopyKey) : lineFallback(code);
}

function formatMetric(locale: string, m: FinancialMetric): string | null {
  const n = m.value;
  switch (metricValueKind(m.unit)) {
    case "pct": {
      const v = Number(n);
      return n === null || !Number.isFinite(v) ? null : fmtPct(locale, v / 100);
    }
    case "ratio": {
      const text = fmtRatio(locale, n);
      return text === null ? null : `${text}×`;
    }
    case "perShare":
      return fmtPrice(locale, n);
    case "currency":
      return fmtEgpMillions(locale, n);
    default:
      return fmtRatio(locale, n);
  }
}

function SourceCell({ m }: { m: FinancialMetric }) {
  const { t } = useLang();
  if (m.provisional) return <Tag title={t("source_provisional_title")}>{t("source_provisional")}</Tag>;
  if (m.source_tier === "filing") return <Tag>{t("source_filing")}</Tag>;
  return null;
}

/** Which statement lines fed the number, in a popover. */
function Inputs({ m, ticker }: { m: FinancialMetric; ticker: string }) {
  const { t, locale } = useLang();
  const label = useLineLabel(ticker);
  if (m.inputs.length === 0) return null;
  return (
    <InfoPopover label={t("fn_metrics_inputs_label", { metric: metricLabel(m.metric_code, t) })}>
      <p>{t("fn_metrics_inputs_intro")}</p>
      <ul>
        {m.inputs.map((input) => {
          const unit = unitForCode(input.code);
          const value = unit === "shares" ? fmtInt(locale, input.value) : unit === "currency_per_share" ? fmtPrice(locale, input.value) : fmtEgpMillions(locale, input.value);
          return (
            <li key={`${input.input_role}-${input.line_id}`}>
              {label(input.code)} · {input.fiscal_year} · <bdi dir="ltr">{value}</bdi>
              {input.provisional ? ` · ${t("source_provisional")}` : ""}
            </li>
          );
        })}
      </ul>
    </InfoPopover>
  );
}

function MetricRow({ m, ticker }: { m: FinancialMetric; ticker: string }) {
  const { t, locale } = useLang();
  const text = m.status === "AVAILABLE" ? formatMetric(locale, m) : null;
  let note: ReactNode = null;
  let value: ReactNode;
  if (text !== null) {
    value = text;
    note = m.warnings ? <ReasonText ticker={ticker} reason={m.warnings} /> : null;
  } else if (m.status === "NOT_APPLICABLE") {
    value = <span className="missing">—</span>;
    note = (
      <>
        {t("fn_metric_not_applicable")} <ReasonText ticker={ticker} reason={m.reason} />
      </>
    );
  } else {
    value = <span className="missing">—</span>;
    note = <ReasonText ticker={ticker} reason={m.reason} />;
  }
  return (
    <tr>
      <th scope="row">{metricLabel(m.metric_code, t)}</th>
      <td className="num" dir="ltr">
        {value}
      </td>
      <td>
        <SourceCell m={m} />
      </td>
      <td className="note-cell">
        {note} <Inputs m={m} ticker={ticker} />
      </td>
    </tr>
  );
}

function YearSection({ group, ticker }: { group: MetricYear; ticker: string }) {
  const { t, locale } = useLang();
  const end = fmtDate(locale, group.periodEnd);
  return (
    <section>
      <h2 className="section-title">
        {group.fiscalYear === null ? t("fn_metrics_year_unknown") : t("fn_metrics_year_heading", { year: group.fiscalYear })}
        {end && <span className="text-note"> · {t("fn_metrics_period_end", { date: end })}</span>}
      </h2>
      <div className="table-wrap">
        <table aria-label={group.fiscalYear === null ? t("fn_metrics_year_unknown") : t("fn_metrics_year_heading", { year: group.fiscalYear })}>
          <thead>
            <tr>
              <th scope="col">{t("fn_col_metric")}</th>
              <th scope="col" className="num" dir="ltr">
                {t("col_value")}
              </th>
              <th scope="col">{t("col_source")}</th>
              <th scope="col">{t("fn_col_note")}</th>
            </tr>
          </thead>
          <tbody>
            {group.rows.map((m) => (
              <MetricRow key={m.id} m={m} ticker={ticker} />
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/**
 * Financials › Metrics (spec 4.4.3, R43 4.3): read-only. The server computes
 * the metrics from statement lines, grouped here by fiscal year.
 */
export default function FinancialMetrics() {
  const { ticker = "" } = useParams<{ ticker: string }>();
  const { t } = useLang();
  const { data: company } = useCompanyByTicker(ticker);
  const { data, isLoading, error, refetch } = useCompanyMetrics(company?.id);

  if (isLoading) return <LoadingState thing={t("fn_metrics_title")} />;
  if (error) return <ErrorState thing={t("fn_metrics_title")} onRetry={() => void refetch()} />;
  if (!data || data.length === 0) return <EmptyState>{t("fn_metrics_empty", { ticker })}</EmptyState>;

  const groups = groupByFiscalYear(data);
  return (
    <div className="page">
      <p className="table-meta">{t("fn_metrics_meta")}</p>
      {groups.map((g) => (
        <YearSection key={`${g.fiscalYear}-${g.periodType}`} group={g} ticker={ticker} />
      ))}
    </div>
  );
}
