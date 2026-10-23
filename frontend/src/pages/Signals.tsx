import { useParams } from "react-router-dom";
import CompanyTabs from "../components/CompanyTabs";
import { useStance } from "../api/client";
import { useLang } from "../i18n/useLang";
import type { CopyKey } from "../i18n";
import { fmtNum } from "../i18n/format";
import type { ShariahStatus, TargetLevel } from "../types";

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

const EGX33_KEY: Record<ShariahStatus["egx33"], CopyKey> = {
  member: "shariah_member",
  not_member: "shariah_not_member",
  unknown: "shariah_unknown",
};

const VERDICT_KEY: Record<ShariahStatus["verdict"], CopyKey> = {
  COMPLIANT: "shariah_compliant",
  NON_COMPLIANT: "shariah_non_compliant",
  INSUFFICIENT_DATA: "insufficient_data",
  NOT_SCREENED: "shariah_not_screened",
};

function ShariahBlock({ shariah }: { shariah: ShariahStatus }) {
  const { t } = useLang();
  return (
    <table className="stance-targets">
      <caption>{t("signals_shariah")}</caption>
      <tbody>
        <tr>
          <td>{t("shariah_our_verdict")}</td>
          <td>{t(VERDICT_KEY[shariah.verdict])}</td>
          <td dir="ltr">{shariah.methodology_version ?? ""}</td>
        </tr>
        <tr>
          <td>{t("shariah_egx33")}</td>
          <td>{t(EGX33_KEY[shariah.egx33])}</td>
          <td dir="ltr">
            {shariah.egx33_source ? (
              <a href={shariah.egx33_source} target="_blank" rel="noreferrer">
                {shariah.egx33_review_cycle}
              </a>
            ) : (
              shariah.egx33_review_cycle ?? ""
            )}
          </td>
        </tr>
      </tbody>
    </table>
  );
}

export default function Signals() {
  const { ticker } = useParams();
  const tk = ticker ?? "";
  const { data, isLoading, error } = useStance(tk);
  const { t, locale } = useLang();
  const num = (value: string | null | undefined): string =>
    value ? fmtNum(locale, value, { maximumFractionDigits: 2 }) : t("no_value");

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
            {" · "}
            {t("signals_score")}:{" "}
            <span className="num" dir="ltr">
              {data.score ?? t("no_value")}
            </span>
            {" · "}
            {t("signals_coverage")}:{" "}
            <span className="num" dir="ltr">
              {Math.round(Number.parseFloat(data.coverage) * 100)}%
            </span>
          </p>
          {data.liquidity.low && (
            <p className="alert alert-warning" title={t("low_liquidity_title")}>
              ⚠ {t("low_liquidity")}
            </p>
          )}

          {data.reference_levels && (
            <table className="stance-targets">
              <caption>
                {t("signals_levels")}{" "}
                <span className="muted" dir="ltr">
                  ({data.reference_levels.horizon}, ATR {data.reference_levels.atr})
                </span>
              </caption>
              <tbody>
                <tr>
                  <td>{t("level_entry")}</td>
                  <td className="num" dir="ltr">{num(data.reference_levels.entry)}</td>
                </tr>
                <tr>
                  <td>{t("level_upside")}</td>
                  <td className="num" dir="ltr">{num(data.reference_levels.upside)}</td>
                </tr>
                <tr>
                  <td>{t("level_downside")}</td>
                  <td className="num" dir="ltr">{num(data.reference_levels.downside)}</td>
                </tr>
              </tbody>
            </table>
          )}
          <p className="stance-liquidity">
            {t("signals_liquidity")}:{" "}
            <span className="num" dir="ltr">
              {num(data.liquidity.avg_value_traded)}
            </span>
          </p>

          <ShariahBlock shariah={data.shariah} />

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
