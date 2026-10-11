"""Tests for Shariah screening rules and service."""

import uuid
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import FinancialFact
from app.models.market import Company, CompanyStatus
from app.models.screening import ScreeningStatusDB, ShariahScreeningResult
from app.screening.methodology import DEFAULT_METHODOLOGY
from app.screening.rules import (
    ScreeningVerdict,
    screen_cash_and_securities,
    screen_debt_ratio,
    screen_industry,
    screen_interest_income,
)


class TestDebtRatioScreening:
    def test_pass_under_threshold(self):
        result = screen_debt_ratio(
            total_debt=Decimal("25"),
            total_assets=Decimal("100"),
            threshold=Decimal("0.33"),
        )
        assert result.verdict == ScreeningVerdict.PASS
        assert result.value == Decimal("0.25")

    def test_fail_over_threshold(self):
        result = screen_debt_ratio(
            total_debt=Decimal("40"),
            total_assets=Decimal("100"),
            threshold=Decimal("0.33"),
        )
        assert result.verdict == ScreeningVerdict.FAIL
        assert result.value == Decimal("0.40")

    def test_fail_at_threshold(self):
        result = screen_debt_ratio(
            total_debt=Decimal("33"),
            total_assets=Decimal("100"),
            threshold=Decimal("0.33"),
        )
        assert result.verdict == ScreeningVerdict.FAIL

    def test_missing_data(self):
        result = screen_debt_ratio(
            total_debt=None,
            total_assets=Decimal("100"),
        )
        assert result.verdict == ScreeningVerdict.INSUFFICIENT_DATA

    def test_zero_assets(self):
        result = screen_debt_ratio(
            total_debt=Decimal("10"),
            total_assets=Decimal("0"),
        )
        assert result.verdict == ScreeningVerdict.INSUFFICIENT_DATA


class TestInterestIncomeScreening:
    def test_pass_under_threshold(self):
        result = screen_interest_income(
            interest_income=Decimal("3"),
            total_revenue=Decimal("100"),
            threshold=Decimal("0.05"),
        )
        assert result.verdict == ScreeningVerdict.PASS
        assert result.value == Decimal("0.03")

    def test_fail_over_threshold(self):
        result = screen_interest_income(
            interest_income=Decimal("6"),
            total_revenue=Decimal("100"),
            threshold=Decimal("0.05"),
        )
        assert result.verdict == ScreeningVerdict.FAIL
        assert result.value == Decimal("0.06")

    def test_missing_data(self):
        result = screen_interest_income(
            interest_income=None,
            total_revenue=Decimal("100"),
        )
        assert result.verdict == ScreeningVerdict.INSUFFICIENT_DATA


class TestCashAndSecuritiesScreening:
    def test_pass_under_threshold(self):
        result = screen_cash_and_securities(
            cash_and_securities=Decimal("20"),
            total_assets=Decimal("100"),
            threshold=Decimal("0.33"),
        )
        assert result.verdict == ScreeningVerdict.PASS
        assert result.value == Decimal("0.20")

    def test_fail_over_threshold(self):
        result = screen_cash_and_securities(
            cash_and_securities=Decimal("40"),
            total_assets=Decimal("100"),
            threshold=Decimal("0.33"),
        )
        assert result.verdict == ScreeningVerdict.FAIL
        assert result.value == Decimal("0.40")


class TestIndustryScreening:
    def test_pass_permitted_industry(self):
        result = screen_industry(
            industry="Technology",
            prohibited_industries=("alcohol", "gambling", "pork"),
        )
        assert result.verdict == ScreeningVerdict.PASS

    def test_fail_prohibited_industry(self):
        result = screen_industry(
            industry="Alcohol Production",
            prohibited_industries=("alcohol", "gambling", "pork"),
        )
        assert result.verdict == ScreeningVerdict.FAIL

    def test_missing_industry(self):
        result = screen_industry(
            industry=None,
            prohibited_industries=("alcohol", "gambling", "pork"),
        )
        assert result.verdict == ScreeningVerdict.INSUFFICIENT_DATA


class TestDefaultMethodology:
    def test_thresholds(self):
        assert DEFAULT_METHODOLOGY.debt_to_assets_threshold == Decimal("0.33")
        assert DEFAULT_METHODOLOGY.interest_income_to_revenue_threshold == Decimal("0.05")
        assert DEFAULT_METHODOLOGY.cash_and_securities_to_assets_threshold == Decimal("0.33")

    def test_version(self):
        # R32 B1: v2 identifier pins denominator + window + thresholds.
        assert DEFAULT_METHODOLOGY.version.value == "aaoifi-assets-spot/33-33-5"
        assert DEFAULT_METHODOLOGY.denominator == "spot_total_assets"
        assert DEFAULT_METHODOLOGY.averaging_window == "spot"

    def test_source_reference(self):
        assert "AAOIFI" in DEFAULT_METHODOLOGY.source_reference


class TestScreeningPersistence:
    """Tri-state persistence: missing data stays visible, never collapsed to a binary."""

    async def test_screening_insufficient_status_persisted(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
    ):
        # No facts → ratio rules are INSUFFICIENT_DATA; permitted industry passes.
        response = await client.post(f"/api/screening/companies/{test_company.id}/screen")
        assert response.status_code == 200
        assert response.json()["is_compliant"] is None

        row = (
            await db_session.execute(
                select(ShariahScreeningResult).where(
                    ShariahScreeningResult.company_id == test_company.id
                )
            )
        ).scalar_one()
        assert row.status == ScreeningStatusDB.INSUFFICIENT_DATA
        assert row.is_compliant is None

    async def test_screening_any_fail_overrides_insufficient(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        company = Company(
            id=uuid.uuid4(),
            ticker=f"ALC_{uuid.uuid4().hex[:8].upper()}",
            isin=f"EG{uuid.uuid4().hex[:10].upper()}",
            name="Alcohol Producer",
            sector="Beverages",
            industry="Alcohol Production",
            currency="EGP",
            status=CompanyStatus.ACTIVE,
        )
        db_session.add(company)
        await db_session.flush()

        # Prohibited industry FAILs while every ratio rule lacks data.
        response = await client.post(f"/api/screening/companies/{company.id}/screen")
        assert response.status_code == 200
        assert response.json()["is_compliant"] is False

        row = (
            await db_session.execute(
                select(ShariahScreeningResult).where(
                    ShariahScreeningResult.company_id == company.id
                )
            )
        ).scalar_one()
        assert row.status == ScreeningStatusDB.NON_COMPLIANT
        assert row.is_compliant is False

    async def test_zero_value_not_replaced(
        self,
        client: AsyncClient,
        test_company: Company,
        zero_value_facts: list[FinancialFact],
    ):
        # normalized total_debt is 0; falling back to the reported 999 would flip the rule.
        response = await client.post(f"/api/screening/companies/{test_company.id}/screen")
        assert response.status_code == 200
        rules = {r["rule_name"]: r for r in response.json()["rule_results"]}
        assert rules["debt_ratio"]["verdict"] == "PASS"
        assert Decimal(rules["debt_ratio"]["value"]) == 0
