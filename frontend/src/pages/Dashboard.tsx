import "./Dashboard.css";

/*
 * Market overview: a stat strip, the most-traded stances beside the momentum
 * leaders, and a one-line summary of the reader's tracking. Each block owns its
 * loading, empty and error state, so one failing request never blanks the page.
 */

import { useMemo, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useFiredAlerts, useSignalCoverage, useSignals, useStanceRadar, useWatchlists } from "../api/client";
import { StanceBadge, ShariahPair } from "../components/ui/Badges";
import DataTable, { type Column } from "../components/ui/DataTable";
import { Missing } from "../components/ui/Missing";
import { PageHeader } from "../components/ui/PageHeader";
import { PageTitle } from "../components/ui/PageTitle";
import { StatStrip, type StatItem } from "../components/ui/StatStrip";
import { EmptyState, ErrorState } from "../components/ui/States";
import { BarIcon, TriangleDownIcon, TriangleUpIcon } from "../components/ui/icons";
import { useLang } from "../i18n/useLang";
import { fmtDate, fmtInt, fmtPrice, toNumber } from "../lib/format";
import { useMediaQuery } from "../lib/useMediaQuery";
import type { MarketSignal, StanceRadarItem } from "../types";
import { ReturnText, RichText, Stock, TierTag, assessedStance, countText, fmt1, stockFirst } from "./companies/shared";

const ROWS = 10;

