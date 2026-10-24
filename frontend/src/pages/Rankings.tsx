import "./Rankings.css";

/*
 * Momentum rankings: every company with price history, scored 0-100 against
 * the others on prices only (egx_price_momentum). Read-only: scores are
 * computed by the backend after each price sync. Missing values render as
 * <Missing>, never zero; a drawdown is always a decline, so it carries no
 * colour or arrow, and trend is a plain signed number.
 */

import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useScoringModel, useSignals, useUnscorable } from "../api/client";
import DataTable, { type Column } from "../components/ui/DataTable";
import { Missing } from "../components/ui/Missing";
import { Notice } from "../components/ui/Notice";
import { PageHeader } from "../components/ui/PageHeader";
import { PageTitle } from "../components/ui/PageTitle";
import { Segmented } from "../components/ui/Segmented";
import { EmptyState, ErrorState, NoMatch } from "../components/ui/States";
import type { CopyKey } from "../i18n";
import { useLang } from "../i18n/useLang";
import { fmtDate, fmtInt, fmtPct, toNumber } from "../lib/format";
import { useDebouncedValue } from "../lib/useDebouncedValue";
import { useMediaQuery } from "../lib/useMediaQuery";
import type { MarketSignal, SignalTier } from "../types";
import { ReturnText, Stock, TierTag, countText, fmt1, fmtSigned2, stockFirst, tierLabel } from "./companies/shared";

type TierFilter = "all" | SignalTier;
const TIER_FILTERS: readonly TierFilter[] = ["all", "STRONGEST", "STRONG", "NEUTRAL", "WEAK", "WEAKEST"];
const TIER_ORDER: Record<SignalTier, number> = { STRONGEST: 0, STRONG: 1, NEUTRAL: 2, WEAK: 3, WEAKEST: 4 };

type ShowValue = "25" | "50" | "100" | "all";
const SHOW_VALUES: readonly ShowValue[] = ["25", "50", "100", "all"];
const SHOW_LIMIT: Record<ShowValue, number> = { "25": 25, "50": 50, "100": 100, all: 500 };

const FACTOR_KEY: Record<string, CopyKey> = {
  momentum_1m: "factor_momentum_1m",
  momentum_3m: "factor_momentum_3m",
  momentum_6m: "factor_momentum_6m",
  trend_alignment: "factor_trend_alignment",
  distance_from_high: "factor_distance_from_high",
  max_drawdown: "factor_max_drawdown",
  volatility: "factor_volatility",
  liquidity: "factor_liquidity",
  volume_confirmation: "factor_volume_confirmation",
};

const ORDINAL_SUFFIX: Record<string, string> = { one: "st", two: "nd", few: "rd", other: "th" };
const ordinalRules = new Intl.PluralRules("en", { type: "ordinal" });

function isTier(value: string | null): value is TierFilter {
  return value !== null && (TIER_FILTERS as readonly string[]).includes(value);
}
function isShow(value: string | null): value is ShowValue {
  return value !== null && (SHOW_VALUES as readonly string[]).includes(value);
}

