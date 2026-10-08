"""Persistence round-trip for the data_quality_assessments model."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.data_quality import DataQualityAssessment, DataQualityStatusDB
from app.models.market import DataSource, DataSourceType


def _assessment(company_id: uuid.UUID, source_id: uuid.UUID) -> DataQualityAssessment:
    return DataQualityAssessment(
        id=uuid.uuid4(),
        company_id=company_id,
        scope="price_history",
        as_of=date(2026, 10, 8),
        score=Decimal("87.50"),
        status=DataQualityStatusDB.OK,
        components=[{"key": "completeness", "score": 100.0, "weight": 0.3}],
        issues=[],
        methodology_version="1.0",
        source_id=source_id,
        computed_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_model_roundtrip(db_session, test_company) -> None:
    source = DataSource(
        id=uuid.uuid4(),
        name=f"DQ Source {uuid.uuid4().hex[:8]}",
        source_type=DataSourceType.EGX,
    )
    db_session.add(source)
    await db_session.flush()

    assessment = _assessment(test_company.id, source.id)
    db_session.add(assessment)
    await db_session.flush()
    db_session.expunge(assessment)

    row = (
        await db_session.execute(
            select(DataQualityAssessment).where(
                DataQualityAssessment.id == assessment.id
            )
        )
    ).scalar_one()
    assert row.company_id == test_company.id
    assert row.scope == "price_history"
    assert row.as_of == date(2026, 10, 8)
    assert row.score == Decimal("87.50")
    assert row.status == DataQualityStatusDB.OK
    assert row.status.value == "OK"
    assert row.components == [{"key": "completeness", "score": 100.0, "weight": 0.3}]
    assert row.issues == []
    assert row.methodology_version == "1.0"
    assert row.source_id == source.id
    assert row.computed_at is not None
    assert row.created_at is not None

    # Duplicate (company_id, scope, as_of, methodology_version) must be rejected
    # by uq_data_quality_assessment.
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(_assessment(test_company.id, source.id))
            await db_session.flush()
