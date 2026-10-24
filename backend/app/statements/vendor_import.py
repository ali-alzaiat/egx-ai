"""Offline import of provisional vendor statements (stockanalysis.com / S&P Global).

Reads JSON files saved under ``data/vendor/stockanalysis/`` (one per ticker) and
turns each fiscal year into ontology statement lines. Nothing here touches the
network: collection is a separate, supervised step outside the app.

Rules:
- Explicit, versioned field map (``VENDOR_MAPPING_VERSION``). Unmapped vendor
  fields are ignored, missing ontology lines stay INSUFFICIENT_DATA — nothing is
  derived or estimated.
- Values are stored in raw reporting-currency units exactly as the vendor gives
  them; expense fields the vendor shows as negatives are stored as magnitudes
  (the ontology convention). Cash-flow lines keep their reported sign.
- Every line is ``vendor_aggregator`` (provisional) and runs through the same
  StatementValidator gates as filings. Filing-backed lines always outrank them.
- Companies reporting in a currency other than EGP are imported but held as
  ``extraction_candidate`` until an FX policy exists, so mixed-currency ratios
  never reach calculations.

Usage:
    python -m app.statements.vendor_import                 # all saved files
    python -m app.statements.vendor_import COMI AMOC       # selected tickers
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.models.financial import FinancialDocument, ReportingPeriodType
from app.models.market import Company, DataSourceType
from app.models.statements import ExtractionMethod, ExtStatus
from app.repositories.data_source import DataSourceRepository
from app.repositories.financial import FinancialDocumentRepository, FinancialPeriodRepository
from app.repositories.statements import StatementLineRepository
from app.schemas.financial import FinancialDocumentCreate, FinancialPeriodCreate
from app.statements.extractor import LineCandidate
from app.statements.ontology import STATEMENT_LINES, STATEMENT_ONTOLOGY_VERSION
from app.statements.validator import StatementValidator

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

VENDOR_MAPPING_VERSION = "stockanalysis-map-1.2"
VENDOR_SOURCE_NAME = "STOCKANALYSIS_SPG"
VENDOR_DOCUMENT_TYPE = "VENDOR_ANNUAL_STATEMENTS"
DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "vendor" / "stockanalysis"

AS_REPORTED = "as_reported"
MAGNITUDE = "magnitude"
#: Vendor ``equity`` (shareholders' equity incl. any minority) used as common equity
#: only when the period has no ``totalCommonEquity`` and no non-zero minority
#: interest (map 1.2; the vendor omits zero rows - 87 of 230 files, and
#: assets = liabilities + equity holds in all 408 such periods).
EQUITY_IF_NO_MINORITY = "equity_if_no_minority"

# (statement, vendor field id, ontology code, transform). When two entries map
# to the same code, the first one present for a period wins and the later one
# is skipped for that period (never both): banks carry interest income under
# ``interestIncomeTotalBank`` instead of ``interestIncome`` (map 1.1); total equity
# falls back from ``totalCommonEquity`` to ``equity`` (map 1.2, see above).
FIELD_MAP: tuple[tuple[str, str, str, str], ...] = (
    ("income", "revenue", "revenue", AS_REPORTED),
    ("income", "cor", "cost_of_revenue", AS_REPORTED),
    ("income", "gp", "gross_profit", AS_REPORTED),
    ("income", "opex", "operating_expenses", AS_REPORTED),
    ("income", "opinc", "operating_profit", AS_REPORTED),
    ("income", "interestExpense", "finance_costs", MAGNITUDE),
    ("income", "taxexp", "income_tax", AS_REPORTED),
    ("income", "netinccmn", "net_income", AS_REPORTED),
    ("income", "epsBasic", "eps", AS_REPORTED),
    ("income", "interestIncome", "interest_income", AS_REPORTED),
    ("income", "interestIncomeTotalBank", "interest_income", AS_REPORTED),
    ("income", "sharesBasic", "weighted_avg_shares_basic", AS_REPORTED),
    ("balance", "assets", "total_assets", AS_REPORTED),
    ("balance", "assetsc", "current_assets", AS_REPORTED),
    ("balance", "cashneq", "cash_and_equivalents", AS_REPORTED),
    ("balance", "inventory", "inventory", AS_REPORTED),
    ("balance", "liabilities", "total_liabilities", AS_REPORTED),
    ("balance", "currentLiabilities", "current_liabilities", AS_REPORTED),
    ("balance", "debt", "interest_bearing_debt", AS_REPORTED),
    # Common equity excludes minority interest, which maps separately, so the
    # assets = liabilities + equity + minority identity does not double count.
    ("balance", "totalCommonEquity", "total_equity", AS_REPORTED),
    ("balance", "equity", "total_equity", EQUITY_IF_NO_MINORITY),
    ("balance", "minorityInterestBS", "minority_interests", AS_REPORTED),
    ("balance", "sharesOutTotalCommon", "shares_outstanding", AS_REPORTED),
    ("cash_flow", "ncfo", "cfo", AS_REPORTED),
    ("cash_flow", "ncfi", "cfi", AS_REPORTED),
    ("cash_flow", "ncff", "cff", AS_REPORTED),
    ("cash_flow", "capex", "capex", AS_REPORTED),
    ("cash_flow", "commonDividendCF", "dividends_paid", AS_REPORTED),
    ("cash_flow", "debtRepaidTotal", "debt_repayment", AS_REPORTED),
)

@dataclass
class VendorPeriod:
    fiscal_year: int
    period_end: date
    currency: str
    candidates: list[LineCandidate] = field(default_factory=list)


@dataclass
class ImportSummary:
    companies: int = 0
    periods: int = 0
    auto_validated: int = 0
    rejected: int = 0
    held: int = 0
    skipped: list[str] = field(default_factory=list)
    company_ids: list[uuid.UUID] = field(default_factory=list)


def _decimal(raw: Any) -> Decimal | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return Decimal(str(raw)).quantize(Decimal("0.0001"))
    except (InvalidOperation, ValueError):
        return None


def _titles(statement: dict[str, Any]) -> dict[str, str]:
    return {m["id"]: m.get("title", m["id"]) for m in statement.get("map") or [] if "id" in m}


def period_start(end: date) -> date:
    try:
        prior = end.replace(year=end.year - 1)
    except ValueError:  # 29 February
        prior = end.replace(year=end.year - 1, day=28)
    return prior + timedelta(days=1)


def vendor_periods(payload: dict[str, Any]) -> list[VendorPeriod]:
    """Pure mapping of one saved vendor file into per-fiscal-year candidates."""
    currency = (payload.get("currency_financial") or "").upper() or "EGP"
    statements: dict[str, dict[str, Any]] = payload.get("statements") or {}
    periods: dict[date, VendorPeriod] = {}
    for section, vendor_id, code, transform in FIELD_MAP:
        statement = statements.get(section) or {}
        data = statement.get("financialData") if statement.get("available") else None
        if not isinstance(data, dict):
            continue
        datekeys = data.get("datekey") or []
        years = data.get("fiscalYear") or []
        values = data.get(vendor_id)
        if not isinstance(values, list):
            continue
        label = _titles(statement).get(vendor_id, vendor_id)
        for i, key in enumerate(datekeys):
            if key == "TTM" or i >= len(values) or i >= len(years):
                continue
            value = _decimal(values[i])
            if value is None:
                continue
            if transform == EQUITY_IF_NO_MINORITY:
                minority = data.get("minorityInterestBS")
                has_minority = (
                    isinstance(minority, list)
                    and i < len(minority)
                    and (_decimal(minority[i]) or Decimal(0)) != 0
                )
                if has_minority:
                    continue  # equity would include minority interest: leave it unmapped
            if transform == MAGNITUDE:
                value = abs(value)
            end = date.fromisoformat(str(key))
            period = periods.setdefault(
                end, VendorPeriod(fiscal_year=int(years[i]), period_end=end, currency=currency)
            )
            if any(c.ontology_code == code for c in period.candidates):
                continue  # an earlier field already supplied this code (first wins)
            period.candidates.append(
                LineCandidate(
                    ontology_code=code,
                    ontology_version=STATEMENT_ONTOLOGY_VERSION,
                    value=value,
                    currency=currency,
                    source_label_reported=label,
                    source_label_en=label,
                    source_label_ar=STATEMENT_LINES[code].label_ar,
                    source_page=None,
                    extraction_method=ExtractionMethod.vendor_aggregator.value,
                )
            )
    return sorted(periods.values(), key=lambda p: p.period_end, reverse=True)


def _provenance(payload: dict[str, Any]) -> str:
    trust = next(
        (
            s.get("trust")
            for s in (payload.get("statements") or {}).values()
            if isinstance(s, dict) and s.get("trust")
        ),
        None,
    ) or {}
    sources = ", ".join(s.get("name", "") for s in trust.get("sources") or []) or "unknown"
    return (
        f"PROVISIONAL vendor data: {sources} via stockanalysis.com; "
        f"vendor last updated {trust.get('lastUpdated', 'unknown')}; "
        f"fetched {payload.get('fetched_at', 'unknown')}; mapping {VENDOR_MAPPING_VERSION}"
    )


async def import_payload(
    session: AsyncSession, payload: dict[str, Any], summary: ImportSummary
) -> None:
    """Persist one company's vendor periods as validated statement lines."""
    ticker = str(payload.get("ticker", "")).upper()
    company = (
        await session.execute(select(Company).where(Company.ticker == ticker))
    ).scalar_one_or_none()
    periods = vendor_periods(payload)
    if company is None or not periods:
        summary.skipped.append(ticker or "?")
        return

    source = await DataSourceRepository(session).get_or_create(
        name=VENDOR_SOURCE_NAME,
        source_type=DataSourceType.DATA_PROVIDER,
        base_url="https://stockanalysis.com",
        description="Provisional statements (S&P Global Market Intelligence via stockanalysis.com)",
    )
    fetched_raw = payload.get("fetched_at")
    fetched_at = datetime.fromisoformat(fetched_raw) if fetched_raw else datetime.now(UTC)
    page_url = (
        ((payload.get("statements") or {}).get("income") or {}).get("url")
        or f"https://stockanalysis.com/quote/egx/{ticker}/financials/"
    )
    notes = _provenance(payload)
    validator = StatementValidator()
    lines = StatementLineRepository(session)

    for vp in periods:
        period = await FinancialPeriodRepository(session).upsert(
            FinancialPeriodCreate(
                company_id=company.id,
                period_type=ReportingPeriodType.ANNUAL,
                fiscal_year=vp.fiscal_year,
                fiscal_quarter=None,
                start_date=period_start(vp.period_end),
                end_date=vp.period_end,
            )
        )
        document: FinancialDocument = await FinancialDocumentRepository(session).upsert(
            FinancialDocumentCreate(
                period_id=period.id,
                source_id=source.id,
                document_type=VENDOR_DOCUMENT_TYPE,
                document_url=page_url[:500],
                fiscal_year_end=vp.period_end,
                notes=notes,
            )
        )
        document.source_kind = "VENDOR"
        document.fetched_at = fetched_at

        validated = validator.validate(vp.candidates)
        for line in validated.lines:
            candidate = line.candidate
            if vp.currency != "EGP" and candidate.ext_status == ExtStatus.auto_validated.value:
                candidate.ext_status = ExtStatus.extraction_candidate.value
                candidate.ext_reason = (
                    f"NON_EGP_REPORTING_CURRENCY: {vp.currency} needs an FX policy first"
                )
        await lines.upsert_candidates(
            document_id=document.id,
            company_id=company.id,
            period_id=period.id,
            lines=[v.candidate for v in validated.lines],
        )
        summary.periods += 1
        for line in validated.lines:
            status = line.candidate.ext_status
            if status == ExtStatus.auto_validated.value:
                summary.auto_validated += 1
            elif status == ExtStatus.rejected.value:
                summary.rejected += 1
            else:
                summary.held += 1
    summary.companies += 1
    summary.company_ids.append(company.id)


