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
  shariah_egx33_badge: { en: "EGX33 Shariah", ar: "EGX33 شرعي" },
  shariah_egx33_badge_title: {
    en: "Member of the official EGX33 Shariah index (EGX's list, shown beside our own screening)",
    ar: "عضو في مؤشر EGX33 الشرعي الرسمي (قائمة البورصة، تُعرض بجانب فحصنا)",
  },
} as const satisfies Record<string, CopyEntry>;
