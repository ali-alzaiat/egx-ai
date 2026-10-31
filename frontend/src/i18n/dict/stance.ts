import type { CopyEntry } from "./types";

/**
 * Stance and Shariah vocabulary shared by markets, companies and the hub.
 * Labels never read as an instruction to trade (AGENTS.md principle 10).
 */
export const STANCE_COPY = {
  stance_buy: { en: "Leans buy", ar: "يميل للشراء" },
  stance_hold: { en: "Neutral", ar: "محايد" },
  stance_reduce: { en: "Leans reduce", ar: "يميل للتخفيض" },
  stance_not_assessed: { en: "Not assessed", ar: "لم يُقيَّم" },
  stance_tooltip: {
    en: "Model stance under {rules}, confidence {c}/100. A research calculation, not a recommendation to trade.",
    ar: "موقف النموذج وفق {rules}، الثقة {c}/100. حساب بحثي، وليس توصية بالتداول.",
  },
  stance_not_assessed_tooltip: {
    en: "No engine produced an input for this company, so no stance is shown.",
    ar: "لم ينتج أي محرك مدخلاً لهذه الشركة، لذلك لا يُعرض موقف.",
  },
  stance_confidence: { en: "Confidence {c}/100", ar: "الثقة {c}/100" },
  signals_shariah: { en: "Shariah", ar: "الشرعية" },
  shariah_our_verdict: { en: "Our screening", ar: "فحصنا" },
  shariah_egx33: { en: "EGX33 Shariah index", ar: "مؤشر EGX33 الشرعي" },
  shariah_member: { en: "Member", ar: "عضو" },
  shariah_not_member: { en: "Not a member", ar: "ليس عضواً" },
  shariah_unknown: { en: "Unknown", ar: "غير معروف" },
  shariah_not_screened: { en: "Not screened yet", ar: "لم يُفحص بعد" },
  shariah_compliant: { en: "Passes our screen", ar: "يجتاز فحصنا" },
  shariah_non_compliant: { en: "Fails our screen", ar: "لا يجتاز فحصنا" },
  shariah_insufficient: { en: "Not enough data", ar: "بيانات غير كافية" },
  shariah_provisional: { en: "provisional (vendor data)", ar: "مؤقت (بيانات مزوّد)" },
  shariah_egx33_member: {
    en: "EGX33 Shariah index: member ({cycle})",
    ar: "مؤشر EGX33 الشرعي: عضو ({cycle})",
  },
  shariah_egx33_not_member: {
    en: "EGX33: not a member (not a non-compliance verdict)",
    ar: "EGX33: ليس عضواً (وهذا ليس حكماً بعدم التوافق)",
  },
  shariah_egx33_unknown: { en: "EGX33: unknown", ar: "EGX33: غير معروف" },
  shariah_rule_pass: { en: "Passes", ar: "يجتاز" },
  shariah_rule_fail: { en: "Fails", ar: "لا يجتاز" },
  shariah_rule_unknown: { en: "Unknown", ar: "غير معروف" },
  // ---- Stance reasons and limitations written from codes (R51; lib/stanceText.ts). EN mirrors the backend sentence. ----
  sr_ma_sma20: { en: "SMA20", ar: "المتوسط المتحرك 20 يومًا (SMA20)" },
  sr_ma_sma50: { en: "SMA50", ar: "المتوسط المتحرك 50 يومًا (SMA50)" },
  sr_ma_sma200: { en: "SMA200", ar: "المتوسط المتحرك 200 يومًا (SMA200)" },
  sr_trend_above: { en: "Price above {ma}.", ar: "السعر أعلى من {ma}." },
  sr_trend_below: { en: "Price below {ma}.", ar: "السعر أدنى من {ma}." },
  sr_trend_at: { en: "Price at {ma}.", ar: "السعر عند {ma}." },
  sr_long_trend_above: { en: "{short} above {long}.", ar: "{short} أعلى من {long}." },
  sr_long_trend_below: { en: "{short} below {long}.", ar: "{short} أدنى من {long}." },
  sr_long_trend_at: { en: "{short} at {long}.", ar: "{short} عند {long}." },
  sr_rsi_overbought: {
    en: "RSI {value} overbought: no momentum credit.",
    ar: "مؤشر القوة النسبية RSI عند {value}، في منطقة التشبّع الشرائي، فلا يُحتسب له رصيد في الزخم.",
  },
  sr_rsi_oversold: {
    en: "RSI {value} oversold: no momentum penalty.",
    ar: "مؤشر القوة النسبية RSI عند {value}، في منطقة التشبّع البيعي، فلا يُخصم منه في الزخم.",
  },
  sr_rsi_above_50: { en: "RSI {value} above 50.", ar: "مؤشر القوة النسبية RSI عند {value}، أعلى من 50." },
  sr_rsi_below_50: { en: "RSI {value} below 50.", ar: "مؤشر القوة النسبية RSI عند {value}، أدنى من 50." },
  sr_macd_positive: { en: "MACD line positive (EMA12 vs EMA26).", ar: "خط MACD موجب (المتوسط الأسي 12 مقابل 26)." },
  sr_macd_negative: { en: "MACD line negative (EMA12 vs EMA26).", ar: "خط MACD سالب (المتوسط الأسي 12 مقابل 26)." },
  sr_macd_flat: { en: "MACD line flat (EMA12 vs EMA26).", ar: "خط MACD عند الصفر (المتوسط الأسي 12 مقابل 26)." },
  sr_momentum_up: { en: "Up {pct} over 20 sessions.", ar: "ارتفاع بنسبة {pct} خلال 20 جلسة." },
  sr_momentum_down: { en: "Down {pct} over 20 sessions.", ar: "انخفاض بنسبة {pct} خلال 20 جلسة." },
  sr_momentum_flat: { en: "Flat ({pct}) over 20 sessions.", ar: "شبه ثابت ({pct}) خلال 20 جلسة." },
  sr_volume_unusual: {
    en: "Unusual volume: {ratio}x the 20-session average.",
    ar: "حجم تداول غير معتاد: {ratio} ضعف متوسط آخر 20 جلسة.",
  },
  sr_fair_value_vs_market: {
    en: "Price is {ratio}x fair value vs a market median of {market_ratio}x ({peers} companies, {confidence}): sub-score {subscore}.",
    ar: "السعر يعادل {ratio} ضعف القيمة العادلة، مقابل وسيط السوق البالغ {market_ratio} ضعف ({peers} شركة، {confidence}): الدرجة الفرعية {subscore}.",
  },
  sr_confidence_very_high: { en: "Very high confidence", ar: "ثقة عالية جداً" },
  sr_confidence_high: { en: "High confidence", ar: "ثقة عالية" },
  sr_confidence_medium: { en: "Medium confidence", ar: "ثقة متوسطة" },
  sr_confidence_low: { en: "Low confidence", ar: "ثقة منخفضة" },
  sr_scenario_range: {
    en: "Price vs scenario range: sub-score {subscore}.",
    ar: "موضع السعر ضمن نطاق السيناريوهات: الدرجة الفرعية {subscore}.",
  },
  sr_investment_score: {
    en: "Investment score {headline}: sub-score {subscore}.",
    ar: "درجة الاستثمار {headline}: الدرجة الفرعية {subscore}.",
  },
  sr_lim_statement_freshness_unknown: { en: "Statement freshness unknown.", ar: "عمر القوائم المالية غير معروف." },
  sr_lim_statement_stale: {
    en: "Statement freshness {days} days (>{max_days}).",
    ar: "عمر القوائم المالية {days} يومًا (أكثر من {max_days} يومًا).",
  },
  sr_lim_low_liquidity: {
    en: "LOW LIQUIDITY: average value traded below EGP {min_egp} over {window} sessions; levels may not be executable.",
    ar: "سيولة منخفضة: متوسط قيمة التداول أقل من {min_egp} جنيه مصري خلال {window} جلسة، وقد لا تكون المستويات قابلة للتنفيذ.",
  },
  sr_lim_no_engine_input: {
    en: "No engine produced an input: stance defaults to hold.",
    ar: "لم ينتج أي محرك مدخلاً: يبقى الموقف محايدًا افتراضيًا.",
  },
  sr_lim_technical_only: {
    en: "Technical-only stance: no fundamentals available yet.",
    ar: "الموقف فني فقط: لا تتوفر بيانات أساسية بعد.",
  },
  sr_lim_missing_inputs: { en: "Missing inputs: {inputs}.", ar: "مدخلات ناقصة: {inputs}." },
  sr_input_technical: { en: "technical", ar: "التحليل الفني" },
  sr_input_valuation: { en: "valuation scenarios or fair value", ar: "سيناريوهات التقييم أو القيمة العادلة" },
  sr_input_score: { en: "investment score", ar: "درجة الاستثمار" },
  shariah_egx33_badge: { en: "EGX33 Shariah", ar: "EGX33 شرعي" },
  shariah_egx33_badge_title: {
    en: "Member of the official EGX33 Shariah index (EGX's list, shown beside our own screening)",
    ar: "عضو في مؤشر EGX33 الشرعي الرسمي (قائمة البورصة، تُعرض بجانب فحصنا)",
  },
} as const satisfies Record<string, CopyEntry>;
