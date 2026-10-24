import "../components/hub/hubPages.css";

import { useState } from "react";
import { useParams } from "react-router-dom";
import { useCompanyByTicker, useDataQuality, useFairValue, useStance } from "../api/client";
import { fiftyTwoWeekRange, useYearPrices } from "../components/hub/priceData";
import { ReasonMissing } from "../components/hub/Reason";
import SectionLink from "../components/hub/SectionLink";
import { Egx33Note, ShariahBadge, StanceBadge, Tag } from "../components/ui/Badges";
import { BackendText } from "../components/ui/BackendText";
import { Missing } from "../components/ui/Missing";
import PriceChart from "../components/ui/PriceChart";
import { StatStrip, type StatItem } from "../components/ui/StatStrip";
import { useLang } from "../i18n/useLang";
import { fmtDate, fmtEgpCompact, fmtInt, fmtPct, fmtPrice, toNumber } from "../lib/format";
import type { ChartRange } from "../lib/priceChart";
import { visibleReasons } from "../lib/stanceModel";
import type { Company, ComputeMeta, DataQualityScore } from "../types";

const DQ_SCOPES = ["price_history", "company_profile", "financial_statements"] as const;
const DQ_SHORT = {
  price_history: "ov_dq_prices",
  company_profile: "ov_dq_profile",
  financial_statements: "ov_dq_statements",
} as const;

function Skeleton() {
  return <span className="skeleton-bar" style={{ width: "6ch" }} />;
}

/** Free float arrives as a fraction (0.25) or already a percent (25); show a percent either way. */
function freeFloatText(locale: string, value: string | null): string | null {
  const n = toNumber(value);
  if (n === null) return null;
  return fmtPct(locale, n <= 1 ? n : n / 100);
}

function DataQualityLine({ items, to }: { items: readonly DataQualityScore[]; to: string }) {
  const { t } = useLang();
  const parts = DQ_SCOPES.map((scope) => {
    const item = items.find((i) => i.scope === scope);
    const name = t(DQ_SHORT[scope]);
    return !item || item.status === "MISSING"
      ? t("ov_dq_not_scored", { scope: name })
      : t("ov_dq_score", { scope: name, score: Math.round(item.score) });
  });
  return (
    <p className="ov-dq-line">
      <span>{parts.join(" · ")}</span> <SectionLink to={to}>{t("ov_dq_link")}</SectionLink>
    </p>
  );
}

