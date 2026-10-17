"""Statement pipeline: blob -> extract -> validate -> candidates (idempotent)."""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import FinancialDocument
from app.repositories.statements import (
    DocumentBlobRepository,
    StatementLineRepository,
)
from app.statements.extractor import ExtractionResult, StatementExtractor
from app.statements.validator import StatementValidator

logger = logging.getLogger(__name__)


@dataclass
class PipelineSummary:
    candidates_extracted: int
    auto_validated: int
    rejected: int
    drops: int


class StatementPipeline:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def process_document(self, document_id: uuid.UUID) -> PipelineSummary:
        """Run extract -> validate -> persist candidates for one document.

        Idempotent: re-running on the same document replaces its non-approved
        candidate rows (approved rows are never touched). Candidate lines carry
        the document's publication date so calculations pick the latest
        publication per (period, code).
        """
        blob = await DocumentBlobRepository(self.session).get_for_document(document_id)
        if blob is None:
            raise LookupError(f"no blob stored for document {document_id}")
        document = await self.session.get(FinancialDocument, document_id)
        if document is None:
            raise LookupError(f"document {document_id} not found")

        extractor = StatementExtractor()
        extraction: ExtractionResult = extractor.extract(
            blob.content, blob.content_type, document.document_type
        )
        for candidate in extraction.candidates:
            candidate.published_date = document.publication_date or document.filing_date

        validated = StatementValidator().validate(extraction.candidates)
        repo = StatementLineRepository(self.session)
        created = await repo.upsert_candidates(
            document_id=document.id,
            company_id=blob.company_id,
            period_id=document.period_id,
            lines=[v.candidate for v in validated.lines],
        )
        await self.session.commit()
        logger.info(
            "statement_pipeline_processed document=%s extracted=%s rejected=%s drops=%s",
            document_id,
            len(extraction.candidates),
            validated.rejected_count,
            len(extraction.drops),
        )
        return PipelineSummary(
            candidates_extracted=created,
            auto_validated=validated.auto_validated_count,
            rejected=validated.rejected_count,
            drops=len(extraction.drops),
        )