export default function Dashboard() {
  const { t, locale } = useLang();
  const narrow = useMediaQuery("(max-width: 767px)");

  const coverage = useSignalCoverage();
  const signals = useSignals({ limit: ROWS });
  const radar = useStanceRadar(50);
  const watchlists = useWatchlists();
  const unacked = useFiredAlerts({ acked: false });

  const stanceCounts = useMemo(() => {
    const c = { buy: 0, hold: 0, reduce: 0, none: 0 };
    for (const item of radar.data?.items ?? []) {
      const s = assessedStance(item.stance, item.confidence);
      c[s ?? "none"] += 1;
    }
    return c;
  }, [radar.data]);

  const unavailable = <Missing localized={t("dash_stat_unavailable")} />;
  const loadingValue = <Missing localized={t("loading")} />;
  const pick = (loading: boolean, failed: boolean, value: ReactNode | null): ReactNode =>
    loading ? loadingValue : failed || value === null ? unavailable : value;

  const latestClose = fmtDate(locale, signals.data?.as_of);
  const cov = coverage.data;

  const stances: ReactNode =
    radar.data && radar.data.items.length > 0 ? (
      <span
        className="shariah-pair"
        role="img"
        aria-label={t("dash_stances_aria", {
          buy: stanceCounts.buy,
          hold: stanceCounts.hold,
          reduce: stanceCounts.reduce,
        })}
      >
        <span className="shariah-pair">
          <TriangleUpIcon size={12} /> {fmtInt(locale, stanceCounts.buy)}
        </span>
        <span className="shariah-pair">
          <BarIcon size={12} /> {fmtInt(locale, stanceCounts.hold)}
        </span>
        <span className="shariah-pair">
          <TriangleDownIcon size={12} /> {fmtInt(locale, stanceCounts.reduce)}
        </span>
        {stanceCounts.none > 0 && (
          <span className="text-note">{t("dash_not_assessed_count", { n: fmtInt(locale, stanceCounts.none) ?? "" })}</span>
        )}
      </span>
    ) : null;

  const items: StatItem[] = [
    {
      id: "close",
      label: t("dash_stat_latest_close"),
      value: pick(signals.isLoading, signals.isError, latestClose),
    },
    {
      id: "priced",
      label: t("dash_stat_priced"),
      value: pick(
        coverage.isLoading,
        coverage.isError,
        cov
          ? t("dash_stat_priced_value", {
              priced: fmtInt(locale, cov.with_price_data) ?? "",
              total: fmtInt(locale, cov.universe_total) ?? "",
            })
          : null,
      ),
    },
    {
      id: "stances",
      label: t("dash_stat_stances"),
      value: pick(radar.isLoading, radar.isError, stances),
    },
    {
      id: "tracked",
      label: t("dash_stat_tracked"),
      value: pick(coverage.isLoading, coverage.isError, cov ? fmtInt(locale, cov.universe_total) : null),
      numeric: true,
    },
  ];

  const rules = radar.data?.rules_version ?? null;
  const radarColumns = useMemo<Column<StanceRadarItem>[]>(
    () =>
      stockFirst<StanceRadarItem>(
        [
          {
            id: "stock",
            header: t("col_stock"),
            sticky: true,
            cell: (r) => <Stock ticker={r.ticker} name={r.name} href={`/companies/${r.ticker}`} cardLinked />,
          },
          {
            id: "stance",
            header: t("signals_stance"),
            cell: (r) => <StanceBadge stance={assessedStance(r.stance, r.confidence)} confidence={r.confidence} rules={rules} />,
          },
          {
            id: "confidence",
            header: t("reco_col_confidence"),
            type: "num",
            cell: (r) =>
              assessedStance(r.stance, r.confidence) ? (
                fmtInt(locale, r.confidence)
              ) : (
                <Missing localized={t("no_engine_input")} />
              ),
          },
          {
            id: "price",
            header: t("col_last_close"),
            type: "num",
            cell: (r) => fmtPrice(locale, r.price) ?? <Missing localized={t("no_stored_price")} />,
          },
          {
            id: "shariah",
            header: t("reco_col_shariah"),
            cell: (r) => <ShariahPair shariah={r.shariah} />,
          },
        ],
        narrow,
      ),
    [t, locale, rules, narrow],
  );

  const leaderColumns = useMemo<Column<MarketSignal>[]>(
    () =>
      stockFirst<MarketSignal>(
        [
          { id: "rank", header: t("col_rank"), type: "num", cell: (s) => fmtInt(locale, s.rank) ?? "" },
          {
            id: "stock",
            header: t("col_stock"),
            sticky: true,
            cell: (s) => <Stock ticker={s.ticker} name={s.name ?? ""} href={`/companies/${s.ticker}`} cardLinked />,
          },
          {
            id: "score",
            header: t("rank_col_score"),
            type: "num",
            cell: (s) =>
              s.score === null ? (
                <Missing localized={t("rank_value_missing")} />
              ) : (
                fmt1(locale, s.score)
              ),
          },
          {
            id: "tier",
            header: t("col_tier"),
            cell: (s) => (s.tier ? <TierTag tier={s.tier} /> : <Missing localized={t("rank_value_missing")} />),
          },
          {
            id: "ret3m",
            header: t("rank_col_3m"),
            type: "num",
            cell: (s) => {
              const v = toNumber(s.factors.momentum_3m);
              return v === null ? <Missing localized={t("rank_value_missing")} /> : <ReturnText value={v} />;
            },
          },
        ],
        narrow,
      ),
    [t, locale, narrow],
  );

  const radarRows = (radar.data?.items ?? []).slice(0, ROWS);
  const leaderRows = signals.data?.results ?? [];

  const watchlistCount = watchlists.data?.length ?? 0;
  const alertCount = unacked.data?.length ?? 0;
  const trackingFailed = watchlists.isError || unacked.isError;

  return (
    <div className="page">
      <PageTitle parts={[t("dash_title")]} />
      <PageHeader title={t("dash_title")} subtitle={t("dash_subtitle")} />

      <StatStrip items={items} label={t("dash_strip_aria")} />

      <div className="dash-grid">
        <section aria-labelledby="dash-traded">
          <h2 className="section-title" id="dash-traded">
            {t("dash_traded_title")}
          </h2>
          {radar.isError ? (
            <ErrorState thing={t("dash_traded_thing")} onRetry={() => void radar.refetch()} />
          ) : (
            <DataTable
              columns={radarColumns}
              rows={radarRows}
              rowKey={(r) => r.company_id}
              caption={t("dash_traded_title")}
              loading={radar.isLoading}
              loadingThing={t("dash_traded_thing")}
              empty={<EmptyState>{t("dash_traded_empty")}</EmptyState>}
              cardFields={["stance", "confidence", "price", "shariah"]}
              rowHref={(r) => `/companies/${r.ticker}`}
              hideDensityToggle
              footnote={<Link to="/recommendations">{t("dash_traded_more")}</Link>}
            />
          )}
        </section>

        <section aria-labelledby="dash-leaders">
          <h2 className="section-title" id="dash-leaders">
            {t("dash_leaders_title")}
          </h2>
          {signals.isError ? (
            <ErrorState thing={t("dash_leaders_thing")} onRetry={() => void signals.refetch()} />
          ) : (
            <DataTable
              columns={leaderColumns}
              rows={leaderRows}
              rowKey={(s) => s.ticker}
              caption={t("dash_leaders_title")}
              loading={signals.isLoading}
              loadingThing={t("dash_leaders_thing")}
              empty={<EmptyState>{t("dash_leaders_empty")}</EmptyState>}
              cardFields={["rank", "score", "tier", "ret3m"]}
              rowHref={(s) => `/companies/${s.ticker}`}
              hideDensityToggle
              footnote={<Link to="/rankings">{t("dash_leaders_more")}</Link>}
            />
          )}
        </section>
      </div>

      <section aria-labelledby="dash-tracking">
        <h2 className="section-title" id="dash-tracking">
          {t("dash_tracking_title")}
        </h2>
        {trackingFailed ? (
          <p className="muted">{t("dash_tracking_unavailable")}</p>
        ) : watchlists.isLoading || unacked.isLoading ? (
          <p className="muted">{t("loading")}</p>
        ) : watchlistCount === 0 && alertCount === 0 ? (
          <p>
            <Link to="/watchlists">{t("dash_tracking_empty")}</Link>
          </p>
        ) : (
          <p>
            <RichText
              text={t("dash_tracking_line")}
              parts={{
                watchlists: <Link to="/watchlists">{countText(t, locale, watchlistCount, "watchlists_count")}</Link>,
                alerts: <Link to="/alerts">{countText(t, locale, alertCount, "unacked_alerts_count")}</Link>,
              }}
            />
          </p>
        )}
      </section>
    </div>
  );
}
