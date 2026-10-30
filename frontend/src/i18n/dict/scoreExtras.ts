import type { CopyEntry } from "./types";

/**
 * R47 Q1-Q3: the Piotroski F-Score and dividend-safety cards on the Score tab,
 * and the "Fundamentals" / "Prices as of" freshness lines.
 * Prefix: rx_.
 */
export const SCORE_EXTRAS_COPY = {
  // ---- Freshness lines (Q3) ----
  rx_prices_as_of: { en: "Prices as of {date}", ar: "الأسعار حتى {date}" },
  rx_fund_vendor_prov: {
    en: "Fundamentals: FY{year} (vendor, provisional)",
    ar: "البيانات المالية: السنة المالية {year} (مزوّد بيانات، مؤقتة)",
  },
  rx_fund_vendor: {
    en: "Fundamentals: FY{year} (vendor)",
    ar: "البيانات المالية: السنة المالية {year} (مزوّد بيانات)",
  },
  rx_fund_filing: {
    en: "Fundamentals: FY{year} (official filing)",
    ar: "البيانات المالية: السنة المالية {year} (قوائم رسمية)",
  },
  rx_fund_plain: { en: "Fundamentals: FY{year}", ar: "البيانات المالية: السنة المالية {year}" },
  rx_fund_none: { en: "Fundamentals: not available", ar: "البيانات المالية: غير متوفرة" },

  // ---- Shared ----
  rx_pass: { en: "Pass", ar: "ناجح" },
  rx_fail: { en: "Fail", ar: "غير ناجح" },
  rx_insufficient: { en: "Insufficient data", ar: "بيانات غير كافية" },
  rx_not_meaningful: { en: "Not meaningful", ar: "غير ذي دلالة" },
  rx_times: { en: "{n}x", ar: "{n}×" },
  rx_extras_title: { en: "Shown beside the score", ar: "تُعرض بجوار الدرجة" },
  rx_extras_lead: {
    en: "These two cards are computed from the same statement lines but are not part of the score and do not change it.",
    ar: "تُحسب هاتان البطاقتان من بنود القوائم نفسها، لكنهما ليستا جزءًا من الدرجة ولا تغيّرانها.",
  },
  rx_method_line: { en: "Method {version}", ar: "المنهجية {version}" },

  // ---- Piotroski F-Score (Q1) ----
  rx_pio_title: { en: "Piotroski F-Score", ar: "مؤشر بيوتروسكي (F-Score)" },
  rx_pio_thing: { en: "Piotroski F-Score", ar: "مؤشر بيوتروسكي" },
  rx_pio_lead: {
    en: "Nine yes/no checks on the latest fiscal year against the one before it.",
    ar: "تسعة فحوص بنعم أو لا على أحدث سنة مالية مقارنة بالتي قبلها.",
  },
  rx_pio_hero: { en: "{n} of 9 pass", ar: "{n} من 9 فحوص ناجحة" },
  rx_pio_hero_partial: { en: "{n} of {run} pass", ar: "{n} من {run} فحوص ناجحة" },
  rx_pio_ran: {
    en: "Only {run} of {total} checks had the data to run; the rest are not counted as passes or fails.",
    ar: "{run} فقط من {total} فحوص توفرت لها البيانات؛ والباقي لا يُحسب نجاحًا ولا إخفاقًا.",
  },
  rx_pio_periods: { en: "FY{year} compared with FY{prior}", ar: "السنة المالية {year} مقارنة بـ {prior}" },
  rx_pio_bank: {
    en: "Not run: banks are not scored here. Working capital, gross margin and debt-to-assets ratios do not describe a bank.",
    ar: "لم يُجرَ: لا تُقيَّم البنوك هنا، فرأس المال العامل وهامش الربح الإجمالي ونسب الدين إلى الأصول لا تصف البنك.",
  },
  rx_pio_none: {
    en: "No check could run: the statement lines they need are missing.",
    ar: "تعذّر إجراء أي فحص: بنود القوائم اللازمة غير متوفرة.",
  },
  rx_pio_col_check: { en: "Check", ar: "الفحص" },
  rx_pio_col_result: { en: "Result", ar: "النتيجة" },
  rx_pio_col_inputs: { en: "Inputs", ar: "المدخلات" },
  rx_pio_shares_rose: {
    en: "The share count rose; a bonus issue or split is not told apart from new equity.",
    ar: "ارتفع عدد الأسهم؛ ولا يُفرَّق بين أسهم المنحة أو التجزئة وبين الإصدار الجديد.",
  },
  rx_pio_no_statements: {
    en: "No approved annual statements for FY{year}.",
    ar: "لا توجد قوائم سنوية معتمدة للسنة المالية {year}.",
  },
  rx_pio_not_positive: {
    en: "{line} is not positive (FY{year}), so the ratio is undefined.",
    ar: "{line} غير موجب (السنة المالية {year})، فالنسبة غير معرّفة.",
  },
  rx_pio_unit_note: {
    en: "Ratios use year-end total assets of the same year. Details are under Technical details.",
    ar: "تستخدم النسب إجمالي أصول نهاية السنة نفسها. التفاصيل تحت «تفاصيل فنية».",
  },
  rx_grp_profitability: { en: "Profitability", ar: "الربحية" },
  rx_grp_leverage_liquidity: { en: "Leverage and liquidity", ar: "المديونية والسيولة" },
  rx_grp_operating_efficiency: { en: "Operating efficiency", ar: "الكفاءة التشغيلية" },
  rx_chk_roa_positive: { en: "Return on assets is positive", ar: "العائد على الأصول موجب" },
  rx_chk_cfo_positive: { en: "Operating cash flow is positive", ar: "التدفق النقدي التشغيلي موجب" },
  rx_chk_roa_improving: {
    en: "Return on assets is higher than last year",
    ar: "العائد على الأصول أعلى من العام الماضي",
  },
  rx_chk_accruals_cash_backed: {
    en: "Operating cash flow exceeds net income",
    ar: "التدفق النقدي التشغيلي يفوق صافي الدخل",
  },
  rx_chk_leverage_falling: {
    en: "Interest-bearing debt / total assets is lower than last year",
    ar: "الدين ذو الفائدة / إجمالي الأصول أقل من العام الماضي",
  },
  rx_chk_current_ratio_improving: {
    en: "Current ratio is higher than last year",
    ar: "نسبة التداول أعلى من العام الماضي",
  },
  rx_chk_no_new_shares: { en: "No new shares issued", ar: "لم تُصدر أسهم جديدة" },
  rx_chk_gross_margin_improving: {
    en: "Gross margin is higher than last year",
    ar: "هامش الربح الإجمالي أعلى من العام الماضي",
  },
  rx_chk_asset_turnover_improving: {
    en: "Asset turnover is higher than last year",
    ar: "معدل دوران الأصول أعلى من العام الماضي",
  },
  rx_in_line_fy: { en: "{line} FY{year}", ar: "{line} للسنة المالية {year}" },
  rx_in_ratio: { en: "Ratio", ar: "النسبة" },
  rx_in_ratio_now: { en: "Ratio, this year", ar: "النسبة هذا العام" },
  rx_in_ratio_prior: { en: "Ratio, last year", ar: "النسبة العام الماضي" },

  // ---- Dividend safety (Q2) ----
  rx_div_title: { en: "Dividend safety", ar: "أمان التوزيعات" },
  rx_div_year: { en: "FY{year}", ar: "السنة المالية {year}" },
  rx_div_label: { en: "from dividends paid (derived)", ar: "من التوزيعات المدفوعة (مشتقة)" },
  rx_div_lead: {
    en: "Cash dividends paid in the year, not the dividend declared for it, so timing and bonus-share years can make a single year noisy.",
    ar: "التوزيعات النقدية المدفوعة خلال السنة وليست المعلنة عنها، لذا قد تتأثر سنة بعينها بالتوقيت وأسهم المنحة.",
  },
  rx_div_col_payout: { en: "Payout ratio", ar: "نسبة التوزيع" },
  rx_div_col_cover: { en: "Cash coverage", ar: "تغطية نقدية" },
  rx_div_no_dividend: { en: "No dividend paid", ar: "لا توزيعات مدفوعة" },
  rx_div_nm_nodiv: { en: "no dividends paid, nothing to cover", ar: "لا توزيعات مدفوعة، فلا شيء لتغطيته" },
  rx_div_nm_ni: {
    en: "net income to common holders is not positive",
    ar: "صافي الدخل لحملة الأسهم العادية غير موجب",
  },
  rx_div_nm_bank: {
    en: "a bank's operating cash flow includes deposit and loan flows",
    ar: "التدفق النقدي التشغيلي للبنك يشمل حركة الودائع والقروض",
  },
  rx_div_not_no_div: { en: "not read as no dividend", ar: "ولا يُعدّ ذلك غياب توزيعات" },
  rx_div_empty: {
    en: "Dividend safety is not available: the statement lines it needs are missing.",
    ar: "أمان التوزيعات غير متوفر: بنود القوائم اللازمة غير متوفرة.",
  },
  rx_div_formulas: {
    en: "Payout ratio = dividends paid / net income to common holders. Cash coverage = (operating cash flow − capex) / dividends paid.",
    ar: "نسبة التوزيع = التوزيعات المدفوعة / صافي الدخل لحملة الأسهم العادية. التغطية النقدية = (التدفق النقدي التشغيلي − النفقات الرأسمالية) / التوزيعات المدفوعة.",
  },
} as const satisfies Record<string, CopyEntry>;
