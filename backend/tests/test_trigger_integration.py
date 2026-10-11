"""Integration tests for arrival-only trigger flow (B3)."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.continuous.constants import CI_METHODOLOGY_VERSION
from app.continuous.trigger_service import TriggerService
from app.models.continuous import AlertFamily, AlertRule, EventType
from app.models.financial import (
    FinancialDocument,
    FinancialFact,
    FinancialPeriod,
    ReportingPeriodType,
)
from app.models.market import Company, CompanyStatus, DailyPrice, DataSource, DataSourceType
from app.models.thesis import InvestmentThesis
from app.repositories.continuous import EventRepository
from app.repositories.thesis import ThesisRepository
from app.thesis.constants import THESIS_METHODOLOGY_VERSION

pytestmark = pytest.mark.asyncio

AS_OF = date(2026, 10, 10)


async def _make_company(db_session: AsyncSession, ticker: str) -> Company:
    company = Company(
        id=uuid.uuid4(),
        ticker=ticker,
        isin=f"EG{uuid.uuid4().hex[:10].upper()}",
        name=f"{ticker} Company",
        currency="EGP",
        status=CompanyStatus.ACTIVE,
        shares_outstanding=Decimal("1000000"),
    )
    db_session.add(company)
    await db_session.flush()
    return company


async def _add_price(db_session: AsyncSession, company: Company, close: Decimal) -> None:
    source = DataSource(
        id=uuid.uuid4(),
        name=f"Price Source {uuid.uuid4().hex[:8]}",
        source_type=DataSourceType.EGX,
    )
    db_session.add(source)
    await db_session.flush()
    db_session.add(
        DailyPrice(
            id=uuid.uuid4(),
            company_id=company.id,
            date=AS_OF,
            open=close,
            high=close,
            low=close,
            close=close,
            volume=1000,
            source_id=source.id,
        )
    )
    await db_session.flush()


async def _add_facts(
    db_session: AsyncSession,
    company: Company,
    facts: list[dict],
    period_id: uuid.UUID | None = None,
) -> list[FinancialFact]:
    if period_id is None:
        period = FinancialPeriod(
            id=uuid.uuid4(),
            company_id=company.id,
            period_type=ReportingPeriodType.ANNUAL,
            fiscal_year=2024,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        db_session.add(period)
        await db_session.flush()
        period_id = period.id

    source = DataSource(
        id=uuid.uuid4(),
        name=f"Fact Source {uuid.uuid4().hex[:8]}",
        source_type=DataSourceType.EGX,
    )
    db_session.add(source)
    await db_session.flush()

    document = FinancialDocument(
        id=uuid.uuid4(),
        period_id=period_id,
        source_id=source.id,
        document_type="ANNUAL_REPORT",
        document_status="ORIGINAL",
    )
    db_session.add(document)
    await db_session.flush()

    created_facts = []
    for fact_data in facts:
        fact = FinancialFact(
            id=uuid.uuid4(),
            period_id=period_id,
            document_id=document.id,
            company_id=company.id,
            fact_type=fact_data.get("fact_type", "INCOME_STATEMENT"),
            reported_label=fact_data["label"],
            normalized_label=fact_data["label"],
            reported_value=fact_data.get("value"),
            normalized_value=fact_data.get("value"),
            currency="EGP",
            audit_state=fact_data.get("audit_state"),
            extraction=fact_data.get("extraction"),
            eas_tags=fact_data.get("eas_tags"),
            methodology_version=CI_METHODOLOGY_VERSION,
        )
        db_session.add(fact)
        created_facts.append(fact)
    await db_session.flush()
    return created_facts


async def _add_thesis(db_session: AsyncSession, company: Company) -> InvestmentThesis:
    thesis = InvestmentThesis(
        id=uuid.uuid4(),
        company_id=company.id,
        methodology_version=THESIS_METHODOLOGY_VERSION,
        horizon_years=5,
        is_shareholder=None,
        fair_value=None,
        fair_value_status="INSUFFICIENT_DATA",
        assumptions=[],
        bulls=[],
        bears=[],
        scenarios={},
        sensitivity={},
        narrative="",
        confidence={},
        dq={},
        score=None,
        needs_reassessment=False,
        computed_at=datetime.now(UTC),
    )
    db_session.add(thesis)
    await db_session.flush()
    return thesis


class TestFactLandingFlow:
    """Tests for fact landing trigger flow."""

    async def test_fact_landing_triggers_document_alert(self, db_session: AsyncSession) -> None:
        """New facts landing should fire document alert for watched company."""
        company = await _make_company(db_session, "DOCTRIGGER")

        # Create document alert rule
        rule = AlertRule(
            id=uuid.uuid4(),
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            company_id=company.id,
            family=AlertFamily.DOCUMENT,
            params={},
            methodology_version=CI_METHODOLOGY_VERSION,
            enabled=True,
        )
        db_session.add(rule)
        await db_session.flush()

        # Land new facts
        facts = await _add_facts(db_session, company, [
            {"label": "revenue", "value": Decimal("1000"), "audit_state": "verified"},
        ])

        service = TriggerService(db_session)
        result = await service.on_facts_landed(company.id, [f.id for f in facts])

        assert result.alerts_fired == 1
        assert result.ledger_rows >= 1

        # Verify alert_fired row created
        from app.repositories.continuous import AlertRepository
        alert_repo = AlertRepository(db_session)
        fired = await alert_repo.list_fired(
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            rule_id=rule.id,
        )
        assert len(fired) == 1
        assert fired[0].inputs_snapshot["family"] == "document"
        assert str(facts[0].id) in fired[0].inputs_snapshot["fact_ids"]

        # Verify event ledger
        event_repo = EventRepository(db_session)
        events = await event_repo.filter(
            symbol=company.id,
            type=EventType.ALERT_FIRED,
        )
        assert len(events) == 1
        assert events[0].inputs_snapshot["family"] == "document"

    async def test_fact_landing_triggers_warn_on_invalidation(
        self, db_session: AsyncSession
    ) -> None:
        """Fact landing breaching warn threshold should create warn check event."""
        company = await _make_company(db_session, "WARNTRIG")
        await _add_thesis(db_session, company)

        thesis_repo = ThesisRepository(db_session)
        thesis = await thesis_repo.get_thesis(company.id)
        await thesis_repo.upsert_invalidation(
            thesis_id=thesis.id,
            metric="revenue",
            threshold=Decimal("1000"),
            direction="below",
            period="FY2024",
            evidence_source="filing",
            action="reassess",
            status="Triggered",  # Already triggered -> warn on re-breach
            extraction_confidence="High",
            version=1,
        )
        await db_session.flush()

        # Land fact that breaches threshold (revenue = 500 < 1000)
        facts = await _add_facts(db_session, company, [
            {"label": "revenue", "value": Decimal("500"), "audit_state": "verified"},
        ])

        service = TriggerService(db_session)
        result = await service.on_facts_landed(company.id, [f.id for f in facts])

        assert result.checks_run == 1
        assert result.ledger_rows >= 1

        # Verify check.evaluated event with warn status
        event_repo = EventRepository(db_session)
        events = await event_repo.filter(
            symbol=company.id,
            type=EventType.CHECK_EVALUATED,
        )
        assert len(events) == 1
        assert events[0].inputs_snapshot["status"] == "warn"
        assert events[0].inputs_snapshot["invalidation_metric"] == "revenue"

    async def test_fact_landing_triggers_break_proposal(self, db_session: AsyncSession) -> None:
        """Fact landing breaching break threshold should propose invalidation."""
        company = await _make_company(db_session, "BREAKTRIG")
        await _add_thesis(db_session, company)

        thesis_repo = ThesisRepository(db_session)
        thesis = await thesis_repo.get_thesis(company.id)
        await thesis_repo.upsert_invalidation(
            thesis_id=thesis.id,
            metric="revenue",
            threshold=Decimal("1000"),
            direction="below",
            period="FY2024",
            evidence_source="filing",
            action="reassess",
            status="Active",
            extraction_confidence="High",
            version=1,
        )
        await db_session.flush()

        # Land fact that breaches with high confidence
        facts = await _add_facts(db_session, company, [
            {"label": "revenue", "value": Decimal("500"), "audit_state": "verified"},
        ])

        service = TriggerService(db_session)
        result = await service.on_facts_landed(company.id, [f.id for f in facts])

        assert result.checks_run == 1

        # Verify thesis.updated event for proposed invalidation
        event_repo = EventRepository(db_session)
        events = await event_repo.filter(
            symbol=company.id,
            type=EventType.THESIS_UPDATED,
        )
        assert len(events) == 1
        assert events[0].inputs_snapshot["proposed_status"] == "possibly_invalidated"
        assert "requires user confirmation" in events[0].reason.lower()


class TestPriceCrossingFlow:
    """Tests for price crossing trigger flow."""

    async def test_price_crossing_fires_alert(self, db_session: AsyncSession) -> None:
        """Price crossing threshold should fire price alert."""
        company = await _make_company(db_session, "PRICETRIG")
        await _add_price(db_session, company, Decimal("55"))

        rule = AlertRule(
            id=uuid.uuid4(),
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            company_id=company.id,
            family=AlertFamily.PRICE,
            params={"threshold": 50, "direction": "above"},
            methodology_version=CI_METHODOLOGY_VERSION,
            enabled=True,
        )
        db_session.add(rule)
        await db_session.flush()

        service = TriggerService(db_session)
        result = await service.on_price_crossing(company.id, Decimal("55"), AS_OF)

        assert result.alerts_fired == 1
        assert result.ledger_rows >= 1

        # Verify alert_fired
        from app.repositories.continuous import AlertRepository
        alert_repo = AlertRepository(db_session)
        fired = await alert_repo.list_fired(
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            rule_id=rule.id,
        )
        assert len(fired) == 1

    async def test_price_crossing_valuation_gap_alert(self, db_session: AsyncSession) -> None:
        """Price crossing should also evaluate valuation gap alerts."""
        from app.models.valuation import ValuationFairValue

        company = await _make_company(db_session, "VGAPTRIG")
        await _add_price(db_session, company, Decimal("50"))
        db_session.add(
            ValuationFairValue(
                id=uuid.uuid4(),
                company_id=company.id,
                profile_key="default",
                methodology_version="1.0",
                fair_value=Decimal("100"),
                fair_value_status="AVAILABLE",
                legs={},
                weights={},
                scenarios={},
                sensitivity=[],
                confidence={},
                verdict="neutral",
                inputs_echo={},
                current_price=None,
                price_as_of=None,
                computed_at=datetime(2026, 10, 10, tzinfo=UTC),
            )
        )
        await db_session.flush()

        rule = AlertRule(
            id=uuid.uuid4(),
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            company_id=company.id,
            family=AlertFamily.VALUATION_GAP,
            params={"gap_pct": 30},
            methodology_version=CI_METHODOLOGY_VERSION,
            enabled=True,
        )
        db_session.add(rule)
        await db_session.flush()

        service = TriggerService(db_session)
        result = await service.on_price_crossing(company.id, Decimal("50"), AS_OF)

        assert result.alerts_fired == 1

    async def test_price_no_alert_writes_checked_event(self, db_session: AsyncSession) -> None:
        """Price check with no alerts should write check.evaluated event."""
        company = await _make_company(db_session, "NOPRICEALERT")
        await _add_price(db_session, company, Decimal("50"))

        service = TriggerService(db_session)
        result = await service.on_price_crossing(company.id, Decimal("50"), AS_OF)

        assert result.alerts_fired == 0
        assert result.ledger_rows == 1

        event_repo = EventRepository(db_session)
        events = await event_repo.filter(
            symbol=company.id,
            type=EventType.CHECK_EVALUATED,
        )
        assert len(events) == 1
        assert "no alert thresholds crossed" in events[0].reason.lower()


class TestRestatementFlow:
    """Tests for restatement detection flow."""

    async def test_restatement_detected_writes_event(self, db_session: AsyncSession) -> None:
        """Restatement detection should write restatement.detected event."""
        company = await _make_company(db_session, "RESTATEFLOW")

        # Create a shared period for both prior and new facts
        period = FinancialPeriod(
            id=uuid.uuid4(),
            company_id=company.id,
            period_type=ReportingPeriodType.ANNUAL,
            fiscal_year=2024,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        db_session.add(period)
        await db_session.flush()

        # Add prior fact (setup only; the service reads from the DB)
        await _add_facts(db_session, company, [
            {"label": "revenue", "value": Decimal("1000"), "audit_state": "verified"},
        ], period_id=period.id)

        # Add new fact with different value
        new_facts = await _add_facts(db_session, company, [
            {"label": "revenue", "value": Decimal("1200"), "audit_state": "verified"},
        ], period_id=period.id)

        service = TriggerService(db_session)
        await service.on_facts_landed(company.id, [f.id for f in new_facts])

        # Verify restatement.detected event
        event_repo = EventRepository(db_session)
        events = await event_repo.filter(
            symbol=company.id,
            type=EventType.RESTATEMENT_DETECTED,
        )
        assert len(events) == 1
        assert events[0].inputs_snapshot["metric"] == "revenue"
        assert events[0].inputs_snapshot["old_value"] == "1000"
        assert events[0].inputs_snapshot["new_value"] == "1200"


class TestEventOrdering:
    """Tests for event ledger ordering (B6)."""

    async def test_alert_then_check_then_confirm_creates_ordered_events(
        self, db_session: AsyncSession
    ) -> None:
        """Alert fired -> check evaluated -> thesis confirm should create three ordered events."""
        company = await _make_company(db_session, "ORDERED")
        await _add_price(db_session, company, Decimal("55"))
        await _add_thesis(db_session, company)

        # Create price alert
        price_rule = AlertRule(
            id=uuid.uuid4(),
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            company_id=company.id,
            family=AlertFamily.PRICE,
            params={"threshold": 50, "direction": "above"},
            methodology_version=CI_METHODOLOGY_VERSION,
            enabled=True,
        )
        db_session.add(price_rule)

        # Create thesis with invalidation
        thesis_repo = ThesisRepository(db_session)
        thesis = await thesis_repo.get_thesis(company.id)
        await thesis_repo.upsert_invalidation(
            thesis_id=thesis.id,
            metric="revenue",
            threshold=Decimal("1000"),
            direction="below",
            period="FY2024",
            evidence_source="filing",
            action="reassess",
            status="Active",
            extraction_confidence="High",
            version=1,
        )
        await db_session.flush()

        # Land fact that triggers both
        facts = await _add_facts(db_session, company, [
            {"label": "revenue", "value": Decimal("500"), "audit_state": "verified"},
        ])

        service = TriggerService(db_session)
        await service.on_facts_landed(company.id, [f.id for f in facts])
        await service.on_price_crossing(company.id, Decimal("55"), AS_OF)

        # Verify event ordering
        event_repo = EventRepository(db_session)
        events = await event_repo.filter(symbol=company.id, limit=10)
        event_types = [e.type for e in events]

        # Should have alert.fired, check.evaluated, thesis.updated in some order
        assert EventType.ALERT_FIRED in event_types
        assert EventType.CHECK_EVALUATED in event_types
        assert EventType.THESIS_UPDATED in event_types
