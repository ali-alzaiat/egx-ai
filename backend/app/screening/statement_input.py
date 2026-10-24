"""Build a ScreeningInput from approved statement lines (R43: the canonical Shariah engine).

The Shariah methodology (versioned record, unchanged) is reused verbatim; only
the inputs come from the statement-line bridge, latest ANNUAL period only.
Partial data never returns None: each missing input goes in as ``None`` and its
rule reports INSUFFICIENT_DATA naming the missing statement line.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from app.screening.rules import ScreeningRuleResult, ScreeningVerdict
from app.screening.service import RuleProvenance, ScreeningInput
from app.statements import bridge

if TYPE_CHECKING:
    from decimal import Decimal

    from app.models.market import Company
    from app.statements.bridge import CompanyStatements, LineValue, PeriodLines

#: Statement-line codes behind each ratio rule.
RULE_LINE_CODES: dict[str, tuple[str, ...]] = {
    "debt_ratio": ("interest_bearing_debt", "total_assets"),
    "interest_income_ratio": ("interest_income", "revenue"),
    "cash_securities_ratio": ("cash_and_equivalents", "total_assets"),
}

#: Rule-level input labels -> the statement line that feeds them.
RULE_LABEL_TO_LINE: dict[str, str] = {
    "total_debt": "interest_bearing_debt",
    "total_assets": "total_assets",
    "interest_income": "interest_income",
    "total_revenue": "revenue",
    "cash_and_equivalents": "cash_and_equivalents",
}

NO_STATEMENTS_REASON = "no approved statement lines"


def _rule_source(lines: list[LineValue]) -> RuleProvenance | None:
    if not lines:
        return None
    tier = bridge.tier_of(lines)
    head = next((lv for lv in lines if lv.source_tier == tier), lines[0])
    pages = sorted({lv.source_page for lv in lines if lv.source_page})
    source = (
        f"{tier}: {head.document_type or 'statement'} FY{head.fiscal_year} "
        f"(period end {head.period_end.isoformat()})"
    )
    if pages:
        source += f", p.{', '.join(pages)}"
    dated = [lv.published_date for lv in lines if lv.published_date is not None]
    return RuleProvenance(source=source, source_date=max(dated) if dated else None)


def build_screening_input_from_statements(
    company: Company, statements: CompanyStatements
) -> ScreeningInput:
    """Map the latest period's lines onto a ``ScreeningInput`` (never None)."""
    p = statements.latest()

    def value(code: str) -> Decimal | None:
        lv = p.get(code) if p is not None else None
        return lv.value if lv is not None else None

    provenance: dict[str, RuleProvenance] = {
        "industry_screen": RuleProvenance(source="company record", source_date=None)
    }
    if p is not None:
        for rule_name, codes in RULE_LINE_CODES.items():
            prov = _rule_source([lv for c in codes if (lv := p.get(c)) is not None])
            if prov is not None:
                provenance[rule_name] = prov

    return ScreeningInput(
        company_id=str(company.id),
        ticker=company.ticker,
        industry=company.industry,
        total_debt=value("interest_bearing_debt"),
        total_assets=value("total_assets"),
        interest_income=value("interest_income"),
        total_revenue=value("revenue"),
        cash_and_securities=value("cash_and_equivalents"),
        provenance=provenance,
    )


def name_missing_lines(
    rules: list[ScreeningRuleResult], p: PeriodLines | None
) -> list[ScreeningRuleResult]:
    """Rewrite INSUFFICIENT rules so ``missing_input``/``reason`` name statement lines."""
    out: list[ScreeningRuleResult] = []
    for rule in rules:
        if rule.verdict != ScreeningVerdict.INSUFFICIENT_DATA or not rule.missing_input:
            out.append(rule)
            continue
        labels = [part.strip() for part in rule.missing_input.split(",") if part.strip()]
        codes = [RULE_LABEL_TO_LINE.get(label) for label in labels]
        if any(code is None for code in codes):
            out.append(rule)
            continue
        line_codes = [c for c in codes if c is not None]
        reason = "; ".join(bridge.missing_reason(code, p) for code in line_codes)
        out.append(replace(rule, missing_input=", ".join(line_codes), reason=reason))
    return out


def statement_sources(statements: CompanyStatements) -> list[LineValue]:
    """Every line the screen read (for the tier / provisional summary)."""
    p = statements.latest()
    if p is None:
        return []
    codes = {c for codes in RULE_LINE_CODES.values() for c in codes}
    return [lv for c in sorted(codes) if (lv := p.get(c)) is not None]
