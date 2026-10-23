import "./Companies.css";

/*
 * Recommendations radar (signal-rules-2.0): the most-traded EGX stocks with
 * stance, confidence, ATR reference levels, liquidity and Shariah side by
 * side. One batch request (useStanceRadar); the Shariah-only toggle narrows
 * the server query to official EGX33 members, the stance filter is local.
 * Missing values render as a dash with an INSUFFICIENT_DATA note — never zero.
 */

import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useStanceRadar } from "../api/client";
import { useLang } from "../i18n/useLang";
import type { CopyKey } from "../i18n";
import { fmtNum } from "../i18n/format";
import type { ShariahStatus, StanceRadarItem } from "../types";
import { sortRadarRows, type RadarSortDir } from "./companies/radarSort";

type StanceValue = "buy" | "hold" | "reduce";
type StanceFilter = "all" | StanceValue;

const STANCE_FILTERS: StanceFilter[] = ["all", "buy", "hold", "reduce"];

const STANCE_KEY: Record<StanceValue, CopyKey> = {
  buy: "stance_buy",
  hold: "stance_hold",
  reduce: "stance_reduce",
};

const STANCE_SHAPES: Record<StanceValue, string> = { buy: "▲", hold: "●", reduce: "▼" };

interface RecoRow extends StanceRadarItem {
  scoreValue: number | null;
}

type RecoSortKey = "ticker" | "stance" | "scoreValue" | "confidence";

