"""Review-queue API tests (client fixture over ASGITransport)."""

import uuid
from datetime import date
from hashlib import sha256

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import FinancialDocument, FinancialPeriod, ReportingPeriodType
from app.models.market import Company, CompanyStatus, DataSource, DataSourceType
from app.repositories.statements import DocumentBlobRepository
from app.statements.pipeline import StatementPipeline

pytestmark = pytest.mark.asyncio

XML = b"""<?xml version="1.0"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance">
  <line item="Total Assets" decimals="-2">700000</line>
  <line item="Total Liabilities" decimals="-2">200000</line>
  <line item="Total Equity" decimals="-2">500000</line>
  <line item="EPS" decimals="-2">1.25</line>
</xbrli:xbrl>"""


async def _confidence_seed(
    db_session: AsyncSession,
) -> tuple[Company, FinancialDocument, FinancialPeriod]:
    company = Company(
        id=uuid.uuid4(),
        ticker=f"RVQ_{uuid.uuid4().hex[:6].upper()}",
        isin=f"EG{uuid.uuid4().hex[:10].upper()}",
        name="Review Co",
        currency="EGP",
        status=CompanyStatus.ACTIVE,
    )
    db_session.add(company)
    await db_session.flush()
    source = DataSource(name=f"RV_SRC_{uuid.uuid4().hex[:8]}", source_type=DataSourceType.EGX)
    db_session.add(source)
    await db_session.flush()
    period = FinancialPeriod(
        company_id=company.id,
        period_type=ReportingPeriodType.ANNUAL,
        fiscal_year=2024,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    db_session.add(period)
    await db_session.flush()
    document = FinancialDocument(
        period_id=period.id,
        source_id=source.id,
        document_type="annual_report",
        document_url="https://feed.test/review.xml",
        publication_date=date(2024, 12, 31),
    )
    db_session.add(document)
    await db_session.flush()
    await DocumentBlobRepository(db_session).store(
        document_id=document.id,
        company_id=company.id,
        content_hash=sha256(XML).hexdigest(),
        content_type="application/xml",
        content=XML,
    )
    document.content_hash = sha256(XML).hexdigest()
    await db_session.flush()
    return company, document, period


class TestReviewQueueApi:
    async def test_queue_lists_candidates_with_provenance(
        self, client, db_session: AsyncSession
    ) -> None:
        company, document, _period = await _confidence_seed(db_session)
        await StatementPipeline(db_session).process_document(document.id)
        response = await client.get(
            f"/api/statements/review-queue?company_id={company.id}"
        )
        assert response.status_code == 200
        items = response.json()
        assert len(items) >= 1
        assert any(item["ontology_code"] == "eps" for item in items)
        eps_item = next(i for i in items if i["ontology_code"] == "eps")
        assert eps_item["document_url"] == "https://feed.test/review.xml"
        assert eps_item["source_label_reported"] == "EPS"
        assert eps_item["value"] == "1.2500"

    async def test_approve_moves_line_to_approved_stream(
        self, client, db_session: AsyncSession
    ) -> None:
        company, document, _period = await _confidence_seed(db_session)
        await StatementPipeline(db_session).process_document(document.id)
        queue = (await client.get(f"/api/statements/review-queue?company_id={company.id}")).json()
        line_id = queue[0]["id"]
        response = await client.post(f"/api/statements/lines/{line_id}/approve")
        assert response.status_code == 200
        assert response.json()["ext_status"] == "approved"
        # gone from queue
        queue_after = (
            await client.get(f"/api/statements/review-queue?company_id={company.id}")
        ).json()
        assert queue_after == []

    async def test_approve_twice_conflicts(self, client, db_session: AsyncSession) -> None:
        company, document, _period = await _confidence_seed(db_session)
        await StatementPipeline(db_session).process_document(document.id)
        queue = (await client.get(f"/api/statements/review-queue?company_id={company.id}")).json()
        line_id = queue[0]["id"]
        first = await client.post(f"/api/statements/lines/{line_id}/approve")
        assert first.status_code == 200
        second = await client.post(f"/api/statements/lines/{line_id}/approve")
        assert second.status_code == 409

    async def test_reject_records_reason(self, client, db_session: AsyncSession) -> None:
        company, document, _period = await _confidence_seed(db_session)
        await StatementPipeline(db_session).process_document(document.id)
        queue = (await client.get(f"/api/statements/review-queue?company_id={company.id}")).json()
        line_id = queue[0]["id"]
        response = await client.post(
            f"/api/statements/lines/{line_id}/reject", json={"reason": "misplaced"}
        )
        assert response.status_code == 200
        assert response.json()["ext_status"] == "rejected"
        assert response.json()["ext_reason"] == "misplaced"

    async def test_unknown_line_404(self, client) -> None:
        response = await client.post(
            f"/api/statements/lines/{uuid.uuid4()}/approve"
        )
        assert response.status_code == 404
