
/*
 * Companies: every EGX-listed company we track, with last close, stance and
 * momentum. Data comes from three batch requests, never one per row:
 *   last close, stance, gross margin -> useCompaniesOverview (this page's tickers)
 *   momentum score and tier          -> useSignals (single batch)
 *   company list + search            -> useCompanies (server paging)
 * The only controls are search, sort by ticker and pagination. Missing values
 * render as <Missing> with the reason, never as zero.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useCompanies, useCompaniesOverview, useSignals, useStanceRadar } from "../api/client";
import DataTable, { type Column } from "../components/ui/DataTable";
import { Missing } from "../components/ui/Missing";
import { PageHeader } from "../components/ui/PageHeader";
import { PageTitle } from "../components/ui/PageTitle";
import { EmptyState, ErrorState } from "../components/ui/States";
import { useLang } from "../i18n/useLang";
import { fmtDate, fmtInt, fmtPct, fmtPrice } from "../lib/format";
import { useMediaQuery } from "../lib/useMediaQuery";
import { FORMING_NAME_KEY } from "../lib/priceOverlays";
import { Segmented } from "../components/ui/Segmented";
import type { Company, FormingFilter, FormingSummary, MarketSignal } from "../types";
import {
  Pagination,
  RichText,
  Stock,
  StanceWithConfidence,
  TierTag,
  assessedStance,
  countText,
  fmt1,
  stockFirst,
} from "./companies/shared";

const PAGE_SIZE = 50;

/** Statement lines the gross-margin calculation can be missing. */
const LINE_KEY = {
  revenue: "comp_line_revenue",
  cost_of_revenue: "comp_line_cost_of_revenue",
  gross_profit: "comp_line_gross_profit",
} as const;
function isLine(line: string): line is keyof typeof LINE_KEY {
  return line in LINE_KEY;
}
const SEARCH_DEBOUNCE_MS = 250;

const FORMING_CHOICES = ["any", "up", "down"] as const satisfies readonly FormingFilter[];
function parseForming(value: string | null): FormingFilter | null {
  return FORMING_CHOICES.find((c) => c === value) ?? null;
}

