export const SHORT_COPY: Record<string, { en: string; ar: string }> = {
  nav_dashboard: { en: "Dashboard", ar: "لوحة التحكم" },
  nav_companies: { en: "Companies", ar: "الشركات" },
  hub_overview: { en: "Overview", ar: "نظرة عامة" },
  signals_title: { en: "Signals", ar: "الإشارات" },
  statements_title: { en: "Statements", ar: "القوائم المالية" },
  ratios_title: { en: "Ratios", ar: "النسب" },
  calculation: { en: "Calculation", ar: "حساب" },
  screening: { en: "Screening", ar: "التصفية" },
  radar: { en: "Radar", ar: "الرادار" },
};

export function t(key: string, lang: "en" | "ar"): string {
  const entry = SHORT_COPY[key];
  if (!entry) throw new Error(`missing copy key: ${key}`);
  return entry[lang];
}
