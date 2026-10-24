"""Seed helpers for R43 tests: approved statement lines and price bars.

Every number here is a SYNTHETIC test value; tests seed every row they need.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from app.models.financial import FinancialDocument, FinancialPeriod
from app.models.market import Company, CompanyStatus, DailyPrice, DataSource, DataSourceType
from app.models.statements import ExtractionMethod, ExtStatus, FinancialStatementLine
from app.statements.ontology import STATEMENT_ONTOLOGY_VERSION

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

#: A full, internally consistent synthetic year (EGP units).
FULL_YEAR: dict[str, Decimal] = {
    "revenue": Decimal("1000"),
    "cost_of_revenue": Decimal("600"),
    "gross_profit": Decimal("400"),
    "operating_profit": Decimal("250"),
    "net_income": Decimal("200"),
    "interest_income": Decimal("20"),
    "weighted_avg_shares_basic": Decimal("100"),
    "total_assets": Decimal("2000"),
    "current_assets": Decimal("800"),
    "cash_and_equivalents": Decimal("300"),
    "inventory": Decimal("100"),
    "total_liabilities": Decimal("900"),
    "current_liabilities": Decimal("400"),
    "interest_bearing_debt": Decimal("500"),
    "total_equity": Decimal("1100"),
    "shares_outstanding": Decimal("100"),
    "cfo": Decimal("300"),
    "capex": Decimal("-50"),
    "dividends_paid": Decimal("-80"),
}


async def make_company(session: AsyncSession, industry: str | None = None) -> Company:
    company = Company(
        id=uuid.uuid4(),
        ticker=f"R43_{uuid.uuid4().hex[:6].upper()}",
        isin=f"EG{uuid.uuid4().hex[:10].upper()}",
        name="R43 Test Co",
        currency="EGP",
        industry=industry,
        status=CompanyStatus.ACTIVE,
    )
    session.add(company)
    await session.flush()
    return company


async def seed_year(
    session: AsyncSession,
    company: Company,
    fiscal_year: int,
    values: dict[str, Decimal],
    *,
    tier: str = "vendor",
    published: date | None = None,
    status: ExtStatus = ExtStatus.auto_validated,
    page: str | None = None,
) -> dict[str, FinancialStatementLine]:
    """One ANNUAL period (calendar year) with one document and its lines."""
    from sqlalchemy import select

    period = (
        await session.execute(
            select(FinancialPeriod).where(
                FinancialPeriod.company_id == company.id,
                FinancialPeriod.fiscal_year == fiscal_year,
            )
        )
    ).scalar_one_or_none()
    if period is None:
        period = FinancialPeriod(
            id=uuid.uuid4(),
            company_id=company.id,
            period_type="ANNUAL",
            fiscal_year=fiscal_year,
            start_date=date(fiscal_year, 1, 1),
            end_date=date(fiscal_year, 12, 31),
        )
        session.add(period)
        await session.flush()
    source = DataSource(
        id=uuid.uuid4(),
        name=f"R43 {tier} {uuid.uuid4().hex[:8]}",
        source_type=DataSourceType.DATA_PROVIDER if tier == "vendor" else DataSourceType.EGX,
    )
    session.add(source)
    await session.flush()
    document = FinancialDocument(
        id=uuid.uuid4(),
        period_id=period.id,
        source_id=source.id,
        document_type="VENDOR_ANNUAL_STATEMENTS" if tier == "vendor" else "ANNUAL_FILING",
        document_url=f"https://example.test/{company.ticker}/{fiscal_year}/{tier}",
        publication_date=published,
        document_status="ORIGINAL",
    )
    session.add(document)
    await session.flush()
    method = (
        ExtractionMethod.vendor_aggregator if tier == "vendor" else ExtractionMethod.manual_seed
    )
    out: dict[str, FinancialStatementLine] = {}
    for code, value in values.items():
        row = FinancialStatementLine(
            id=uuid.uuid4(),
            period_id=period.id,
            company_id=company.id,
            ontology_code=code,
            ontology_version=STATEMENT_ONTOLOGY_VERSION,
            value=value,
            currency="EGP",
            source_document_id=document.id,
            source_label_reported=code,
            source_page=page,
            extraction_method=method,
            ext_status=status,
            published_date=published,
        )
        session.add(row)
        out[code] = row
    await session.flush()
    return out


async def seed_prices(
    session: AsyncSession, company: Company, bars: int = 220, start: Decimal = Decimal("10")
) -> date:
    """Rising synthetic daily bars ending today; returns the last bar date."""
    source = DataSource(
        id=uuid.uuid4(),
        name=f"R43 prices {uuid.uuid4().hex[:8]}",
        source_type=DataSourceType.DATA_PROVIDER,
    )
    session.add(source)
    await session.flush()
    last = date.today()
    for i in range(bars):
        day = last - timedelta(days=bars - 1 - i)
        close = start + Decimal(i) / Decimal("10")
        session.add(
            DailyPrice(
                id=uuid.uuid4(),
                company_id=company.id,
                date=day,
                open=close,
                high=close + Decimal("0.5"),
                low=close - Decimal("0.5"),
                close=close,
                volume=100000 + i,
                source_id=source.id,
            )
        )
    await session.flush()
    return last