export default function Companies() {
  const { t, locale } = useLang();
  const narrow = useMediaQuery("(max-width: 767px)");
  const [params, setParams] = useSearchParams();
  // `search` is the older parameter name still used by "company not found" links.
  const q = params.get("q") ?? params.get("search") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? "1") || 1);
  const forming = parseForming(params.get("forming"));

  const update = (patch: Record<string, string | null>): void => {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("search");
        for (const [key, value] of Object.entries(patch)) {
          if (value === null || value === "") next.delete(key);
          else next.set(key, value);
        }
        return next;
      },
      { replace: true },
    );
  };

  // One query per pause in typing; the URL holds the committed value.
  const [draft, setDraft] = useState(q);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => setDraft(q), [q]);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  const onSearch = (value: string): void => {
    setDraft(value);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => update({ q: value.trim() || null, page: null }), SEARCH_DEBOUNCE_MS);
  };
  const clearSearch = (): void => {
    window.clearTimeout(timer.current);
    setDraft("");
    update({ q: null, page: null });
  };

  const list = useCompanies({ page, page_size: PAGE_SIZE, search: q || undefined, forming: forming ?? undefined });
  const universe = useCompanies({ page_size: 1 });
  const universeTotal = universe.data?.total ?? (q ? undefined : list.data?.total);

  const tickers = useMemo(() => (list.data?.items ?? []).map((c) => c.ticker), [list.data]);
  const overview = useCompaniesOverview(tickers, forming !== null);
  const signals = useSignals({ limit: 500 });
  const radar = useStanceRadar(50);
  const rules = radar.data?.rules_version ?? null;

  const signalByTicker = useMemo(() => {
    const map = new Map<string, MarketSignal>();
    for (const signal of signals.data?.results ?? []) map.set(signal.ticker, signal);
    return map;
  }, [signals.data]);

  const marketDate = overview.data?.price_date ?? null;
  // With the forming filter on, a company opens with its chart patterns shown.
  const companyHref = useCallback(
    (ticker: string): string => `/companies/${ticker}${forming !== null ? "?patterns=1" : ""}`,
    [forming],
  );
  const formingOptions = [
    { value: "all" as const, label: t("comp_forming_all") },
    ...FORMING_CHOICES.map((c) => ({ value: c, label: t(`comp_forming_${c}` as const) })),
  ];
  const overviewPending = overview.isLoading;

  const columns = useMemo<Column<Company>[]>(() => {
    const pending = <span className="skeleton-bar" />;
    const lineLabel = (line: string): string => (isLine(line) ? t(LINE_KEY[line]) : line.replace(/_/g, " "));
    const shapeText = (f: FormingSummary): string => {
      const nameKey = FORMING_NAME_KEY[f.pattern];
      const name = nameKey ? t(nameKey) : f.pattern.replace(/_/g, " ");
      const above = fmtPrice(locale, f.confirm_above);
      const below = fmtPrice(locale, f.confirm_below);
      const level =
        above !== null && below !== null
          ? t("comp_forming_either", { above, below })
          : above !== null
            ? t("comp_forming_above", { price: above })
            : t("comp_forming_below", { price: below ?? "" });
      return `${name} · ${level} · ${t("comp_forming_left", { n: fmtInt(locale, f.sessions_left) ?? "" })}`;
    };
    const formingColumn: Column<Company>[] =
      forming === null
        ? []
        : [
            {
              id: "forming",
              header: t("comp_col_forming"),
              cell: (c) => {
                if (overviewPending) return pending;
                const shapes = overview.data?.items[c.ticker]?.forming ?? [];
                return shapes.length === 0 ? (
                  <Missing localized={t("comp_forming_none")} />
                ) : (
                  <span className="forming-cell">
                    {shapes.map((f) => (
                      <span key={f.pattern}>{shapeText(f)}</span>
                    ))}
                  </span>
                );
              },
            },
          ];
    return stockFirst<Company>(
      [
        {
          id: "stock",
          header: t("col_stock"),
          sortable: true,
          sticky: true,
          sortValue: (c) => c.ticker,
          cell: (c) => <Stock ticker={c.ticker} name={c.name} nameAr={c.name_ar} href={companyHref(c.ticker)} cardLinked />,
        },
        ...formingColumn,
        {
          id: "close",
          header: t("comp_col_close"),
          type: "num",
          cell: (c) => {
            if (overviewPending) return pending;
            const close = overview.data?.items[c.ticker]?.latest_price?.close;
            return fmtPrice(locale, close) ?? <Missing localized={t("no_stored_price")} />;
          },
        },
        {
          id: "asof",
          header: t("comp_col_asof"),
          type: "num",
          cell: (c) => {
            if (overviewPending) return pending;
            const date = overview.data?.items[c.ticker]?.latest_price?.date;
            const text = fmtDate(locale, date);
            if (text === null || !date) return <Missing localized={t("no_stored_price")} />;
            const stale = marketDate !== null && date < marketDate;
            return stale ? (
              <span className="badge badge-warn" title={t("comp_stale_title")}>
                {text}
              </span>
            ) : (
              text
            );
          },
        },
        {
          id: "stance",
          header: t("comp_col_stance"),
          cell: (c) => {
            if (overviewPending) return pending;
            const s = overview.data?.items[c.ticker]?.stance;
            return (
              <StanceWithConfidence
                stance={s ? assessedStance(s.stance, s.confidence) : null}
                confidence={s?.confidence}
                reasonsCount={s?.reasons.length}
                rules={rules}
              />
            );
          },
        },
        {
          id: "momentum",
          header: t("comp_col_momentum"),
          type: "num",
          cell: (c) => {
            const score = signalByTicker.get(c.ticker)?.score;
            if (signals.isLoading) return pending;
            return score === null || score === undefined ? (
              <Missing localized={t("comp_no_momentum")} />
            ) : (
              fmt1(locale, score)
            );
          },
        },
        {
          id: "tier",
          header: t("comp_col_tier"),
          cell: (c) => {
            const tier = signalByTicker.get(c.ticker)?.tier;
            if (signals.isLoading) return pending;
            return tier ? <TierTag tier={tier} /> : <Missing localized={t("comp_no_momentum")} />;
          },
        },
        {
          id: "margin",
          header: t("comp_col_margin"),
          type: "num",
          cell: (c) => {
            if (overviewPending) return pending;
            const margin = overview.data?.items[c.ticker]?.gross_margin;
            const text = margin?.value != null ? fmtPct(locale, margin.value) : null;
            if (text !== null) return text;
            return margin?.reason ? <Missing reason={margin.reason} lineLabel={lineLabel} /> : <Missing localized={t("comp_no_margin")} />;
          },
        },
      ],
      narrow,
    );
  }, [t, locale, narrow, overview.data, overviewPending, marketDate, signalByTicker, signals.isLoading, rules, forming, companyHref]);

  const data = list.data;
  const total = data?.total ?? 0;
  const from = (page - 1) * PAGE_SIZE + 1;
  const to = from + (data?.items.length ?? 0) - 1;
  const meta = (() => {
    if (!data) return undefined;
    if (q) return t("comp_meta_matches", { count: countText(t, locale, total, "matches_count"), q });
    const range = t("comp_meta_range", {
      from: fmtInt(locale, from) ?? "",
      to: fmtInt(locale, to) ?? "",
      total: fmtInt(locale, total) ?? "",
    });
    return range;
  })();

  const empty = forming !== null ? (
    <div className="state">
      <p>{t("comp_forming_none")}</p>
      <button type="button" className="link-btn" onClick={() => update({ forming: null, page: null })}>
        {t("clear_filters")}
      </button>
    </div>
  ) : q ? (
    <div className="state">
      <p>{t("comp_no_match", { q })}</p>
      <button type="button" className="link-btn" onClick={clearSearch}>
        {t("clear_filters")}
      </button>
    </div>
  ) : (
    <EmptyState>{t("comp_empty")}</EmptyState>
  );

  return (
    <div className="page">
      <PageTitle parts={[t("comp_title")]} />
      <PageHeader
        title={t("comp_title")}
        subtitle={universeTotal !== undefined ? t("comp_subtitle", { n: fmtInt(locale, universeTotal) ?? "" }) : undefined}
        pricesAsOf={fmtDate(locale, marketDate)}
      />
      <p className="muted">
        <RichText
          text={t("comp_see_also")}
          parts={{
            rankings: <Link to="/rankings">{t("nav_rankings")}</Link>,
            reco: <Link to="/recommendations">{t("nav_recommendations")}</Link>,
          }}
        />
      </p>

      <div className="filters">
        <input
          type="search"
          className="filter-input"
          aria-label={t("comp_search_label")}
          placeholder={t("comp_search_label")}
          value={draft}
          onChange={(e) => onSearch(e.target.value)}
        />
        <Segmented
          label={t("comp_forming_label")}
          options={formingOptions}
          value={forming ?? "all"}
          onChange={(v) => update({ forming: v === "all" ? null : v, page: null })}
        />
      </div>
      {forming !== null && <p className="muted">{t("comp_forming_note")}</p>}

      {list.isError ? (
        <ErrorState thing={t("comp_thing")} onRetry={() => void list.refetch()} />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            rowKey={(c) => c.id}
            caption={t("comp_title")}
            loading={list.isLoading}
            loadingThing={t("comp_thing")}
            meta={meta}
            empty={empty}
            cardFields={forming === null ? ["close", "asof", "stance", "tier"] : ["forming", "close", "stance", "tier"]}
            rowHref={(c) => companyHref(c.ticker)}
            footnote={t("comp_footnote")}
          />
          <Pagination
            page={page}
            totalPages={data?.total_pages ?? 0}
            total={total}
            onPage={(p) => update({ page: p > 1 ? String(p) : null })}
          />
        </>
      )}
    </div>
  );
}
