"""Repositories for statement lines and raw document blobs (migration 019)."""

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Protocol

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import FinancialDocument
from app.models.statements import (
    ExtStatus,
    FinancialDocumentBlob,
    FinancialStatementLine,
)

CalculationStatuses = frozenset({ExtStatus.approved, ExtStatus.auto_validated})


class StatementLineLike(Protocol):
    """Structural type for extractor candidates going into the repository."""

    @property
    def ontology_code(self) -> str: ...

    @property
    def ontology_version(self) -> str: ...

    @property
    def value(self) -> Decimal | str | float | int | None: ...

    @property
    def currency(self) -> str: ...

    @property
    def source_label_reported(self) -> str | None: ...

    @property
    def source_label_en(self) -> str | None: ...

    @property
    def source_label_ar(self) -> str | None: ...

    @property
    def source_page(self) -> str | None: ...

    @property
    def extraction_method(self) -> str: ...

    @property
    def ext_status(self) -> str: ...

    @property
    def ext_reason(self) -> str | None: ...

    @property
    def published_date(self) -> object | None: ...


class StatementLineRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_candidates(
        self,
        document_id: uuid.UUID,
        company_id: uuid.UUID,
        period_id: uuid.UUID,
        lines: Sequence[StatementLineLike],
    ) -> int:
        """Idempotently replace this document's candidate/outcome rows.

        Re-running the pipeline on the same document hash replaces everything
        except rows already ``approved`` by Ops — those are never touched.
        """
        await self.session.execute(
            delete(FinancialStatementLine).where(
                FinancialStatementLine.source_document_id == document_id,
                FinancialStatementLine.ext_status != ExtStatus.approved,
            )
        )
        created = 0
        for line in lines:
            self.session.add(
                FinancialStatementLine(
                    company_id=company_id,
                    period_id=period_id,
                    ontology_code=line.ontology_code,
                    ontology_version=line.ontology_version,
                    value=line.value,
                    currency=line.currency,
                    source_document_id=document_id,
                    source_label_reported=line.source_label_reported,
                    source_label_en=line.source_label_en,
                    source_label_ar=line.source_label_ar,
                    source_page=line.source_page,
                    extraction_method=line.extraction_method,
                    ext_status=line.ext_status,
                    ext_reason=line.ext_reason,
                    published_date=line.published_date,
                )
            )
            created += 1
        await self.session.flush()
        return created

    async def latest_approved(self, company_id: uuid.UUID) -> list[FinancialStatementLine]:
        """Approved/auto_validated lines only, latest publication wins per key.

        Per ``(period_id, ontology_code)`` the row with the max ``published_date``
        wins; ties (same date) fall back to the newest ``created_at`` — and the
        result is deterministic in Postgres on that ordering. ``extraction_candidate``
        and ``rejected`` rows are always excluded (candidate-leakage invariant).
        """
        query = (
            select(FinancialStatementLine)
            .where(
                FinancialStatementLine.company_id == company_id,
                FinancialStatementLine.ext_status.in_(CalculationStatuses),
            )
            .order_by(
                FinancialStatementLine.period_id,
                FinancialStatementLine.ontology_code,
                FinancialStatementLine.published_date.desc().nulls_last(),
                FinancialStatementLine.created_at.desc(),
            )
        )
        rows = (await self.session.execute(query)).scalars().all()
        best: dict[tuple[uuid.UUID, str], FinancialStatementLine] = {}
        for row in rows:
            key = (row.period_id, row.ontology_code)
            if key not in best:
                best[key] = row
        return list(best.values())

    async def list_candidates(
        self,
        company_id: uuid.UUID | None = None,
        limit: int = 100,
    ) -> list[tuple[FinancialStatementLine, FinancialDocument]]:
        """Review queue: extraction_candidate rows with their source document."""
        query = (
            select(FinancialStatementLine, FinancialDocument)
            .join(
                FinancialDocument,
                FinancialStatementLine.source_document_id == FinancialDocument.id,
            )
            .where(FinancialStatementLine.ext_status == ExtStatus.extraction_candidate)
            .order_by(FinancialStatementLine.created_at.desc())
            .limit(limit)
        )
        if company_id is not None:
            query = query.where(FinancialStatementLine.company_id == company_id)
        return [(line, doc) for line, doc in (await self.session.execute(query)).all()]

    async def get(self, line_id: uuid.UUID) -> FinancialStatementLine | None:
        return await self.session.get(FinancialStatementLine, line_id)

    async def set_status(
        self,
        line_row: FinancialStatementLine,
        status: ExtStatus,
        reason: str | None = None,
    ) -> FinancialStatementLine:
        line_row.ext_status = status
        line_row.ext_reason = reason
        await self.session.flush()
        return line_row

    async def count_for_status(self, company_id: uuid.UUID, status: ExtStatus) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(FinancialStatementLine)
            .where(
                FinancialStatementLine.company_id == company_id,
                FinancialStatementLine.ext_status == status,
            )
        )
        return int(result.scalar_one())


class DocumentBlobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_hash(self, content_hash: str) -> FinancialDocumentBlob | None:
        result = await self.session.execute(
            select(FinancialDocumentBlob).where(
                FinancialDocumentBlob.content_hash == content_hash
            )
        )
        return result.scalar_one_or_none()

    async def get_for_document(
        self, document_id: uuid.UUID
    ) -> FinancialDocumentBlob | None:
        result = await self.session.execute(
            select(FinancialDocumentBlob).where(
                FinancialDocumentBlob.document_id == document_id
            )
        )
        return result.scalar_one_or_none()

    async def store(
        self,
        document_id: uuid.UUID,
        company_id: uuid.UUID,
        content_hash: str,
        content_type: str,
        content: bytes,
    ) -> FinancialDocumentBlob:
        existing = await self.get_by_hash(content_hash)
        if existing is not None:
            return existing
        blob = FinancialDocumentBlob(
            document_id=document_id,
            company_id=company_id,
            content_hash=content_hash,
            content_type=content_type,
            content=content,
        )
        self.session.add(blob)
        await self.session.flush()
        return blob
