import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  LineSeries,
  LineStyle,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type LogicalRange,
  type Time,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useLang } from "../../i18n/useLang";
import type { ChartPalette } from "../../lib/chartPalette";
import { fmtDate, fmtPrice } from "../../lib/format";
import {
  candleData,
  coneOverlay,
  coneValues,
  lineData,
  patternOverlay,
  patternValues,
  priceExtent,
  sliceRange,
  tickLabel,
  tickUnitFor,
  timeToIso,
  type ChartBar,
  type ChartMode,
  type ChartRange,
  type ConeShape,
  type PatternShape,
} from "../../lib/priceChart";
import { horizonLabel } from "../../lib/priceOverlays";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { OverlayPrimitive, type ConeDraw, type OverlaySpec, type PatternDraw } from "./priceChartOverlay";
import { EmptyState } from "./States";
import { usePriceChartPalette } from "./usePriceChartPalette";
import "./PriceChart.css";

export interface RefLine {
  value: number;
  label: string;
}

const NO_REFS: readonly RefLine[] = [];
const NO_PATTERNS: readonly PatternShape[] = [];
const PRICE_FORMAT = { type: "price", precision: 2, minMove: 0.01 } as const;

type ChartOptions = Parameters<IChartApi["applyOptions"]>[0];

/** The series on the chart, tagged with its kind so each call is typed without casts. */
type Drawn =
  | { kind: "line"; series: ISeriesApi<"Line"> }
  | { kind: "candles"; series: ISeriesApi<"Candlestick"> };

function chartOptions(p: ChartPalette, locale: string, withCone: boolean): ChartOptions {
  return {
    layout: {
      background: { type: ColorType.Solid, color: p.surface },
      textColor: p.axis,
      fontFamily: p.fontFamily,
      fontSize: p.fontSize,
      // TradingView licence: keep the attribution logo.
      attributionLogo: true,
    },
    grid: { vertLines: { visible: false }, horzLines: { color: p.grid } },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: { color: p.crosshair, width: 1, style: LineStyle.Solid, labelBackgroundColor: p.text2 },
      horzLine: { visible: false, labelVisible: false },
    },
    rightPriceScale: { borderColor: p.grid, scaleMargins: { top: 0.1, bottom: 0.12 } },
    timeScale: {
      borderColor: p.grid,
      fixLeftEdge: true,
      // The library's right edge is the last bar, so with the cone (empty future slots) it must be free.
      fixRightEdge: !withCone,
      // Five years of bars in a narrow plot is well under half a pixel per bar.
      minBarSpacing: 0.05,
      timeVisible: false,
      tickMarkFormatter: (time: Time, type: number) => {
        const iso = timeToIso(time);
        return iso ? tickLabel(locale, iso, tickUnitFor(type)) : null;
      },
    },
    localization: {
      locale,
      priceFormatter: (price: number) => fmtPrice(locale, price) ?? "",
      timeFormatter: (time: Time) => {
        const iso = timeToIso(time);
        return (iso && fmtDate(locale, iso)) ?? "";
      },
    },
  };
}

interface Hover {
  date: string;
  x: number;
  y: number;
  /** Plot width when the pointer moved, to keep the readout inside it. */
  width: number;
}

