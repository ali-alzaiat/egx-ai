"""Unit tests for deterministic trigger evaluators (B2/B3/B5)."""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.continuous.alert_service import AlertService
from app.continuous.constants import CI_METHODOLOGY_VERSION
from app.continuous.restatement_detector import RestatementDetector
from app.continuous.trigger_service import TriggerService
from app.models.continuous import AlertFamily, AlertRule
from app.models.financial import (
    FinancialDocument,
    FinancialFact,
    FinancialPeriod,
    ReportingPeriodType,
)
from app.models.market import Company, CompanyStatus, DailyPrice, DataSource, DataSourceType
from app.models.scores import InvestmentScore
from app.models.thesis import InvestmentThesis
from app.models.valuation import ValuationFairValue
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


async def _add_fair_value(db_session: AsyncSession, company: Company, fv: Decimal) -> None:
    db_session.add(
        ValuationFairValue(
            id=uuid.uuid4(),
            company_id=company.id,
            profile_key="default",
            methodology_version="1.0",
            fair_value=fv,
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


async def _add_score(
    db_session: AsyncSession,
    company: Company,
    headline: Decimal,
    methodology_version: str = "1.0",
) -> None:
    db_session.add(
        InvestmentScore(
            id=uuid.uuid4(),
            company_id=company.id,
            profile_key="default",
            methodology_version=methodology_version,
            headline=headline,
            headline_status="AVAILABLE",
            components={},
            checks=[],
            confidence={"level": "High"},
            buy_zone={},
            n_with_data=10,
            margin_of_safety=Decimal("0.2"),
            inputs_echo={},
            computed_at=datetime.now(UTC),
        )
    )
    await db_session.flush()


# Module-level counter for unique fiscal years in tests
_fiscal_year_counter = 2024


async def _add_facts(
    db_session: AsyncSession,
    company: Company,
    facts: list[dict],
    period_id: uuid.UUID | None = None,
    fiscal_year: int | None = None,
) -> list[FinancialFact]:
    """Add financial facts for testing."""
    global _fiscal_year_counter

    if period_id is None:
        if fiscal_year is None:
            fiscal_year = _fiscal_year_counter
            _fiscal_year_counter += 1
        period = FinancialPeriod(
            id=uuid.uuid4(),
            company_id=company.id,
            period_type=ReportingPeriodType.ANNUAL,
            fiscal_year=fiscal_year,
            start_date=date(fiscal_year, 1, 1),
            end_date=date(fiscal_year, 12, 31),
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


class TestPriceCrossingEvaluator:
    """Tests for price crossing alert evaluator."""

    async def test_price_crosses_above_threshold(self, db_session: AsyncSession) -> None:
        """Price crossing above threshold should fire."""
        company = await _make_company(db_session, "PRICEUP")
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

        service = AlertService(db_session)
        result = await service._eval_price_crossing(rule, company.id)

        assert result.should_fire is True
        assert result.inputs_snapshot["direction"] == "above"
        assert result.inputs_snapshot["threshold"] == "50"
        assert result.inputs_snapshot["current_close"] == "55"
        assert result.inputs_snapshot["methodology_version"] == CI_METHODOLOGY_VERSION

    async def test_price_crosses_below_threshold(self, db_session: AsyncSession) -> None:
        """Price crossing below threshold should fire."""
        company = await _make_company(db_session, "PRICEDOWN")
        await _add_price(db_session, company, Decimal("45"))

        rule = AlertRule(
            id=uuid.uuid4(),
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            company_id=company.id,
            family=AlertFamily.PRICE,
            params={"threshold": 50, "direction": "below"},
            methodology_version=CI_METHODOLOGY_VERSION,
            enabled=True,
        )
        db_session.add(rule)
        await db_session.flush()

        service = AlertService(db_session)
        result = await service._eval_price_crossing(rule, company.id)

        assert result.should_fire is True
        assert result.inputs_snapshot["direction"] == "below"

    async def test_price_not_crossed(self, db_session: AsyncSession) -> None:
        """Price not crossing threshold should not fire."""
        company = await _make_company(db_session, "PRICENO")
        await _add_price(db_session, company, Decimal("55"))

        rule = AlertRule(
            id=uuid.uuid4(),
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            company_id=company.id,
            family=AlertFamily.PRICE,
            params={"threshold": 60, "direction": "above"},
            methodology_version=CI_METHODOLOGY_VERSION,
            enabled=True,
        )
        db_session.add(rule)
        await db_session.flush()

        service = AlertService(db_session)
        result = await service._eval_price_crossing(rule, company.id)

        assert result.should_fire is False

    async def test_no_price_data(self, db_session: AsyncSession) -> None:
        """Missing price data should not fire and return INSUFFICIENT_DATA reason."""
        company = await _make_company(db_session, "NOPRICE")

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

        service = AlertService(db_session)
        result = await service._eval_price_crossing(rule, company.id)

        assert result.should_fire is False
        assert "No price data available" in result.reason


class TestValuationGapEvaluator:
    """Tests for valuation gap alert evaluator."""

    async def test_price_below_fair_value_gap(self, db_session: AsyncSession) -> None:
        """Price significantly below fair value should fire."""
        company = await _make_company(db_session, "VGAP")
        await _add_price(db_session, company, Decimal("50"))
        await _add_fair_value(db_session, company, Decimal("100"))

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

        service = AlertService(db_session)
        result = await service._eval_valuation_gap(rule, company.id)

        assert result.should_fire is True
        assert result.inputs_snapshot["gap_pct"] == 30
        assert result.inputs_snapshot["fair_value"] == "100"
        assert result.inputs_snapshot["current_close"] == "50"

    async def test_price_within_gap(self, db_session: AsyncSession) -> None:
        """Price within gap threshold should not fire."""
        company = await _make_company(db_session, "VGAPNO")
        await _add_price(db_session, company, Decimal("90"))
        await _add_fair_value(db_session, company, Decimal("100"))

        rule = AlertRule(
            id=uuid.uuid4(),
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            company_id=company.id,
            family=AlertFamily.VALUATION_GAP,
            params={"gap_pct": 20},
            methodology_version=CI_METHODOLOGY_VERSION,
            enabled=True,
        )
        db_session.add(rule)
        await db_session.flush()

        service = AlertService(db_session)
        result = await service._eval_valuation_gap(rule, company.id)

        assert result.should_fire is False

    async def test_no_fair_value(self, db_session: AsyncSession) -> None:
        """Missing fair value should not fire."""
        company = await _make_company(db_session, "NOFV")
        await _add_price(db_session, company, Decimal("50"))

        rule = AlertRule(
            id=uuid.uuid4(),
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            company_id=company.id,
            family=AlertFamily.VALUATION_GAP,
            params={"gap_pct": 20},
            methodology_version=CI_METHODOLOGY_VERSION,
            enabled=True,
        )
        db_session.add(rule)
        await db_session.flush()

        service = AlertService(db_session)
        result = await service._eval_valuation_gap(rule, company.id)

        assert result.should_fire is False
        assert "No fair value available" in result.reason


class TestScoreChangeEvaluator:
    """Tests for score change alert evaluator."""

    async def test_score_change_exceeds_threshold(self, db_session: AsyncSession) -> None:
        """Score change exceeding threshold should fire."""
        company = await _make_company(db_session, "SCOREUP")
        await _add_score(db_session, company, Decimal("80"), methodology_version="1.0")
        # Add previous score with different methodology_version to avoid unique constraint
        db_session.add(
            InvestmentScore(
                id=uuid.uuid4(),
                company_id=company.id,
                profile_key="default",
                methodology_version="1.0_prev",
                headline=Decimal("60"),
                headline_status="AVAILABLE",
                components={},
                checks=[],
                confidence={"level": "High"},
                buy_zone={},
                n_with_data=10,
                margin_of_safety=Decimal("0.2"),
                inputs_echo={},
                computed_at=datetime(2026, 9, 1, tzinfo=UTC),
            )
        )
        await db_session.flush()

        rule = AlertRule(
            id=uuid.uuid4(),
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            company_id=company.id,
            family=AlertFamily.SCORE_CHANGE,
            params={"threshold_pct": 10},
            methodology_version=CI_METHODOLOGY_VERSION,
            enabled=True,
        )
        db_session.add(rule)
        await db_session.flush()

        service = AlertService(db_session)
        result = await service._eval_score_change(rule, company.id)

        assert result.should_fire is True
        assert result.inputs_snapshot["change_pct"] >= 10

    async def test_score_change_below_threshold(self, db_session: AsyncSession) -> None:
        """Score change below threshold should not fire."""
        company = await _make_company(db_session, "SCORENO")
        await _add_score(db_session, company, Decimal("75"), methodology_version="1.0")
        db_session.add(
            InvestmentScore(
                id=uuid.uuid4(),
                company_id=company.id,
                profile_key="default",
                methodology_version="1.0_prev",
                headline=Decimal("70"),
                headline_status="AVAILABLE",
                components={},
                checks=[],
                confidence={"level": "High"},
                buy_zone={},
                n_with_data=10,
                margin_of_safety=Decimal("0.2"),
                inputs_echo={},
                computed_at=datetime(2026, 9, 1, tzinfo=UTC),
            )
        )
        await db_session.flush()

        rule = AlertRule(
            id=uuid.uuid4(),
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            company_id=company.id,
            family=AlertFamily.SCORE_CHANGE,
            params={"threshold_pct": 10},
            methodology_version=CI_METHODOLOGY_VERSION,
            enabled=True,
        )
        db_session.add(rule)
        await db_session.flush()

        service = AlertService(db_session)
        result = await service._eval_score_change(rule, company.id)

        assert result.should_fire is False

    async def test_insufficient_score_history(self, db_session: AsyncSession) -> None:
        """Single score assessment should not fire."""
        company = await _make_company(db_session, "SCOREONE")
        await _add_score(db_session, company, Decimal("75"))

        rule = AlertRule(
            id=uuid.uuid4(),
            user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            company_id=company.id,
            family=AlertFamily.SCORE_CHANGE,
            params={"threshold_pct": 10},
            methodology_version=CI_METHODOLOGY_VERSION,
            enabled=True,
        )
        db_session.add(rule)
        await db_session.flush()

        service = AlertService(db_session)
        result = await service._eval_score_change(rule, company.id)

        assert result.should_fire is False
        assert "Insufficient score history" in result.reason


class TestRestatementDetector:
    """Tests for restatement detector (B4)."""

    async def test_detects_restatement(self, db_session: AsyncSession) -> None:
        """Same period different value should detect restatement."""
        company = await _make_company(db_session, "RESTATE")

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

        # Add prior fact
        prior_facts = await _add_facts(db_session, company, [
            {"label": "revenue", "value": Decimal("1000"), "audit_state": "verified"},
        ], period_id=period.id)
        prior_fact_id = prior_facts[0].id

        # Add new fact with different value (same period)
        new_facts = await _add_facts(db_session, company, [
            {"label": "revenue", "value": Decimal("1200"), "audit_state": "verified"},
        ], period_id=period.id)
        new_fact_id = new_facts[0].id

        detector = RestatementDetector(db_session)
        result = await detector.detect(company.id, [new_fact_id])

        assert result.detected is True
        assert result.metric == "revenue"
        assert result.old_value == Decimal("1000")
        assert result.new_value == Decimal("1200")
        assert result.delta == Decimal("200")
        assert result.prior_fact_id == prior_fact_id
        assert result.current_fact_id == new_fact_id

    async def test_excludes_eas_gotcha_tags(self, db_session: AsyncSession) -> None:
        """EAS-gotcha tagged facts should be excluded from restatement detection."""
        company = await _make_company(db_session, "EASGOTCHA")

        # Create a shared period
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

        # Add prior fact
        await _add_facts(db_session, company, [
            {"label": "revenue", "value": Decimal("1000"), "audit_state": "verified"},
        ], period_id=period.id)

        # Add new fact with EAS-gotcha tag (same period)
        new_facts = await _add_facts(db_session, company, [
            {
                "label": "revenue",
                "value": Decimal("1200"),
                "audit_state": "verified",
                "extraction": {"confidence": 0.9},
                "eas_tags": ["eas_reclassification"],
            },
        ], period_id=period.id)
        new_fact_id = new_facts[0].id

        detector = RestatementDetector(db_session)
        result = await detector.detect(company.id, [new_fact_id])

        assert result.detected is False
        assert "EAS-gotcha" in result.reason or "No restatements" in result.reason

    async def test_low_confidence_excluded(self, db_session: AsyncSession) -> None:
        """Low confidence extraction should be excluded."""
        company = await _make_company(db_session, "LOWCONF")

        # Create a shared period
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

        # Add prior fact (setup only; detection reads from the DB)
        await _add_facts(db_session, company, [
            {"label": "revenue", "value": Decimal("1000"), "audit_state": "verified"},
        ], period_id=period.id)

        new_facts = await _add_facts(db_session, company, [
            {
                "label": "revenue",
                "value": Decimal("1200"),
                "audit_state": "ocr_low_confidence",
                "extraction": {"confidence": 0.5},
            },
        ], period_id=period.id)
        new_fact_id = new_facts[0].id

        detector = RestatementDetector(db_session)
        result = await detector.detect(company.id, [new_fact_id])

        assert result.detected is False


class TestEvidenceQualityGate:
    """Tests for evidence-quality gate (B5)."""

    async def test_low_confidence_returns_unknown(self, db_session: AsyncSession) -> None:
        """Low confidence fact should return unknown, never broken."""
        company = await _make_company(db_session, "EVIDENCE")
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
            extraction_confidence="Low",
            version=1,
        )
        await db_session.flush()

        invalidations = await thesis_repo.list_invalidations(thesis.id)

        # Add low confidence fact
        facts = await _add_facts(db_session, company, [
            {
                "label": "revenue",
                "value": Decimal("500"),
                "audit_state": "ocr_low_confidence",
                "extraction": {"confidence": 0.5},
            },
        ])

        service = TriggerService(db_session)
        check_result = await service._evaluate_invalidation(
            company.id, invalidations[0], [facts[0].id]
        )

        assert check_result.status == "unknown"
        assert check_result.confidence == "Low"
        assert "Low extraction confidence" in check_result.reason

    async def test_missing_metric_returns_unknown(self, db_session: AsyncSession) -> None:
        """Missing metric should return unknown with reason."""
        company = await _make_company(db_session, "MISSINGMETRIC")
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

        invalidations = await thesis_repo.list_invalidations(thesis.id)

        # Add fact with different metric
        facts = await _add_facts(db_session, company, [
            {"label": "profit", "value": Decimal("500"), "audit_state": "verified"},
        ])

        service = TriggerService(db_session)
        check_result = await service._evaluate_invalidation(
            company.id, invalidations[0], [facts[0].id]
        )

        assert check_result.status == "unknown"
        assert "Missing data for metric" in check_result.reason


class TestQuietDayPath:
    """Tests for quiet-day path writing 'checked, nothing new'."""

    async def test_quiet_day_writes_ledger(self, db_session: AsyncSession) -> None:
        """No alerts or checks should write check.evaluated event."""
        company = await _make_company(db_session, "QUIET")

        service = TriggerService(db_session)
        result = await service.on_facts_landed(company.id, [])

        assert result.alerts_fired == 0
        assert result.checks_run == 0
        assert result.ledger_rows == 1
        assert "0 alerts, 0 checks" in result.message
