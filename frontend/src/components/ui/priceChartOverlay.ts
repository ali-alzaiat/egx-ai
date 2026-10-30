import type {
  AutoscaleInfo,
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  SeriesType,
  Time,
} from "lightweight-charts";
import type { ChartPalette } from "../../lib/chartPalette";
import type { ConeOverlay, DatedPrice, PatternOverlay } from "../../lib/priceChart";

/** One pattern with the already translated texts it carries. */
export interface PatternDraw {
  overlay: PatternOverlay;
  /** The emphasised pattern is drawn in full; the others are dimmed. */
  selected: boolean;
  breakText: string;
  targetText: string;
  /** Text of a forming shape's "Confirms above/below" level. */
  levelText: { above: string; below: string };
}

export interface ConeDraw {
  overlay: ConeOverlay;
  /** Short label of each horizon ("1M", "3M"), by trading days. */
  labels: { date: string; text: string }[];
  /** The last bar's date: where the dashed "last close" line stands. */
  lastDate: string;
}

export interface RefDraw {
  price: number;
  label: string;
}

/** Everything the overlay draws, in (date, price) space; pixels come from the chart at draw time. */
export interface OverlaySpec {
  palette: ChartPalette;
  /** Arabic: text runs are laid out right to left. */
  rtl: boolean;
  cone: ConeDraw | null;
  patterns: readonly PatternDraw[];
  refLines: readonly RefDraw[];
  /** Prices the overlay reaches, so the price scale makes room for them. */
  extent: { min: number; max: number } | null;
}

type Target = Parameters<IPrimitivePaneRenderer["draw"]>[0];
type Ctx = CanvasRenderingContext2D;
interface Pt {
  x: number;
  y: number;
}

const DIM = 0.4;

/**
 * Draws the volatility cone (under the series), then reference lines, the last-close line and the
 * pattern shapes (over it), as a lightweight-charts series primitive. Display only.
 */
export class OverlayPrimitive implements ISeriesPrimitive {
  private param: SeriesAttachedParameter<Time, SeriesType> | null = null;
  private spec: OverlaySpec | null = null;
  private readonly views: readonly IPrimitivePaneView[];

  constructor() {
    const under: IPrimitivePaneRenderer = { draw: (target) => this.paint(target, "under") };
    const over: IPrimitivePaneRenderer = { draw: (target) => this.paint(target, "over") };
    this.views = [
      { zOrder: () => "bottom", renderer: () => under },
      { zOrder: () => "top", renderer: () => over },
    ];
  }

  attached(param: SeriesAttachedParameter<Time, SeriesType>): void {
    this.param = param;
  }

  detached(): void {
    this.param = null;
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }

  autoscaleInfo(): AutoscaleInfo | null {
    const extent = this.spec?.extent;
    return extent ? { priceRange: { minValue: extent.min, maxValue: extent.max } } : null;
  }

  /** Replace what is drawn and repaint. */
  setSpec(spec: OverlaySpec): void {
    this.spec = spec;
    this.param?.requestUpdate();
  }

  // ---- drawing ----

  private at(date: string, price: number): Pt | null {
    const p = this.param;
    if (!p) return null;
    const x = p.chart.timeScale().timeToCoordinate(date);
    const y = p.series.priceToCoordinate(price);
    return x === null || y === null ? null : { x, y };
  }

  private paint(target: Target, layer: "under" | "over"): void {
    const spec = this.spec;
    if (!spec || !this.param) return;
    target.useMediaCoordinateSpace(({ context, mediaSize }) => {
      context.save();
      context.font = `${spec.palette.fontSize}px ${spec.palette.fontFamily}`;
      context.direction = spec.rtl ? "rtl" : "ltr";
      if (layer === "under") {
        if (spec.cone) this.drawBands(context, spec.cone, spec.palette);
      } else {
        for (const r of spec.refLines) this.drawRef(context, r, mediaSize.width, spec.palette);
        if (spec.cone) this.drawMarks(context, spec.cone, mediaSize, spec.palette);
        for (const pattern of spec.patterns) this.drawPattern(context, pattern, mediaSize.width, spec.palette);
      }
      context.restore();
    });
  }

  private polygon(ctx: Ctx, points: readonly DatedPrice[]): boolean {
    ctx.beginPath();
    let started = false;
    for (const point of points) {
      const p = this.at(point.date, point.price);
      if (!p) continue;
      if (started) ctx.lineTo(p.x, p.y);
      else ctx.moveTo(p.x, p.y);
      started = true;
    }
    return started;
  }

  private drawBands(ctx: Ctx, cone: ConeDraw, pal: ChartPalette): void {
    ctx.fillStyle = pal.cone;
    ctx.strokeStyle = pal.cone;
    ctx.lineJoin = "round";
    ctx.lineWidth = 1;
    if (this.polygon(ctx, cone.overlay.band90)) {
      ctx.closePath();
      ctx.globalAlpha = 0.14;
      ctx.fill();
      ctx.globalAlpha = 0.55;
      ctx.stroke();
    }
    if (this.polygon(ctx, cone.overlay.band50)) {
      ctx.closePath();
      ctx.globalAlpha = 0.28;
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  /** The dashed last-close line and a short label under each horizon. */
  private drawMarks(ctx: Ctx, cone: ConeDraw, size: { width: number; height: number }, pal: ChartPalette): void {
    ctx.strokeStyle = pal.crosshair;
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 3]);
    const nowX = this.param?.chart.timeScale().timeToCoordinate(cone.lastDate);
    if (nowX !== null && nowX !== undefined) {
      ctx.beginPath();
      ctx.moveTo(nowX, 0);
      ctx.lineTo(nowX, size.height);
      ctx.stroke();
    }
    ctx.setLineDash([]);
    const last = cone.labels.length - 1;
    cone.labels.forEach((label, i) => {
      const x = this.param?.chart.timeScale().timeToCoordinate(label.date);
      if (x === null || x === undefined) return;
      ctx.strokeStyle = pal.crosshair;
      ctx.beginPath();
      ctx.moveTo(x, size.height - 16);
      ctx.lineTo(x, size.height - 11);
      ctx.stroke();
      halo(ctx, label.text, x, size.height - 2, i === last ? "right" : "center", pal, pal.axis);
    });
  }

