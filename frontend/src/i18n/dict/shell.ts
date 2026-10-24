import type { CopyEntry } from "./types";

/** App shell, navigation, shared states and the shared ui/ components. */
export const SHELL_COPY = {
  // ---- Navigation ----
  nav_dashboard: { en: "Dashboard", ar: "لوحة المعلومات" },
  nav_recommendations: { en: "Recommendations", ar: "الترشيحات" },
  nav_intake: { en: "Filings intake", ar: "إدخال القوائم الرسمية" },
  nav_companies: { en: "Companies", ar: "الشركات" },
  nav_rankings: { en: "Momentum rankings", ar: "ترتيب الزخم" },
  nav_screening: { en: "Shariah screening", ar: "التصفية الشرعية" },
  nav_watchlists: { en: "Watchlists", ar: "قوائم المتابعة" },
  nav_alerts: { en: "Alerts", ar: "التنبيهات" },
  nav_events: { en: "Events", ar: "سجل الأحداث" },
  nav_admin: { en: "Admin", ar: "الإدارة" },
  nav_group_markets: { en: "Markets", ar: "السوق" },
  nav_group_research: { en: "Research", ar: "البحث" },
  nav_group_tracking: { en: "Tracking", ar: "المتابعة" },
  lang_toggle_aria: { en: "Language", ar: "اللغة" },
  sidebar_aria: { en: "Main navigation", ar: "التنقل الرئيسي" },
  skip_to_content: { en: "Skip to content", ar: "تخطَّ إلى المحتوى" },
  menu_open: { en: "Menu", ar: "القائمة" },
  menu_close: { en: "Close", ar: "إغلاق" },
  theme_aria: { en: "Theme", ar: "المظهر" },
  theme_system: { en: "System", ar: "النظام" },
  theme_light: { en: "Light", ar: "فاتح" },
  theme_dark: { en: "Dark", ar: "داكن" },
  title_suffix: { en: "EGX AI", ar: "EGX AI" },

  // ---- Search / picker ----
  search_placeholder: { en: "Search ticker or company", ar: "ابحث بالرمز أو اسم الشركة" },
  search_open: { en: "Search", ar: "بحث" },
  search_no_results: { en: "No company matches \"{q}\"", ar: "لا توجد شركة تطابق \"{q}\"" },
  search_error: { en: "Search is unavailable.", ar: "البحث غير متاح." },
  search_retry: { en: "Retry", ar: "إعادة المحاولة" },
  search_searching: { en: "Searching…", ar: "جارٍ البحث…" },
  picker_clear: { en: "Clear selection", ar: "مسح الاختيار" },

  // ---- Shared states ----
  calculation: { en: "Calculation", ar: "حساب" },
  loading: { en: "Loading…", ar: "جارٍ التحميل…" },
  loading_thing: { en: "Loading {thing}…", ar: "جارٍ تحميل {thing}…" },
  load_error: { en: "Failed to load.", ar: "تعذر التحميل." },
  load_error_thing: { en: "Couldn't load {thing}.", ar: "تعذّر تحميل {thing}." },
  retry: { en: "Retry", ar: "إعادة المحاولة" },
  no_match_things: { en: "No {things} match these filters.", ar: "لا توجد {things} تطابق هذه الفلاتر." },
  clear_filters: { en: "Clear filters", ar: "مسح الفلاتر" },
  back: { en: "Back", ar: "رجوع" },
  available: { en: "Available", ar: "متوفر" },
  insufficient_data: { en: "Insufficient data", ar: "بيانات غير كافية" },
  no_value: { en: "—", ar: "—" },
  egp: { en: "EGP", ar: "ج.م" },
  missing_line: { en: "Missing line: {line}", ar: "بند غير متوفر: {line}" },
  missing_default: { en: "Not available", ar: "غير متوفر" },
  not_enough_history: { en: "Not enough price history", ar: "سجل الأسعار غير كافٍ" },

  // ---- Table ----
  table_density_compact: { en: "Compact rows", ar: "صفوف مضغوطة" },
  table_density_comfortable: { en: "Comfortable rows", ar: "صفوف مريحة" },
  table_sort_by: { en: "Sort by {col}", ar: "ترتيب حسب {col}" },

  // ---- Not found ----
  not_found_title: { en: "Page not found", ar: "الصفحة غير موجودة" },
  not_found_body: {
    en: "This address does not match any page. Use the menu to continue.",
    ar: "هذا العنوان لا يطابق أي صفحة. استخدم القائمة للمتابعة.",
  },
  not_found_home: { en: "Go to the dashboard", ar: "الانتقال إلى لوحة المعلومات" },
} as const satisfies Record<string, CopyEntry>;
