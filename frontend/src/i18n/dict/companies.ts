import type { CopyEntry } from "./types";

/** Companies list page and the pagination it uses. */
export const COMPANIES_COPY = {
  comp_title: { en: "Companies", ar: "الشركات" },
  comp_subtitle: {
    en: "All {n} EGX-listed companies we track.",
    ar: "جميع الشركات المدرجة التي نتابعها ({n}).",
  },
  comp_see_also: {
    en: "For ranked views see {rankings} and {reco}.",
    ar: "للاطلاع على الترتيب انظر {rankings} و{reco}.",
  },
  comp_search_label: { en: "Search ticker or name", ar: "ابحث بالرمز أو الاسم" },
  comp_thing: { en: "companies", ar: "الشركات" },
  comp_things: { en: "companies", ar: "شركات" },
  comp_meta_range: {
    en: "Showing {from}–{to} of {total}",
    ar: "عرض {from}–{to} من {total}",
  },
  comp_meta_matches: { en: "{count} for \"{q}\"", ar: "{count} لـ \"{q}\"" },
  comp_empty: {
    en: "No companies yet. The company list loads with the first market sync.",
    ar: "لا توجد شركات بعد. تُحمَّل قائمة الشركات مع أول مزامنة للسوق.",
  },
  comp_no_match: { en: "No company matches \"{q}\".", ar: "لا توجد شركة تطابق \"{q}\"." },
  comp_col_close: { en: "Last close (EGP)", ar: "آخر إغلاق (ج.م)" },
  comp_col_asof: { en: "As of", ar: "بتاريخ" },
  comp_stale_title: {
    en: "Older than the latest market close",
    ar: "أقدم من آخر إغلاق للسوق",
  },
  comp_col_stance: { en: "Stance", ar: "الموقف" },
  comp_col_momentum: { en: "Momentum score (0–100)", ar: "درجة الزخم (0–100)" },
  comp_col_tier: { en: "Momentum tier", ar: "فئة الزخم" },
  comp_col_margin: { en: "Gross margin, latest FY", ar: "هامش الربح الإجمالي (آخر سنة)" },
  comp_no_momentum: {
    en: "No momentum score: not enough price history",
    ar: "لا توجد درجة زخم: سجل الأسعار غير كافٍ",
  },
  comp_no_margin: {
    en: "Gross margin is not in our data yet",
    ar: "هامش الربح الإجمالي غير متوفر في بياناتنا بعد",
  },
  comp_line_revenue: { en: "Revenue", ar: "الإيرادات" },
  comp_line_cost_of_revenue: { en: "Cost of revenue", ar: "تكلفة الإيرادات" },
  comp_line_gross_profit: { en: "Gross profit", ar: "مجمل الربح" },
  comp_footnote: {
    en: "Momentum uses prices only. Stances are research calculations, not advice.",
    ar: "يعتمد الزخم على الأسعار فقط. المواقف حسابات بحثية وليست نصيحة.",
  },

  page_prev: { en: "Previous", ar: "السابق" },
  page_next: { en: "Next", ar: "التالي" },
  page_info: {
    en: "Page {page} of {pages} ({total} companies)",
    ar: "صفحة {page} من {pages} ({total} شركة)",
  },
  page_aria: { en: "Pagination", ar: "التنقل بين الصفحات" },
} as const satisfies Record<string, CopyEntry>;
