import type { CopyEntry } from "./types";

/**
 * Company overview price history (R47 P1-P5): range selector, Day summary, the
 * volatility cone ("range of typical moves", not a prediction) with its measured
 * calibration, and confirmed chart patterns with their measured EGX odds.
 * Display only: nothing here feeds the stance, and no copy reads as advice.
 */
export const PRICE_HISTORY_COPY = {
  // ---- Range selector and overlay toggles ----
  pxf_range_1D: { en: "Day", ar: "يوم" },
  pxf_range_1W: { en: "Week", ar: "أسبوع" },
  pxf_range_1M: { en: "Month", ar: "شهر" },
  pxf_range_YTD: { en: "YTD", ar: "هذا العام" },
  pxf_range_1Y: { en: "1Y", ar: "سنة" },
  pxf_range_5Y: { en: "5Y", ar: "5 سنوات" },
  pxf_overlays_aria: { en: "Chart overlays", ar: "إضافات الرسم" },
  pxf_forecast: { en: "Forecast", ar: "التوقّع" },
  pxf_patterns: { en: "Patterns", ar: "الأنماط" },
  pxf_loading_history: { en: "price history", ar: "سجل الأسعار" },
  pxf_mode_aria: { en: "Chart type", ar: "نوع الرسم" },
  pxf_mode_line: { en: "Line", ar: "خط" },
  pxf_mode_candles: { en: "Candles", ar: "شموع" },
  pxf_zoom_hint: {
    en: "Drag to pan; Ctrl or Cmd + scroll, or pinch, to zoom; double-click an axis to reset.",
    ar: "اسحب للتحريك؛ اضغط Ctrl أو Cmd مع تمرير العجلة، أو اقرص، للتكبير؛ انقر نقرًا مزدوجًا على أحد المحورين لإعادة الضبط.",
  },

  // ---- Day: last session summary ----
  pxf_day_title: { en: "Last session · {date}", ar: "آخر جلسة · {date}" },
  pxf_day_close: { en: "Close", ar: "الإغلاق" },
  pxf_day_change: { en: "Change", ar: "التغيّر" },
  pxf_day_vs_prev: {
    en: "Against the previous stored session: close {price} on {date}.",
    ar: "مقارنة بالجلسة المخزّنة السابقة: إغلاق {price} في {date}.",
  },
  pxf_day_empty: {
    en: "No daily prices are stored for this company yet.",
    ar: "لا توجد أسعار يومية مخزّنة لهذه الشركة بعد.",
  },
  pxf_day_note: {
    en: "End-of-day figures only; there is no intraday data.",
    ar: "أرقام نهاية اليوم فقط؛ لا توجد بيانات خلال اليوم.",
  },

  // ---- Forecast axis and legend ----
  pxf_horizon_1M: { en: "1M", ar: "شهر" },
  pxf_horizon_3M: { en: "3M", ar: "3 أشهر" },
  pxf_horizon_6M: { en: "6M", ar: "6 أشهر" },
  pxf_axis_1M: { en: "1M", ar: "1 ش" },
  pxf_axis_3M: { en: "3M", ar: "3 ش" },
  pxf_axis_6M: { en: "6M", ar: "6 ش" },
  pxf_horizon_days: { en: "{n} sessions", ar: "{n} جلسة" },
  pxf_legend_label: {
    en: "Range of typical moves, not a prediction",
    ar: "نطاق الحركات المعتادة، وليس توقعًا",
  },
  pxf_band_50: { en: "50% of the time", ar: "50% من الوقت" },
  pxf_band_90: { en: "90% of the time", ar: "90% من الوقت" },
  pxf_legend_now: {
    en: "Dashed line: last close; the time axis continues over the coming trading days",
    ar: "الخط المتقطع: آخر إغلاق؛ ويمتد محور الزمن على أيام التداول القادمة",
  },

  // ---- Forecast panel ----
  pxf_cone_title: { en: "Range of typical moves", ar: "نطاق الحركات المعتادة" },
  pxf_cone_intro: {
    en: "Centred on the last close of {price}, with no trend assumed. Built from the last {n} daily moves (annual volatility {sigma}).",
    ar: "متمركز حول آخر إغلاق عند {price}، دون افتراض أي اتجاه. مبني على آخر {n} حركة يومية (التقلب السنوي {sigma}).",
  },
  pxf_cone_horizon: {
    en: "{horizon} · about {date}",
    ar: "{horizon} · نحو {date}",
  },
  pxf_cone_range_50: {
    en: "Lands in, 50% of the time",
    ar: "يقع داخل النطاق 50% من الوقت",
  },
  pxf_cone_range_90: {
    en: "Lands in, 90% of the time",
    ar: "يقع داخل النطاق 90% من الوقت",
  },
  pxf_cone_unavailable: {
    en: "The range is not available.",
    ar: "النطاق غير متاح.",
  },

  // ---- Calibration: did the range hold on this stock's own history ----
  pxf_cal_title: {
    en: "How often the range held in the past",
    ar: "كم مرة صمد النطاق في الماضي",
  },
  pxf_cal_intro: {
    en: "The same method, rebuilt at past dates on this stock's own history: the share of cases that ended inside each range. A range that matched exactly would show 50% and 90%. The 95% interval is in brackets.",
    ar: "الطريقة نفسها مُعاد بناؤها عند تواريخ سابقة على تاريخ هذا السهم: نسبة الحالات التي انتهت داخل كل نطاق. النطاق المطابق تمامًا يعطي 50% و90%. الفاصل بنسبة 95% بين قوسين.",
  },
  pxf_cal_inside_50: {
    en: "Ended inside the 50% range",
    ar: "انتهى داخل نطاق 50%",
  },
  pxf_cal_inside_90: {
    en: "Ended inside the 90% range",
    ar: "انتهى داخل نطاق 90%",
  },
  pxf_cal_share: { en: "{share} ({low}–{high})", ar: "{share} ({low}–{high})" },
  pxf_cal_cases: {
    en: "{n} past cases, {first} to {last}",
    ar: "{n} حالة سابقة، من {first} إلى {last}",
  },
  pxf_cal_not_measured: { en: "Not measured:", ar: "لم يُقَس:" },

  // ---- Patterns panel ----
  pxf_pat_title: { en: "Chart patterns", ar: "أنماط الرسم" },
  pxf_pat_intro: {
    en: "Shapes found by fixed rules and counted only after a closing price broke out of them. Each shows how often the price later moved in the pattern's usual direction on EGX history. Display only: nothing here feeds the stance.",
    ar: "أشكال تُكتشف بقواعد ثابتة ولا تُحتسب إلا بعد إغلاق كسرها. يعرض كل شكل كم مرة تحرك السعر لاحقًا في الاتجاه المعتاد للنمط في تاريخ البورصة المصرية. للعرض فقط: لا شيء هنا يدخل في الموقف.",
  },
  pxf_pat_legend: {
    en: "Dots: key points. Line: boundary. Diamond: break level. Dashed: measured move, a chart convention and not a forecast. Dashed shape with a dotted level: still forming, and the close that would confirm it.",
    ar: "النقاط: النقاط الرئيسية. الخط: الحد. المعيّن: مستوى الكسر. المتقطع: الحركة المقاسة، وهي عُرف في الرسوم وليست توقعًا. الشكل المتقطع مع مستوى منقّط: نمط قيد التكوّن، والإغلاق الذي يؤكده.",
  },
  pxf_pat_head_and_shoulders_top: {
    en: "Head and shoulders",
    ar: "الرأس والكتفان",
  },
  pxf_pat_head_and_shoulders_inverse: {
    en: "Inverse head and shoulders",
    ar: "الرأس والكتفان المقلوب",
  },
  pxf_pat_double_top: { en: "Double top", ar: "القمة المزدوجة" },
  pxf_pat_double_bottom: { en: "Double bottom", ar: "القاع المزدوج" },
  pxf_pat_ascending_triangle: { en: "Ascending triangle", ar: "المثلث الصاعد" },
  pxf_pat_descending_triangle: {
    en: "Descending triangle",
    ar: "المثلث الهابط",
  },
  pxf_pat_symmetrical_triangle_up: {
    en: "Symmetrical triangle, broke up",
    ar: "مثلث متماثل، كُسر لأعلى",
  },
  pxf_pat_symmetrical_triangle_down: {
    en: "Symmetrical triangle, broke down",
    ar: "مثلث متماثل، كُسر لأسفل",
  },
  pxf_pat_confirmed: { en: "Confirmed {date}", ar: "تأكد في {date}" },
  pxf_pat_broke_up: { en: "Broke up", ar: "كُسر لأعلى" },
  pxf_pat_broke_down: { en: "Broke down", ar: "كُسر لأسفل" },
  pxf_pat_odds: {
    en: "After {h} sessions: moved that way {hit} of the time, against {base} on an ordinary day. 95% interval {low} to {high}, {n} cases.",
    ar: "بعد {h} جلسة: تحرك في هذا الاتجاه {hit} من الحالات، مقابل {base} في يوم عادي. الفاصل 95%: من {low} إلى {high}، {n} حالة.",
  },
  pxf_pat_odds_few: {
    en: "After {h} sessions: too few cases to measure ({n}, at least {min} needed).",
    ar: "بعد {h} جلسة: عدد الحالات قليل جدًا للقياس ({n}، والحد الأدنى {min}).",
  },
  pxf_pat_odds_missing: {
    en: "After {h} sessions: not measured.",
    ar: "بعد {h} جلسة: لم يُقَس.",
  },
  pxf_pat_odds_reason: {
    en: "After {h} sessions: not measured.",
    ar: "بعد {h} جلسة: لم يُقَس.",
  },
  pxf_pat_differs: {
    en: "The interval excludes the ordinary-day rate.",
    ar: "الفاصل لا يشمل معدل اليوم العادي.",
  },
  pxf_pat_same: {
    en: "The interval includes the ordinary-day rate: no clear difference.",
    ar: "الفاصل يشمل معدل اليوم العادي: لا فرق واضح.",
  },
  pxf_pat_empty: {
    en: "No confirmed patterns in this range.",
    ar: "لا توجد أنماط مؤكدة في هذا النطاق.",
  },
  pxf_pat_outside: {
    en: "Confirmed in the last year but outside this range: {n}.",
    ar: "مؤكدة في آخر سنة لكنها خارج هذا النطاق: {n}.",
  },
  pxf_pat_unavailable: {
    en: "Patterns are not available.",
    ar: "الأنماط غير متاحة.",
  },
  pxf_pat_basis: {
    en: "Odds measured on {companies} EGX companies, {start} to {end}.",
    ar: "الاحتمالات مقاسة على {companies} شركة في البورصة المصرية، من {start} إلى {end}.",
  },
  pxf_break_label: { en: "Break {price}", ar: "الكسر {price}" },
  pxf_target_label: {
    en: "Measured move {price}",
    ar: "الحركة المقاسة {price}",
  },
  pxf_pat_pick: { en: "Show on chart", ar: "اعرض على الرسم" },
  pxf_pat_note: {
    en: "Patterns are drawn by fixed rules; the odds are measured on EGX history, not a prediction.",
    ar: "الأنماط تُرسم بقواعد ثابتة، والاحتمالات مقاسة على تاريخ البورصة المصرية، وليست توقعًا.",
  },
  pxf_pat_overlap_note: {
    en: "Cases overlap in time across stocks, and their forward windows overlap within a stock, so they are not independent and the interval is narrower than the true uncertainty.",
    ar: "الحالات تتداخل زمنيًا بين الأسهم، وتتداخل فترات ما بعدها داخل السهم الواحد، فهي ليست مستقلة والفاصل أضيق من عدم اليقين الحقيقي.",
  },

  // ---- Forming shapes (R47 P6) ----
  pxf_pat_symmetrical_triangle: {
    en: "Symmetrical triangle",
    ar: "مثلث متماثل",
  },
  pxf_pat_forming_title: { en: "Forming now", ar: "قيد التكوّن الآن" },
  pxf_pat_forming_intro: {
    en: "No breakout yet, and many such shapes never break out. Their odds are measured from this forming stage on EGX history, not from a breakout.",
    ar: "لم يحدث كسر بعد، وكثير من هذه الأشكال لا يُكسر أبدًا. احتمالاتها مقاسة من مرحلة التكوّن هذه في تاريخ البورصة المصرية، وليس من الكسر.",
  },
  pxf_pat_forming_empty: {
    en: "No shapes forming now.",
    ar: "لا توجد أشكال قيد التكوّن الآن.",
  },
  pxf_pat_forming_meta: {
    en: "Forming since {date} · {n} sessions left to confirm",
    ar: "قيد التكوّن منذ {date} · متبقٍ {n} جلسة للتأكيد",
  },
  pxf_pat_forming_above: {
    en: "Confirms on a close above {price}.",
    ar: "يتأكد بإغلاق أعلى من {price}.",
  },
  pxf_pat_forming_below: {
    en: "Confirms on a close below {price}.",
    ar: "يتأكد بإغلاق أدنى من {price}.",
  },
  pxf_pat_forming_either: {
    en: "Confirms on a close above {above} (up) or below {below} (down).",
    ar: "يتأكد بإغلاق أعلى من {above} (لأعلى) أو أدنى من {below} (لأسفل).",
  },
  pxf_pat_forming_fails_above: {
    en: "Fails on a close above {price}.",
    ar: "يفشل بإغلاق أعلى من {price}.",
  },
  pxf_pat_forming_fails_below: {
    en: "Fails on a close below {price}.",
    ar: "يفشل بإغلاق أدنى من {price}.",
  },
  pxf_pat_forming_outcome: {
    en: "Similar shapes went on to confirm {rate} of the time (95% interval {low} to {high}); {failed} failed and {expired} expired. {n} cases.",
    ar: "الأشكال المماثلة تأكدت لاحقًا في {rate} من الحالات (الفاصل 95%: من {low} إلى {high})؛ وفشل {failed} وانتهت مهلة {expired}. {n} حالة.",
  },
  pxf_pat_forming_up_share: {
    en: "Of those that broke out, {share} broke up.",
    ar: "من بين التي كُسرت، كُسر {share} لأعلى.",
  },
  pxf_pat_forming_odds: {
    en: "From this stage, after {h} sessions: moved the expected way {hit} of the time, against {base} on an ordinary day. 95% interval {low} to {high}, {n} cases.",
    ar: "من هذه المرحلة، بعد {h} جلسة: تحرك في الاتجاه المتوقع {hit} من الحالات، مقابل {base} في يوم عادي. الفاصل 95%: من {low} إلى {high}، {n} حالة.",
  },
  pxf_pat_forming_few: {
    en: "Too few similar shapes to measure ({n}, at least {min} needed).",
    ar: "عدد الأشكال المماثلة قليل جدًا للقياس ({n}، والحد الأدنى {min}).",
  },
  pxf_level_above: { en: "Confirms above {price}", ar: "يتأكد فوق {price}" },
  pxf_level_below: { en: "Confirms below {price}", ar: "يتأكد تحت {price}" },

  // ---- Translated fixed notes (the backend sends the English text) ----
  pxf_cone_note: {
    en: "A range of typical moves if past volatility continues, not a prediction.",
    ar: "نطاق الحركات المعتادة إذا استمر التقلب السابق، وليس توقعًا.",
  },
  pxf_cone_calendar_note: {
    en: "Dates skip Friday and Saturday only; Egyptian public holidays are not in the calendar, so the dates are approximate.",
    ar: "التواريخ تتخطى الجمعة والسبت فقط؛ العطلات الرسمية المصرية ليست في التقويم، لذا التواريخ تقريبية.",
  },
  pxf_cal_overlap_note: {
    en: "Cases are 5 sessions apart but each looks 21 to 126 sessions ahead, so they overlap and are not independent: the intervals are optimistic. Past coverage does not guarantee future coverage.",
    ar: "الحالات تفصلها 5 جلسات لكن كل منها ينظر من 21 إلى 126 جلسة للأمام، فهي متداخلة وغير مستقلة: الفواصل متفائلة. التغطية في الماضي لا تضمن التغطية في المستقبل.",
  },
} as const satisfies Record<string, CopyEntry>;
