"""Pinning tests for valuation chunk indexing (ruling R11)."""

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.document_indexer import DocumentIndexer
from app.models.ai import ChunkTypeDB, DocumentChunk
from app.models.valuation import ValuationModelDB, ValuationResult, ValuationStatusDB


@pytest.mark.asyncio
async def test_zero_valuation_indexes_as_zero(
    db_session: AsyncSession, test_company
) -> None:
    """A valuation of 0 indexes as "0"; a missing one stays None — never falsy-dropped."""
    db_session.add(
        ValuationResult(
            id=uuid.uuid4(),
            company_id=test_company.id,
            model=ValuationModelDB.PE,
            value=Decimal("0"),
            status=ValuationStatusDB.AVAILABLE,
            calculated_at=datetime.now(UTC),
        )
    )
    db_session.add(
        ValuationResult(
            id=uuid.uuid4(),
            company_id=test_company.id,
            model=ValuationModelDB.PB,
            value=None,
            status=ValuationStatusDB.INSUFFICIENT_DATA,
            reason="no earnings data",
            calculated_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    indexer = DocumentIndexer(db_session)
    count = await indexer.index_valuations(test_company.id)
    assert count == 2

    chunks = (
        await db_session.execute(
            select(DocumentChunk).where(
                DocumentChunk.company_id == test_company.id,
                DocumentChunk.chunk_type == ChunkTypeDB.VALUATION,
            )
        )
    ).scalars().all()
    metadata = [json.loads(c.metadata_json) for c in chunks]

    zero = next(m for m in metadata if m["label"] == "price_to_earnings valuation")
    missing = next(m for m in metadata if m["label"] == "price_to_book valuation")

    assert zero["value"] is not None
    assert Decimal(zero["value"]) == Decimal("0")
    assert missing["value"] is None
