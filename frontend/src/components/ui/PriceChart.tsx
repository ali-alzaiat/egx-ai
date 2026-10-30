import { useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { useLang } from "../../i18n/useLang";
import {
  coneGeometry,
  coneValues,
  FORECAST_SHARE,
  gridValues,
  linePath,
  nearestIndex,
  patternGeometry,
  patternValues,
  periodTicks,
  scaleX,
  scaleY,
  sliceRange,
  splitX,
  tickUnit,
  yDomain,
  type ChartBar,
  type ChartRange,
  type ConeShape,
  type Domain,
  type PatternShape,
  type PlotBox,
  type TickUnit,
} from "../../lib/priceChart";
import { fmtDate, fmtPrice } from "../../lib/format";
import { horizonLabel } from "../../lib/priceOverlays";
import { useMediaQuery } from "../../lib/useMediaQuery";
import { EmptyState } from "./States";
import "./PriceChart.css";

export interface RefLine {
  value: number;
  label: string;
}

const PAD = { top: 12, right: 52, bottom: 26, left: 6 };

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

const TICK_FORMAT: Record<TickUnit, Intl.DateTimeFormatOptions> = {
  day: { day: "numeric", month: "short", timeZone: "UTC" },
  month: { month: "short", timeZone: "UTC" },
  year: { year: "numeric", timeZone: "UTC" },
};
const TICK_GAP: Record<TickUnit, number> = { day: 54, month: 44, year: 44 };

function ConeLayer({ cone, domain, box, nowX }: { cone: ConeShape; domain: Domain; box: PlotBox; nowX: number }) {
  const { t } = useLang();
  const geo = coneGeometry(cone, domain, box, nowX);
  const last = geo.marks.length - 1;
  return (
    <g data-layer="cone">
      <path d={geo.band90} className="chart-cone-90" />
      <path d={geo.band50} className="chart-cone-50" />
      <line x1={nowX} x2={nowX} y1={box.top} y2={box.bottom} className="chart-now" />
      {geo.marks.map((m, i) => (
        <g key={m.days}>
          <line x1={m.x} x2={m.x} y1={box.bottom} y2={box.bottom + 4} className="chart-now" />
          <text x={m.x} y={box.bottom + 20} className="chart-axis" textAnchor={i === last ? "end" : "middle"}>
            {horizonLabel(t, m.days, true)}
          </text>
        </g>
      ))}
    </g>
  );
}

function PatternLayer({
  shape,
  selected,
  bars,
  domain,
  box,
  nowX,
}: {
  shape: PatternShape;
  selected: boolean;
  bars: readonly ChartBar[];
  domain: Domain;
  box: PlotBox;
  nowX: number;
}) {
  const { t, locale } = useLang();
  const geo = patternGeometry(shape, bars, domain, box, nowX);
  const breakText = t("pxf_break_label", {
    price: fmtPrice(locale, shape.breakLevel) ?? "",
  });
  const targetText = shape.target === null ? "" : t("pxf_target_label", { price: fmtPrice(locale, shape.target) ?? "" });
  const nearLeft = geo.breakMark.x - box.left < 110;
  // Rough text width (12px labels), so a label near the right edge is pulled back inside the plot.
  const targetX = geo.targetLine ? Math.max(box.left + 2, Math.min(geo.targetLine.x1, box.right - targetText.length * 6.4)) : box.left;
  return (
    <g className="chart-pat" data-selected={selected} data-forming={!!shape.forming} data-layer="pattern">
      <path d={geo.outline} className="chart-pat-outline" />
      {geo.lines.map((l, i) => (
        <line key={i} x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2} className="chart-pat-line" />
      ))}
      {geo.points.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={3} className="chart-pat-dot" />
      ))}
      {geo.targetLine && (
        <g>
          <line x1={geo.targetLine.x1} x2={geo.targetLine.x2} y1={geo.targetLine.y} y2={geo.targetLine.y} className="chart-pat-target" />
          <line x1={geo.breakMark.x} x2={geo.breakMark.x} y1={geo.breakMark.y} y2={geo.targetLine.y} className="chart-pat-target" />
        </g>
      )}
      {geo.levels.map((l) => (
        <g key={l.side}>
          <line x1={l.x1} x2={l.x2} y1={l.y} y2={l.y} className="chart-pat-level" />
          {selected && (
            <text x={l.x2 - 4} y={l.y + (l.side === "above" ? -5 : 13)} textAnchor="end" className="chart-pat-label">
              {t(l.side === "above" ? "pxf_level_above" : "pxf_level_below", {
                price: fmtPrice(locale, l.side === "above" ? shape.forming?.above : shape.forming?.below) ?? "",
              })}
            </text>
          )}
        </g>
      ))}
      {!shape.forming && (
        <rect
          x={geo.breakMark.x - 4}
          y={geo.breakMark.y - 4}
          width={8}
          height={8}
          transform={`rotate(45 ${geo.breakMark.x} ${geo.breakMark.y})`}
          className="chart-pat-break"
        />
      )}
      {selected && !shape.forming && (
        <g>
          <text
            x={geo.breakMark.x + (nearLeft ? 8 : -8)}
            y={geo.breakMark.y + (geo.targetLine && geo.targetLine.y > geo.breakMark.y ? -6 : 14)}
            textAnchor={nearLeft ? "start" : "end"}
            className="chart-pat-label"
          >
            {breakText}
          </text>
          {geo.targetLine && (
            <text x={targetX} y={geo.targetLine.y + (geo.targetLine.y < box.top + 14 ? 14 : -5)} className="chart-pat-label">
              {targetText}
            </text>
          )}
        </g>
      )}
    </g>
  );
}

