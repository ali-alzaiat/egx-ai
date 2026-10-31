import { describe, expect, it } from "vitest";
import { t as translate, type Lang } from "../i18n/dict";
import type { LimitationItem, StancePart } from "../types";
import { limitationText, partText, reasonText, type TextContext } from "./stanceText";

const EN: TextContext = { t: (k, p) => translate(k, "en" satisfies Lang, p), locale: "en" };
const AR: TextContext = { t: (k, p) => translate(k, "ar" satisfies Lang, p), locale: "ar-EG-u-nu-latn" };

/** Left-to-right isolates wrap numbers in Arabic text. */
const iso = (s: string): string => `⁦${s}⁩`;

const part = (code: string, params: Record<string, string> = {}): StancePart => ({ code, params });
const lim = (code: string, params: Record<string, string> = {}): LimitationItem => ({ code, params, text: "english" });

describe("partText in English matches the backend sentences", () => {
  const cases: [StancePart, string][] = [
    [part("trend", { side: "below", ma: "SMA50" }), "Price below SMA50."],
    [part("trend", { side: "above", ma: "SMA20" }), "Price above SMA20."],
    [part("trend", { side: "at", ma: "SMA50" }), "Price at SMA50."],
    [part("long_trend", { side: "below" }), "SMA50 below SMA200."],
    [part("rsi", { value: "37.88", state: "below_50" }), "RSI 37.88 below 50."],
    [part("rsi", { value: "78.20", state: "overbought" }), "RSI 78.20 overbought: no momentum credit."],
    [part("rsi", { value: "22.1", state: "oversold" }), "RSI 22.1 oversold: no momentum penalty."],
    [part("macd", { side: "negative" }), "MACD line negative (EMA12 vs EMA26)."],
    [part("momentum", { direction: "up", pct: "6.3" }), "Up 6.3% over 20 sessions."],
    [part("momentum", { direction: "down", pct: "9.1" }), "Down 9.1% over 20 sessions."],
    [part("momentum", { direction: "flat", pct: "-4.6" }), "Flat (−4.6%) over 20 sessions."],
    [part("volume_unusual", { ratio: "1.8" }), "Unusual volume: 1.8x the 20-session average."],
    [
      part("fair_value_vs_market", { ratio: "0.88", market_ratio: "2.60", peers: "118", confidence: "High", subscore: "+1.00" }),
      "Price is 0.88x fair value vs a market median of 2.60x (118 companies, High confidence): sub-score +1.00.",
    ],
    [part("scenario_range", { subscore: "+0.5" }), "Price vs scenario range: sub-score +0.5."],
    [part("investment_score", { headline: "62", subscore: "+0.24" }), "Investment score 62: sub-score +0.24."],
  ];
  it.each(cases)("%j", (p, expected) => {
    expect(partText(p, EN)).toBe(expected);
  });
});

describe("partText in Arabic", () => {
  it("writes Arabic with Western digits and isolated numbers", () => {
    expect(partText(part("rsi", { value: "37.88", state: "below_50" }), AR)).toBe(
      `مؤشر القوة النسبية RSI عند ${iso("37.88")}، أدنى من 50.`,
    );
    expect(partText(part("momentum", { direction: "flat", pct: "-4.6" }), AR)).toBe(`شبه ثابت (${iso("−4.6%")}) خلال 20 جلسة.`);
    expect(partText(part("scenario_range", { subscore: "+0.5" }), AR)).toBe(
      `موضع السعر ضمن نطاق السيناريوهات: الدرجة الفرعية ${iso("+0.5")}.`,
    );
  });

  it("names the moving averages and the confidence in Arabic", () => {
    expect(partText(part("trend", { side: "below", ma: "SMA50" }), AR)).toBe("السعر أدنى من المتوسط المتحرك 50 يومًا (SMA50).");
    const fv = partText(
      part("fair_value_vs_market", { ratio: "0.88", market_ratio: "2.60", peers: "118", confidence: "Medium", subscore: "+1.00" }),
      AR,
    );
    expect(fv).toContain("ثقة متوسطة");
    expect(fv).toContain(iso("118"));
  });

  it("knows the VeryHigh fair-value confidence level", () => {
    const p = part("fair_value_vs_market", { ratio: "0.88", market_ratio: "2.60", peers: "118", confidence: "VeryHigh", subscore: "+1.00" });
    expect(partText(p, EN)).toContain("Very high confidence");
    expect(partText(p, AR)).toContain("ثقة عالية جداً");
  });

  it("has no Latin sentence words in any Arabic result", () => {
    const parts = [
      part("trend", { side: "above", ma: "SMA20" }),
      part("long_trend", { side: "above" }),
      part("rsi", { value: "55", state: "above_50" }),
      part("macd", { side: "positive" }),
      part("momentum", { direction: "up", pct: "7.0" }),
      part("volume_unusual", { ratio: "2.4" }),
      part("investment_score", { headline: "62", subscore: "+0.24" }),
    ];
    for (const p of parts) {
      const text = partText(p, AR) ?? "";
      expect(text.replace(/SMA\d+|RSI|MACD|[\d.+−%]/g, "")).not.toMatch(/[A-Za-z]{3,}/);
    }
  });
});

