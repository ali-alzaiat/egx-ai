import "../components/hub/hubPages.css";

import { useMemo } from "react";
import { useParams } from "react-router-dom";
import { useCompanyByTicker, useStance } from "../api/client";
import { useYearPrices } from "../components/hub/priceData";
import { ReasonMissing } from "../components/hub/Reason";
import { StanceBadge, Tag, isNotAssessed } from "../components/ui/Badges";
import { BackendText } from "../components/ui/BackendText";
import { InfoPopover } from "../components/ui/InfoPopover";
import { Missing } from "../components/ui/Missing";
import PriceChart, { type RefLine } from "../components/ui/PriceChart";
import { ErrorState, LoadingState } from "../components/ui/States";
import type { CopyKey } from "../i18n";
import { useLang } from "../i18n/useLang";
import { fmtDate, fmtEgpCompact, fmtPrice, fmtScore, toNumber } from "../lib/format";
import {
  CONFIDENCE_CAPS,
  engineCoverage,
  engineWeight,
  isSwingHorizon,
  visibleLimitations,
  visibleReasons,
  joinList,
  type CompositeEngine,
} from "../lib/stanceModel";
import type { StanceResult, TargetLevel } from "../types";

const ENGINE_KEY: Record<CompositeEngine, CopyKey> = {
  technical: "px_engine_technical",
  valuation: "px_engine_valuation",
  score: "px_engine_score",
};

const UNSPECIFIED_LEVEL: TargetLevel = { value: null, status: "INSUFFICIENT_DATA", reason: null };

function useStanceForTab() {
  const { ticker = "" } = useParams<{ ticker: string }>();
  const { data: company } = useCompanyByTicker(ticker);
  return { ticker, company, stance: useStance(ticker) };
}

function StanceBlock({ s }: { s: StanceResult }) {
  const { t, locale } = useLang();
  const notAssessed = isNotAssessed(s.stance, s.confidence, s.reasons.length);
  const { used, missing } = engineCoverage(s.reasons.map((r) => r.engine));
  const list = { format: (items: readonly string[]) => joinList(items, t("px_list_sep"), t("px_list_and")) };
  const usedText = list.format(
    used.map((e) => {
      const w = engineWeight(s.rules_version, e);
      return w === null ? t(ENGINE_KEY[e]) : t("px_engine_with_weight", { engine: t(ENGINE_KEY[e]), w });
    }),
  );
  const missingText = list.format(missing.map((e) => t(ENGINE_KEY[e])));
  const composite = fmtScore(locale, s.score);

  return (
    <div className="stance-block card-surface">
      <div className="stance-head">
        <span className="stance-badge-lg">
          <StanceBadge stance={s.stance} confidence={s.confidence} reasonsCount={s.reasons.length} rules={s.rules_version} />
        </span>
        {!notAssessed && (
          <span className="stance-confidence">
            {t("stance_confidence", { c: s.confidence })}
            <InfoPopover label={t("px_confidence_info_label")}>
              <p>{t("px_confidence_info_intro")}</p>
              <ul>
                <li>{t("px_confidence_cap_technical", { n: CONFIDENCE_CAPS.technicalOnly })}</li>
                <li>{t("px_confidence_cap_liquidity", { n: CONFIDENCE_CAPS.lowLiquidity })}</li>
                <li>
                  {t("px_confidence_cap_stale", { n: CONFIDENCE_CAPS.staleStatements, days: CONFIDENCE_CAPS.staleStatementDays })}
                </li>
              </ul>
            </InfoPopover>
          </span>
        )}
      </div>
      {notAssessed ? (
        <p className="stance-line">{t("stance_not_assessed_tooltip")}</p>
      ) : (
        <>
          {composite && (
            <p className="stance-line" dir="auto">
              {t("px_composite_line", { score: composite })}
            </p>
          )}
          <p className="stance-line">
            {used.length > 0 && <span>{t("px_stance_inputs", { inputs: usedText })} </span>}
            {missing.length > 0 && <span>{t("px_stance_missing_inputs", { inputs: missingText })}</span>}
          </p>
        </>
      )}
    </div>
  );
}

function BulletList({ title, items }: { title: string; items: readonly string[] }) {
  if (items.length === 0) return null;
  return (
    <section>
      <h2 className="section-title">{title}</h2>
      <ul className="bullet-list">
        {items.map((text) => (
          <li key={text}>
            <BackendText>{text}</BackendText>
          </li>
        ))}
      </ul>
    </section>
  );
}

