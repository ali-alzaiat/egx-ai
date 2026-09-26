"""Document indexer for RAG pipeline.

Indexes financial facts, metrics, valuations, and screening results
as embedded chunks for retrieval.
"""

import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import ChunkTypeDB, DocumentChunk
from app.models.financial import FinancialFact
from app.models.market import Company
from app.models.metrics import FinancialMetric
from app.models.screening import ShariahScreeningResult
from app.models.valuation import ValuationResult

logger = logging.getLogger(__name__)


def _chunk_to_embedding_text(chunk_type: str, content: dict) -> str:
    """Convert chunk content to text suitable for embedding."""
    parts = []
    if content.get("company_name"):
        parts.append(f"Company: {content['company_name']}")
    if content.get("ticker"):
        parts.append(f"Ticker: {content['ticker']}")
    if content.get("label"):
        parts.append(content["label"])
    if content.get("value") is not None:
        parts.append(f"Value: {content['value']}")
    if content.get("reason"):
        parts.append(f"Reason: {content['reason']}")
    if content.get("context"):
        parts.append(content["context"])
    return " | ".join(parts) if parts else ""


class DocumentIndexer:
    """Indexes financial data as chunks for RAG retrieval."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def index_financial_facts(self, company_id: uuid.UUID) -> int:
        """Index financial facts as document chunks."""
        query = (
            select(FinancialFact)
            .where(FinancialFact.company_id == company_id)
            .order_by(FinancialFact.created_at.desc())
            .limit(200)
        )
        result = await self.session.execute(query)
        facts = result.scalars().all()

        company = await self._get_company(company_id)
        count = 0

        for fact in facts:
            ft = fact.fact_type
            fact_type_val = ft.value if hasattr(ft, 'value') else str(ft)
            content = {
                "company_name": company.name if company else None,
                "ticker": company.ticker if company else None,
                "label": fact.normalized_label or fact.reported_label,
                "value": str(fact.normalized_value or fact.reported_value),
                "currency": fact.currency,
                "status": fact.status.value if hasattr(fact.status, 'value') else str(fact.status),
                "fact_type": fact_type_val,
            }
            embedding_text = _chunk_to_embedding_text("financial_fact", content)

            chunk = DocumentChunk(
                company_id=company_id,
                document_id=fact.document_id,
                chunk_type=ChunkTypeDB.FINANCIAL_FACT,
                content=embedding_text,
                metadata_json=json.dumps(content),
            )
            self.session.add(chunk)
            count += 1

        await self.session.flush()
        logger.info("Indexed %d financial facts for company %s", count, company_id)
        return count

    async def index_financial_metrics(self, company_id: uuid.UUID) -> int:
        """Index financial metrics as document chunks."""
        query = (
            select(FinancialMetric)
            .where(FinancialMetric.company_id == company_id)
            .order_by(FinancialMetric.created_at.desc())
            .limit(100)
        )
        result = await self.session.execute(query)
        metrics = result.scalars().all()

        company = await self._get_company(company_id)
        count = 0

        for metric in metrics:
            st = metric.status
            status_val = st.value if hasattr(st, 'value') else str(st)
            content = {
                "company_name": company.name if company else None,
                "ticker": company.ticker if company else None,
                "label": metric.display_name,
                "value": str(metric.value) if metric.value else None,
                "status": status_val,
                "reason": metric.reason,
            }
            embedding_text = _chunk_to_embedding_text("metric", content)

            chunk = DocumentChunk(
                company_id=company_id,
                chunk_type=ChunkTypeDB.METRIC,
                content=embedding_text,
                metadata_json=json.dumps(content),
            )
            self.session.add(chunk)
            count += 1

        await self.session.flush()
        logger.info("Indexed %d financial metrics for company %s", count, company_id)
        return count

    async def index_valuations(self, company_id: uuid.UUID) -> int:
        """Index valuation results as document chunks."""
        query = (
            select(ValuationResult)
            .where(ValuationResult.company_id == company_id)
            .order_by(ValuationResult.created_at.desc())
            .limit(50)
        )
        result = await self.session.execute(query)
        valuations = result.scalars().all()

        company = await self._get_company(company_id)
        count = 0

        for val in valuations:
            model_val = val.model.value if hasattr(val.model, 'value') else val.model
            content = {
                "company_name": company.name if company else None,
                "ticker": company.ticker if company else None,
                "label": f"{model_val} valuation",
                "value": str(val.value) if val.value else None,
                "assumptions": val.assumptions,
                "reason": val.reason,
            }
            embedding_text = _chunk_to_embedding_text("valuation", content)

            chunk = DocumentChunk(
                company_id=company_id,
                chunk_type=ChunkTypeDB.VALUATION,
                content=embedding_text,
                metadata_json=json.dumps(content),
            )
            self.session.add(chunk)
            count += 1

        await self.session.flush()
        logger.info("Indexed %d valuations for company %s", count, company_id)
        return count

    async def index_screenings(self, company_id: uuid.UUID) -> int:
        """Index Shariah screening results as document chunks."""
        query = (
            select(ShariahScreeningResult)
            .where(ShariahScreeningResult.company_id == company_id)
            .order_by(ShariahScreeningResult.created_at.desc())
            .limit(50)
        )
        result = await self.session.execute(query)
        screenings = result.scalars().all()

        company = await self._get_company(company_id)
        count = 0

        for screen in screenings:
            compliance = "Compliant" if screen.is_compliant else "Non-compliant"
            content = {
                "company_name": company.name if company else None,
                "ticker": company.ticker if company else None,
                "label": f"Shariah screening: {compliance}",
                "value": compliance,
                "methodology": screen.methodology_version,
                "reason": screen.overall_reason,
            }
            embedding_text = _chunk_to_embedding_text("screening", content)

            chunk = DocumentChunk(
                company_id=company_id,
                chunk_type=ChunkTypeDB.SCREENING,
                content=embedding_text,
                metadata_json=json.dumps(content),
            )
            self.session.add(chunk)
            count += 1

        await self.session.flush()
        logger.info("Indexed %d screenings for company %s", count, company_id)
        return count

    async def index_company(self, company_id: uuid.UUID) -> dict[str, int]:
        """Index all data for a company."""
        return {
            "financial_facts": await self.index_financial_facts(company_id),
            "financial_metrics": await self.index_financial_metrics(company_id),
            "valuations": await self.index_valuations(company_id),
            "screenings": await self.index_screenings(company_id),
        }

    async def _get_company(self, company_id: uuid.UUID) -> Company | None:
        """Get company by ID."""
        result = await self.session.execute(
            select(Company).where(Company.id == company_id)
        )
        return result.scalar_one_or_none()
