import "./hub/hubPages.css";

import { useDataQuality } from "../api/client";
import type { CopyKey } from "../i18n";
import { useLang } from "../i18n/useLang";
import { fmtDate, fmtInt } from "../lib/format";
import { qualityLabelKey } from "../lib/quality";
import { parseSourceType, type SourceType } from "../lib/reasons";
import type { DataQualityScore } from "../types";
import { BackendText } from "./ui/BackendText";
import { Notice } from "./ui/Notice";
import { EmptyState, ErrorState, LoadingState } from "./ui/States";

// Canonical scope order: the API returns them in whatever order they were stored.
const SCOPE_ORDER = ["price_history", "company_profile", "financial_statements"] as const;

const SCOPE_KEY: Record<(typeof SCOPE_ORDER)[number], CopyKey> = {
  price_history: "fn_dq_scope_price_history",
  company_profile: "fn_dq_scope_company_profile",
  financial_statements: "fn_dq_scope_financial_statements",
};

const SOURCE_TYPE_KEY: Record<SourceType, CopyKey> = {
  DATA_PROVIDER: "fn_dq_source_data_provider",
  EGX: "fn_dq_source_egx",
  FRA: "fn_dq_source_fra",
  COMPANY: "fn_dq_source_company",
  MANUAL: "fn_dq_source_manual",
  SYNTHETIC: "fn_dq_source_synthetic",
  unknown: "fn_dq_source_unknown",
};

const COMPONENT_KEY: Record<string, CopyKey> = {
  completeness: "fn_dq_component_completeness",
  freshness: "fn_dq_component_freshness",
  validation: "fn_dq_component_validation",
  historical_depth: "fn_dq_component_historical_depth",
  source_reliability: "fn_dq_component_source_reliability",
};

/** Detail text: the source-type code is translated; everything else is backend text. */
function Detail({ text }: { text: string }) {
  const { t } = useLang();
  const sourceType = parseSourceType(text);
  if (sourceType) return <>{t("fn_dq_source_type", { type: t(SOURCE_TYPE_KEY[sourceType]) })}</>;
  return <BackendText>{text}</BackendText>;
}

function ScopeSection({ item }: { item: DataQualityScore }) {
  const { t, locale } = useLang();
  const missing = item.status === "MISSING";
  const scopeName = t(SCOPE_KEY[item.scope] ?? "fn_dq_scope_unknown");
  const heading = missing
    ? t("fn_dq_heading_not_scored", { scope: scopeName })
    : t("fn_dq_heading", { scope: scopeName, score: fmtInt(locale, Math.round(item.score)) ?? "", band: t(qualityLabelKey(item.status)) });
  const asOf = fmtDate(locale, item.as_of);

  return (
    <section className="dq-scope">
      <h2 className="section-title">{heading}</h2>
      {asOf && <p className="table-meta">{t("fn_dq_as_of", { date: asOf })}</p>}
      {missing && <p className="dq-score-note">{t("fn_dq_missing_note")}</p>}
      <div className="table-wrap">
        <table aria-label={scopeName}>
          <thead>
            <tr>
              <th scope="col">{t("fn_dq_col_component")}</th>
              <th scope="col" className="num" dir="ltr">
                {t("fn_dq_col_weight")}
              </th>
              <th scope="col" className="num" dir="ltr">
                {t("fn_dq_col_score")}
              </th>
              <th scope="col">{t("fn_dq_col_detail")}</th>
            </tr>
          </thead>
          <tbody>
            {item.components.map((component) => {
              const key = COMPONENT_KEY[component.key];
              return (
                <tr key={component.key}>
                  <th scope="row">{key ? t(key) : component.label}</th>
                  <td className="num" dir="ltr">
                    {Math.round(component.weight * 100)}%
                  </td>
                  <td className="num" dir="ltr">
                    {missing ? "—" : Math.round(component.score)}
                  </td>
                  <td className="note-cell">
                    <Detail text={component.reason} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {/* Issues omitted for MISSING: the strings hard-code "(0/100)", which the
          heading and component details already say in that state. */}
      {item.issues.length > 0 && !missing && (
        <div className="dq-issues">
          <Notice>
            <p className="dq-issues-title">{t("fn_dq_issues")}</p>
            <ul>
              {item.issues.map((issue) => (
                <li key={issue}>
                  <BackendText>{issue}</BackendText>
                </li>
              ))}
            </ul>
          </Notice>
        </div>
      )}
    </section>
  );
}

/** Financials › Data quality (spec 4.4.3): one table per scope. It describes the inputs, not the company. */
export default function DataQualityCard({ companyId }: { companyId: string }) {
  const { t } = useLang();
  const { data, isLoading, error, refetch } = useDataQuality(companyId);

  if (isLoading) return <LoadingState thing={t("fn_dq_title")} />;
  if (error || !data) return <ErrorState thing={t("fn_dq_title")} onRetry={() => void refetch()} />;

  const items = [...data.items].sort(
    (a, b) => (SCOPE_ORDER as readonly string[]).indexOf(a.scope) - (SCOPE_ORDER as readonly string[]).indexOf(b.scope),
  );

  return (
    <div className="page">
      <p className="dq-definition">{t("fn_dq_definition")}</p>
      {items.length === 0 && <EmptyState>{t("fn_dq_empty")}</EmptyState>}
      {items.map((item) => (
        <ScopeSection item={item} key={item.scope} />
      ))}
      <p className="table-footnote">{t("fn_dq_footnote", { version: data.methodology_version })}</p>
    </div>
  );
}