function Profile({ company }: { company: Company }) {
  const { t, locale } = useLang();
  const rows: { id: string; label: string; value: string | null; ltr?: boolean }[] = [
    { id: "isin", label: t("ov_isin"), value: company.isin, ltr: true },
    { id: "sector", label: t("ov_sector"), value: company.sector },
    { id: "listing", label: t("ov_listing_date"), value: fmtDate(locale, company.listing_date) },
    { id: "shares", label: t("ov_shares"), value: fmtInt(locale, company.shares_outstanding), ltr: true },
    { id: "float", label: t("ov_free_float"), value: freeFloatText(locale, company.free_float), ltr: true },
  ];
  if (rows.every((r) => r.value === null)) {
    return <p className="empty">{t("ov_profile_empty")}</p>;
  }
  return (
    <dl className="profile-list card-surface">
      {rows.map((r) => (
        <div key={r.id} className="profile-row">
          <dt>{r.label}</dt>
          <dd {...(r.ltr ? { dir: "ltr" } : {})}>{r.value ?? <Missing localized={t("ov_not_in_data")} />}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Hub Overview (spec 4.4.1): day stats, 1Y chart, at a glance, data quality, profile. Read-only. */
export default function CompanyDetail() {
  const { ticker = "" } = useParams<{ ticker: string }>();
  const { t, locale } = useLang();
  const { data: company } = useCompanyByTicker(ticker);
  const { query, bars, series, latest, source } = useYearPrices(company?.id);
  const stance = useStance(ticker);
  const fairValue = useFairValue(company?.id);
  const quality = useDataQuality(company?.id);
  const [range, setRange] = useState<ChartRange>("1Y");

  if (!company) return null;

  const base = `/companies/${encodeURIComponent(company.ticker)}`;
  const week52 = fiftyTwoWeekRange(bars);
  const s = stance.data;
  const loading = query.isLoading;
  const num = (text: string | null) => (loading ? <Skeleton /> : (text ?? <Missing localized={t("ov_not_in_data")} />));

  const items: StatItem[] = [
    { id: "open", label: t("ov_open"), numeric: true, value: num(latest ? fmtPrice(locale, latest.open) : null) },
    { id: "high", label: t("ov_high"), numeric: true, value: num(latest ? fmtPrice(locale, latest.high) : null) },
    { id: "low", label: t("ov_low"), numeric: true, value: num(latest ? fmtPrice(locale, latest.low) : null) },
    { id: "volume", label: t("ov_volume"), numeric: true, value: num(latest ? fmtInt(locale, latest.volume) : null) },
    { id: "value", label: t("ov_value_traded"), numeric: true, value: num(latest ? fmtEgpCompact(locale, latest.value_traded) : null) },
    {
      id: "range",
      label: t("ov_range_52w"),
      numeric: true,
      value: num(week52 ? `${fmtPrice(locale, week52.low)} – ${fmtPrice(locale, week52.high)}` : null),
    },
    {
      id: "liquidity",
      label: t("ov_avg_value", { n: s?.liquidity.window ?? 20 }),
      numeric: true,
      value: stance.isLoading ? (
        <Skeleton />
      ) : (
        (fmtEgpCompact(locale, s?.liquidity.avg_value_traded) ?? <Missing localized={t("ov_not_in_data")} />)
      ),
    },
  ];

  const reason = s ? visibleReasons(s.reasons)[0] : undefined;
  const fv = fairValue.data;
  const fvMeta: Partial<ComputeMeta> = fv ?? {};
  const fvValue = fv ? fmtPrice(locale, fv.fair_value.value) : null;

  return (
    <div className="page">
      <StatStrip items={items} label={t("ov_stats_aria")} />

      <section className="card-surface" aria-label={t("ov_chart_aria")}>
        <PriceChart bars={series} range={range} onRangeChange={setRange} source={source} />
      </section>

      <section>
        <h2 className="section-title">{t("ov_glance")}</h2>
        <div className="glance-grid">
          <article className="glance-item card-surface">
            <h3>{t("ov_glance_stance")}</h3>
            {stance.isLoading ? (
              <Skeleton />
            ) : s ? (
              <>
                <p className="glance-main">
                  <StanceBadge stance={s.stance} confidence={s.confidence} reasonsCount={s.reasons.length} rules={s.rules_version} />
                  {s.confidence > 0 && <span className="text-note">{t("stance_confidence", { c: s.confidence })}</span>}
                </p>
                <p className="glance-text">{reason ? <BackendText>{reason}</BackendText> : t("stance_not_assessed_tooltip")}</p>
              </>
            ) : (
              <Missing localized={t("load_error_thing", { thing: t("ov_glance_stance") })} />
            )}
            <SectionLink to={`${base}/price`}>{t("tab_price")}</SectionLink>
          </article>

          <article className="glance-item card-surface">
            <h3>{t("ov_glance_shariah")}</h3>
            {stance.isLoading ? (
              <Skeleton />
            ) : s ? (
              <div className="shariah-full">
                <ShariahBadge verdict={s.shariah.verdict} />
                <Egx33Note shariah={s.shariah} />
              </div>
            ) : (
              <Missing localized={t("load_error_thing", { thing: t("ov_glance_shariah") })} />
            )}
            <SectionLink to={`${base}/shariah`}>{t("tab_shariah")}</SectionLink>
          </article>

          <article className="glance-item card-surface">
            <h3>{t("ov_glance_fair_value")}</h3>
            {fairValue.isLoading ? (
              <Skeleton />
            ) : fv ? (
              <>
                <p className="glance-text">
                  {fvValue ? t("ov_fair_value_line", { value: fvValue }) : <ReasonMissing ticker={ticker} reason={fv.fair_value.reason} />}
                </p>
                {fvMeta.provisional && (
                  <p>
                    <Tag title={t("source_provisional_title")}>{t("ov_provisional_vendor")}</Tag>
                  </p>
                )}
              </>
            ) : (
              <Missing localized={t("load_error_thing", { thing: t("ov_glance_fair_value") })} />
            )}
            <SectionLink to={`${base}/valuation`}>{t("tab_valuation")}</SectionLink>
          </article>
        </div>
      </section>

      <section>
        <h2 className="section-title">{t("ov_data_quality")}</h2>
        {quality.isLoading ? (
          <Skeleton />
        ) : quality.data ? (
          <DataQualityLine items={quality.data.items} to={`${base}/financials/quality`} />
        ) : (
          <Missing localized={t("load_error_thing", { thing: t("ov_data_quality") })} />
        )}
      </section>

      <section>
        <h2 className="section-title">{t("ov_profile")}</h2>
        <Profile company={company} />
      </section>
    </div>
  );
}
