import { useParams } from "react-router-dom";
import CompanyTabs from "../components/CompanyTabs";
import { useStance } from "../api/client";
import { useLang } from "../i18n/useLang";
import type { CopyKey } from "../i18n";
import { fmtNum } from "../i18n/format";
import type { TargetLevel } from "../types";

const UNSPECIFIED_LEVEL: TargetLevel = {
  value: null,
  status: "INSUFFICIENT_DATA",
  reason: null,
};

const STANCE_KEY: Record<string, CopyKey> = {
  buy: "stance_buy",
  hold: "stance_hold",
  reduce: "stance_reduce",
};

function TargetRow({ label, level }: { label: string; level: TargetLevel }) {
  const { t, locale } = useLang();
  return (
    <tr>
      <td>{label}</td>
      <td className="num" dir="ltr">
        {level.value === null
          ? t("no_value")
          : fmtNum(locale, level.value, { maximumFractionDigits: 2 })}
      </td>
      <td>
        {level.status === "INSUFFICIENT_DATA"
          ? t("insufficient_data")
          : t("available")}
        {level.reason && (
          <span className="ratio-reason">
            {" "}
            ({level.reason})
          </span>
        )}
      </td>
    </tr>
  );
}

export default function Signals() {
  const { ticker } = useParams();
  const tk = ticker ?? "";
  const { data, isLoading, error } = useStance(tk);
  const { t } = useLang();

  return (
    <div className="page">
      <CompanyTabs ticker={tk} />
      <h1>{t("signals_title")}</h1>
      {isLoading && <p>{t("loading")}</p>}
      {error && <p>{t("load_error")}</p>}
      {data && (
        <div className="stance-summary">
          <p className="stance-stance">
            {t("signals_stance")}:{" "}
            <strong className={`stance-badge stance-${data.stance}`}>
              {t(STANCE_KEY[data.stance] ?? "stance_hold")}
            </strong>
            {" · "}
            {t("signals_confidence")}: {data.confidence}
          </p>

          <table className="stance-targets">
            <caption>{t("signals_targets")}</caption>
            <tbody>
              <TargetRow
                label={t("target_bull")}
                level={data.targets.bull ?? UNSPECIFIED_LEVEL}
              />
              <TargetRow
                label={t("target_base")}
                level={data.targets.base ?? UNSPECIFIED_LEVEL}
              />
              <TargetRow
                label={t("target_bear")}
                level={data.targets.bear ?? UNSPECIFIED_LEVEL}
              />
              <TargetRow label={t("signals_stop_level")} level={data.stop_level} />
            </tbody>
          </table>

          <p className="stance-why-title">{t("signals_why")}</p>
          <ul className="stance-reasons">
            {data.reasons.map((r, i: number) => (
              <li key={i} dir="ltr" lang="en">
                {r.text}
              </li>
            ))}
          </ul>

          <p className="stance-limits-title">{t("signals_limitations")}</p>
          <ul className="stance-limitations">
            {data.limitations.map((l: string, i: number) => {
              // The bilingual disclaimer line renders RTL-aware as-is; the
              // rest of the limitation strings currently come from the
              // backend in English.
              const bilingual = l.includes("·");
              return (
                <li key={i} dir={bilingual ? "auto" : "ltr"} lang="en">
                  {l}
                </li>
              );
            })}
          </ul>
          <p className="stance-freshness">
            {t("signals_freshness")}: {data.statement_freshness ?? t("no_value")}
            {data.as_of ? (
              <span className="num" dir="ltr">
                {" · "}
                {data.as_of.slice(0, 10)}
              </span>
            ) : null}
          </p>
          <p className="stance-disclaimer" dir="auto">
            {t("not_investment_advice")}
          </p>
        </div>
      )}
    </div>
  );
}
