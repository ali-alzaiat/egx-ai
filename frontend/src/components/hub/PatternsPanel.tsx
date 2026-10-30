import type { UseQueryResult } from "@tanstack/react-query";
import { useLang } from "../../i18n/useLang";
import type { CopyKey } from "../../i18n/dict";
import { fmtDate, fmtInt, fmtPct, fmtPrice } from "../../lib/format";
import { FORMING_NAME_KEY, formingId, patternId, patternStats } from "../../lib/priceOverlays";
import type { ChartPattern, FormingChartPattern, FormingStats, PatternStats, PatternsResponse } from "../../types";
import { BackendText } from "../ui/BackendText";
import { ErrorState, LoadingState } from "../ui/States";

const PATTERN_NAME: Record<string, CopyKey> = {
  head_and_shoulders_top: "pxf_pat_head_and_shoulders_top",
  head_and_shoulders_inverse: "pxf_pat_head_and_shoulders_inverse",
  double_top: "pxf_pat_double_top",
  double_bottom: "pxf_pat_double_bottom",
  ascending_triangle: "pxf_pat_ascending_triangle",
  descending_triangle: "pxf_pat_descending_triangle",
  symmetrical_triangle_up: "pxf_pat_symmetrical_triangle_up",
  symmetrical_triangle_down: "pxf_pat_symmetrical_triangle_down",
};

const HORIZONS = ["20", "60"] as const;

function Odds({ stats, horizon, minCases }: { stats: PatternStats | undefined; horizon: "20" | "60"; minCases: number }) {
  const { t, locale } = useLang();
  const h = fmtInt(locale, horizon) ?? horizon;
  if (!stats) return <span>{t("pxf_pat_odds_missing", { h })}</span>;
  if (stats.status !== "OK") {
    return /^too few cases/.test(stats.reason) ? (
      <span>
        {t("pxf_pat_odds_few", {
          h,
          n: fmtInt(locale, stats.n) ?? "",
          min: fmtInt(locale, minCases) ?? "",
        })}
      </span>
    ) : (
      <span>
        {t("pxf_pat_odds_reason", { h })} <BackendText>{stats.reason}</BackendText>
      </span>
    );
  }
  return (
    <span>
      {t("pxf_pat_odds", {
        h,
        hit: fmtPct(locale, stats.hit_rate) ?? "—",
        base: fmtPct(locale, stats.base_rate) ?? "—",
        low: fmtPct(locale, stats.wilson_low) ?? "—",
        high: fmtPct(locale, stats.wilson_high) ?? "—",
        n: fmtInt(locale, stats.n) ?? "",
      })}{" "}
      {stats.interval_excludes_base ? t("pxf_pat_differs") : t("pxf_pat_same")}
    </span>
  );
}

