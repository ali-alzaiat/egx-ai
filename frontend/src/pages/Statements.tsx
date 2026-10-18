import { useParams } from "react-router-dom";
import CompanyTabs from "../components/CompanyTabs";
import { useStatements } from "../api/client";
import { useLang } from "../i18n/useLang";
import type { CopyKey } from "../i18n";
import { fmtNum } from "../i18n/format";
import type { PeriodStatements, StatementLineRead } from "../types";

const SECTIONS: { field: "income" | "balance" | "cash_flow"; key: CopyKey }[] = [
  { field: "income", key: "section_income" },
  { field: "balance", key: "section_balance" },
  { field: "cash_flow", key: "section_cash_flow" },
];

function SectionTable({ title, lines }: { title: string; lines: StatementLineRead[] }) {
  const { lang, t, locale } = useLang();
  return (
    <table className="statements-table">
      <caption>{title}</caption>
      <thead>
        <tr>
          <th scope="col">{t("col_line")}</th>
          <th scope="col">{t("col_value")}</th>
        </tr>
      </thead>
      <tbody>
        {lines.map((l) => {
          // Backend already ships the real bilingual label; pick by language.
          const label = lang === "ar" ? (l.label_ar || l.label_en) : l.label_en;
          return (
            <tr key={l.ontology_code} title={l.source_label_reported ?? undefined}>
              <td>{label}</td>
              <td className="num" dir="ltr">
                {l.value === null
                  ? t("no_value")
                  : fmtNum(locale, l.value, { maximumFractionDigits: 4 })}
              </td>
            </tr>
          );
        })}
        {lines.length === 0 && (
          <tr>
            <td colSpan={2}>{t("insufficient_data")}</td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

function PeriodBlock({ p }: { p: PeriodStatements }) {
  const { t } = useLang();
  const typeKey = ("period_" + p.period_type) as CopyKey;
  return (
    <section className="period-block">
      <h2>
        {t(typeKey)} {p.fiscal_year}
        {p.published_date && (
          <span className="published-date">
            {" · "}
            {t("published_on")} {p.published_date}
          </span>
        )}
      </h2>
      {SECTIONS.map((s) => (
        <SectionTable key={s.field} title={t(s.key)} lines={p[s.field]} />
      ))}
    </section>
  );
}

export default function Statements() {
  const { ticker } = useParams();
  const tk = ticker ?? "";
  const { data, isLoading, error } = useStatements(tk);
  const { t } = useLang();

  return (
    <div className="page">
      <CompanyTabs ticker={tk} />
      <h1>{t("statements_title")}</h1>
      {isLoading && <p>{t("loading")}</p>}
      {error && <p>{t("load_error")}</p>}
      {data && data.periods.length === 0 && <p>{t("statements_empty")}</p>}
      {data?.periods.map((p: PeriodStatements) => (
        <PeriodBlock key={p.period_id} p={p} />
      ))}
    </div>
  );
}
