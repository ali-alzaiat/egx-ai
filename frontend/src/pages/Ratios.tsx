import { useParams } from "react-router-dom";
import CompanyTabs from "../components/CompanyTabs";
import { useRatios } from "../api/client";
import { useLang } from "../i18n/useLang";
import type { CopyKey } from "../i18n";
import { fmtNum } from "../i18n/format";
import type { RatioResult } from "../types";

const PERCENT_RATIOS = new Set([
  "gross_margin",
  "operating_margin",
  "net_margin",
  "roe",
  "roa",
  "revenue_growth_yoy",
  "net_income_growth_yoy",
]);

export default function Ratios() {
  const { ticker } = useParams();
  const tk = ticker ?? "";
  const { data, isLoading, error } = useRatios(tk);
  const { t, locale } = useLang();

  return (
    <div className="page">
      <CompanyTabs ticker={tk} />
      <h1>{t("ratios_title")}</h1>
      {isLoading && <p>{t("loading")}</p>}
      {error && <p>{t("load_error")}</p>}
      {data && data.ratios.length === 0 && <p>{t("ratios_empty")}</p>}
      {data && data.ratios.length > 0 && (
      <table className="ratios-table">
        <thead>
          <tr>
            <th scope="col">{t("col_ratio")}</th>
            <th scope="col">{t("col_value")}</th>
            <th scope="col">{t("col_status")}</th>
          </tr>
        </thead>
        <tbody>
          {data?.ratios?.map((r: RatioResult) => {
            const nameKey = ("ratio_" + r.code) as CopyKey;
            const isPct = PERCENT_RATIOS.has(r.code) && r.value !== null;
            return (
              <tr key={r.code}>
                <td>{t(nameKey)}</td>
                <td className="num" dir="ltr">
                  {r.value === null
                    ? t("no_value")
                    : isPct
                      ? fmtNum(locale, Number(r.value) * 100, {
                          style: "percent",
                          maximumFractionDigits: 1,
                        })
                      : fmtNum(locale, r.value, { maximumFractionDigits: 4 })}
                </td>
                <td>
                  {r.status === "AVAILABLE"
                    ? t("available")
                    : t("insufficient_data")}
                  {r.reason && (
                    <span className="ratio-reason" title={r.reason}>
                      {" "}
                      ({r.reason})
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      )}
    </div>
  );
}