function PatternItem({
  pattern,
  data,
  selected,
  onSelect,
}: {
  pattern: ChartPattern;
  data: PatternsResponse;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const { t, locale } = useLang();
  const nameKey = PATTERN_NAME[pattern.stats_key];
  return (
    <li>
      <button
        type="button"
        className="pattern-item"
        aria-pressed={selected}
        title={t("pxf_pat_pick")}
        onClick={() => onSelect(patternId(pattern))}
      >
        <span className="pattern-item-head">
          <span>{nameKey ? t(nameKey) : <BackendText>{pattern.stats_key}</BackendText>}</span>
          <span className="pattern-item-date">
            {pattern.direction === "up" ? t("pxf_pat_broke_up") : t("pxf_pat_broke_down")} ·{" "}
            {t("pxf_pat_confirmed", {
              date: fmtDate(locale, pattern.confirmation_date) ?? "",
            })}
          </span>
        </span>
        <span className="pattern-odds">
          {HORIZONS.map((h) => (
            <Odds key={h} stats={patternStats(data, pattern.stats_key, h)} horizon={h} minCases={data.universe.min_cases} />
          ))}
        </span>
      </button>
    </li>
  );
}

/** Where a forming shape confirms or fails, from its levels at the latest close. */
function FormingLevels({ forming }: { forming: FormingChartPattern }) {
  const { t, locale } = useLang();
  const price = (v: string | null): string => fmtPrice(locale, v) ?? "";
  const confirm =
    forming.confirm_above !== null && forming.confirm_below !== null
      ? t("pxf_pat_forming_either", {
          above: price(forming.confirm_above),
          below: price(forming.confirm_below),
        })
      : forming.confirm_above !== null
        ? t("pxf_pat_forming_above", { price: price(forming.confirm_above) })
        : t("pxf_pat_forming_below", { price: price(forming.confirm_below) });
  const fails =
    forming.invalid_above !== null
      ? t("pxf_pat_forming_fails_above", {
          price: price(forming.invalid_above),
        })
      : forming.invalid_below !== null
        ? t("pxf_pat_forming_fails_below", {
            price: price(forming.invalid_below),
          })
        : null;
  return <span>{fails ? `${confirm} ${fails}` : confirm}</span>;
}

/** Odds measured from the forming stage (R47 P6): how often similar shapes confirmed, then moved. */
function FormingOdds({ stats, minCases }: { stats: FormingStats | undefined; minCases: number }) {
  const { t, locale } = useLang();
  const pct = (v: number | null): string => (v === null ? "—" : (fmtPct(locale, v) ?? "—"));
  if (!stats || stats.status !== "OK") {
    return (
      <span>
        {t("pxf_pat_forming_few", {
          n: fmtInt(locale, stats?.n ?? 0) ?? "",
          min: fmtInt(locale, minCases) ?? "",
        })}
      </span>
    );
  }
  const upShare =
    stats.expected === null && stats.up_break_share !== null ? t("pxf_pat_forming_up_share", { share: pct(stats.up_break_share) }) : null;
  const outcome = t("pxf_pat_forming_outcome", {
    rate: pct(stats.confirm_rate),
    low: pct(stats.confirm_wilson_low),
    high: pct(stats.confirm_wilson_high),
    failed: pct(stats.failed / stats.n),
    expired: pct(stats.expired / stats.n),
    n: fmtInt(locale, stats.n) ?? "",
  });
  return (
    <>
      <span>{upShare ? `${outcome} ${upShare}` : outcome}</span>
      {HORIZONS.map((h) => {
        const cell = stats.horizons[h];
        if (!cell) return null;
        const hh = fmtInt(locale, h) ?? h;
        return cell.status === "OK" ? (
          <span key={h}>
            {t("pxf_pat_forming_odds", {
              h: hh,
              hit: pct(cell.hit_rate),
              base: pct(cell.base_rate),
              low: pct(cell.wilson_low),
              high: pct(cell.wilson_high),
              n: fmtInt(locale, cell.n) ?? "",
            })}{" "}
            {cell.interval_excludes_base ? t("pxf_pat_differs") : t("pxf_pat_same")}
          </span>
        ) : (
          <span key={h}>
            {t("pxf_pat_odds_few", {
              h: hh,
              n: fmtInt(locale, cell.n) ?? "",
              min: fmtInt(locale, minCases) ?? "",
            })}
          </span>
        );
      })}
    </>
  );
}

function FormingItem({
  forming,
  data,
  selected,
  onSelect,
}: {
  forming: FormingChartPattern;
  data: PatternsResponse;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const { t, locale } = useLang();
  const nameKey = FORMING_NAME_KEY[forming.pattern];
  return (
    <li>
      <button
        type="button"
        className="pattern-item"
        aria-pressed={selected}
        title={t("pxf_pat_pick")}
        onClick={() => onSelect(formingId(forming))}
      >
        <span className="pattern-item-head">
          <span>{nameKey ? t(nameKey) : <BackendText>{forming.pattern}</BackendText>}</span>
          <span className="pattern-item-date">
            {t("pxf_pat_forming_meta", {
              date: fmtDate(locale, forming.known_date) ?? "",
              n: fmtInt(locale, forming.sessions_left) ?? "",
            })}
          </span>
        </span>
        <span className="pattern-odds">
          <FormingLevels forming={forming} />
          <FormingOdds stats={data.forming_stats[forming.pattern]} minCases={data.universe.min_cases} />
        </span>
      </button>
    </li>
  );
}

/**
 * Confirmed chart patterns inside the visible range, each with its measured EGX odds
 * (R47 P4), then shapes still forming with odds measured from that stage (R47 P6). Display only: nothing here feeds Buy / Hold / Reduce and the copy never
 * reads as advice. Picking a pattern emphasises it on the chart.
 */
export default function PatternsPanel({
  query,
  visible,
  outside,
  forming,
  selectedId,
  onSelect,
}: {
  query: UseQueryResult<PatternsResponse>;
  /** Patterns inside the visible range, newest first. */
  visible: readonly ChartPattern[];
  /** Confirmed patterns of the last year that fall outside the visible range. */
  outside: number;
  /** Shapes still forming whose start is inside the visible range, most recently known first. */
  forming: readonly FormingChartPattern[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const { t, locale } = useLang();
  const data = query.data;

  return (
    <section className="price-panel card-surface" aria-label={t("pxf_pat_title")}>
      <h3 className="price-panel-title">{t("pxf_pat_title")}</h3>
      {query.isLoading ? (
        <LoadingState thing={t("pxf_pat_title")} />
      ) : query.error || !data ? (
        <ErrorState thing={t("pxf_pat_title")} onRetry={() => void query.refetch()} />
      ) : data.status !== "OK" ? (
        <>
          <p className="empty">{t("pxf_pat_unavailable")}</p>
          {data.reason && (
            <p className="price-panel-note">
              <BackendText>{data.reason}</BackendText>
            </p>
          )}
        </>
      ) : (
        <>
          <p className="price-panel-note">{t("pxf_pat_intro")}</p>
          {visible.length === 0 ? (
            <p className="empty">{t("pxf_pat_empty")}</p>
          ) : (
            <ul className="pattern-list">
              {visible.map((p) => (
                <PatternItem key={patternId(p)} pattern={p} data={data} selected={patternId(p) === selectedId} onSelect={onSelect} />
              ))}
            </ul>
          )}
          {outside > 0 && <p className="price-panel-note">{t("pxf_pat_outside", { n: fmtInt(locale, outside) ?? "" })}</p>}
          <h4 className="price-panel-subtitle">{t("pxf_pat_forming_title")}</h4>
          <p className="price-panel-note">{t("pxf_pat_forming_intro")}</p>
          {forming.length === 0 ? (
            <p className="empty">{t("pxf_pat_forming_empty")}</p>
          ) : (
            <ul className="pattern-list">
              {forming.map((f) => (
                <FormingItem key={formingId(f)} forming={f} data={data} selected={formingId(f) === selectedId} onSelect={onSelect} />
              ))}
            </ul>
          )}
          <p className="price-panel-note">{t("pxf_pat_legend")}</p>
          <p className="price-panel-note">{t("pxf_pat_note")}</p>
          <p className="price-panel-note">
            {t("pxf_pat_basis", {
              companies: fmtInt(locale, data.universe.companies) ?? "",
              start: fmtDate(locale, data.universe.period_start) ?? "",
              end: fmtDate(locale, data.universe.period_end) ?? "",
            })}
          </p>
          <p className="price-panel-note">{t("pxf_pat_overlap_note")}</p>
        </>
      )}
    </section>
  );
}