function ChartCanvas({
  shown,
  refLines,
  range,
  height,
  mode,
  cone,
  patterns,
  selectedPattern,
}: {
  shown: readonly ChartBar[];
  refLines: readonly RefLine[];
  range: ChartRange;
  height: number;
  mode: ChartMode;
  cone: ConeShape | null;
  patterns: readonly PatternShape[];
  selectedPattern: string | null;
}) {
  const { t, lang, locale } = useLang();
  const palette = usePriceChartPalette();
  const hostRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const drawnRef = useRef<Drawn | null>(null);
  const overlayRef = useRef<OverlayPrimitive | null>(null);
  const barsByDate = useRef<ReadonlyMap<string, ChartBar>>(new Map());
  const keepView = useRef<LogicalRange | null>(null);
  const drawnData = useRef<{ shown: readonly ChartBar[]; futureDates: readonly string[] | undefined } | null>(null);
  const [hover, setHover] = useState<Hover | null>(null);

  const lastDate = shown[shown.length - 1]!.date;
  const byDate = useMemo(() => new Map(shown.map((b) => [b.date, b] as const)), [shown]);

  // ---- Overlays in (date, price) space; the chart turns them into pixels ----
  const coneLayer = useMemo(() => (cone ? coneOverlay(cone, lastDate) : null), [cone, lastDate]);
  const futureDates = coneLayer?.futureDates;
  const coneDraw = useMemo<ConeDraw | null>(
    () =>
      coneLayer
        ? {
            overlay: coneLayer,
            lastDate,
            labels: coneLayer.horizons.map((h) => ({ date: h.date, text: horizonLabel(t, h.days, true) })),
          }
        : null,
    [coneLayer, lastDate, t],
  );
  const patternDraws = useMemo<PatternDraw[]>(
    () =>
      patterns.map((shape) => ({
        overlay: patternOverlay(shape, shown),
        selected: shape.id === selectedPattern,
        breakText: t("pxf_break_label", { price: fmtPrice(locale, shape.breakLevel) ?? "" }),
        targetText: shape.target === null ? "" : t("pxf_target_label", { price: fmtPrice(locale, shape.target) ?? "" }),
        levelText: {
          above: t("pxf_level_above", { price: fmtPrice(locale, shape.forming?.above) ?? "" }),
          below: t("pxf_level_below", { price: fmtPrice(locale, shape.forming?.below) ?? "" }),
        },
      })),
    [patterns, selectedPattern, shown, t, locale],
  );
  const spec = useMemo<OverlaySpec>(
    () => ({
      palette,
      rtl: lang === "ar",
      cone: coneDraw,
      patterns: patternDraws,
      refLines: refLines.map((r) => ({ price: r.value, label: r.label })),
      extent: priceExtent([
        ...refLines.map((r) => r.value),
        ...(cone ? coneValues(cone) : []),
        ...patterns.flatMap(patternValues),
      ]),
    }),
    [palette, lang, coneDraw, patternDraws, refLines, cone, patterns],
  );

  // ---- Chart: created once, removed on unmount; sized by the container (autoSize) ----
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const chart = createChart(host, { autoSize: true });
    const overlay = new OverlayPrimitive();
    chartRef.current = chart;
    overlayRef.current = overlay;
    chart.subscribeCrosshairMove((param) => {
      const drawn = drawnRef.current;
      const iso = param.time === undefined ? null : timeToIso(param.time);
      const x = iso === null ? null : chart.timeScale().timeToCoordinate(iso);
      const bar = iso === null ? undefined : barsByDate.current.get(iso);
      const y = bar && drawn ? drawn.series.priceToCoordinate(bar.close) : null;
      if (!bar || x === null || y === null) {
        setHover(null);
        return;
      }
      const next: Hover = { date: bar.date, x, y, width: host.clientWidth };
      setHover((prev) => (prev && prev.date === next.date && prev.x === next.x && prev.width === next.width ? prev : next));
    });
    return () => {
      chartRef.current = null;
      drawnRef.current = null;
      overlayRef.current = null;
      chart.remove();
    };
  }, []);

  // Theme, language and locale: colours, font and number/date formats.
  useEffect(() => {
    chartRef.current?.applyOptions(chartOptions(palette, locale, futureDates !== undefined));
  }, [palette, locale, futureDates]);

  // The series: a line or candles; the overlay is attached to whichever is shown.
  useEffect(() => {
    const chart = chartRef.current;
    const overlay = overlayRef.current;
    if (!chart || !overlay) return;
    const drawn: Drawn =
      mode === "candles"
        ? { kind: "candles", series: chart.addSeries(CandlestickSeries, { lastValueVisible: false, priceLineVisible: false, priceFormat: PRICE_FORMAT }) }
        : { kind: "line", series: chart.addSeries(LineSeries, { lastValueVisible: false, priceLineVisible: false, priceFormat: PRICE_FORMAT }) };
    drawn.series.attachPrimitive(overlay);
    drawnRef.current = drawn;
    return () => {
      // Unmounting removes the chart first; only a mode switch gets here with a live chart.
      if (chartRef.current !== chart) return;
      keepView.current = chart.timeScale().getVisibleLogicalRange();
      drawn.series.detachPrimitive(overlay);
      chart.removeSeries(drawn.series);
      drawnRef.current = null;
    };
  }, [mode]);

  useEffect(() => {
    const drawn = drawnRef.current;
    if (!drawn) return;
    if (drawn.kind === "candles") {
      drawn.series.applyOptions({
        upColor: palette.gain,
        downColor: palette.loss,
        borderUpColor: palette.gain,
        borderDownColor: palette.loss,
        wickUpColor: palette.gain,
        wickDownColor: palette.loss,
      });
    } else {
      drawn.series.applyOptions({
        color: palette.line,
        lineWidth: 2,
        crosshairMarkerRadius: 4,
        crosshairMarkerBackgroundColor: palette.line,
        crosshairMarkerBorderColor: palette.surface,
      });
    }
  }, [palette, mode]);

  // The bars, plus empty slots on the cone's future trading dates so the time axis reaches them.
  useEffect(() => {
    const chart = chartRef.current;
    const drawn = drawnRef.current;
    if (!chart || !drawn) return;
    const gaps = (futureDates ?? []).map((time) => ({ time }));
    if (drawn.kind === "candles") {
      const candles = new Map(candleData(shown).map((c) => [c.time, c] as const));
      drawn.series.setData([...shown.map((b) => candles.get(b.date) ?? { time: b.date }), ...gaps]);
    } else {
      drawn.series.setData([...lineData(shown), ...gaps]);
    }
    barsByDate.current = byDate;
    // Switching line / candles keeps the user's zoom and pan; new bars or a new cone fit the view again.
    const sameData = drawnData.current?.shown === shown && drawnData.current.futureDates === futureDates;
    if (keepView.current && sameData) chart.timeScale().setVisibleLogicalRange(keepView.current);
    else chart.timeScale().fitContent();
    keepView.current = null;
    drawnData.current = { shown, futureDates };
    setHover(null);
  }, [shown, byDate, futureDates, mode, range]);

  // Overlays: cone, patterns and reference lines; the price scale makes room for them.
  useEffect(() => {
    overlayRef.current?.setSpec(spec);
    chartRef.current?.priceScale("right").applyOptions({ autoScale: true });
  }, [spec, mode]);

  // Left / Right arrows move the crosshair one bar, for keyboard users.
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>): void => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight" && e.key !== "Escape") return;
    e.preventDefault();
    const chart = chartRef.current;
    const drawn = drawnRef.current;
    if (!chart || !drawn) return;
    if (e.key === "Escape") {
      chart.clearCrosshairPosition();
      setHover(null);
      return;
    }
    const current = hover ? shown.findIndex((b) => b.date === hover.date) : shown.length - 1;
    const index = Math.min(shown.length - 1, Math.max(0, (current < 0 ? shown.length - 1 : current) + (e.key === "ArrowLeft" ? -1 : 1)));
    const bar = shown[index]!;
    chart.setCrosshairPosition(bar.close, bar.date, drawn.series);
  };
  const onBlur = (): void => {
    chartRef.current?.clearCrosshairPosition();
    setHover(null);
  };

  const bar = hover ? byDate.get(hover.date) : undefined;
  const candle = mode === "candles" && bar && bar.open !== undefined && bar.high !== undefined && bar.low !== undefined ? bar : null;
  const dateText = bar ? (fmtDate(locale, bar.date) ?? bar.date) : "";

  return (
    <div className="price-chart-plot" dir="ltr">
      <div
        ref={hostRef}
        className="price-chart-host"
        style={{ height }}
        tabIndex={0}
        role="img"
        aria-label={t("px_chart_aria", { n: shown.length })}
        data-mode={mode}
        data-cone={cone ? "on" : "off"}
        data-patterns={patterns.length}
        onKeyDown={onKeyDown}
        onBlur={onBlur}
      />
      {bar && hover && (
        <div
          className="price-chart-tip"
          role="status"
          dir="auto"
          style={{
            left: Math.min(Math.max(hover.x, candle ? 96 : 70), Math.max(candle ? 96 : 70, hover.width - (candle ? 96 : 70))),
            top: Math.max(0, hover.y - (candle ? 82 : 38)),
          }}
        >
          {candle ? (
            <>
              <span className="price-chart-tip-date">{dateText}</span>
              <dl className="price-chart-tip-ohlc">
                <dt>{t("ov_open")}</dt>
                <dd>{fmtPrice(locale, candle.open)}</dd>
                <dt>{t("ov_high")}</dt>
                <dd>{fmtPrice(locale, candle.high)}</dd>
                <dt>{t("ov_low")}</dt>
                <dd>{fmtPrice(locale, candle.low)}</dd>
                <dt>{t("pxf_day_close")}</dt>
                <dd>{fmtPrice(locale, candle.close)}</dd>
              </dl>
            </>
          ) : (
            `${dateText} · ${fmtPrice(locale, bar.close) ?? ""}`
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Daily price chart (spec 3.10) on lightweight-charts: a close line or candlesticks, drag to pan and
 * wheel / pinch to zoom. Time always runs left to right, also in Arabic (a time axis on a price
 * chart keeps its direction). Hover or Left/Right keys show a crosshair and the day's figures.
 * Optional overlays, both display only: a volatility cone on the real trading days after the last
 * close, and chart patterns (confirmed or still forming) over the history.
 */
export default function PriceChart({
  bars,
  refLines = NO_REFS,
  range,
  source,
  height = 240,
  mode = "line",
  showHint = true,
  cone = null,
  patterns = NO_PATTERNS,
  selectedPattern = null,
}: {
  /** Ascending daily bars (close, and open/high/low for candles). */
  bars: readonly ChartBar[];
  refLines?: readonly RefLine[];
  /** Shown range, counted back from the newest bar. */
  range: ChartRange;
  /** Data source name for the caption. */
  source?: string | null;
  height?: number;
  /** Close line (default) or candlesticks. */
  mode?: ChartMode;
  /** Show the one-line pan / zoom hint under the chart. */
  showHint?: boolean;
  /** Range of typical moves drawn on the trading days after the last close; not a prediction. */
  cone?: ConeShape | null;
  /** Patterns to draw; the caller passes only those inside the visible range. */
  patterns?: readonly PatternShape[];
  selectedPattern?: string | null;
}) {
  const { t, locale } = useLang();
  const phone = useMediaQuery("(max-width: 767px)");
  const shown = useMemo(() => sliceRange(bars, range), [bars, range]);
  const lastBar = shown[shown.length - 1];

  if (shown.length < 2 || !lastBar) {
    return (
      <div className="price-chart">
        <EmptyState>{t("not_enough_history")}</EmptyState>
      </div>
    );
  }

  const asOf = fmtDate(locale, lastBar.date);
  return (
    <figure className="price-chart">
      <ChartCanvas
        shown={shown}
        refLines={refLines}
        range={range}
        height={phone ? Math.min(height, 200) : height}
        mode={mode}
        cone={cone}
        patterns={patterns}
        selectedPattern={selectedPattern}
      />
      <figcaption className="price-chart-caption">
        {source ? t("px_chart_caption_source", { source, date: asOf ?? "" }) : t("px_chart_caption", { date: asOf ?? "" })}
        {showHint && <span className="price-chart-hint">{t("pxf_zoom_hint")}</span>}
      </figcaption>
    </figure>
  );
}