  private drawRef(ctx: Ctx, ref: RefDraw, width: number, pal: ChartPalette): void {
    const y = this.param?.series.priceToCoordinate(ref.price);
    if (y === null || y === undefined) return;
    ctx.strokeStyle = pal.ref;
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 4]);
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
    ctx.setLineDash([]);
    // Right-aligned: the attribution logo sits at the bottom left of the plot.
    halo(ctx, ref.label, width - 4, y - 4, "right", pal, pal.text2);
  }

  private line(ctx: Ctx, a: Pt, b: Pt): void {
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }

  private drawPattern(ctx: Ctx, draw: PatternDraw, width: number, pal: ChartPalette): void {
    const { overlay, selected } = draw;
    const dash = overlay.forming ? [4, 3] : [];
    ctx.globalAlpha = selected ? 1 : DIM;
    ctx.strokeStyle = pal.pattern;
    ctx.fillStyle = pal.pattern;
    ctx.lineJoin = "round";

    // Outline through the key points.
    ctx.lineWidth = 1;
    ctx.setLineDash(dash);
    ctx.globalAlpha = (selected ? 1 : DIM) * 0.7;
    if (this.polygon(ctx, overlay.outline)) ctx.stroke();
    ctx.globalAlpha = selected ? 1 : DIM;

    // Boundary lines.
    ctx.lineWidth = 1.5;
    for (const l of overlay.lines) {
      const a = this.at(l.start.date, l.start.price);
      const b = this.at(l.end.date, l.end.price);
      if (a && b) this.line(ctx, a, b);
    }

    // Measured move: target across the pattern's width, joined to the break mark.
    const breakPt = overlay.breakMark ? this.at(overlay.breakMark.date, overlay.breakMark.price) : null;
    let targetPt: { x1: number; x2: number; y: number } | null = null;
    if (overlay.target) {
      const a = this.at(overlay.target.startDate, overlay.target.price);
      const b = this.at(overlay.target.endDate, overlay.target.price);
      if (a && b) {
        targetPt = { x1: a.x, x2: b.x, y: a.y };
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 4]);
        this.line(ctx, a, b);
        if (breakPt) this.line(ctx, breakPt, { x: breakPt.x, y: a.y });
      }
    }

    // Forming shapes: the closes that would confirm them.
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 3]);
    for (const level of overlay.levels) {
      const a = this.at(level.startDate, level.price);
      const b = this.at(level.endDate, level.price);
      if (!a || !b) continue;
      this.line(ctx, a, b);
      if (selected) halo(ctx, draw.levelText[level.side], b.x - 4, a.y + (level.side === "above" ? -5 : 13), "right", pal, pal.text);
    }
    ctx.setLineDash([]);

    // Key points.
    ctx.lineWidth = 1.5;
    ctx.fillStyle = pal.surface;
    for (const point of overlay.points) {
      const p = this.at(point.date, point.price);
      if (!p) continue;
      ctx.beginPath();
      ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    }

    // Break diamond and its labels (confirmed shapes only).
    if (breakPt) {
      ctx.fillStyle = pal.pattern;
      ctx.beginPath();
      ctx.moveTo(breakPt.x, breakPt.y - 5.7);
      ctx.lineTo(breakPt.x + 5.7, breakPt.y);
      ctx.lineTo(breakPt.x, breakPt.y + 5.7);
      ctx.lineTo(breakPt.x - 5.7, breakPt.y);
      ctx.closePath();
      ctx.fill();
      if (selected) {
        const nearLeft = breakPt.x < 110;
        const below = targetPt !== null && targetPt.y > breakPt.y;
        halo(ctx, draw.breakText, breakPt.x + (nearLeft ? 8 : -8), breakPt.y + (below ? -6 : 14), nearLeft ? "left" : "right", pal, pal.text);
        if (targetPt && draw.targetText) {
          const textWidth = ctx.measureText(draw.targetText).width;
          const x = Math.max(2, Math.min(targetPt.x1, width - textWidth - 2));
          halo(ctx, draw.targetText, x, targetPt.y + (targetPt.y < 14 ? 14 : -5), "left", pal, pal.text);
        }
      }
    }
    ctx.globalAlpha = 1;
  }
}

/** Text with a surface-coloured outline, so it stays readable over lines and candles. */
function halo(ctx: Ctx, text: string, x: number, y: number, align: CanvasTextAlign, pal: ChartPalette, color: string): void {
  ctx.save();
  ctx.textAlign = align;
  ctx.lineWidth = 3;
  ctx.lineJoin = "round";
  ctx.setLineDash([]);
  ctx.strokeStyle = pal.surface;
  ctx.strokeText(text, x, y);
  ctx.fillStyle = color;
  ctx.fillText(text, x, y);
  ctx.restore();
}
