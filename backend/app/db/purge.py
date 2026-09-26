"""Maintenance commands for the local development database.

Usage:
    python -m app.db.purge --status        # what is actually in the database
    python -m app.db.purge --synthetic     # drop SYNTHETIC sources and their rows
    python -m app.db.purge --test-companies  # drop leaked TEST_* / hex-ticker companies
    python -m app.db.purge --all-prices    # drop every daily price row
    python -m app.db.purge --reset         # drop all derived + financial analysis data
"""

import argparse
import asyncio
import logging
import re
import uuid

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.ai import AIAnalysis, DocumentChunk
from app.models.financial import FinancialDocument, FinancialFact, FinancialPeriod
from app.models.market import Company, DailyPrice, DataSource, DataSourceType
from app.models.metrics import FinancialMetric, FinancialMetricInput
from app.models.screening import ScreeningRuleResultDB, ShariahScreeningResult
from app.models.technical import TechnicalIndicator
from app.models.valuation import ValuationResult

logger = logging.getLogger(__name__)

# Fixtures used ISIN-shaped tickers (T + 8..12 hex chars) and TEST_-prefixed tickers.
TEST_TICKER_RE = re.compile(r"^TEST_[0-9A-F]{1,12}$|^T[0-9A-F]{8,12}$")


async def _delete_by_source(session: AsyncSession, source_ids: list[uuid.UUID]) -> None:
    """Delete every row that references the given data sources, in FK-safe order."""
    if not source_ids:
        return
    await session.execute(
        delete(FinancialDocument).where(FinancialDocument.source_id.in_(source_ids))
    )
    await session.execute(
        delete(DailyPrice).where(DailyPrice.source_id.in_(source_ids))
    )
    await session.execute(delete(DataSource).where(DataSource.id.in_(source_ids)))


async def purge_synthetic() -> int:
    """Delete data sources tagged SYNTHETIC and everything that references them."""
    async with async_session_factory() as session:
        source_ids = (
            await session.execute(
                select(DataSource.id).where(DataSource.source_type == DataSourceType.SYNTHETIC)
            )
        ).scalars().all()

        if not source_ids:
            logger.info("No SYNTHETIC data sources found; nothing to purge")
            return 0

        await _delete_by_source(session, list(source_ids))
        await session.commit()
        logger.info("Purged %d SYNTHETIC data sources and their rows", len(source_ids))
        return len(source_ids)


async def purge_test_companies() -> int:
    """Delete companies left behind by test fixtures, with all dependent rows."""
    async with async_session_factory() as session:
        companies = (
            await session.execute(select(Company))
        ).scalars().all()
        doomed = [c.id for c in companies if TEST_TICKER_RE.match(c.ticker or "")]
        if not doomed:
            logger.info("No leaked test companies found")
            return 0

        await session.execute(
            delete(ScreeningRuleResultDB).where(
                ScreeningRuleResultDB.screening_result_id.in_(
                    select(ShariahScreeningResult.id).where(
                        ShariahScreeningResult.company_id.in_(doomed)
                    )
                )
            )
        )
        await session.execute(
            delete(ShariahScreeningResult).where(ShariahScreeningResult.company_id.in_(doomed))
        )
        await session.execute(
            delete(ValuationResult).where(ValuationResult.company_id.in_(doomed))
        )
        await session.execute(
            delete(TechnicalIndicator).where(TechnicalIndicator.company_id.in_(doomed))
        )
        await session.execute(delete(DocumentChunk).where(DocumentChunk.company_id.in_(doomed)))
        await session.execute(delete(AIAnalysis).where(AIAnalysis.company_id.in_(doomed)))

        period_ids = (
            await session.execute(
                select(FinancialPeriod.id).where(FinancialPeriod.company_id.in_(doomed))
            )
        ).scalars().all()
        metric_ids = (
            await session.execute(
                select(FinancialMetric.id).where(FinancialMetric.company_id.in_(doomed))
            )
        ).scalars().all()
        await session.execute(
            delete(FinancialMetricInput).where(FinancialMetricInput.metric_id.in_(metric_ids))
        )
        await session.execute(
            delete(FinancialMetric).where(FinancialMetric.company_id.in_(doomed))
        )
        await session.execute(
            delete(FinancialFact).where(FinancialFact.period_id.in_(period_ids))
        )
        await session.execute(
            delete(FinancialDocument).where(FinancialDocument.period_id.in_(period_ids))
        )
        await session.execute(
            delete(FinancialPeriod).where(FinancialPeriod.company_id.in_(doomed))
        )
        await session.execute(delete(DailyPrice).where(DailyPrice.company_id.in_(doomed)))
        await session.execute(delete(Company).where(Company.id.in_(doomed)))
        await session.commit()
        logger.info("Purged %d leaked test companies", len(doomed))
        return len(doomed)


