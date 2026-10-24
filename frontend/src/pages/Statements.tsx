import "../components/hub/hubPages.css";

import { useMemo } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useStatements } from "../api/client";
import { Missing } from "../components/ui/Missing";
import { Notice } from "../components/ui/Notice";
import { Segmented } from "../components/ui/Segmented";
import { EmptyState, ErrorState, LoadingState } from "../components/ui/States";
import { Tag } from "../components/ui/Badges";
import { ExternalLinkIcon } from "../components/ui/icons";
import type { CopyKey } from "../i18n";
import { useLang } from "../i18n/useLang";
import { fmtEgpMillions, fmtInt, fmtPrice } from "../lib/format";
import {
  STATEMENT_FIELDS,
  allAnnual,
  anyVendor,
  buildMatrix,
  lineUnit,
  type MatrixColumn,
  type StatementField,
} from "../lib/statementMatrix";
import type { StatementLineRead } from "../types";

const FIELD_KEY: Record<StatementField, CopyKey> = {
  income: "section_income",
  balance: "section_balance",
  cash_flow: "section_cash_flow",
};

function isField(value: string | null): value is StatementField {
  return STATEMENT_FIELDS.some((f) => f === value);
}

/** Money lines in EGP millions; share counts as whole numbers; per-share lines to 2 dp. */
function formatLine(locale: string, line: StatementLineRead): string | null {
  switch (lineUnit(line)) {
    case "shares":
      return fmtInt(locale, line.value);
    case "currency_per_share":
      return fmtPrice(locale, line.value);
    default:
      return fmtEgpMillions(locale, line.value);
  }
}

function PeriodHeader({ column }: { column: MatrixColumn }) {
  const { t } = useLang();
  const annual = column.periodType === "ANNUAL";
  const typeKey = `period_${column.periodType}` as CopyKey;
  return <>{annual ? column.fiscalYear : `${t(typeKey)} ${column.fiscalYear}`}</>;
}

function SourceHeader({ column }: { column: MatrixColumn }) {
  const { t } = useLang();
  if (column.source === "vendor") return <Tag title={t("source_provisional_title")}>{t("source_provisional")}</Tag>;
  if (column.source === "filing") {
    return column.documentUrl ? (
      <a href={column.documentUrl} target="_blank" rel="noreferrer" className="source-link">
        {t("source_filing")}
        <ExternalLinkIcon size={12} />
      </a>
    ) : (
      <Tag>{t("source_filing")}</Tag>
    );
  }
  return <Missing localized={t("fn_not_reported_in_source")} />;
}

function Cell({ line }: { line: StatementLineRead | null }) {
  const { t, locale } = useLang();
  const text = line ? formatLine(locale, line) : null;
  if (!line || text === null) return <Missing localized={t("fn_not_reported_in_source")} />;
  const title =
    line.source_tier === "filing" && line.source_page
      ? `${t("source_filing")} ${t("source_page")} ${line.source_page}`
      : (line.source_label_reported ?? undefined);
  return <span title={title}>{text}</span>;
}

/** Financials › Statements (spec 4.4.3): one statement at a time, lines by fiscal year, source under each year. */
export default function Statements() {
  const { ticker = "" } = useParams<{ ticker: string }>();
  const { t, lang } = useLang();
  const { data, isLoading, error, refetch } = useStatements(ticker);
  const [params, setParams] = useSearchParams();
  const stmtParam = params.get("statement");
  const field: StatementField = isField(stmtParam) ? stmtParam : "income";

  const matrix = useMemo(() => buildMatrix(data?.periods ?? [], field), [data, field]);

  if (isLoading) return <LoadingState thing={t("statements_title")} />;
  if (error || !data) return <ErrorState thing={t("statements_title")} onRetry={() => void refetch()} />;
  if (data.periods.length === 0) return <EmptyState>{t("statements_empty")}</EmptyState>;

  const setField = (next: StatementField): void =>
    setParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        if (next === "income") p.delete("statement");
        else p.set("statement", next);
        return p;
      },
      { replace: true },
    );

  return (
    <div className="page">
      <div className="statements-controls">
        <Segmented
          label={t("fn_statements_view_aria")}
          value={field}
          onChange={setField}
          options={STATEMENT_FIELDS.map((f) => ({ value: f, label: t(FIELD_KEY[f]) }))}
        />
        <p className="table-meta">{t(allAnnual(matrix.columns) ? "fn_statements_meta_annual" : "fn_statements_meta")}</p>
      </div>
      {anyVendor(data.periods) && <Notice>{t("fn_statements_provisional_notice")}</Notice>}
      <div className="table-wrap">
        <table className="matrix-table" aria-label={t(FIELD_KEY[field])}>
          <thead>
            <tr>
              <th scope="col" className="col-sticky">
                {t("col_line")}
              </th>
              {matrix.columns.map((c) => (
                <th key={c.periodId} scope="col" className="num" dir="ltr">
                  <PeriodHeader column={c} />
                </th>
              ))}
            </tr>
            <tr className="source-row">
              <th scope="row" className="col-sticky">
                {t("col_source")}
              </th>
              {matrix.columns.map((c) => (
                <td key={c.periodId} className="num" dir="ltr">
                  <SourceHeader column={c} />
                </td>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.rows.map((row) => {
              const label = lang === "ar" ? row.labelAr || row.labelEn : row.labelEn;
              return (
                <tr key={row.code}>
                  <th scope="row" className="col-sticky">
                    {label}
                  </th>
                  {row.cells.map((cell, i) => (
                    <td key={matrix.columns[i]?.periodId ?? i} className="num" dir="ltr">
                      <Cell line={cell} />
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