describe("partText falls back (null) instead of guessing", () => {
  it.each([
    ["unknown code", part("new_code", { x: "1" })],
    ["unknown side", part("trend", { side: "sideways", ma: "SMA50" })],
    ["unknown moving average", part("trend", { side: "above", ma: "EMA9" })],
    ["unknown rsi state", part("rsi", { value: "50", state: "weird" })],
    ["unknown momentum direction", part("momentum", { direction: "sideways", pct: "1" })],
    ["unknown confidence", part("fair_value_vs_market", { ratio: "1", market_ratio: "1", peers: "9", confidence: "Huge", subscore: "+1" })],
    ["missing parameter", part("rsi", { state: "above_50" })],
    ["unreadable number", part("volume_unusual", { ratio: "lots" })],
  ])("%s", (_name, p) => {
    expect(partText(p, EN)).toBeNull();
    expect(partText(p, AR)).toBeNull();
  });
});

describe("reasonText", () => {
  it("joins the sentences of a reason in order", () => {
    const parts = [part("trend", { side: "below", ma: "SMA50" }), part("long_trend", { side: "below" })];
    expect(reasonText(parts, EN)).toBe("Price below SMA50. SMA50 below SMA200.");
  });

  it("is null when parts are missing, empty or any one cannot be written", () => {
    expect(reasonText(undefined, EN)).toBeNull();
    expect(reasonText([], EN)).toBeNull();
    expect(reasonText([part("macd", { side: "positive" }), part("new_code")], AR)).toBeNull();
  });
});

describe("limitationText", () => {
  it("matches the backend sentences in English", () => {
    expect(limitationText(lim("statement_freshness_unknown"), EN)).toBe("Statement freshness unknown.");
    expect(limitationText(lim("statement_stale", { days: "450", max_days: "400" }), EN)).toBe("Statement freshness 450 days (>400).");
    expect(limitationText(lim("low_liquidity", { min_egp: "50,000", window: "20" }), EN)).toBe(
      "LOW LIQUIDITY: average value traded below EGP 50,000 over 20 sessions; levels may not be executable.",
    );
    expect(limitationText(lim("no_engine_input"), EN)).toBe("No engine produced an input: stance defaults to hold.");
    expect(limitationText(lim("technical_only"), EN)).toBe("Technical-only stance: no fundamentals available yet.");
  });

  it("writes Arabic with grouped numbers", () => {
    expect(limitationText(lim("low_liquidity", { min_egp: "50,000", window: "20" }), AR)).toBe(
      `سيولة منخفضة: متوسط قيمة التداول أقل من ${iso("50,000")} جنيه مصري خلال ${iso("20")} جلسة، وقد لا تكون المستويات قابلة للتنفيذ.`,
    );
    expect(limitationText(lim("statement_stale", { days: "450", max_days: "400" }), AR)).toBe(
      `عمر القوائم المالية ${iso("450")} يومًا (أكثر من ${iso("400")} يومًا).`,
    );
  });

  it("lists missing inputs in Arabic and keeps the detailed English text in English", () => {
    expect(limitationText(lim("missing_inputs", { inputs: "technical,valuation,score" }), AR)).toBe(
      "مدخلات ناقصة: التحليل الفني، سيناريوهات التقييم أو القيمة العادلة ودرجة الاستثمار.",
    );
    expect(limitationText(lim("missing_inputs", { inputs: "technical" }), EN)).toBeNull();
    expect(limitationText(lim("missing_inputs", { inputs: "technical,mystery" }), AR)).toBeNull();
    expect(limitationText(lim("missing_inputs", { inputs: "" }), AR)).toBeNull();
  });

  it("has no sentence for the covered codes, unknown codes or a missing item", () => {
    for (const code of ["compliance_footer", "levels_band", "stop_reference", "brand_new"]) {
      expect(limitationText(lim(code), EN)).toBeNull();
      expect(limitationText(lim(code), AR)).toBeNull();
    }
    expect(limitationText(undefined, AR)).toBeNull();
    expect(limitationText(lim("statement_stale", { days: "x", max_days: "400" }), AR)).toBeNull();
  });
});
