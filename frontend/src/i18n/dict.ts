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
  nav_companies: { en: "Companies", ar: "الشركات" },
  nav_rankings: { en: "Market Rankings", ar: "ترتيب السوق" },
  nav_screening: { en: "Screening", ar: "التصفية الشرعية" },
  nav_pricing: { en: "Pricing", ar: "الأسعار" },
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

  // ---- Pricing page ----
  pricing_title: { en: "Pricing", ar: "الأسعار" },
  pricing_per_month: { en: "per month", ar: "شهريًا" },
  plan_free_name: { en: "Free", ar: "مجاني" },
  plan_pro_name: { en: "Pro", ar: "احترافي" },
  plan_max_name: { en: "Max", ar: "أقصى" },
  plan_free_desc: {
    en: "3 stance lookups per day · 1 radar scan per day",
    ar: "3 استعلامات موقف يوميًا · مسحة رادار واحدة يوميًا",
  },
  plan_pro_desc: {
    en: "Unlimited stance lookups and radar scans · full company hub",
    ar: "استعلامات موقف ورادار بلا حدود · لوحة الشركة الكاملة",
  },
  plan_max_desc: {
    en: "All Pro capabilities, on the highest data tier",
    ar: "كل قدرات الاحترافي، أعلى مستوى بيانات",
  },
  billing_current_plan: { en: "Current plan", ar: "خطتك الحالية" },
} as const;

export type CopyKey = keyof typeof SHORT_COPY;

export function t(key: CopyKey, lang: "en" | "ar"): string {
  return SHORT_COPY[key][lang];
}
