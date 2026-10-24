/*
 * Recommendations (signal-rules-2.0): model stances for the most-traded EGX
 * stocks with confidence, composite, ATR reference levels, liquidity and
 * Shariah side by side. One batch request (useStanceRadar); the Shariah-only
 * toggle narrows the server query to official EGX33 members, the stance and
 * text filters are local. Filter state lives in the URL. Missing values render
 * as <Missing> with the reason, never zero.
 */

import { useMemo, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";
import { useSignals, useStanceRadar } from "../api/client";
import { StanceBadge, Tag, ShariahPair, type StanceCode } from "../components/ui/Badges";
import DataTable, { type Column } from "../components/ui/DataTable";
import { Missing } from "../components/ui/Missing";
import { PageHeader } from "../components/ui/PageHeader";
import { PageTitle } from "../components/ui/PageTitle";
import { Segmented } from "../components/ui/Segmented";
import { EmptyState, ErrorState, NoMatch } from "../components/ui/States";
import { useLang } from "../i18n/useLang";
import { fmtDate, fmtInt, fmtPrice, fmtScore, toNumber } from "../lib/format";
import { useMediaQuery } from "../lib/useMediaQuery";
import type { StanceRadarItem } from "../types";
import { Stock, assessedStance, countText, stockFirst } from "./companies/shared";

type StanceFilter = "all" | StanceCode;
const STANCE_FILTERS: readonly StanceFilter[] = ["all", "buy", "hold", "reduce"];
const STANCE_ORDER: Record<StanceCode, number> = { buy: 0, hold: 1, reduce: 2 };

interface RecoRow {
  item: StanceRadarItem;
  /** Position in the server's most-traded order. */
  rank: number;
  /** Null means "Not assessed" (no stance, or the zero-confidence default). */
  stance: StanceCode | null;
}

function isStanceFilter(value: string | null): value is StanceFilter {
  return value !== null && (STANCE_FILTERS as readonly string[]).includes(value);
}

export default function Recommendations() {
  const { t, locale } = useLang();
  const narrow = useMediaQuery("(max-width: 767px)");
  const [params, setParams] = useSearchParams();

  const stanceParam = params.get("stance");
  const stanceFilter: StanceFilter = isStanceFilter(stanceParam) ? stanceParam : "all";
  const shariahOnly = params.get("egx33") === "1";
  const text = params.get("q") ?? "";

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
  const clearFilters = (): void => update({ stance: null, egx33: null, q: null });

  const { data, isLoading, error, refetch } = useStanceRadar(50, shariahOnly ? "egx33" : undefined);
  // Latest scored close date, the same date the stances are computed on.
  const { data: market } = useSignals({ limit: 1 });

  const allRows = useMemo<RecoRow[]>(
    () =>
      (data?.items ?? []).map((item, index) => ({
        item,
        rank: index + 1,
        stance: assessedStance(item.stance, item.confidence),
      })),
    [data],
  );

  // Text filter first, so the stance counts reflect what the reader typed.
  const textRows = useMemo(() => {
    const q = text.trim().toLowerCase();
    if (!q) return allRows;
    return allRows.filter(
      ({ item }) => item.ticker.toLowerCase().includes(q) || item.name.toLowerCase().includes(q),
    );
  }, [allRows, text]);

  const counts = useMemo(() => {
    const c: Record<StanceCode, number> = { buy: 0, hold: 0, reduce: 0 };
    for (const row of textRows) if (row.stance) c[row.stance] += 1;
    return c;
  }, [textRows]);

  const rows = useMemo(
    () => (stanceFilter === "all" ? textRows : textRows.filter((row) => row.stance === stanceFilter)),
    [textRows, stanceFilter],
  );

  const rules = data?.rules_version ?? null;
  const filtersActive = stanceFilter !== "all" || shariahOnly || text !== "";

  const columns = useMemo<Column<RecoRow>[]>(() => {
    const dash = <Missing localized={t("no_engine_input")} />;
    const level = (v: string | undefined): ReactNode => {
      const formatted = v === undefined ? null : fmtPrice(locale, v);
      return formatted ?? <Missing localized={t("reco_no_atr")} />;
    };
    return stockFirst<RecoRow>(
      [
        {
          id: "rank",
          header: t("col_rank"),
          type: "num",
          sortable: true,
          sortValue: (r) => r.rank,
          cell: (r) => r.rank,
        },
        {
          id: "stock",
          header: t("reco_col_stock"),
          sortable: true,
          sticky: true,
          sortValue: (r) => r.item.ticker,
          cell: (r) => (
            <span className="shariah-pair">
              <Stock ticker={r.item.ticker} name={r.item.name} href={`/companies/${r.item.ticker}/price`} cardLinked />
              {r.item.low_liquidity && <Tag title={t("low_liquidity_title")}>{t("low_liquidity")}</Tag>}
            </span>
          ),
        },
        {
          id: "stance",
          header: t("signals_stance"),
          sortable: true,
          sortValue: (r) => (r.stance ? STANCE_ORDER[r.stance] : null),
          cell: (r) => <StanceBadge stance={r.stance} confidence={r.item.confidence} rules={rules} />,
        },
        {
          id: "confidence",
          header: t("reco_col_confidence"),
          type: "num",
          sortable: true,
          sortValue: (r) => (r.stance ? r.item.confidence : null),
          cell: (r) => (r.stance ? fmtInt(locale, r.item.confidence) : dash),
        },
        {
          id: "composite",
          header: t("reco_col_composite"),
          type: "num",
          sortable: true,
          sortValue: (r) => (r.stance ? toNumber(r.item.score) : null),
          cell: (r) => (r.stance ? (fmtScore(locale, r.item.score) ?? dash) : dash),
        },
        {
          id: "price",
          header: t("reco_col_price"),
          type: "num",
          sortable: true,
          sortValue: (r) => toNumber(r.item.price),
          cell: (r) => fmtPrice(locale, r.item.price) ?? <Missing localized={t("no_stored_price")} />,
        },
        {
          id: "upside",
          header: t("reco_col_upside"),
          type: "num",
          sortable: true,
          sortValue: (r) => toNumber(r.item.reference_levels?.upside),
          cell: (r) => level(r.item.reference_levels?.upside),
        },
        {
          id: "downside",
          header: t("reco_col_downside"),
          type: "num",
          sortable: true,
          sortValue: (r) => toNumber(r.item.reference_levels?.downside),
          cell: (r) => level(r.item.reference_levels?.downside),
        },
        {
          id: "shariah",
          header: t("reco_col_shariah"),
          sortable: true,
          sortValue: (r) => r.item.shariah?.verdict ?? null,
          cell: (r) => <ShariahPair shariah={r.item.shariah} />,
        },
      ],
      narrow,
    );
  }, [t, locale, rules, narrow]);

  const stanceOptions = STANCE_FILTERS.map((value) => ({
    value,
    label:
      value === "all"
        ? t("reco_filter_all")
        : `${t(value === "buy" ? "stance_buy" : value === "hold" ? "stance_hold" : "stance_reduce")} ${fmtInt(locale, counts[value])}`,
  }));

  const asOf = fmtDate(locale, market?.as_of);
  const meta = [
    countText(t, locale, rows.length, "stocks_count"),
    asOf ? t("prices_as_of_short", { date: asOf }) : null,
    rules ? t("rules_label", { rules }) : null,
  ]
    .filter((part): part is string => part !== null)
    .join(" · ");

  const empty = filtersActive ? (
    <NoMatch things={t("reco_things")} onClear={clearFilters} />
  ) : (
    <EmptyState>{t("reco_empty")}</EmptyState>
  );

  return (
    <div className="page">
      <PageTitle parts={[t("reco_title")]} />
      <PageHeader title={t("reco_title")} subtitle={t("reco_subtitle")} />

      <div className="filters">
        <Segmented
          label={t("reco_filter_label")}
          options={stanceOptions}
          value={stanceFilter}
          onChange={(value) => update({ stance: value === "all" ? null : value })}
        />
        <label>
          <input
            type="checkbox"
            checked={shariahOnly}
            onChange={(e) => update({ egx33: e.target.checked ? "1" : null })}
          />
          {t("reco_shariah_only")}
        </label>
        <input
          type="search"
          className="filter-input"
          aria-label={t("reco_filter_text")}
          placeholder={t("reco_filter_text")}
          value={text}
          onChange={(e) => update({ q: e.target.value })}
        />
      </div>

      {error ? (
        <ErrorState thing={t("reco_thing_loading")} onRetry={() => void refetch()} />
      ) : (
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(r) => r.item.company_id}
          caption={t("reco_title")}
          loading={isLoading}
          loadingThing={t("reco_thing_loading")}
          meta={meta}
          empty={empty}
          defaultSort={{ id: "rank", dir: "asc" }}
          cardFields={["stance", "confidence", "price", "shariah"]}
          rowHref={(r) => `/companies/${r.item.ticker}/price`}
          footnote={
            <>
              {t("reco_levels_note")} {t("reco_confidence_note")} {t("reco_composite_note")}{" "}
              {t("not_investment_advice")}
            </>
          }
        />
      )}
    </div>
  );
}