/**
 * Daily close line (spec 3.10): hand-written SVG, no dependency. Always laid
 * out left to right (it is never mirrored, also in Arabic: a time axis on a
 * price chart keeps its direction). Hover or Left/Right keys show a crosshair
 * and the day's close. Optional overlays, both display only: a volatility cone
 * to the right of the last close and confirmed chart patterns over the history.
 */
export default function PriceChart({
  bars,
  refLines = [],
  range,
  source,
  height = 240,
  cone = null,
  patterns = [],
  selectedPattern = null,
}: {
  /** Ascending daily closes. */
  bars: readonly ChartBar[];
  refLines?: readonly RefLine[];
  /** Shown range, counted back from the newest bar. */
  range: ChartRange;
  /** Data source name for the caption. */
  source?: string | null;
  height?: number;
  /** Range of typical moves drawn right of the last close; not a prediction. */
  cone?: ConeShape | null;
  /** Confirmed patterns to draw; the caller passes only those inside the visible range. */
  patterns?: readonly PatternShape[];
  selectedPattern?: string | null;
}) {
  const { t, locale } = useLang();
  const phone = useMediaQuery("(max-width: 767px)");
  const wrapRef = useRef<HTMLDivElement>(null);
  const width = useWidth(wrapRef);
  const [active, setActive] = useState<number | null>(null);
  const unit = tickUnit(range);
  const tickFmt = useMemo(() => new Intl.DateTimeFormat(locale === "en" ? "en-GB" : locale, TICK_FORMAT[unit]), [locale, unit]);

  const shown = useMemo(() => sliceRange(bars, range), [bars, range]);
  const h = phone ? Math.min(height, 180) : height;
  const box: PlotBox = {
    left: PAD.left,
    right: Math.max(PAD.left + 1, width - PAD.right),
    top: PAD.top,
    bottom: h - PAD.bottom,
  };
  const nowX = cone ? splitX(box, phone ? FORECAST_SHARE + 0.06 : FORECAST_SHARE) : box.right;

  const domain = useMemo(
    () =>
      yDomain(
        shown.map((b) => b.close),
        [...refLines.map((r) => r.value), ...(cone ? coneValues(cone) : []), ...patterns.flatMap(patternValues)],
      ),
    [shown, refLines, cone, patterns],
  );

  const lastBar = shown[shown.length - 1];
  const asOf = lastBar ? fmtDate(locale, lastBar.date) : null;

  if (shown.length < 2 || !domain) {
    return (
      <div className="price-chart">
        <EmptyState>{t("not_enough_history")}</EmptyState>
      </div>
    );
  }

  const point = (i: number): { x: number; y: number } => ({
    x: scaleX(i, shown.length, box.left, nowX),
    y: scaleY(shown[i]!.close, domain, box.top, box.bottom),
  });

  const move = (e: PointerEvent<SVGSVGElement>): void => {
    const x = e.clientX - e.currentTarget.getBoundingClientRect().left;
    setActive(x > nowX + 4 ? null : nearestIndex(x, shown.length, box.left, nowX));
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
  // With a cone, keep past labels clear of the first horizon label.
  const ticks = periodTicks(shown, unit, box.left, nowX, TICK_GAP[unit]).filter(
    (tick) => !cone || scaleX(tick.index, shown.length, box.left, nowX) <= nowX - 36,
  );

  return (
    <figure className="price-chart">
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
              <text
                key={tick.date}
                x={scaleX(tick.index, shown.length, box.left, nowX)}
                y={h - 6}
                className="chart-axis"
                textAnchor="start"
              >
                {tickFmt.format(new Date(`${tick.date}T00:00:00Z`))}
              </text>
            ))}
            {cone && <ConeLayer cone={cone} domain={domain} box={box} nowX={nowX} />}
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
            <path d={linePath(shown, domain, { ...box, right: nowX })} className="chart-line" />
            {patterns.map((p) => (
              <PatternLayer key={p.id} shape={p} selected={p.id === selectedPattern} bars={shown} domain={domain} box={box} nowX={nowX} />
            ))}
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
            style={{
              left: Math.min(Math.max(curPoint.x, 70), Math.max(70, width - 70)),
              top: Math.max(0, curPoint.y - 38),
            }}
          >
            {tooltip}
          </div>
        )}
      </div>
      <figcaption className="price-chart-caption">
        {source ? t("px_chart_caption_source", { source, date: asOf ?? "" }) : t("px_chart_caption", { date: asOf ?? "" })}
      </figcaption>
    </figure>
  );
}