async def purge_all_prices() -> int:
    """Delete every daily price row, leaving the company universe intact."""
    async with async_session_factory() as session:
        count = (await session.execute(select(func.count(DailyPrice.id)))).scalar_one()
        await session.execute(delete(DailyPrice))
        await session.commit()
        logger.info("Purged %d daily price rows", count)
        return count


async def reset_derived() -> None:
    """Drop all analysis output: indicators, signals, valuation, screening, AI, financial."""
    async with async_session_factory() as session:
        for model in (
            ScreeningRuleResultDB,
            ShariahScreeningResult,
            ValuationResult,
            TechnicalIndicator,
            AIAnalysis,
            DocumentChunk,
            FinancialMetricInput,
            FinancialMetric,
            FinancialFact,
            FinancialDocument,
            FinancialPeriod,
        ):
            await session.execute(delete(model))

        financial_sources = (
            await session.execute(
                select(DataSource.id).where(
                    or_(
                        DataSource.source_type == DataSourceType.SYNTHETIC,
                        DataSource.name.in_(("SYNTHETIC_FINANCIALS",)),
                    )
                )
            )
        ).scalars().all()
        await session.execute(delete(DataSource).where(DataSource.id.in_(financial_sources)))
        await session.commit()
        logger.info("Reset all derived analysis and financial data")


async def show_status() -> None:
    """Print a summary of what is currently in the database."""
    async with async_session_factory() as session:
        companies = (await session.execute(select(func.count(Company.id)))).scalar_one()
        with_prices = (
            await session.execute(select(func.count(func.distinct(DailyPrice.company_id))))
        ).scalar_one()
        prices = (await session.execute(select(func.count(DailyPrice.id)))).scalar_one()
        sources = (
            await session.execute(
                select(DataSource.source_type, func.count(DataSource.id)).group_by(
                    DataSource.source_type
                )
            )
        ).all()

        print(f"companies      : {companies}")
        print(f"with prices    : {with_prices}")
        print(f"price rows     : {prices}")
        print(f"data sources   : {dict(sources)}")

        junk = (
            await session.execute(select(Company.ticker).where(Company.ticker.like("TEST\\_%"))
        )
        ).scalars().all()
        print(f"test tickers   : {len(junk)}")

        gaps = (
            await session.execute(
                select(Company.ticker)
                .outerjoin(DailyPrice, DailyPrice.company_id == Company.id)
                .where(DailyPrice.id.is_(None))
                .order_by(Company.ticker)
            )
        ).scalars().all()
        print(f"no price data  : {len(gaps)}")

        undated = (
            await session.execute(
                select(func.count(Company.id)).where(Company.name == Company.ticker)
            )
        ).scalar_one()
        print(f"missing name   : {undated}")

        last = await session.execute(text("select version_num from alembic_version"))
        print(f"alembic head   : {last.scalar()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Local database maintenance")
    parser.add_argument("--synthetic", action="store_true", help="Purge SYNTHETIC data")
    parser.add_argument(
        "--test-companies", action="store_true", help="Purge leaked test companies"
    )
    parser.add_argument("--all-prices", action="store_true", help="Purge all price rows")
    parser.add_argument("--reset", action="store_true", help="Purge all derived analysis data")
    parser.add_argument("--status", action="store_true", help="Show database summary")
    args = parser.parse_args()

    if not any(
        [args.synthetic, args.test_companies, args.all_prices, args.reset, args.status]
    ):
        parser.error(
            "choose at least one of --status, --synthetic, --test-companies, "
            "--all-prices, --reset"
        )

    async def run() -> None:
        if args.status:
            await show_status()
        if args.synthetic:
            await purge_synthetic()
        if args.test_companies:
            await purge_test_companies()
        if args.all_prices:
            await purge_all_prices()
        if args.reset:
            await reset_derived()

    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())


if __name__ == "__main__":
    main()
