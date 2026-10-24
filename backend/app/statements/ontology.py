"""Statement line ontology (stmt-ontology-1.1).

Canonical codes for income / balance / cash-flow lines extracted from published
filings. Labels are shipped here as the single source of truth and mirrored in
the REST contract and frontend types.

1.1 (R43, additive): ``interest_income``, ``weighted_avg_shares_basic`` and
``shares_outstanding``, plus a per-line ``unit`` so readers format share
counts and per-share values correctly (never from the ``currency`` column).
"""

from enum import StrEnum
from typing import Literal, NamedTuple

LineUnit = Literal["currency", "shares", "currency_per_share"]


class LineSection(StrEnum):
    """Which statement a line belongs to."""

    INCOME = "income"
    BALANCE = "balance"
    CASH_FLOW = "cash_flow"


class StatementLine(NamedTuple):
    """One canonical ontology line with bilingual display labels."""

    code: str
    section: LineSection
    label_en: str
    label_ar: str
    unit: LineUnit = "currency"


STATEMENT_ONTOLOGY_VERSION = "stmt-ontology-1.1"

_STATEMENT_LINE_TUPLES: tuple[StatementLine, ...] = (
    # --- Income statement ---
    StatementLine("revenue", LineSection.INCOME, "Revenue", "الإيرادات"),
    StatementLine("cost_of_revenue", LineSection.INCOME, "Cost of revenue", "تكلفة الإيرادات"),
    StatementLine("gross_profit", LineSection.INCOME, "Gross profit", "الربح الإجمالي"),
    StatementLine(
        "selling_expenses", LineSection.INCOME, "Selling expenses", "مصروفات البيع والتسويق"
    ),
    StatementLine(
        "admin_expenses", LineSection.INCOME, "Administrative expenses", "المصروفات الإدارية"
    ),
    StatementLine(
        "operating_expenses", LineSection.INCOME, "Operating expenses", "المصروفات التشغيلية"
    ),
    StatementLine("operating_profit", LineSection.INCOME, "Operating profit", "الربح التشغيلي"),
    StatementLine("finance_costs", LineSection.INCOME, "Finance costs", "التكاليف التمويلية"),
    StatementLine("income_tax", LineSection.INCOME, "Income tax", "ضريبة الدخل"),
    StatementLine("net_income", LineSection.INCOME, "Net income", "صافي الربح"),
    StatementLine(
        "eps", LineSection.INCOME, "Earnings per share", "ربحية السهم", "currency_per_share"
    ),
    StatementLine("interest_income", LineSection.INCOME, "Interest income", "إيرادات الفوائد"),
    StatementLine(
        "weighted_avg_shares_basic",
        LineSection.INCOME,
        "Weighted average shares (basic)",
        "المتوسط المرجح لعدد الأسهم",
        "shares",
    ),
    # --- Balance sheet ---
    StatementLine("total_assets", LineSection.BALANCE, "Total assets", "إجمالي الأصول"),
    StatementLine("current_assets", LineSection.BALANCE, "Current assets", "الأصول المتداولة"),
    StatementLine(
        "cash_and_equivalents", LineSection.BALANCE, "Cash and equivalents", "النقد وما في حكمه"
    ),
    StatementLine(
        "interest_bearing_assets",
        LineSection.BALANCE,
        "Interest-bearing assets",
        "الأصول ذات العائد الربوي",
    ),
    StatementLine("inventory", LineSection.BALANCE, "Inventory", "المخزون"),
    StatementLine(
        "non_current_assets", LineSection.BALANCE, "Non-current assets", "الأصول غير المتداولة"
    ),
    StatementLine("total_liabilities", LineSection.BALANCE, "Total liabilities", "إجمالي الخصوم"),
    StatementLine(
        "current_liabilities", LineSection.BALANCE, "Current liabilities", "الالتزامات المتداولة"
    ),
    StatementLine(
        "interest_bearing_debt", LineSection.BALANCE, "Interest-bearing debt", "الدين ذو الفائدة"
    ),
    StatementLine("total_equity", LineSection.BALANCE, "Total equity", "إجمالي حقوق الملكية"),
    StatementLine("minority_interests", LineSection.BALANCE, "Minority interests", "حقوق الأقلية"),
    StatementLine(
        "shares_outstanding",
        LineSection.BALANCE,
        "Shares outstanding",
        "عدد الأسهم القائمة",
        "shares",
    ),
    # --- Cash flow statement ---
    StatementLine(
        "cfo", LineSection.CASH_FLOW, "Cash flow from operations", "التدفق النقدي التشغيلي"
    ),
    StatementLine(
        "cfi", LineSection.CASH_FLOW, "Cash flow from investing", "التدفق النقدي الاستثماري"
    ),
    StatementLine(
        "cff", LineSection.CASH_FLOW, "Cash flow from financing", "التدفق النقدي التمويلي"
    ),
    StatementLine("capex", LineSection.CASH_FLOW, "Capital expenditure", "النفقات الرأسمالية"),
    StatementLine(
        "dividends_paid", LineSection.CASH_FLOW, "Dividends paid", "التوزيعات النقدية المدفوعة"
    ),
    StatementLine("debt_repayment", LineSection.CASH_FLOW, "Debt repayment", "سداد الدين"),
)

STATEMENT_LINES: dict[str, StatementLine] = {sl.code: sl for sl in _STATEMENT_LINE_TUPLES}


def line(code: str) -> StatementLine:
    """Return the ontology line for ``code``; unknown codes raise ``KeyError``."""
    return STATEMENT_LINES[code]
