import { useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { useLang } from "../../i18n/useLang";
import {
  gridValues,
  linePath,
  monthTicks,
  nearestIndex,
  scaleX,
  scaleY,
  sliceRange,
  yDomain,
  type ChartBar,
  type ChartRange,
} from "../../lib/priceChart";
import { fmtDate, fmtPrice } from "../../lib/format";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { EmptyState } from "./States";
import { Segmented } from "./Segmented";
import "./PriceChart.css";

export interface RefLine {
  value: number;
  label: string;
}

const PAD = { top: 12, right: 52, bottom: 26, left: 6 };
const RANGES: readonly ChartRange[] = ["3M", "6M", "1Y"];

function useWidth(ref: React.RefObject<HTMLDivElement | null>): number {
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = (): void => setWidth(Math.floor(el.getBoundingClientRect().width));
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}

/**
 * Daily close line (spec 3.10): hand-written SVG, no dependency. Always laid
 * out left to right (it is never mirrored). Hover or Left/Right keys show a
 * crosshair and the day's close.
 */
export default function PriceChart({
  bars,
  refLines = [],
  range,
  onRangeChange,
  source,
  height = 240,
}: {
  /** Ascending daily closes. */
  bars: readonly ChartBar[];
  refLines?: readonly RefLine[];
  /** Shown range. With `onRangeChange` the 3M / 6M / 1Y control is rendered. */
  range: ChartRange;
  onRangeChange?: (range: ChartRange) => void;
  /** Data source name for the caption. */
  source?: string | null;
  height?: number;
}) {
  const { t, locale } = useLang();
  const phone = useMediaQuery("(max-width: 767px)");
  const wrapRef = useRef<HTMLDivElement>(null);
  const width = useWidth(wrapRef);
  const [active, setActive] = useState<number | null>(null);
  const monthFmt = useMemo(
    () => new Intl.DateTimeFormat(locale === "en" ? "en-GB" : locale, { month: "short", timeZone: "UTC" }),
    [locale],
  );

  const shown = useMemo(() => sliceRange(bars, range), [bars, range]);
  const h = phone ? Math.min(height, 180) : height;
  const box = { left: PAD.left, right: Math.max(PAD.left + 1, width - PAD.right), top: PAD.top, bottom: h - PAD.bottom };

  const domain = useMemo(
    () =>
      yDomain(
        shown.map((b) => b.close),
        refLines.map((r) => r.value),
      ),
    [shown, refLines],
  );

  const rangeOptions = RANGES.map((r) => ({ value: r, label: t(`px_chart_range_${r}` as const) }));
  const lastBar = shown[shown.length - 1];
  const asOf = lastBar ? fmtDate(locale, lastBar.date) : null;

  const control = onRangeChange ? (
    <Segmented options={rangeOptions} value={range} onChange={onRangeChange} label={t("px_chart_range_aria")} />
  ) : null;

  if (shown.length < 2 || !domain) {
    return (
      <div className="price-chart">
        {control}
        <EmptyState>{t("not_enough_history")}</EmptyState>
      </div>
    );
  }

  const point = (i: number): { x: number; y: number } => ({
    x: scaleX(i, shown.length, box.left, box.right),
    y: scaleY(shown[i]!.close, domain, box.top, box.bottom),
  });

  const move = (e: PointerEvent<SVGSVGElement>): void => {
    const rect = e.currentTarget.getBoundingClientRect();
    setActive(nearestIndex(e.clientX - rect.left, shown.length, box.left, box.right));
  };
  const key = (e: KeyboardEvent<SVGSVGElement>): void => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const step = e.key === "ArrowLeft" ? -1 : 1;
    setActive((cur) => Math.min(shown.length - 1, Math.max(0, (cur ?? shown.length - 1) + step)));
  };

  const cur = active !== null ? shown[active] : undefined;
  const curPoint = active !== null ? point(active) : null;
  const tooltip = cur ? `${fmtDate(locale, cur.date) ?? cur.date} · ${fmtPrice(locale, cur.close) ?? ""}` : null;
  const ticks = monthTicks(shown, box.left, box.right, 44);

  return (
    <figure className="price-chart">
      {control}
      <div className="price-chart-plot" dir="ltr" ref={wrapRef}>
        {width > 0 && (
          <svg
            width={width}
            height={h}
            viewBox={`0 0 ${width} ${h}`}
            role="img"
            tabIndex={0}
            aria-label={t("px_chart_aria", { n: shown.length })}
            onPointerMove={move}
            onPointerLeave={() => setActive(null)}
            onBlur={() => setActive(null)}
            onKeyDown={key}
          >
            {gridValues(domain).map((v) => {
              const y = scaleY(v, domain, box.top, box.bottom);
              return (
                <g key={v}>
                  <line x1={box.left} x2={box.right} y1={y} y2={y} className="chart-grid" />
                  <text x={width - PAD.right + 6} y={y + 4} className="chart-axis">
                    {fmtPrice(locale, v)}
                  </text>
                </g>
              );
            })}
            {ticks.map((tick) => (
              <text key={tick.date} x={scaleX(tick.index, shown.length, box.left, box.right)} y={h - 6} className="chart-axis" textAnchor="start">
                {monthFmt.format(new Date(`${tick.date}T00:00:00Z`))}
              </text>
            ))}
            {refLines.map((r) => {
              const y = scaleY(r.value, domain, box.top, box.bottom);
              return (
                <g key={r.label}>
                  <line x1={box.left} x2={box.right} y1={y} y2={y} className="chart-ref" />
                  <text x={box.left + 4} y={y - 4} className="chart-ref-label">
                    {r.label}
                  </text>
                </g>
              );
            })}
            <path d={linePath(shown, domain, box)} className="chart-line" />
            {curPoint && (
              <g>
                <line x1={curPoint.x} x2={curPoint.x} y1={box.top} y2={box.bottom} className="chart-cross" />
                <circle cx={curPoint.x} cy={curPoint.y} r={4} className="chart-dot" />
              </g>
            )}
          </svg>
        )}
        {tooltip && curPoint && (
          <div
            className="price-chart-tip"
            role="status"
            style={{ left: Math.min(Math.max(curPoint.x, 70), Math.max(70, width - 70)), top: Math.max(0, curPoint.y - 38) }}
          >
            {tooltip}
          </div>
        )}
      </div>
      <figcaption className="price-chart-caption">
        {source
          ? t("px_chart_caption_source", { source, date: asOf ?? "" })
          : t("px_chart_caption", { date: asOf ?? "" })}
      </figcaption>
    </figure>
  );
}