export default function Rankings() {
  const { t, lang, locale } = useLang();
  const narrow = useMediaQuery("(max-width: 767px)");
  const [params, setParams] = useSearchParams();
  const tierParam = params.get("tier");
  const tier: TierFilter = isTier(tierParam) ? tierParam : "all";
  const showParam = params.get("show");
  const show: ShowValue = isShow(showParam) ? showParam : "50";

  const [minDraft, setMinDraft] = useState("");
  const minDebounced = useDebouncedValue(minDraft, 250);
  const minParsed = Number(minDebounced);
  const minScore = minDebounced.trim() !== "" && Number.isFinite(minParsed) ? Math.min(100, Math.max(0, minParsed)) : 0;
  const [showExcluded, setShowExcluded] = useState(false);

  const update = (patch: Record<string, string | null>): void => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [key, value] of Object.entries(patch)) {
          if (value === null || value === "") next.delete(key);
          else next.set(key, value);
        }
        return next;
      },
      { replace: true },
    );
  };
  const clearFilters = (): void => {
    update({ tier: null, show: null });
    setMinDraft("");
  };

  const { data, isLoading, error, refetch } = useSignals({
    limit: SHOW_LIMIT[show],
    tier: tier === "all" ? undefined : tier,
    min_score: minScore > 0 ? minScore : undefined,
  });
  const { data: model } = useScoringModel();
  const { data: unscorable } = useUnscorable();

  const filtersActive = tier !== "all" || minScore > 0;

  const factorLabel = (key: string): string => {
    const copyKey = FACTOR_KEY[key];
    return copyKey ? t(copyKey) : key.replace(/_/g, " ");
  };
  const percentileText = (value: number): string => {
    const n = Math.round(value * 100);
    return lang === "ar" ? (fmtInt(locale, n) ?? "") : `${n}${ORDINAL_SUFFIX[ordinalRules.select(n)] ?? "th"}`;
  };
  const topFactors = (s: MarketSignal): string => {
    const top = Object.entries(s.percentiles)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 2)
      .map(([key, value]) => t("rank_factor_pctl", { factor: factorLabel(key), p: percentileText(value) }));
    if (s.excluded_factors.length > 0) top.push(countText(t, locale, s.excluded_factors.length, "factors_missing"));
    return top.join(" · ");
  };

  const columns = useMemo<Column<MarketSignal>[]>(() => {
    const missing = <Missing localized={t("rank_value_missing")} />;
    const factor = (s: MarketSignal, key: string): number | null => toNumber(s.factors[key]);
    return stockFirst<MarketSignal>(
      [
        {
          id: "rank",
          header: t("col_rank"),
          type: "num",
          sortable: true,
          sortValue: (s) => s.rank,
          cell: (s) => fmtInt(locale, s.rank) ?? missing,
        },
        {
          id: "stock",
          header: t("col_stock"),
          sortable: true,
          sticky: true,
          sortValue: (s) => s.ticker,
          cell: (s) => <Stock ticker={s.ticker} name={s.name ?? ""} href={`/companies/${s.ticker}`} cardLinked />,
        },
        {
          id: "score",
          header: t("rank_col_score"),
          type: "num",
          sortable: true,
          sortValue: (s) => s.score,
          cell: (s) => (s.score === null ? missing : fmt1(locale, s.score)),
        },
        {
          id: "tier",
          header: t("col_tier"),
          sortable: true,
          sortValue: (s) => (s.tier ? TIER_ORDER[s.tier] : null),
          cell: (s) => (s.tier ? <TierTag tier={s.tier} /> : missing),
        },
        {
          id: "ret3m",
          header: t("rank_col_3m"),
          type: "num",
          sortable: true,
          sortValue: (s) => factor(s, "momentum_3m"),
          cell: (s) => {
            const v = factor(s, "momentum_3m");
            return v === null ? missing : <ReturnText value={v} />;
          },
        },
        {
          id: "ret6m",
          header: t("rank_col_6m"),
          type: "num",
          sortable: true,
          sortValue: (s) => factor(s, "momentum_6m"),
          cell: (s) => {
            const v = factor(s, "momentum_6m");
            return v === null ? missing : <ReturnText value={v} />;
          },
        },
        {
          id: "trend",
          header: t("rank_col_trend"),
          type: "num",
          sortable: true,
          sortValue: (s) => factor(s, "trend_alignment"),
          cell: (s) => {
            const v = factor(s, "trend_alignment");
            return v === null ? missing : fmtSigned2(locale, v);
          },
        },
        {
          id: "drawdown",
          header: t("rank_col_drawdown"),
          type: "num",
          sortable: true,
          // The API reports the size of the fall; a larger fall sorts as a lower value.
          sortValue: (s) => {
            const v = factor(s, "max_drawdown");
            return v === null ? null : -Math.abs(v);
          },
          cell: (s) => {
            const v = factor(s, "max_drawdown");
            if (v === null) return missing;
            const text = fmtPct(locale, Math.abs(v));
            return text === null ? missing : v === 0 ? text : `−${text}`;
          },
        },
        {
          id: "factors",
          header: t("rank_col_factors"),
          cell: (s) => {
            const text = topFactors(s);
            return text === "" ? missing : <span title={s.rationale ?? text}>{text}</span>;
          },
        },
      ],
      narrow,
    );
    // topFactors only reads t, locale and lang.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [t, lang, locale, narrow]);

  const tierOptions = TIER_FILTERS.map((value) => ({
    value,
    label: value === "all" ? t("reco_filter_all") : tierLabel(t, value),
  }));
  const showOptions = SHOW_VALUES.map((value) => ({
    value,
    label: value === "all" ? t("rank_show_all") : (fmtInt(locale, Number(value)) ?? value),
  }));

  const coverage = data?.coverage;
  const asOf = fmtDate(locale, data?.as_of);
  const meta = coverage ? (
    <>
      {t("rank_meta_scored", {
        scored: fmtInt(locale, coverage.analyzable) ?? "",
        total: fmtInt(locale, coverage.active_total) ?? "",
      })}
      {coverage.unscorable > 0 && (
        <>
          {" · "}
          {countText(t, locale, coverage.unscorable, "no_history_count")} (
          <button type="button" className="link-btn" aria-expanded={showExcluded} onClick={() => setShowExcluded((v) => !v)}>
            {showExcluded ? t("rank_hide_excluded") : t("rank_show_excluded")}
          </button>
          )
        </>
      )}
      {asOf && ` · ${t("rank_meta_as_of", { date: asOf })}`}
      {data?.model && (
        <>
          {` · ${t("rank_meta_model")} `}
          <span className="text-mono" dir="ltr">
            {data.model}
          </span>
        </>
      )}
    </>
  ) : undefined;

  const excluded = (unscorable ?? []).filter((u) => u.ticker !== null);

  const empty = filtersActive ? (
    <NoMatch things={t("rank_things")} onClear={clearFilters} />
  ) : (
    <EmptyState>{t("rank_empty")}</EmptyState>
  );

  return (
    <div className="page">
      <PageTitle parts={[t("rank_title")]} />
      <PageHeader title={t("rank_title")} subtitle={t("rank_subtitle")} />

      <div className="filters">
        <Segmented label={t("rank_tier_label")} options={tierOptions} value={tier} onChange={(v) => update({ tier: v === "all" ? null : v })} />
        <label>
          {t("rank_min_score")}
          <input
            type="number"
            min={0}
            max={100}
            step={5}
            inputMode="numeric"
            className="filter-select"
            dir="ltr"
            value={minDraft}
            placeholder="0"
            onChange={(e) => setMinDraft(e.target.value)}
          />
        </label>
        <Segmented label={t("rank_show_label")} options={showOptions} value={show} onChange={(v) => update({ show: v === "50" ? null : v })} />
      </div>

      {data?.notice && (
        <Notice>
          <span {...(lang === "ar" ? { lang: "en", dir: "ltr" } : {})}>{data.notice}</span>
        </Notice>
      )}

      {showExcluded && excluded.length > 0 && (
        <section aria-label={t("rank_excluded_title")}>
          <h2 className="section-title">{t("rank_excluded_title")}</h2>
          <ul className="excluded-list">
            {excluded.map((u) => (
              <li key={u.ticker}>
                <Stock ticker={u.ticker ?? ""} name={u.name ?? ""} href={`/companies/${u.ticker ?? ""}`} />{" "}
                {u.reason && (
                  <span className="text-note" {...(lang === "ar" ? { lang: "en", dir: "ltr" } : {})}>
                    {u.reason}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {error ? (
        <ErrorState thing={t("rank_thing")} onRetry={() => void refetch()} />
      ) : (
        <DataTable
          columns={columns}
          rows={data?.results ?? []}
          rowKey={(s) => s.ticker}
          caption={t("rank_title")}
          loading={isLoading}
          loadingThing={t("rank_thing")}
          meta={meta}
          empty={empty}
          defaultSort={{ id: "rank", dir: "asc" }}
          cardFields={["score", "tier", "ret3m", "drawdown"]}
          rowHref={(s) => `/companies/${s.ticker}`}
          footnote={t("rank_disclaimer")}
        />
      )}

      {model && (
        <details className="model-factors">
          <summary>{t("rank_how_title")}</summary>
          <ul>
            {model.factors.map((f) => (
              <li key={f.key}>
                <strong>{factorLabel(f.key)}</strong>
                {" — "}
                {t("rank_how_weight", { w: fmtInt(locale, f.weight * 100) ?? "" })},{" "}
                {f.direction === "HIGHER_IS_BETTER" ? t("rank_how_higher") : t("rank_how_lower")}
              </li>
            ))}
          </ul>
          <p className="muted">{t("rank_how_note")}</p>
        </details>
      )}
    </div>
  );
}
