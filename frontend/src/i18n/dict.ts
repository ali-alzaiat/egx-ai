/**
 * Single source of truth for all UI copy, EN and AR.
 * Every key MUST carry both languages (asserted in i18n.test.ts).
 * Arabic is real translated copy — never transliteration; the app renders
 * it with an Arabic font (Cairo) and RTL layout + `ar-EG` number formatting.
 */

export type Lang = "en" | "ar";

export const SHORT_COPY = {
  // ---- Layout ----
  nav_dashboard: { en: "Dashboard", ar: "لوحة التحكم" },
  nav_recommendations: { en: "Recommendations", ar: "الترشيحات" },
  nav_companies: { en: "Companies", ar: "الشركات" },
  nav_rankings: { en: "Market Rankings", ar: "ترتيب السوق" },
  nav_screening: { en: "Screening", ar: "التصفية الشرعية" },
  nav_watchlists: { en: "Watchlists", ar: "قوائم المتابعة" },
  nav_alerts: { en: "Alerts", ar: "التنبيهات" },
  nav_events: { en: "Events", ar: "الأحداث" },
  lang_toggle_aria: { en: "Switch language", ar: "تغيير اللغة" },
  sidebar_aria: { en: "Main navigation", ar: "التنقل الرئيسي" },

  // ---- Company tabs ----
  tab_overview: { en: "Overview", ar: "نظرة عامة" },
  tab_signals: { en: "Signals", ar: "الإشارات" },
  tab_financials: { en: "Financial Data", ar: "البيانات المالية" },
  tab_statements: { en: "Statements", ar: "القوائم المالية" },
  tab_ratios: { en: "Ratios", ar: "النسب" },
  tab_metrics: { en: "Metrics", ar: "المؤشرات" },
  tab_technical: { en: "Technical", ar: "التحليل الفني" },
  tab_valuation: { en: "Valuation", ar: "التقييم" },
  tab_score: { en: "Score", ar: "الدرجة" },
  tab_screening: { en: "Shariah Screening", ar: "التصفية الشرعية" },
  tab_peers: { en: "Peers", ar: "الشركات المماثلة" },
  tab_thesis: { en: "Thesis", ar: "فرضية الاستثمار" },
  tab_disclosures: { en: "Disclosures", ar: "الإفصاحات" },
  company_sections_aria: { en: "Company sections", ar: "أقسام الشركة" },

  // ---- Shared ----
  calculation: { en: "Calculation", ar: "حساب" },
  loading: { en: "Loading…", ar: "جارٍ التحميل…" },
  load_error: { en: "Failed to load.", ar: "تعذر التحميل." },
  back: { en: "Back", ar: "رجوع" },
  available: { en: "Available", ar: "متوفر" },
  insufficient_data: { en: "Insufficient data", ar: "بيانات غير كافية" },
  no_value: { en: "—", ar: "—" },
  egp: { en: "EGP", ar: "ج.م" },

  // ---- Period types ----
  period_ANNUAL: { en: "Annual", ar: "سنوي" },
  period_SEMI_ANNUAL: { en: "Semi-annual", ar: "نصف سنوي" },
  period_INTERIM: { en: "Interim", ar: "مرحلي" },
  period_Q1: { en: "Q1", ar: "الربع الأول" },
  period_Q2: { en: "Q2", ar: "الربع الثاني" },
  period_Q3: { en: "Q3", ar: "الربع الثالث" },
  period_Q4: { en: "Q4", ar: "الربع الرابع" },

  // ---- Statements page ----
  statements_title: { en: "Statements", ar: "القوائم المالية" },
  statements_empty: {
    en: "No published statements yet. Statements appear after filings are fetched and approved by ops review.",
    ar: "لا توجد قوائم مالية منشورة بعد. تظهر القوائم بعد جلب الإفصاحات واعتمادها من مراجعة العمليات.",
  },
  section_income: { en: "Income statement", ar: "قائمة الدخل" },
  section_balance: { en: "Balance sheet", ar: "قائمة المركز المالي" },
  section_cash_flow: { en: "Cash flows", ar: "التدفقات النقدية" },
  col_line: { en: "Line", ar: "البيان" },
  col_value: { en: "Value", ar: "القيمة" },
  published_on: { en: "Published", ar: "تاريخ النشر" },
  reported_as: { en: "as reported", ar: "كما ورد في الإفصاح" },

  // ---- Ratios page ----
  ratios_title: { en: "Ratios", ar: "النسب" },
  col_ratio: { en: "Ratio", ar: "النسبة" },
  col_status: { en: "Status", ar: "الحالة" },
  ratio_gross_margin: { en: "Gross margin", ar: "هامش الربح الإجمالي" },
  ratio_operating_margin: { en: "Operating margin", ar: "هامش التشغيل" },
  ratio_net_margin: { en: "Net margin", ar: "هامش صافي الربح" },
  ratio_roe: { en: "Return on equity", ar: "العائد على حقوق الملكية" },
  ratio_roa: { en: "Return on assets", ar: "العائد على الأصول" },
  ratio_leverage: { en: "Leverage (debt/equity)", ar: "الرافعة المالية (دين/حقوق)" },
  ratio_current_ratio: { en: "Current ratio", ar: "نسبة التداول" },
  ratio_eps: { en: "Earnings per share", ar: "ربحية السهم" },
  ratio_revenue_growth_yoy: { en: "Revenue growth YoY", ar: "نمو الإيرادات سنويًا" },
  ratio_net_income_growth_yoy: { en: "Net income growth YoY", ar: "نمو صافي الربح سنويًا" },
  ratios_empty: {
    en: "No ratios yet. Ratios compute once approved statement lines exist for at least one period.",
    ar: "لا توجد نسب بعد. تُحتسب النسب عند وجود بنود قوائم مالية معتمدة لفترة واحدة على الأقل.",
  },

  // ---- Signals (stance) page ----
  signals_title: { en: "Signals", ar: "الإشارات" },
  signals_stance: { en: "Stance", ar: "الموقف" },
  stance_buy: { en: "Buy", ar: "شراء" },
  stance_hold: { en: "Hold", ar: "انتظار" },
  stance_reduce: { en: "Reduce", ar: "تخفيض" },
  signals_confidence: { en: "Confidence", ar: "الثقة" },
  signals_why: { en: "Why", ar: "الأسباب" },
  signals_limitations: { en: "Limitations", ar: "الحدود" },
  signals_targets: { en: "Price targets", ar: "الأسعار المستهدفة" },
  target_bull: { en: "Bull", ar: "المتفائل" },
  target_base: { en: "Base", ar: "الأساسي" },
  target_bear: { en: "Bear", ar: "المتحفظ" },
  signals_stop_level: { en: "Risk reference level", ar: "مرجع المخاطر" },
  signals_freshness: { en: "Statement freshness", ar: "حداثة القوائم المالية" },
  not_investment_advice: {
    en: "Research calculation — not investment advice",
    ar: "حساب بحثي — ليس توصية استثمارية",
  },

  // ---- Radar ----
  signals_radar_title: { en: "Stance radar", ar: "رادار المواقف" },
  signals_radar_count: { en: "companies", ar: "شركة" },

  // ---- Recommendations radar + stance v2 ----
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
    ar: "مرجعا الصعود والهبوط نطاق تذبذب (٢× / ١٫٥× ATR) حول آخر إغلاق — وليسا توقعاً.",
  },
  low_liquidity: { en: "Low liquidity", ar: "سيولة منخفضة" },
  low_liquidity_title: {
    en: "Average value traded below EGP 500K over 20 sessions",
    ar: "متوسط قيمة التداول أقل من ٥٠٠ ألف جنيه خلال ٢٠ جلسة",
  },
  signals_score: { en: "Composite score", ar: "الدرجة المركبة" },
  signals_coverage: { en: "Engine coverage", ar: "تغطية المحركات" },
  signals_levels: { en: "Reference levels", ar: "المستويات المرجعية" },
  level_entry: { en: "Last close", ar: "آخر إغلاق" },
  level_upside: { en: "Upside reference", ar: "مرجع الصعود" },
  level_downside: { en: "Downside reference", ar: "مرجع الهبوط" },
  signals_liquidity: {
    en: "Avg value traded (20 sessions, EGP)",
    ar: "متوسط قيمة التداول (٢٠ جلسة، جنيه)",
  },
  signals_shariah: { en: "Shariah", ar: "الشرعية" },
  shariah_our_verdict: { en: "Our screening", ar: "فحصنا" },
  shariah_egx33: { en: "EGX33 Shariah index", ar: "مؤشر EGX33 الشرعي" },
  shariah_member: { en: "Member", ar: "عضو" },
  shariah_not_member: { en: "Not a member", ar: "ليس عضواً" },
  shariah_unknown: { en: "Unknown", ar: "غير معروف" },
  shariah_not_screened: { en: "Not screened yet", ar: "لم يُفحص بعد" },
  shariah_compliant: { en: "Compliant", ar: "متوافق" },
  shariah_non_compliant: { en: "Non-compliant", ar: "غير متوافق" },
  shariah_egx33_badge: { en: "EGX33 Shariah", ar: "EGX33 شرعي" },
  shariah_egx33_badge_title: {
    en: "Member of the official EGX33 Shariah index (EGX's list, shown beside our own screening)",
    ar: "عضو في مؤشر EGX33 الشرعي الرسمي (قائمة البورصة، تُعرض بجانب فحصنا)",
  },
} as const;

export type CopyKey = keyof typeof SHORT_COPY;

export function t(key: CopyKey, lang: "en" | "ar"): string {
  return SHORT_COPY[key][lang];
}