async def import_directory(
    session: AsyncSession, directory: Path, tickers: list[str] | None = None
) -> ImportSummary:
    summary = ImportSummary()
    wanted = {t.upper() for t in tickers} if tickers else None
    for path in sorted(directory.glob("*.json")):
        if wanted is not None and path.stem.upper() not in wanted:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        await import_payload(session, payload, summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tickers", nargs="*", help="limit to these tickers")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument(
        "--no-recompute", action="store_true", help="skip the automatic snapshot recompute"
    )
    args = parser.parse_args()
    if not args.dir.exists():
        print(f"No vendor files at {args.dir}; nothing to import.")
        return 1

    async def _run() -> ImportSummary:
        from app.db.session import async_session_factory

        async with async_session_factory() as session:
            summary = await import_directory(session, args.dir, args.tickers or None)
            await session.commit()
            return summary

    s = asyncio.run(_run())
    print(
        f"Imported {s.companies} companies, {s.periods} fiscal years: "
        f"{s.auto_validated} lines validated, {s.rejected} rejected, {s.held} held for review."
    )
    if s.skipped:
        print(f"Skipped (no company row or no statements): {', '.join(s.skipped)}")
    if not args.no_recompute and s.company_ids:
        from app.services.recompute import after_statement_import

        print(asyncio.run(after_statement_import(s.company_ids)).summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
