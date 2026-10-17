"""Versioned reported-label alias table (stmt-extractor-alias-1.0).

Maps observed reported labels (English, Arabic, XBRL standard tag names) to
ontology codes. ``resolve_label`` is THE only admission route into a
candidate: a variant that matches zero codes returns None (unknown), and a
variant matching more than one code returns None (ambiguous) — the extractor
drops those, it never guesses positions.
"""

from typing import Literal

ALIAS_TABLE_VERSION = "stmt-extractor-alias-1.0"

ALIASES: dict[str, tuple[str, ...]] = {
    # Income statement
    "revenue": (
        "revenue", "revenues", "total revenue", "sales revenue",
        "الإيرادات", "إجمالي الإيرادات", "الإيراد",
    ),
    "cost_of_revenue": (
        "cost of revenue", "cost of sales", "cost of goods sold", "cogs",
        "تكلفة الإيرادات", "تكلفة الإيراد", "تكلفة المبيعات",
    ),
    "gross_profit": (
        "gross profit", "gross income", "total gross profit",
        "الربح الإجمالي", "إجمالي الربح", "الربح من العمليات",
    ),
    "selling_expenses": (
        "selling expenses", "selling and marketing expenses",
        "sales and marketing expense", "مصروفات البيع والتسويق",
    ),
    "admin_expenses": (
        "administrative expenses", "general and administrative expenses",
        "المصروفات الإدارية", "مصروفات إدارية",
    ),
    "operating_expenses": (
        "operating expenses", "total operating expenses",
        "المصروفات التشغيلية", "إجمالي مصروفات التشغيل",
    ),
    "operating_profit": (
        "operating profit", "operating income", "income from operations",
        "operating income loss",
        "الربح التشغيلي", "إجمالي الربح التشغيلي",
    ),
    "finance_costs": (
        "finance costs", "financing costs", "finance expenses",
        "interest expense", "التكاليف التمويلية", "المصروفات التمويلية",
        "مصروفات تمويلية",
    ),
    "income_tax": (
        "income tax", "income tax expense", "tax expense",
        "income tax expense benefit",
        "ضريبة الدخل", "الضرائب على الدخل", "مصروف ضريبي",
    ),
    "net_income": (
        "net income", "net profit", "profit for the period",
        "net income for the period", "net income loss", "loss for the period",
        "صافي الربح", "صافي دخل",
        "صافي ربح الفترة", "الربح الصافي",
    ),
    "eps": (
        "eps", "earnings per share", "basic eps", "basic earnings per share",
        "ربحية السهم", "ربح السهم", "ربحية السهم الأساسية",
    ),
    # Balance sheet
    "total_assets": (
        "total assets", "assets", "إجمالي الأصول", "مجموع الأصول",
        # Ambiguous on purpose — see total_liabilities above.
        "total liabilities and equity",
    ),
    "current_assets": (
        "current assets", "total current assets", "الأصول المتداولة",
    ),
    "cash_and_equivalents": (
        "cash and equivalents", "cash and cash equivalents", "cash",
        "النقد وما في حكمه", "النقدية وما يعادلها",
    ),
    "interest_bearing_assets": (
        "interest bearing assets", "interest earning assets",
        "financial assets at amortized cost", "finance assets",
        "الأصول ذات العائد الربوي",
    ),
    "inventory": (
        "inventory", "inventories", "inventory and work in progress",
        "المخزون", "المخزونات",
    ),
    "non_current_assets": (
        "non current assets", "non-current assets", "fixed assets",
        "أصول غير متداولة", "الأصول غير المتداولة",
    ),
    "total_liabilities": (
        "total liabilities", "liabilities", "إجمالي الخصوم", "مجموع الخصوم",
        # Deliberately ambiguous variant: also listed under total_assets —
        # the ambiguity gate must DROP a line carrying it (drop-not-guess).
        "total liabilities and equity",
    ),
    "current_liabilities": (
        "current liabilities", "total current liabilities",
        "الالتزامات المتداولة", "الخصوم المتداولة",
    ),
    "interest_bearing_debt": (
        "interest bearing debt", "interest bearing loans",
        "borrowings", "debt", "funding and borrowings",
        "الدين ذو الفائدة", "أقساط الديون ذات الفائدة", "الاقتراضات",
        "الدين", "أموال متعلقة بالفائدة",
    ),
    "total_equity": (
        "total equity", "equity", "shareholders equity",
        "stockholders equity", "total shareholders equity",
        "إجمالي حقوق الملكية", "حقوق الملكية", "حقوق المساهمين",
    ),
    "minority_interests": (
        "minority interests", "non controlling interests",
        "noncontrolling interests", "حقوق الأقلية", "حقوق الملكية غير المسيطرة",
    ),
    # Cash flow
    "cfo": (
        "cfo", "cash flows from used in operating activities",
        "cash flow from operations", "net cash from operating activities",
        "cash flows from operating activities",
        "التدفق النقدي التشغيلي", "التدفقات النقدية من الأنشطة التشغيلية",
    ),
    "cfi": (
        "cfi", "cash flows from used in investing activities",
        "cash flow from investing activities",
        "net cash used in investing activities",
        "التدفقات النقدية من الأنشطة الاستثمارية",
        "التدفق النقدي الاستثماري",
    ),
    "cff": (
        "cff", "cash flows from used in financing activities",
        "net cash from financing activities",
        "التدفقات النقدية من الأنشطة التمويلية",
        "التدفق النقدي التمويلي",
    ),
    "capex": (
        "capex", "capital expenditure", "capital expenditures",
        "payments for property, plant and equipment",
        "purchase of property, plant and equipment",
        "payments for property plant and equipment",
        "النفقات الرأسمالية", "الاستثمارات الرأسمالية",
    ),
    "dividends_paid": (
        "dividends paid", "cash dividends paid",
        "التوزيعات النقدية المدفوعة", "توزيعات مدفوعة",
    ),
    "debt_repayment": (
        "debt repayment", "repayment of borrowings",
        "سداد الدين", "سداد الأقساط",
    ),
}

# Inverted lookup: variant (normalized) -> set of codes. Built once.
_VARIANTS: dict[str, set[str]] = {}
for _code, _variants in ALIASES.items():
    for _variant in _variants:
        _VARIANTS.setdefault(_variant.casefold().strip(), set()).add(_code)


def resolve_label(label: str) -> tuple[str, Literal["xbrl_tag", "en", "ar"]] | None:
    """Resolve a reported label to its ontology code.

    Returns ``(code, kind)`` or ``None`` when the label is unknown or matches
    more than one code (ambiguous — callers drop, never guess).
    """
    normalized = label.casefold().strip()
    matches = _VARIANTS.get(normalized)
    if matches is None or len(matches) != 1:
        return None
    code = next(iter(matches))
    has_arabic = any("\u0600" <= ch <= "\u06FF" for ch in label)
    return code, ("ar" if has_arabic else "en")