export default function Recommendations() {
  const { t, locale } = useLang();
  const [shariahOnly, setShariahOnly] = useState(false);
  const [stanceFilter, setStanceFilter] = useState<StanceFilter>("all");
  const [sortKey, setSortKey] = useState<RecoSortKey | null>(null);
  const [sortDir, setSortDir] = useState<RadarSortDir>("desc");

  const { data, isLoading, error, refetch } = useStanceRadar(50, shariahOnly ? "egx33" : undefined);

  const rows = useMemo<RecoRow[]>(() => {
    const items = (data?.items ?? []).map((item) => ({
      ...item,
      scoreValue: item.score !== null ? Number.parseFloat(item.score) : null,
    }));
    const filtered =
      stanceFilter === "all" ? items : items.filter((item) => item.stance === stanceFilter);
    // Server order is "most traded first"; only re-sort when a column is chosen.
    return sortKey ? sortRadarRows(filtered, sortKey, sortDir) : filtered;
  }, [data, stanceFilter, sortKey, sortDir]);

  const toggleSort = (key: RecoSortKey): void => {
    if (key === sortKey) {
      setSortDir((dir) => (dir === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "ticker" || key === "stance" ? "asc" : "desc");
    }
  };

  const num = (value: string | null | undefined): string =>
    value ? fmtNum(locale, value, { maximumFractionDigits: 2 }) : t("no_value");

  const sortHeader = (key: RecoSortKey, label: string) => (
    <th
      aria-sort={sortKey === key ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
    >
      <button type="button" className="radar-sort-btn" onClick={() => toggleSort(key)}>
        {label}
        {sortKey === key ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
      </button>
    </th>
  );

  return (
    <div>
      <div className="page-header">
        <h1>{t("reco_title")}</h1>
        <p>{t("reco_subtitle")}</p>
      </div>

      <div className="filters">
        <label className="filter-checkbox">
          <input
            type="checkbox"
            checked={shariahOnly}
            onChange={(e) => setShariahOnly(e.target.checked)}
          />{" "}
          {t("reco_shariah_only")}
        </label>
        <select
          className="filter-select"
          aria-label={t("reco_filter_label")}
          value={stanceFilter}
          onChange={(e) => setStanceFilter(e.target.value as StanceFilter)}
        >
          {STANCE_FILTERS.map((value) => (
            <option key={value} value={value}>
              {value === "all" ? t("reco_filter_all") : t(STANCE_KEY[value])}
            </option>
          ))}
        </select>
      </div>

      {isLoading && <div className="loading">{t("loading")}</div>}
      {error && (
        <div className="alert alert-error">
          {t("load_error")}{" "}
          <button className="link-btn" onClick={() => refetch()}>
            ↻
          </button>
        </div>
      )}

      {data && rows.length === 0 && <div className="empty">{t("reco_empty")}</div>}

      {data && rows.length > 0 && (
        <div className="table-container">
          <table className="radar-table">
            <thead>
              <tr>
                {sortHeader("ticker", t("reco_col_stock"))}
                {sortHeader("stance", t("signals_stance"))}
                {sortHeader("scoreValue", t("signals_score"))}
                {sortHeader("confidence", t("signals_confidence"))}
                <th>{t("reco_col_price")}</th>
                <th>{t("level_upside")}</th>
                <th>{t("level_downside")}</th>
                <th>{t("reco_col_shariah")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.company_id}>
                  <td>
                    <Link to={`/companies/${row.ticker}/signals`} className="ticker-link">
                      {row.ticker}
                    </Link>
                    <div className="radar-name">{row.name}</div>
                    {row.low_liquidity && (
                      <span className="radar-liquidity-low" title={t("low_liquidity_title")}>
                        ⚠ {t("low_liquidity")}
                      </span>
                    )}
                  </td>
                  <td>
                    {row.stance ? (
                      <span className={`radar-stance radar-stance-${row.stance}`}>
                        {STANCE_SHAPES[row.stance]} {t(STANCE_KEY[row.stance])}
                      </span>
                    ) : (
                      <Missing label="stance unavailable" />
                    )}
                  </td>
                  <td className="num" dir="ltr">
                    {row.score ?? <Missing label="no engine produced an input" />}
                  </td>
                  <td className="num" dir="ltr">
                    {row.confidence ?? <Missing label="no confidence" />}
                  </td>
                  <td className="num" dir="ltr">
                    {num(row.price)}
                  </td>
                  <td className="num" dir="ltr">
                    {row.reference_levels ? num(row.reference_levels.upside) : <Missing label="no ATR" />}
                  </td>
                  <td className="num" dir="ltr">
                    {row.reference_levels ? num(row.reference_levels.downside) : <Missing label="no ATR" />}
                  </td>
                  <td>
                    <ShariahCell shariah={row.shariah} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && (
        <>
          <p className="muted">{t("reco_levels_note")}</p>
          <p className="muted" dir="ltr">
            {data.rules_version} · {t("not_investment_advice")}
          </p>
        </>
      )}
    </div>
  );
}

function Missing({ label }: { label: string }) {
  return (
    <span className="radar-missing" title={`INSUFFICIENT_DATA — ${label}`}>
      —
    </span>
  );
}

/** EGX33 membership and our own verdict, shown side by side and never merged. */
export function ShariahCell({ shariah }: { shariah: ShariahStatus | null }) {
  const { t } = useLang();
  if (!shariah) return <Missing label="shariah status unavailable" />;
  const ours =
    shariah.verdict === "COMPLIANT" ? (
      <span className="radar-shariah radar-shariah-ok">✓ {t("shariah_compliant")}</span>
    ) : shariah.verdict === "NON_COMPLIANT" ? (
      <span className="radar-shariah radar-shariah-non">✕ {t("shariah_non_compliant")}</span>
    ) : null;
  const egx33 =
    shariah.egx33 === "member" ? (
      <span
        className="radar-shariah radar-shariah-ok"
        title={`${t("shariah_egx33_badge_title")} · ${shariah.egx33_review_cycle ?? ""}`}
      >
        ☪ {t("shariah_egx33_badge")}
      </span>
    ) : null;
  if (!ours && !egx33) {
    return <Missing label={shariah.note ?? t("shariah_not_screened")} />;
  }
  return (
    <span className="radar-shariah-stack">
      {egx33}
      {ours}
    </span>
  );
}
