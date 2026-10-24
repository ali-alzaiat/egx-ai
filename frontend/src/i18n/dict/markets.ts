import type { CopyEntry } from "./types";

/** Markets: recommendations radar and rankings. */
export const MARKETS_COPY = {
  signals_radar_title: { en: "Stance radar", ar: "رادار المواقف" },
  signals_radar_count: { en: "companies", ar: "شركة" },
  reco_title: { en: "Recommendations radar", ar: "رادار الترشيحات" },
  reco_subtitle: {
    en: "Most-traded EGX stocks, ranked by value traded.",
    ar: "أكثر أسهم البورصة المصرية تداولاً، مرتبة حسب قيمة التداول.",
  },
  reco_shariah_only: {
    en: "EGX33 Shariah members only",
    ar: "أعضاء مؤشر EGX33 الشرعي فقط",
  },
  reco_filter_label: { en: "Stance", ar: "الموقف" },
  reco_filter_all: { en: "All", ar: "الكل" },
  reco_col_stock: { en: "Stock", ar: "السهم" },
  reco_col_price: { en: "Last close", ar: "آخر إغلاق" },
  reco_col_shariah: { en: "Shariah", ar: "الشرعية" },
  reco_empty: { en: "No stocks match these filters.", ar: "لا توجد أسهم مطابقة لهذه الفلاتر." },
  reco_levels_note: {
    en: "Upside / downside are a volatility band (2× / 1.5× ATR) around the last close — not a forecast.",
    ar: "مرجعا الصعود والهبوط نطاق تذبذب (2× / 1.5× ATR) حول آخر إغلاق — وليسا توقعاً.",
  },
  low_liquidity: { en: "Low liquidity", ar: "سيولة منخفضة" },
  low_liquidity_title: {
    en: "Average value traded below EGP 500K over 20 sessions",
    ar: "متوسط قيمة التداول أقل من 500 ألف جنيه خلال 20 جلسة",
  },
  signals_score: { en: "Composite score", ar: "الدرجة المركبة" },
  signals_coverage: { en: "Engine coverage", ar: "تغطية المحركات" },
  signals_levels: { en: "Reference levels", ar: "المستويات المرجعية" },
  level_entry: { en: "Last close", ar: "آخر إغلاق" },
  level_upside: { en: "Upside reference", ar: "مرجع الصعود" },
  level_downside: { en: "Downside reference", ar: "مرجع الهبوط" },
  signals_liquidity: {
    en: "Avg value traded (20 sessions, EGP)",
    ar: "متوسط قيمة التداول (20 جلسة، جنيه)",
  },
} as const satisfies Record<string, CopyEntry>;
