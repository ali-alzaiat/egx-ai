import type { CopyKey, CopyParams } from "../i18n";
import type { LimitationItem, StancePart } from "../types";
import { fmtAsPrinted } from "./format";
import { joinList } from "./stanceModel";

/**
 * Writes stance reasons and limitations from the codes the API sends (R51), so the Arabic page reads
 * Arabic. Pure: the caller passes `t` and the locale from `useLang()`.
 *
 * Every function returns `null` when it cannot write the sentence faithfully (unknown code, unknown variant,
 * a missing or unreadable parameter). The caller then shows the English `text` from the API, so a new
 * backend code degrades to English instead of to a wrong sentence.
 */

export interface TextContext {
  t: (key: CopyKey, params?: CopyParams) => string;
  /** From `useLang()`: "en" or "ar-EG-u-nu-latn". */
  locale: string;
}

const SIDES = ["above", "below", "at"] as const;
const MOVING_AVERAGES = ["SMA20", "SMA50"] as const;
const RSI_STATES = ["overbought", "oversold", "above_50", "below_50"] as const;
const MACD_SIDES = ["positive", "negative", "flat"] as const;
const DIRECTIONS = ["up", "down", "flat"] as const;
const CONFIDENCES = ["VeryHigh", "High", "Medium", "Low"] as const;
const CONFIDENCE_KEYS = {
  VeryHigh: "sr_confidence_very_high",
  High: "sr_confidence_high",
  Medium: "sr_confidence_medium",
  Low: "sr_confidence_low",
} as const;
const MISSING_INPUTS = ["technical", "valuation", "score"] as const;

/** `value` when it is one of `allowed`, else null. */
function pick<T extends string>(value: string | undefined, allowed: readonly T[]): T | null {
  return allowed.find((a) => a === value) ?? null;
}

const isArabic = (locale: string): boolean => locale.startsWith("ar");

/** A number as the API printed it, localized; isolated left-to-right inside Arabic text so the sign and % stay put. */
function num(ctx: TextContext, value: string | undefined, suffix = ""): string | null {
  const text = fmtAsPrinted(ctx.locale, value);
  if (text === null) return null;
  const shown = `${text}${suffix}`;
  return isArabic(ctx.locale) ? `⁦${shown}⁩` : shown;
}

/** Fills the placeholders of one sentence; null as soon as any value is missing. */
function sentence(ctx: TextContext, key: CopyKey, values: Record<string, string | null>): string | null {
  const params: Record<string, string> = {};
  for (const [name, value] of Object.entries(values)) {
    if (value === null) return null;
    params[name] = value;
  }
  return ctx.t(key, params);
}

/** One reason sentence from its code, or null. */
export function partText(part: StancePart, ctx: TextContext): string | null {
  const p = part.params;
  switch (part.code) {
    case "trend": {
      const side = pick(p.side, SIDES);
      const ma = pick(p.ma, MOVING_AVERAGES);
      if (!side || !ma) return null;
      return sentence(ctx, `sr_trend_${side}`, { ma: ctx.t(ma === "SMA20" ? "sr_ma_sma20" : "sr_ma_sma50") });
    }
    case "long_trend": {
      const side = pick(p.side, SIDES);
      if (!side) return null;
      return sentence(ctx, `sr_long_trend_${side}`, { short: ctx.t("sr_ma_sma50"), long: ctx.t("sr_ma_sma200") });
    }
    case "rsi": {
      const state = pick(p.state, RSI_STATES);
      if (!state) return null;
      return sentence(ctx, `sr_rsi_${state}`, { value: num(ctx, p.value) });
    }
    case "macd": {
      const side = pick(p.side, MACD_SIDES);
      return side ? ctx.t(`sr_macd_${side}`) : null;
    }
    case "momentum": {
      const direction = pick(p.direction, DIRECTIONS);
      if (!direction) return null;
      return sentence(ctx, `sr_momentum_${direction}`, { pct: num(ctx, p.pct, "%") });
    }
    case "volume_unusual":
      return sentence(ctx, "sr_volume_unusual", { ratio: num(ctx, p.ratio) });
    case "fair_value_vs_market": {
      const confidence = pick(p.confidence, CONFIDENCES);
      if (!confidence) return null;
      return sentence(ctx, "sr_fair_value_vs_market", {
        ratio: num(ctx, p.ratio),
        market_ratio: num(ctx, p.market_ratio),
        peers: num(ctx, p.peers),
        confidence: ctx.t(CONFIDENCE_KEYS[confidence]),
        subscore: num(ctx, p.subscore),
      });
    }
    case "scenario_range":
      return sentence(ctx, "sr_scenario_range", { subscore: num(ctx, p.subscore) });
    case "investment_score":
      return sentence(ctx, "sr_investment_score", { headline: num(ctx, p.headline), subscore: num(ctx, p.subscore) });
    default:
      return null;
  }
}

/** A whole reason: all its sentences in order, or null when any one cannot be written (then show the English text). */
export function reasonText(parts: readonly StancePart[] | undefined, ctx: TextContext): string | null {
  if (!parts || parts.length === 0) return null;
  const sentences: string[] = [];
  for (const part of parts) {
    const text = partText(part, ctx);
    if (text === null) return null;
    sentences.push(text);
  }
  return sentences.join(" ");
}

/**
 * One limitation from its code, or null. The footer, levels and stop codes are never listed (the page carries
 * them in its own copy), so they have no sentence here. `missing_inputs` stays English in English, because the
 * API text carries parenthetical notes (a currency mismatch, the confidence needed) that the code does not.
 */
export function limitationText(item: LimitationItem | undefined, ctx: TextContext): string | null {
  if (!item) return null;
  const p = item.params;
  switch (item.code) {
    case "statement_freshness_unknown":
      return ctx.t("sr_lim_statement_freshness_unknown");
    case "statement_stale":
      return sentence(ctx, "sr_lim_statement_stale", { days: num(ctx, p.days), max_days: num(ctx, p.max_days) });
    case "low_liquidity":
      return sentence(ctx, "sr_lim_low_liquidity", { min_egp: num(ctx, p.min_egp), window: num(ctx, p.window) });
    case "no_engine_input":
      return ctx.t("sr_lim_no_engine_input");
    case "technical_only":
      return ctx.t("sr_lim_technical_only");
    case "missing_inputs": {
      if (!isArabic(ctx.locale)) return null;
      const codes = (p.inputs ?? "").split(",").map((c) => c.trim()).filter((c) => c !== "");
      if (codes.length === 0) return null;
      const names: string[] = [];
      for (const code of codes) {
        const known = pick(code, MISSING_INPUTS);
        if (!known) return null;
        names.push(ctx.t(`sr_input_${known}`));
      }
      return ctx.t("sr_lim_missing_inputs", { inputs: joinList(names, ctx.t("px_list_sep"), ctx.t("px_list_and")) });
    }
    default:
      return null;
  }
}
