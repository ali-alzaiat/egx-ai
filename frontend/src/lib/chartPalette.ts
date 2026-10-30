/**
 * Colours and font for the canvas chart, taken from our CSS tokens (src/styles/tokens.css).
 * A canvas cannot read CSS variables, so the chart reads their computed values and reads them again
 * when the theme (data-theme attribute or prefers-color-scheme) or the language (font) changes.
 */

export interface ChartPalette {
  /** Close line (--series-1). */
  line: string;
  /** Rising candle (--gain). */
  gain: string;
  /** Falling candle (--loss). */
  loss: string;
  /** Chart patterns (--series-2). */
  pattern: string;
  /** Volatility cone (--series-3). */
  cone: string;
  grid: string;
  /** Axis labels (--chart-axis). */
  axis: string;
  /** Reference lines (--chart-ref). */
  ref: string;
  /** Crosshair and the last-close line (--text-3). */
  crosshair: string;
  surface: string;
  text: string;
  text2: string;
  fontFamily: string;
  /** Label size in px (--fs-micro). */
  fontSize: number;
}

/** Token name behind each palette entry. */
export const PALETTE_TOKENS: Record<keyof ChartPalette, string> = {
  line: "--series-1",
  gain: "--gain",
  loss: "--loss",
  pattern: "--series-2",
  cone: "--series-3",
  grid: "--chart-grid",
  axis: "--chart-axis",
  ref: "--chart-ref",
  crosshair: "--text-3",
  surface: "--surface",
  text: "--text",
  text2: "--text-2",
  fontFamily: "--font-ui",
  fontSize: "--fs-micro",
};

/** Used only when a token cannot be read (no DOM): the light theme's values. */
export const FALLBACK_PALETTE: ChartPalette = {
  line: "#0072b2",
  gain: "#0b7a43",
  loss: "#c42b33",
  pattern: "#9a5b00",
  cone: "#8e4a75",
  grid: "#dde2ec",
  axis: "#5a6480",
  ref: "#5a6480",
  crosshair: "#5a6480",
  surface: "#ffffff",
  text: "#0f1729",
  text2: "#3d4660",
  fontFamily: "system-ui, sans-serif",
  fontSize: 12,
};

/** Palette from a token reader such as `(name) => getComputedStyle(root).getPropertyValue(name)`. */
export function readChartPalette(read: (token: string) => string): ChartPalette {
  const text = (key: Exclude<keyof ChartPalette, "fontSize">): string =>
    read(PALETTE_TOKENS[key]).trim() || FALLBACK_PALETTE[key];
  const size = Number.parseFloat(read(PALETTE_TOKENS.fontSize));
  return {
    line: text("line"),
    gain: text("gain"),
    loss: text("loss"),
    pattern: text("pattern"),
    cone: text("cone"),
    grid: text("grid"),
    axis: text("axis"),
    ref: text("ref"),
    crosshair: text("crosshair"),
    surface: text("surface"),
    text: text("text"),
    text2: text("text2"),
    fontFamily: text("fontFamily"),
    fontSize: Number.isFinite(size) && size > 0 ? size : FALLBACK_PALETTE.fontSize,
  };
}

/** Same palette (every entry equal): lets a re-read after an unrelated change skip a re-render. */
export function samePalette(a: ChartPalette, b: ChartPalette): boolean {
  return (Object.keys(PALETTE_TOKENS) as (keyof ChartPalette)[]).every((k) => a[k] === b[k]);
}
