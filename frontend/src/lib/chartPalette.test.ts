import { describe, expect, it } from "vitest";
import { FALLBACK_PALETTE, PALETTE_TOKENS, readChartPalette, samePalette } from "./chartPalette";

const LIGHT: Record<string, string> = {
  "--series-1": " #0072b2",
  "--gain": "#0b7a43",
  "--loss": "#c42b33",
  "--series-2": "#9a5b00",
  "--series-3": "#8e4a75",
  "--chart-grid": "#dde2ec",
  "--chart-axis": "#5a6480",
  "--chart-ref": "#5a6480",
  "--text-3": "#5a6480",
  "--surface": "#ffffff",
  "--text": "#0f1729",
  "--text-2": "#3d4660",
  "--font-ui": '"Plus Jakarta Sans", "Cairo", system-ui, sans-serif',
  "--fs-micro": "12px",
};

describe("readChartPalette", () => {
  it("reads each entry from its token and trims the value", () => {
    const p = readChartPalette((token) => LIGHT[token] ?? "");
    expect(p.line).toBe("#0072b2");
    expect(p.gain).toBe("#0b7a43");
    expect(p.loss).toBe("#c42b33");
    expect(p.pattern).toBe("#9a5b00");
    expect(p.cone).toBe("#8e4a75");
    expect(p.fontFamily).toContain("Cairo");
    expect(p.fontSize).toBe(12);
  });
  it("asks for every token the palette names", () => {
    const asked: string[] = [];
    readChartPalette((token) => {
      asked.push(token);
      return "";
    });
    expect(asked.sort()).toEqual(Object.values(PALETTE_TOKENS).sort());
  });
  it("falls back to the light theme when a token cannot be read", () => {
    expect(readChartPalette(() => "")).toEqual(FALLBACK_PALETTE);
    expect(readChartPalette(() => "not a size").fontSize).toBe(FALLBACK_PALETTE.fontSize);
  });
  it("sees a theme change", () => {
    const light = readChartPalette((token) => LIGHT[token] ?? "");
    const dark = readChartPalette((token) => (token === "--surface" ? "#131928" : (LIGHT[token] ?? "")));
    expect(samePalette(light, light)).toBe(true);
    expect(samePalette(light, dark)).toBe(false);
  });
});
