import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useChartPatterns, useCompanyPrices, useVolatilityCone } from "../../api/client";
import { useLang } from "../../i18n/useLang";
import {
  CHART_MODES,
  OVERVIEW_RANGES,
  patternInView,
  sliceRange,
  type ChartBar,
  type ChartMode,
  type ChartRange,
  type OverviewRange,
  type PatternShape,
} from "../../lib/priceChart";
import { coneShape, formingShape, patternShape } from "../../lib/priceOverlays";
import type { ChartPattern, FormingChartPattern } from "../../types";
import { ErrorState, LoadingState } from "../ui/States";
import { Segmented } from "../ui/Segmented";
import PriceChart from "../ui/PriceChart";
import ConePanel from "./ConePanel";
import PatternsPanel from "./PatternsPanel";
import { chartBars, realBarsNewestFirst, useYearPrices } from "./priceData";
import SessionSummary from "./SessionSummary";

interface DrawnPattern {
  pattern: ChartPattern;
  shape: PatternShape;
}

/** Start date of the five-year query (the browser's clock; the API returns what is stored). */
function fiveYearStart(): string {
  const d = new Date();
  d.setFullYear(d.getFullYear() - 5);
  return d.toISOString().split("T")[0]!;
}

/**
 * Overview price history (R47 P1-P5): Day summary, line ranges up to five years,
 * and two display-only overlays the user switches on: the volatility cone and
 * confirmed chart patterns. Each range fetches only what it needs: 1W to 1Y read
 * the one-year query the hub header already holds, 5Y adds one request when first
 * chosen, Day reads the latest price, and an overlay is requested only once switched on.
 */
export default function PriceHistory({ companyId }: { companyId: string }) {
  const { t } = useLang();
  const [range, setRange] = useState<OverviewRange>("1Y");
  const [mode, setMode] = useState<ChartMode>("line");
  const [forecastOn, setForecastOn] = useState(false);
  // `?patterns=1` (from the Companies forming filter) opens with the patterns shown.
  const [searchParams] = useSearchParams();
  const [patternsOn, setPatternsOn] = useState(() => searchParams.get("patterns") === "1");
  const [picked, setPicked] = useState<string | null>(null);
  const [wantFiveYears, setWantFiveYears] = useState(false);

  const year = useYearPrices(companyId);
  const startDate = useMemo(fiveYearStart, []);
  const five = useCompanyPrices(wantFiveYears ? companyId : undefined, {
    start_date: startDate,
    page_size: 2000,
  });
  const fiveSeries = useMemo<ChartBar[]>(() => chartBars(realBarsNewestFirst(five.data?.items ?? [])), [five.data]);

  const lineRange: ChartRange | null = range === "1D" ? null : range;
  const series = range === "5Y" ? fiveSeries : year.series;
  const lineQuery = range === "5Y" ? five : year.query;
  const overlaysActive = lineRange !== null;

  const cone = useVolatilityCone(companyId, forecastOn && overlaysActive);
  const patterns = useChartPatterns(companyId, patternsOn && overlaysActive);

  const shown = useMemo(() => (lineRange ? sliceRange(series, lineRange) : []), [series, lineRange]);

  const coneDrawn = useMemo(() => (forecastOn ? coneShape(cone.data) : null), [forecastOn, cone.data]);

  const shapes = useMemo<DrawnPattern[]>(() => {
    if (!patternsOn || patterns.data?.status !== "OK") return [];
    return patterns.data.patterns.flatMap((pattern) => {
      const shape = patternShape(pattern);
      return shape ? [{ pattern, shape }] : [];
    });
  }, [patternsOn, patterns.data]);
  const inView = useMemo(() => shapes.filter((s) => patternInView(s.shape, shown)), [shapes, shown]);
  const formingInView = useMemo<{ forming: FormingChartPattern; shape: PatternShape }[]>(() => {
    if (!patternsOn || patterns.data?.status !== "OK") return [];
    return (patterns.data.forming ?? []).flatMap((forming) => {
      const shape = formingShape(forming);
      return shape && patternInView(shape, shown) ? [{ forming, shape }] : [];
    });
  }, [patternsOn, patterns.data, shown]);
  const allShapes = useMemo(() => [...inView.map((s) => s.shape), ...formingInView.map((s) => s.shape)], [inView, formingInView]);
  // A shape forming now is the most current, so it is emphasised first.
  const activeId = allShapes.find((s) => s.id === picked)?.id ?? formingInView[0]?.shape.id ?? allShapes[0]?.id ?? null;
  const drawn = allShapes;

  const chooseRange = (next: OverviewRange): void => {
    if (next === "5Y") setWantFiveYears(true);
    setRange(next);
  };

  const options = OVERVIEW_RANGES.map((r) => ({
    value: r,
    label: t(`pxf_range_${r}` as const),
  }));
  const modeOptions = CHART_MODES.map((m) => ({
    value: m,
    label: t(m === "line" ? "pxf_mode_line" : "pxf_mode_candles"),
  }));
  const panelOn = overlaysActive && (forecastOn || patternsOn);

  return (
    <div className="price-history">
      <div className="price-history-controls">
        <Segmented options={options} value={range} onChange={chooseRange} label={t("px_chart_range_aria")} />
        {overlaysActive && <Segmented options={modeOptions} value={mode} onChange={setMode} label={t("pxf_mode_aria")} />}
        {overlaysActive && (
          <div className="price-history-toggles" role="group" aria-label={t("pxf_overlays_aria")}>
            <button type="button" className="price-toggle" aria-pressed={forecastOn} onClick={() => setForecastOn((v) => !v)}>
              {t("pxf_forecast")}
            </button>
            <button type="button" className="price-toggle" aria-pressed={patternsOn} onClick={() => setPatternsOn((v) => !v)}>
              {t("pxf_patterns")}
            </button>
          </div>
        )}
      </div>

      {lineRange === null ? (
        <SessionSummary companyId={companyId} />
      ) : lineQuery.isLoading ? (
        <LoadingState thing={t("pxf_loading_history")} />
      ) : lineQuery.error ? (
        <ErrorState thing={t("pxf_loading_history")} onRetry={() => void lineQuery.refetch()} />
      ) : (
        <div className="price-history-body" data-panel={panelOn}>
          <div className="price-history-main">
            <PriceChart
              bars={series}
              range={lineRange}
              source={year.source}
              mode={mode}
              cone={coneDrawn}
              patterns={drawn}
              selectedPattern={activeId}
            />
            {coneDrawn && (
              <p className="price-legend">
                <strong>{t("pxf_legend_label")}</strong>
                <span className="price-legend-item">
                  <span className="price-swatch" data-band="50" aria-hidden="true" />
                  {t("pxf_band_50")}
                </span>
                <span className="price-legend-item">
                  <span className="price-swatch" data-band="90" aria-hidden="true" />
                  {t("pxf_band_90")}
                </span>
                <span>{t("pxf_legend_now")}</span>
              </p>
            )}
          </div>
          {panelOn && (
            <div className="price-history-panel">
              {forecastOn && <ConePanel query={cone} />}
              {patternsOn && (
                <PatternsPanel
                  query={patterns}
                  visible={inView.map((s) => s.pattern)}
                  outside={shapes.length - inView.length}
                  forming={formingInView.map((s) => s.forming)}
                  selectedId={activeId}
                  onSelect={setPicked}
                />
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
