import type { CopyEntry } from "./types";

/** AI assistant (R49): launcher, side panel, /assistant page, Explain buttons and Admin > AI settings. */
export const ASSISTANT_COPY = {
  // ---- Navigation ----
  nav_assistant: { en: "Assistant", ar: "المساعد" },
  admin_ai: { en: "AI settings", ar: "إعدادات الذكاء الاصطناعي" },

  // ---- Launcher + panel ----
  assistant_open: { en: "Ask the assistant", ar: "اسأل المساعد" },
  assistant_panel_aria: { en: "AI assistant", ar: "مساعد الذكاء الاصطناعي" },
  assistant_title: { en: "Assistant", ar: "المساعد" },
  assistant_close: { en: "Close assistant", ar: "إغلاق المساعد" },
  assistant_scope: { en: "Answering about {ticker}", ar: "يجيب عن شركة {ticker}" },
  assistant_scope_none: { en: "General questions across all companies", ar: "أسئلة عامة عن كل الشركات" },
  assistant_new_chat: { en: "New chat", ar: "محادثة جديدة" },
  assistant_open_page: { en: "Open full page", ar: "فتح الصفحة الكاملة" },

  // ---- Chat view ----
  assistant_model: { en: "Model", ar: "النموذج" },
  assistant_model_none: { en: "No model available", ar: "لا يوجد نموذج متاح" },
  assistant_no_models: {
    en: "No AI provider has a key yet, so the assistant can't answer.",
    ar: "لا يوجد مفتاح لأي مزوّد ذكاء اصطناعي بعد، لذلك لا يستطيع المساعد الإجابة.",
  },
  assistant_set_key: { en: "Add a key in AI settings", ar: "أضف مفتاحاً في إعدادات الذكاء الاصطناعي" },
  assistant_models_error: { en: "Couldn't load the model list.", ar: "تعذّر تحميل قائمة النماذج." },
  assistant_input_label: { en: "Your question", ar: "سؤالك" },
  assistant_input_placeholder_company: { en: "Ask about {ticker}…", ar: "اسأل عن {ticker}…" },
  assistant_input_placeholder: { en: "Ask about EGX companies…", ar: "اسأل عن شركات البورصة المصرية…" },
  assistant_send: { en: "Send", ar: "إرسال" },
  assistant_stop: { en: "Stop", ar: "إيقاف" },
  assistant_stopped: { en: "Stopped.", ar: "تم الإيقاف." },
  assistant_you: { en: "You", ar: "أنت" },
  assistant_assistant: { en: "Assistant", ar: "المساعد" },
  assistant_empty_title: { en: "Ask about the data in this app", ar: "اسأل عن البيانات الموجودة في التطبيق" },
  assistant_empty_company: {
    en: "Ask about {ticker}: its score, valuation, stance, Shariah status, price or financials. Every figure in an answer is checked against our data.",
    ar: "اسأل عن {ticker}: درجتها وتقييمها وموقفها وحالتها الشرعية وسعرها وقوائمها المالية. كل رقم في الإجابة يُراجَع على بياناتنا.",
  },
  assistant_empty_general: {
    en: "Ask about any company, or search across companies, for example by sector, Shariah status or a chart pattern. Every figure in an answer is checked against our data.",
    ar: "اسأل عن أي شركة، أو ابحث بين الشركات، مثلاً حسب القطاع أو الحالة الشرعية أو نمط الرسم البياني. كل رقم في الإجابة يُراجَع على بياناتنا.",
  },
  assistant_disclaimer: {
    en: "Not investment advice. The assistant only explains figures from our data.",
    ar: "ليست نصيحة استثمارية. المساعد يشرح فقط أرقاماً من بياناتنا.",
  },

  // ---- Progress ----
  assistant_progress_thinking: { en: "Thinking…", ar: "جارٍ التفكير…" },
  assistant_progress_tool: { en: "Looking up {tool}…", ar: "جارٍ الاطلاع على {tool}…" },
  assistant_progress_tool_plain: { en: "Looking up our data…", ar: "جارٍ الاطلاع على بياناتنا…" },
  assistant_progress_verifying: { en: "Checking every figure against our data…", ar: "جارٍ مطابقة كل رقم مع بياناتنا…" },
  assistant_progress_retrying: { en: "A figure didn't match, trying again…", ar: "لم يطابق أحد الأرقام، جارٍ إعادة المحاولة…" },

  // ---- Answers ----
  assistant_checked: { en: "Figures checked against our data ({n})", ar: "أرقام روجعت على بياناتنا ({n})" },
  assistant_checked_none: { en: "No figures to check", ar: "لا توجد أرقام للمراجعة" },
  assistant_sources: { en: "Sources", ar: "المصادر" },
  assistant_unverified_title: { en: "Couldn't verify the figures", ar: "تعذّر التحقق من الأرقام" },
  assistant_unverified_body: {
    en: "The answer was held back because some figures didn't match our data. Try asking again, or check the numbers on the company pages.",
    ar: "تم حجب الإجابة لأن بعض الأرقام لم تطابق بياناتنا. حاول السؤال مرة أخرى، أو راجع الأرقام في صفحات الشركة.",
  },
  assistant_unverified_list: { en: "Figures that didn't match:", ar: "أرقام لم تتطابق:" },
  assistant_error_details: { en: "Details", ar: "التفاصيل" },
  assistant_open_settings: { en: "Open AI settings", ar: "افتح إعدادات الذكاء الاصطناعي" },

  // ---- Tool names (sources and progress) ----
  assistant_tool_company_overview: { en: "Company overview", ar: "نظرة عامة على الشركة" },
  assistant_tool_investment_score: { en: "Investment score", ar: "درجة الاستثمار" },
  assistant_tool_valuation: { en: "Valuation", ar: "التقييم" },
  assistant_tool_stance: { en: "Stance", ar: "الموقف" },
  assistant_tool_shariah_status: { en: "Shariah status", ar: "الحالة الشرعية" },
  assistant_tool_price_summary: { en: "Price summary", ar: "ملخص السعر" },
  assistant_tool_chart_patterns: { en: "Chart patterns", ar: "أنماط الرسم البياني" },
  assistant_tool_financial_metrics: { en: "Financial metrics", ar: "المؤشرات المالية" },
  assistant_tool_search_companies: { en: "Company search", ar: "البحث عن الشركات" },
  assistant_tool_screen_companies: { en: "Company screen", ar: "فرز الشركات" },

  // ---- Errors ----
  assistant_err_no_key: {
    en: "No API key is set for this model's provider. Add one in AI settings, then ask again.",
    ar: "لا يوجد مفتاح API لمزوّد هذا النموذج. أضف مفتاحاً في إعدادات الذكاء الاصطناعي ثم اسأل مرة أخرى.",
  },
  assistant_err_cap: {
    en: "The monthly spending cap is reached, so the assistant stopped calling the model. Raise or remove the cap in AI settings.",
    ar: "تم بلوغ الحد الشهري للإنفاق، لذلك توقف المساعد عن استدعاء النموذج. ارفع الحد أو أزله من إعدادات الذكاء الاصطناعي.",
  },
  assistant_err_provider: {
    en: "The model provider returned an error. Try again, or pick another model.",
    ar: "أعاد مزوّد النموذج خطأً. حاول مرة أخرى أو اختر نموذجاً آخر.",
  },
  assistant_err_insufficient: {
    en: "We don't have enough data to answer that.",
    ar: "لا تتوفر لدينا بيانات كافية للإجابة عن ذلك.",
  },
  assistant_err_model: {
    en: "That model isn't available. Pick another model, or check AI settings.",
    ar: "هذا النموذج غير متاح. اختر نموذجاً آخر أو راجع إعدادات الذكاء الاصطناعي.",
  },
  assistant_err_not_found: {
    en: "That company or conversation wasn't found.",
    ar: "لم يتم العثور على هذه الشركة أو المحادثة.",
  },
  assistant_err_rejected: {
    en: "The request was rejected. Shorten the question and try again.",
    ar: "تم رفض الطلب. اختصر السؤال وحاول مرة أخرى.",
  },
  assistant_err_auth: {
    en: "The server refused the request (not authorised).",
    ar: "رفض الخادم الطلب (غير مصرّح).",
  },
  assistant_err_server: {
    en: "The server had a problem. Try again in a moment.",
    ar: "حدثت مشكلة في الخادم. حاول مرة أخرى بعد قليل.",
  },
  assistant_err_network: {
    en: "Couldn't reach the server. Check your connection and try again.",
    ar: "تعذّر الوصول إلى الخادم. تحقق من اتصالك وحاول مرة أخرى.",
  },
  assistant_err_interrupted: {
    en: "The answer was cut off before it finished. Try again.",
    ar: "انقطعت الإجابة قبل أن تكتمل. حاول مرة أخرى.",
  },
  assistant_err_generic: { en: "Something went wrong. Try again.", ar: "حدث خطأ ما. حاول مرة أخرى." },

  // ---- Assistant page ----
  assistant_page_subtitle: {
    en: "Ask about any EGX company. Answers use only figures from our data and are checked before they are shown.",
    ar: "اسأل عن أي شركة في البورصة المصرية. تستخدم الإجابات أرقام بياناتنا فقط وتُراجَع قبل عرضها.",
  },
  assistant_conversations: { en: "Conversations", ar: "المحادثات" },
  assistant_conversations_count: { en: "Conversations ({n})", ar: "المحادثات ({n})" },
  assistant_conversations_empty: { en: "No saved conversations yet.", ar: "لا توجد محادثات محفوظة بعد." },
  assistant_conversations_thing: { en: "conversations", ar: "المحادثات" },
  assistant_conversation_loading: { en: "conversation", ar: "المحادثة" },
  assistant_delete: { en: "Delete", ar: "حذف" },
  assistant_delete_aria: { en: "Delete conversation: {title}", ar: "حذف المحادثة: {title}" },
  assistant_delete_confirm: { en: "Delete this conversation?", ar: "هل تريد حذف هذه المحادثة؟" },
  assistant_delete_failed: { en: "Couldn't delete the conversation.", ar: "تعذّر حذف المحادثة." },
  assistant_untitled: { en: "Untitled", ar: "بلا عنوان" },
  assistant_history_show: { en: "Show conversations", ar: "إظهار المحادثات" },
  assistant_history_hide: { en: "Hide conversations", ar: "إخفاء المحادثات" },

  // ---- Explain buttons ----
  assistant_explain: { en: "Explain this", ar: "اشرح هذا" },
  assistant_explain_aria: { en: "Explain this {card} with the assistant", ar: "اشرح {card} هذا باستخدام المساعد" },
  assistant_card_score: { en: "score", ar: "الدرجة" },
  assistant_card_valuation: { en: "valuation", ar: "التقييم" },
  assistant_card_stance: { en: "stance", ar: "الموقف" },
  assistant_card_shariah: { en: "Shariah status", ar: "الحالة الشرعية" },
  assistant_explain_prompt_score: { en: "Explain the investment score for {ticker}", ar: "اشرح درجة الاستثمار لشركة {ticker}" },
  assistant_explain_prompt_valuation: { en: "Explain the valuation for {ticker}", ar: "اشرح التقييم لشركة {ticker}" },
  assistant_explain_prompt_stance: { en: "Explain the stance for {ticker}", ar: "اشرح الموقف لشركة {ticker}" },
  assistant_explain_prompt_shariah: { en: "Explain the Shariah status for {ticker}", ar: "اشرح الحالة الشرعية لشركة {ticker}" },

  // ---- Admin > AI settings ----
  aiset_title: { en: "AI settings", ar: "إعدادات الذكاء الاصطناعي" },
  aiset_subtitle: {
    en: "Keys for the AI providers, the default model and a monthly spending cap. Keys are stored encrypted and are never shown again after saving.",
    ar: "مفاتيح مزوّدي الذكاء الاصطناعي والنموذج الافتراضي وحد إنفاق شهري. تُخزَّن المفاتيح مشفّرة ولا تظهر مرة أخرى بعد الحفظ.",
  },
  aiset_secrets_missing: {
    en: "Saving keys here is switched off because AI_SECRETS_KEY is not set in the server's .env file. Keys already in .env (ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY) still work.",
    ar: "حفظ المفاتيح من هنا معطّل لأن AI_SECRETS_KEY غير مضبوط في ملف .env على الخادم. المفاتيح الموجودة في .env (ANTHROPIC_API_KEY وOPENAI_API_KEY وGEMINI_API_KEY) تعمل كالمعتاد.",
  },
  aiset_providers: { en: "Providers", ar: "المزوّدون" },
  aiset_status_configured: { en: "Key set", ar: "المفتاح مضبوط" },
  aiset_status_missing: { en: "No key", ar: "لا يوجد مفتاح" },
  aiset_source_ui: { en: "Saved here", ar: "محفوظ من هنا" },
  aiset_source_env: { en: "From .env", ar: "من ملف .env" },
  aiset_source_label: { en: "Source", ar: "المصدر" },
  aiset_key_label: { en: "Key", ar: "المفتاح" },
  aiset_set_at: { en: "Set {date}", ar: "ضُبط في {date}" },
  aiset_key_input: { en: "{provider} API key", ar: "مفتاح API لمزوّد {provider}" },
  aiset_key_placeholder: { en: "Paste a new key", ar: "الصق مفتاحاً جديداً" },
  aiset_key_hint: { en: "Tested with one small request before it is saved.", ar: "يُختبر بطلب صغير واحد قبل حفظه." },
  aiset_test_save: { en: "Test & save", ar: "اختبار وحفظ" },
  aiset_saving: { en: "Testing…", ar: "جارٍ الاختبار…" },
  aiset_saved: { en: "Key tested and saved.", ar: "تم اختبار المفتاح وحفظه." },
  aiset_test: { en: "Test key", ar: "اختبار المفتاح" },
  aiset_testing: { en: "Testing…", ar: "جارٍ الاختبار…" },
  aiset_test_ok: { en: "The key works.", ar: "المفتاح يعمل." },
  aiset_test_fail: { en: "The key was refused.", ar: "تم رفض المفتاح." },
  aiset_remove: { en: "Delete key", ar: "حذف المفتاح" },
  aiset_remove_aria: { en: "Delete the saved {provider} key", ar: "حذف مفتاح {provider} المحفوظ" },
  aiset_removing: { en: "Deleting…", ar: "جارٍ الحذف…" },
  aiset_removed: { en: "Key deleted.", ar: "تم حذف المفتاح." },
  aiset_delete_confirm: {
    en: "Delete the saved {provider} key? Chats with {provider} models stop until you add a key again.",
    ar: "حذف مفتاح {provider} المحفوظ؟ تتوقف المحادثات مع نماذج {provider} حتى تضيف مفتاحاً من جديد.",
  },
  aiset_free_tier: {
    en: "Free-tier key: count its calls as $0 and never block them with the cap",
    ar: "مفتاح من الفئة المجانية: تُحتسب مكالماته بصفر دولار ولا يوقفها الحد الشهري",
  },
  aiset_free_tier_hint: {
    en: "Turn on only if the provider does not bill this key, e.g. a Google AI Studio key with billing off. Free tiers have rate limits, and the provider may use free-tier prompts to improve its products.",
    ar: "فعّله فقط إذا كان المزوّد لا يحاسب على هذا المفتاح، مثل مفتاح Google AI Studio مع إيقاف الفوترة. للفئات المجانية حدود لعدد الطلبات، وقد يستخدم المزوّد طلبات الفئة المجانية لتحسين منتجاته.",
  },
  aiset_free_tier_on: { en: "Marked as a free-tier key.", ar: "تم تعيينه مفتاحاً من الفئة المجانية." },
  aiset_free_tier_off: { en: "No longer a free-tier key: its calls count toward the cap.", ar: "لم يعد مفتاحاً مجانياً: تُحتسب مكالماته ضمن الحد الشهري." },
  aiset_env_source_note: {
    en: "This key comes from the .env file. To delete it, remove it from .env and restart the backend; a key saved here replaces it.",
    ar: "هذا المفتاح من ملف ‎.env. لحذفه، احذفه من ‎.env ثم أعد تشغيل الخادم؛ والمفتاح المحفوظ هنا يحل محله.",
  },
  aiset_err_KEY_REJECTED: {
    en: "The provider refused this key. Check it and try again; nothing was saved.",
    ar: "رفض المزوّد هذا المفتاح. تحقق منه وحاول مرة أخرى؛ لم يُحفظ شيء.",
  },
  aiset_err_AI_SECRETS_KEY_MISSING: {
    en: "Keys can't be saved until AI_SECRETS_KEY is set in the server's .env file.",
    ar: "لا يمكن حفظ المفاتيح قبل ضبط AI_SECRETS_KEY في ملف .env على الخادم.",
  },
  aiset_err_INSECURE_TRANSPORT: {
    en: "Keys can only be saved over HTTPS or from this computer's own network.",
    ar: "لا يمكن حفظ المفاتيح إلا عبر HTTPS أو من شبكة هذا الجهاز نفسه.",
  },
  aiset_err_forbidden: {
    en: "The server refused this change (the page's address isn't an allowed origin).",
    ar: "رفض الخادم هذا التغيير (عنوان الصفحة ليس أصلاً مسموحاً به).",
  },
  aiset_err_generic: { en: "Couldn't complete that. Nothing was changed.", ar: "تعذّر إتمام ذلك. لم يتغير شيء." },
  aiset_defaults: { en: "Defaults and spending", ar: "الافتراضيات والإنفاق" },
  aiset_default_model: { en: "Default model", ar: "النموذج الافتراضي" },
  aiset_default_model_none: { en: "No default", ar: "بلا نموذج افتراضي" },
  aiset_model_no_key: { en: "{label} (no key)", ar: "{label} (لا يوجد مفتاح)" },
  aiset_cap: { en: "Monthly cap (USD)", ar: "الحد الشهري (دولار أمريكي)" },
  aiset_cap_hint: {
    en: "Leave empty for no cap. When the cap is reached the assistant stops calling the model.",
    ar: "اتركه فارغاً لعدم وضع حد. عند بلوغ الحد يتوقف المساعد عن استدعاء النموذج.",
  },
  aiset_cap_invalid: {
    en: "Enter a number of dollars, at most two decimals, or leave it empty.",
    ar: "أدخل مبلغاً بالدولار بحد أقصى رقمين عشريين، أو اتركه فارغاً.",
  },
  aiset_cap_placeholder: { en: "No cap", ar: "بلا حد" },
  aiset_spend: { en: "Spent this month", ar: "المُنفَق هذا الشهر" },
  aiset_spend_of_cap: { en: "of {cap}", ar: "من {cap}" },
  aiset_spend_note: {
    en: "Calendar month, UTC. Cost comes from the provider price list and is an estimate.",
    ar: "الشهر الميلادي بتوقيت UTC. التكلفة من قائمة أسعار المزوّد وهي تقدير.",
  },
  aiset_save: { en: "Save settings", ar: "حفظ الإعدادات" },
  aiset_settings_saved: { en: "Settings saved.", ar: "تم حفظ الإعدادات." },
  aiset_thing: { en: "AI settings", ar: "إعدادات الذكاء الاصطناعي" },
} as const satisfies Record<string, CopyEntry>;
