"""Data-first gate: synthetic facts never count as real fundamentals."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dataquality.real_data import real_data_company_count
from app.models.financial import FinancialDocument, FinancialFact
from app.models.market import DataSource


async def test_synthetic_facts_do_not_count(
    db_session: AsyncSession, zero_value_facts: list[FinancialFact]
) -> None:
    baseline_ids = {f.company_id for f in zero_value_facts}
    assert len(baseline_ids) == 1
    # zero_value_facts come from a SYNTHETIC source: the gate must ignore them.
    before = await real_data_company_count(db_session)

    document = await db_session.get(FinancialDocument, zero_value_facts[0].document_id)
    assert document is not None
    source = (
        await db_session.execute(select(DataSource).where(DataSource.id == document.source_id))
    ).scalar_one()
    source.source_type = "COMPANY"  # same facts, now from a real company filing
    await db_session.flush()

    assert await real_data_company_count(db_session) == before + 1
