"""Persistence round-trip for the data_quality_assessments model."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dataquality.service import DataQualityService
from app.models.data_quality import DataQualityAssessment, DataQualityStatusDB
from app.models.financial import FinancialDocument, FinancialFact, FinancialPeriod
from app.models.market import Company, DailyPrice, DataSource, DataSourceType


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


# ---------------------------------------------------------------------------
# Task 5: assessment service + API
# ---------------------------------------------------------------------------

EXPECTED_SCALE = "0-100; higher is better; status MISSING|DEGRADED|POOR|OK"
EXPECTED_DISCLAIMER = (
    "Data quality describes the available inputs. "
    "It is not an assessment of the company."
)


async def test_assess_and_get_roundtrip(
    client: AsyncClient, test_company: Company
) -> None:
    response = await client.post(
        f"/api/data-quality/companies/{test_company.id}/assess"
        "?scope=price_history&as_of=2026-10-08"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scope"] == "price_history"
    assert body["scale"] == EXPECTED_SCALE
    assert body["disclaimer"] == EXPECTED_DISCLAIMER
    assert body["methodology_version"] == "1.0"

    listing = await client.get(
        f"/api/data-quality/companies/{test_company.id}?scope=price_history"
    )
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["methodology_version"] == "1.0"
    assert payload["scale"] == EXPECTED_SCALE
    assert payload["disclaimer"] == EXPECTED_DISCLAIMER
    assert len(payload["items"]) == 1
    assert payload["items"][0]["scope"] == "price_history"
    # R12.2: "check not run" reaches the persisted issues.
    assert any(
        "check not run" in issue for issue in payload["items"][0]["issues"]
    )


async def test_get_never_assessed_returns_empty_items(
    client: AsyncClient, test_company: Company
) -> None:
    response = await client.get(f"/api/data-quality/companies/{test_company.id}")
    assert response.status_code == 200
    assert response.json()["items"] == []


async def test_unknown_company_404(client: AsyncClient) -> None:
    missing = uuid.uuid4()
    get_response = await client.get(f"/api/data-quality/companies/{missing}")
    assert get_response.status_code == 404
    post_response = await client.post(
        f"/api/data-quality/companies/{missing}/assess?scope=price_history"
    )
    assert post_response.status_code == 404


async def test_reassess_is_idempotent(
    client: AsyncClient, db_session: AsyncSession, test_company: Company
) -> None:
    url = (
        f"/api/data-quality/companies/{test_company.id}/assess"
        "?scope=price_history&as_of=2026-10-08"
    )
    first = await client.post(url)
    second = await client.post(url)
    assert first.status_code == 200
    assert second.status_code == 200

    rows = (
        await db_session.execute(
            select(DataQualityAssessment).where(
                DataQualityAssessment.company_id == test_company.id
            )
        )
    ).scalars().all()
    assert len(rows) == 1


async def test_scope_filter_returns_single_scope(
    client: AsyncClient, test_company: Company
) -> None:
    await client.post(
        f"/api/data-quality/companies/{test_company.id}/assess"
        "?scope=price_history&as_of=2026-10-08"
    )
    await client.post(
        f"/api/data-quality/companies/{test_company.id}/assess"
        "?scope=company_profile&as_of=2026-10-08"
    )

    all_scopes = await client.get(
        f"/api/data-quality/companies/{test_company.id}"
    )
    assert {item["scope"] for item in all_scopes.json()["items"]} == {
        "price_history",
        "company_profile",
    }

    filtered = await client.get(
        f"/api/data-quality/companies/{test_company.id}?scope=company_profile"
    )
    scopes = [item["scope"] for item in filtered.json()["items"]]
    assert scopes == ["company_profile"]


async def test_different_methodology_version_is_separate_row(
    db_session: AsyncSession, test_company: Company
) -> None:
    service = DataQualityService(db_session)
    await service.assess(test_company.id, "price_history", date(2026, 10, 8))

    # A second methodology version is a distinct row and is returned when asked.
    v2 = DataQualityAssessment(
        id=uuid.uuid4(),
        company_id=test_company.id,
        scope="price_history",
        as_of=date(2026, 10, 8),
        score=Decimal("42.00"),
        status=DataQualityStatusDB.POOR,
        components=[],
        issues=[],
        methodology_version="2.0",
        computed_at=datetime.now(UTC),
    )
    db_session.add(v2)
    await db_session.flush()

    default = await service.latest(test_company.id, "price_history")
    assert default is not None
    assert default.methodology_version == "1.0"

    explicit = await service.latest(
        test_company.id, "price_history", methodology_version="2.0"
    )
    assert explicit is not None
    assert explicit.methodology_version == "2.0"
    assert explicit.score == 42.0


async def test_screening_embeds_data_quality(
    client: AsyncClient, test_company: Company
) -> None:
    # A screening result must exist before the embedded field is served.
    screened = await client.post(
        f"/api/screening/companies/{test_company.id}/screen"
    )
    assert screened.status_code == 200

    before = await client.get(f"/api/screening/companies/{test_company.id}")
    assert before.status_code == 200
    assert before.json()["data_quality"] is None

    assessed = await client.post(
        f"/api/data-quality/companies/{test_company.id}/assess"
        "?scope=financial_statements&as_of=2026-10-08"
    )
    assert assessed.status_code == 200

    after = await client.get(f"/api/screening/companies/{test_company.id}")
    embedded = after.json()["data_quality"]
    assert embedded is not None
    assert embedded["scope"] == "financial_statements"
    assert "status" in embedded
    # R12.1: scale/disclaimer are scoped to the two data-quality routes.
    assert "scale" not in embedded
    assert "disclaimer" not in embedded


async def test_financial_statements_freshness_reason_has_date(
    client: AsyncClient, db_session: AsyncSession, test_company: Company
) -> None:
    source = DataSource(
        id=uuid.uuid4(),
        name=f"Filing Source {uuid.uuid4().hex[:8]}",
        source_type=DataSourceType.COMPANY,
    )
    db_session.add(source)
    await db_session.flush()

    period = FinancialPeriod(
        id=uuid.uuid4(),
        company_id=test_company.id,
        period_type="ANNUAL",
        fiscal_year=2024,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    db_session.add(period)
    await db_session.flush()

    document = FinancialDocument(
        id=uuid.uuid4(),
        period_id=period.id,
        source_id=source.id,
        document_type="ANNUAL_REPORT",
        document_status="ORIGINAL",
        publication_date=date(2025, 4, 12),
    )
    db_session.add(document)
    await db_session.flush()

    fact = FinancialFact(
        id=uuid.uuid4(),
        period_id=period.id,
        document_id=document.id,
        company_id=test_company.id,
        fact_type="INCOME_STATEMENT",
        reported_label="revenue",
        normalized_label="revenue",
        reported_value=Decimal("100"),
        currency="EGP",
    )
    db_session.add(fact)
    await db_session.flush()

    response = await client.post(
        f"/api/data-quality/companies/{test_company.id}/assess"
        "?scope=financial_statements&as_of=2026-10-08"
    )
    assert response.status_code == 200
    body = response.json()
    components = {c["key"]: c for c in body["components"]}
    # R12.3: freshness reason carries the concrete publication date.
    assert "2025-04-12" in components["freshness"]["reason"]


async def test_price_history_depth_uses_expected_trading_days(
    client: AsyncClient, db_session: AsyncSession, test_company: Company
) -> None:
    source = DataSource(
        id=uuid.uuid4(),
        name=f"Price Source {uuid.uuid4().hex[:8]}",
        source_type=DataSourceType.EGX,
    )
    db_session.add(source)
    await db_session.flush()

    def bar(day: int) -> DailyPrice:
        return DailyPrice(
            id=uuid.uuid4(),
            company_id=test_company.id,
            date=date(2026, 10, day),
            open=Decimal("1"),
            high=Decimal("1"),
            low=Decimal("1"),
            close=Decimal("1"),
            volume=100,
            source_id=source.id,
        )

    for day in (1, 2, 8):
        db_session.add(bar(day))
    await db_session.flush()

    response = await client.post(
        f"/api/data-quality/companies/{test_company.id}/assess"
        "?scope=price_history&as_of=2026-10-08"
    )
    assert response.status_code == 200
    components = {c["key"]: c for c in response.json()["components"]}
    # (2026-10-08 - 2026-10-01).days + 1 = 8; round(8 * 5 / 7) = 6.
    assert components["historical_depth"]["reason"] == (
        "latest bar 2026-10-08; 3/6 expected trading days"
    )
    assert components["completeness"]["score"] == 100.0
    assert components["source_reliability"]["score"] == 95.0
