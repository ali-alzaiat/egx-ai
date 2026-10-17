"""Tests for the statement pipeline (topics: idempotency, supersession)."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import (
    FinancialDocument,
    FinancialPeriod,
    ReportingPeriodType,
)
from app.models.market import Company, CompanyStatus, DataSource, DataSourceType
from app.models.statements import ExtStatus, FinancialStatementLine
from app.repositories.statements import StatementLineRepository
from app.statements.pipeline import StatementPipeline

pytestmark = pytest.mark.asyncio


async def _seed_document(
    db_session: AsyncSession,
    *,
    content: bytes,
    period_type: ReportingPeriodType = ReportingPeriodType.ANNUAL,
    fiscal_year: int = 2024,
) -> tuple[Company, FinancialDocument]:
    company = Company(
        id=uuid.uuid4(),
        ticker=f"PLN_{uuid.uuid4().hex[:6].upper()}",
        isin=f"EG{uuid.uuid4().hex[:10].upper()}",
        name="Pipeline Co",
        currency="EGP",
        status=CompanyStatus.ACTIVE,
    )
    db_session.add(company)
    await db_session.flush()
    source = DataSource(name=f"PL_SRC_{uuid.uuid4().hex[:8]}", source_type=DataSourceType.EGX)
    db_session.add(source)
    await db_session.flush()
    from datetime import date as _date

    period = FinancialPeriod(
        company_id=company.id,
        period_type=period_type,
        fiscal_year=fiscal_year,
        start_date=_date(fiscal_year, 1, 1),
        end_date=_date(fiscal_year, 12, 31),
    )
    db_session.add(period)
    await db_session.flush()
    document = FinancialDocument(
        period_id=period.id,
        source_id=source.id,
        document_type="annual_report",
        document_url="https://feed.test/report.xml",
        content_hash=None,
    )
    db_session.add(document)
    await db_session.flush()

    from hashlib import sha256

    from app.repositories.statements import DocumentBlobRepository

    blob_repo = DocumentBlobRepository(db_session)
    await blob_repo.store(
        document_id=document.id,
        company_id=company.id,
        content_hash=sha256(content).hexdigest(),
        content_type="application/xml",
        content=content,
    )
    document.content_hash = sha256(content).hexdigest()
    await db_session.flush()
    return company, document


EN_XML = b"""<?xml version="1.0"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance">
  <line item="Total Assets" unitRef="EGP" decimals="-2">700000</line>
  <line item="Total Liabilities" unitRef="EGP" decimals="-2">200000</line>
  <line item="Total Equity" unitRef="EGP" decimals="-2">500000</line>
</xbrli:xbrl>"""

RESTATEMENT_XML = b"""<?xml version="1.0"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance">
  <line item="Total Assets" unitRef="EGP" decimals="-2">705000</line>
  <line item="Total Liabilities" unitRef="EGP" decimals="-2">205000</line>
  <line item="Total Equity" unitRef="EGP" decimals="-2">500000</line>
</xbrli:xbrl>"""


class TestPipeline:
    async def test_process_document_creates_approved_stream(
        self, db_session: AsyncSession
    ) -> None:
        company, document = await _seed_document(db_session, content=EN_XML)
        summary = await StatementPipeline(db_session).process_document(document.id)
        assert summary.candidates_extracted == 3
        assert summary.auto_validated == 3
        assert summary.rejected == 0
        repo = StatementLineRepository(db_session)
        approved = await repo.latest_approved(company.id)
        assert {row.ontology_code for row in approved} == {
            "total_assets", "total_liabilities", "total_equity",
        }

    async def test_rerun_is_idempotent(self, db_session: AsyncSession) -> None:
        company, document = await _seed_document(db_session, content=EN_XML)
        pipeline = StatementPipeline(db_session)
        first = await pipeline.process_document(document.id)
        second = await pipeline.process_document(document.id)
        assert second.auto_validated == first.auto_validated
        rows = (
            await db_session.execute(
                select(FinancialStatementLine).where(
                    FinancialStatementLine.company_id == company.id
                )
            )
        ).scalars().all()
        assert len(rows) == first.auto_validated  # no duplicates

    async def test_candidates_excluded_from_latest_approved(
        self, db_session: AsyncSession
    ) -> None:
        # Review Focus #3: candidate (EPS, no share count) never in stream.
        company, document = await _seed_document(db_session, content=EPS_XML)
        summary = await StatementPipeline(db_session).process_document(document.id)
        assert summary.candidates_extracted > summary.auto_validated
        repo = StatementLineRepository(db_session)
        approved = await repo.latest_approved(company.id)
        candidates = await repo.count_for_status(company.id, ExtStatus.extraction_candidate)
        assert candidates >= 1
        assert all(row.ontology_code != "eps" for row in approved)


EPS_XML = b"""<?xml version="1.0"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance">
  <line item="Total Assets" unitRef="EGP" decimals="-2">700000</line>
  <line item="Total Liabilities" unitRef="EGP" decimals="-2">200000</line>
  <line item="Total Equity" unitRef="EGP" decimals="-2">500000</line>
  <line item="EPS" unitRef="EGP" decimals="-2">1.25</line>
</xbrli:xbrl>"""

class TestSupersession:
    async def test_restatement_latest_wins(self, db_session: AsyncSession) -> None:
        company, document = await _seed_document(db_session, content=EN_XML)
        pipeline = StatementPipeline(db_session)
        await pipeline.process_document(document.id)

        # Second document for the SAME period restates assets.
        source2 = DataSource(name=f"PL_SRC_{uuid.uuid4().hex[:8]}", source_type=DataSourceType.EGX)
        db_session.add(source2)
        await db_session.flush()
        from datetime import date

        from app.models.financial import FinancialDocument as FD
        period_id = (
            await db_session.execute(
                select(FinancialPeriod).where(FinancialPeriod.company_id == company.id)
            )
        ).scalars().first().id
        restated_doc = FD(
            period_id=period_id,
            source_id=source2.id,
            document_type="annual_report",
            document_url="https://feed.test/report-restated.xml",
            publication_date=date(2025, 1, 15),
        )
        db_session.add(restated_doc)
        await db_session.flush()
        from hashlib import sha256

        from app.repositories.statements import DocumentBlobRepository

        await DocumentBlobRepository(db_session).store(
            document_id=restated_doc.id,
            company_id=company.id,
            content_hash=sha256(RESTATEMENT_XML).hexdigest(),
            content_type="application/xml",
            content=RESTATEMENT_XML,
        )
        restated_doc.content_hash = sha256(RESTATEMENT_XML).hexdigest()
        original_doc = (
            await db_session.execute(select(FD).where(FD.document_url == "https://feed.test/report.xml"))
        ).scalar_one()
        original_doc.publication_date = date(2024, 12, 31)
        await db_session.flush()

        await pipeline.process_document(restated_doc.id)
        approved = await StatementLineRepository(db_session).latest_approved(company.id)
        by_code = {row.ontology_code: row for row in approved}
        assert by_code["total_assets"].value == Decimal("705000.0000")
        assert by_code["total_assets"].source_document_id == restated_doc.id