function ReferenceLevels({ s }: { s: StanceResult }) {
  const { t, locale } = useLang();
  const { company } = useStanceForTab();
  const { series, source } = useYearPrices(company?.id);
  const levels = s.reference_levels;

  const refLines = useMemo<RefLine[]>(() => {
    if (!levels) return [];
    const up = toNumber(levels.upside);
    const down = toNumber(levels.downside);
    const out: RefLine[] = [];
    if (up !== null) out.push({ value: up, label: t("level_upside") });
    if (down !== null) out.push({ value: down, label: t("level_downside") });
    return out;
  }, [levels, t]);

  if (!levels) {
    return (
      <section>
        <h2 className="section-title">{t("signals_levels")}</h2>
        <p className="empty">{t("px_levels_empty")}</p>
      </section>
    );
  }

  const rows: { id: string; label: string; value: string | null }[] = [
    { id: "last", label: t("level_entry"), value: fmtPrice(locale, levels.entry) },
    { id: "up", label: t("px_level_upside_atr"), value: fmtPrice(locale, levels.upside) },
    { id: "down", label: t("px_level_downside_atr"), value: fmtPrice(locale, levels.downside) },
    { id: "atr", label: t("px_level_atr"), value: fmtPrice(locale, levels.atr) },
  ];

  return (
    <section>
      <h2 className="section-title">{t("signals_levels")}</h2>
      <div className="levels-grid">
        <table className="kv-table card-surface" aria-label={t("signals_levels")}>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <th scope="row">{r.label}</th>
                <td className="num" dir="ltr">
                  {r.value ?? <Missing />}
                </td>
              </tr>
            ))}
            <tr>
              <th scope="row">{t("px_level_horizon")}</th>
              <td>{isSwingHorizon(levels.horizon) ? t("px_level_horizon_swing") : <BackendText>{levels.horizon}</BackendText>}</td>
            </tr>
          </tbody>
        </table>
        <div className="card-surface levels-chart">
          <PriceChart bars={series} range="3M" refLines={refLines} source={source} height={200} />
        </div>
      </div>
      <p className="table-footnote">{t("px_levels_caption")}</p>
    </section>
  );
}

function Liquidity({ s }: { s: StanceResult }) {
  const { t, locale } = useLang();
  const avg = fmtEgpCompact(locale, s.liquidity.avg_value_traded);
  return (
    <section>
      <h2 className="section-title">{t("px_signals_liquidity_title")}</h2>
      <p className="liquidity-line">
        <span>{t("ov_avg_value", { n: s.liquidity.window })}:</span>{" "}
        <strong dir="ltr">{avg ?? <Missing localized={t("ov_not_in_data")} />}</strong>
        {s.liquidity.low && (
          <>
            {" "}
            <Tag title={t("low_liquidity_title")}>{t("low_liquidity")}</Tag>
          </>
        )}
      </p>
    </section>
  );
}

/** Price & signals, top half (spec 4.4.2 items 1 to 5): stance, why, limitations, reference levels, liquidity. */
export default function Signals() {
  const { t } = useLang();
  const { stance } = useStanceForTab();
  const { data, isLoading, refetch } = stance;

  if (isLoading) return <LoadingState thing={t("signals_title")} />;
  if (!data) return <ErrorState thing={t("signals_title")} onRetry={() => void refetch()} />;

  return (
    <>
      <StanceBlock s={data} />
      <BulletList title={t("signals_why")} items={visibleReasons(data.reasons)} />
      <BulletList title={t("signals_limitations")} items={visibleLimitations(data.limitations)} />
      <ReferenceLevels s={data} />
      <Liquidity s={data} />
    </>
  );
}

function ScenarioCell({ level, ticker }: { level: TargetLevel; ticker: string }) {
  const { locale } = useLang();
  const text = fmtPrice(locale, level.value);
  return text ? <span dir="ltr">{text}</span> : <ReasonMissing ticker={ticker} reason={level.reason} />;
}

/** Scenario values (spec 4.4.2 item 7): what each scenario implies, not a price target. */
export function ScenarioValues() {
  const { t, locale } = useLang();
  const { ticker, stance } = useStanceForTab();
  const { data } = stance;
  if (!data) return null;
  const cols: { id: "bear" | "base" | "bull"; label: string }[] = [
    { id: "bear", label: t("target_bear") },
    { id: "base", label: t("target_base") },
    { id: "bull", label: t("target_bull") },
  ];
  const levels = cols.map((c) => ({ ...c, level: data.targets[c.id] ?? UNSPECIFIED_LEVEL }));
  const allMissing = levels.every((l) => fmtPrice(locale, l.level.value) === null);
  const firstReason = levels.find((l) => l.level.reason)?.level.reason ?? null;
  const risk = fmtPrice(locale, data.stop_level.value);

  return (
    <section>
      <h2 className="section-title">{t("px_signals_scenarios")}</h2>
      <div className="table-wrap">
        {allMissing ? (
          <p className="scenario-missing">
            <ReasonMissing ticker={ticker} reason={firstReason} />
          </p>
        ) : (
          <table aria-label={t("px_signals_scenarios")}>
            <thead>
              <tr>
                {levels.map((l) => (
                  <th key={l.id} scope="col" className="num" dir="ltr">
                    {l.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                {levels.map((l) => (
                  <td key={l.id} className="num" dir="ltr">
                    <ScenarioCell level={l.level} ticker={ticker} />
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        )}
      </div>
      <p className="table-footnote">{t("px_scenarios_note")}</p>
      <p className="liquidity-line">
        {risk ? t("px_risk_reference_line", { value: risk }) : <ReasonMissing ticker={ticker} reason={data.stop_level.reason} />}
      </p>
    </section>
  );
}

/** Once per page, current language only: rules version, as-of date, research-calculation line (spec 4.4.2 item 9). */
export function StanceFooter() {
  const { t, locale } = useLang();
  const { data } = useStanceForTab().stance;
  if (!data) return null;
  return (
    <p className="table-footnote stance-footer">
      {t("px_price_footer", { rules: data.rules_version, date: fmtDate(locale, data.as_of) ?? "" })}
    </p>
  );
}
