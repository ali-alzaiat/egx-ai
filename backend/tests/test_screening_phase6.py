"""Phase 6 Shariah tests (R32 B1–B6): methodology v2, report dates, purification, EGX33."""

import uuid
from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import FinancialDocument, FinancialFact, FinancialPeriod
from app.models.market import Company, CompanyStatus, DataSource
from app.screening.methodology import DEFAULT_METHODOLOGY, ShariahMethodologyVersion
from app.screening.purification import (
    NOT_ZAKAT_COPY,
    PURIFICATION_DOCTRINE,
    PurificationBranch,
    PurificationStatus,
    estimate_dividend_purification,
    normalize_ticker,
)
from app.screening.service import RuleProvenance, ScreeningInput, ShariahScreeningService


def _input(**overrides: object) -> ScreeningInput:
    base: dict[str, object] = {
        "company_id": str(uuid.uuid4()),
        "ticker": "TEST",
        "industry": "Software",
        "total_debt": Decimal("10"),
        "total_assets": Decimal("100"),
        "interest_income": Decimal("1"),
        "total_revenue": Decimal("100"),
        "cash_and_securities": Decimal("10"),
        "provenance": None,
    }
    base.update(overrides)
    return ScreeningInput(**base)  # type: ignore[arg-type]


class TestMethodologyV2:
    def test_v2_identifier_pins_denominator_window_thresholds(self) -> None:
        assert ShariahMethodologyVersion.V2_ASSETS_SPOT.value == "aaoifi-assets-spot/33-33-5"

    def test_old_versions_stay_readable(self) -> None:
        assert ShariahMethodologyVersion.V1_0.value == "1.0"
        assert ShariahMethodologyVersion.V1_1.value == "1.1"

    def test_default_is_pinned_not_bare(self) -> None:
        assert DEFAULT_METHODOLOGY.version == ShariahMethodologyVersion.V2_ASSETS_SPOT
        assert "AAOIFI" in DEFAULT_METHODOLOGY.name
        assert DEFAULT_METHODOLOGY.name != "AAOIFI"
        assert "33" in DEFAULT_METHODOLOGY.name and "5" in DEFAULT_METHODOLOGY.name


class TestReportDate:
    async def test_report_date_is_latest_filing(self) -> None:
        service = ShariahScreeningService(session=None)  # type: ignore[arg-type]
        output = await service.screen_company(
            _input(
                provenance={
                    "debt_ratio": RuleProvenance(
                        "ANNUAL_REPORT filing 2024-03-15", date(2024, 3, 15)
                    ),
                    "interest_income_ratio": RuleProvenance(
                        "ANNUAL_REPORT filing 2024-06-30", date(2024, 6, 30)
                    ),
                    "cash_securities_ratio": RuleProvenance("company record", None),
                    "industry_screen": RuleProvenance("company record", None),
                }
            )
        )
        assert output.report_date == date(2024, 6, 30)
        assert output.report_date_reason is None

    async def test_report_date_unknown_without_facts(self) -> None:
        service = ShariahScreeningService(session=None)  # type: ignore[arg-type]
        output = await service.screen_company(_input(provenance=None))
        assert output.report_date is None
        assert output.report_date_reason is not None

    async def test_report_date_unknown_when_filings_undated(self) -> None:
        service = ShariahScreeningService(session=None)  # type: ignore[arg-type]
        output = await service.screen_company(
            _input(
                provenance={
                    "debt_ratio": RuleProvenance("ANNUAL_REPORT (filing date unknown)", None),
                }
            )
        )
        assert output.report_date is None
        assert "Filing dates unknown" in (output.report_date_reason or "")

    async def test_insufficient_rules_carry_missing_input(self) -> None:
        service = ShariahScreeningService(session=None)  # type: ignore[arg-type]
        output = await service.screen_company(
            _input(
                total_debt=None,
                total_assets=None,
                interest_income=None,
                total_revenue=None,
                cash_and_securities=None,
                industry=None,
                provenance=None,
            )
        )
        by_name = {r.rule_name: r for r in output.rule_results}
        assert output.is_compliant is None
        assert by_name["debt_ratio"].missing_input == "total_debt, total_assets"
        assert by_name["interest_income_ratio"].missing_input == (
            "interest_income, total_revenue"
        )
        assert by_name["industry_screen"].missing_input == "industry"
        for result in output.rule_results:
            assert result.value is None
            assert result.reason is not None


class TestDividendPurification:
    def test_ratio_branch(self) -> None:
        est = estimate_dividend_purification(
            ticker="TMGH",
            is_compliant=True,
            dividend_egp=Decimal("300"),
            non_permissible_revenue=Decimal("2"),
            total_revenue=Decimal("100"),
            ratio_provenance="FY2024 annual report income statement",
            dps=Decimal("0.30"),
            dps_source="EGX disclosure",
            dps_date=date(2026, 5, 21),
        )
        assert est.status == PurificationStatus.OK
        assert est.branch == PurificationBranch.RATIO
        assert est.doctrine == PURIFICATION_DOCTRINE == "dividend-method"
        assert est.ratio == Decimal("0.02")
        assert est.amount_egp == Decimal("6.00")
        assert est.note == NOT_ZAKAT_COPY

    def test_zero_dividend_is_real_zero(self) -> None:
        est = estimate_dividend_purification(
            ticker="TMGH",
            is_compliant=True,
            dividend_egp=Decimal("0"),
            non_permissible_revenue=Decimal("2"),
            total_revenue=Decimal("100"),
        )
        assert est.status == PurificationStatus.OK
        assert est.amount_egp == Decimal("0")

    def test_missing_ratio_degrades_with_checklist(self) -> None:
        est = estimate_dividend_purification(
            ticker="TMGH", is_compliant=True, dividend_egp=Decimal("300")
        )
        assert est.status == PurificationStatus.INSUFFICIENT_DATA
        assert est.amount_egp is None
        assert est.missing_input == "non_permissible_revenue, total_revenue"
        assert est.reason is not None and "money-market" in est.reason

    def test_missing_dividend(self) -> None:
        est = estimate_dividend_purification(ticker="TMGH", is_compliant=True)
        assert est.status == PurificationStatus.INSUFFICIENT_DATA
        assert est.amount_egp is None
        assert est.missing_input == "dividend_egp"

    def test_negative_dividend_rejected(self) -> None:
        est = estimate_dividend_purification(
            ticker="TMGH", is_compliant=True, dividend_egp=Decimal("-5")
        )
        assert est.status == PurificationStatus.INSUFFICIENT_DATA
        assert est.amount_egp is None

    def test_negative_revenue_rejected(self) -> None:
        est = estimate_dividend_purification(
            ticker="TMGH",
            is_compliant=True,
            dividend_egp=Decimal("100"),
            non_permissible_revenue=Decimal("-1"),
            total_revenue=Decimal("100"),
        )
        assert est.status == PurificationStatus.INSUFFICIENT_DATA
        assert est.amount_egp is None

    def test_zero_total_revenue_rejected(self) -> None:
        est = estimate_dividend_purification(
            ticker="TMGH",
            is_compliant=True,
            dividend_egp=Decimal("100"),
            non_permissible_revenue=Decimal("1"),
            total_revenue=Decimal("0"),
        )
        assert est.status == PurificationStatus.INSUFFICIENT_DATA
        assert est.amount_egp is None

    def test_fail_holding_purifies_whole_dividend(self) -> None:
        est = estimate_dividend_purification(
            ticker="TMGH", is_compliant=False, dividend_egp=Decimal("300")
        )
        assert est.status == PurificationStatus.OK
        assert est.branch == PurificationBranch.FAIL_HOLDING
        assert est.amount_egp == Decimal("300")

    def test_islamic_bank_carve_out_branches(self) -> None:
        for ticker in ("ADIB", "adib.ca", "FAIT", "SAUD"):
            est = estimate_dividend_purification(
                ticker=ticker,
                is_compliant=True,
                dividend_egp=Decimal("100"),
                non_permissible_revenue=Decimal("0"),
                total_revenue=Decimal("100"),
            )
            assert est.status == PurificationStatus.INSUFFICIENT_DATA
            assert est.branch == PurificationBranch.ISLAMIC_BANK_CARVE_OUT
            assert est.amount_egp is None
            assert est.reason is not None and "carve-out" in est.reason

    def test_dps_times_shares_derives_dividend(self) -> None:
        est = estimate_dividend_purification(
            ticker="TMGH",
            is_compliant=True,
            dps=Decimal("0.30"),
            shares_held=Decimal("1000"),
            non_permissible_revenue=Decimal("2"),
            total_revenue=Decimal("100"),
            dps_source="EGX disclosure",
            dps_date=date(2026, 5, 21),
        )
        assert est.status == PurificationStatus.OK
        assert est.dividend_egp == Decimal("300.00")
        assert est.amount_egp == Decimal("6.0000")
        assert est.dps_source == "EGX disclosure"
        assert est.dps_date == date(2026, 5, 21)

    def test_normalize_ticker(self) -> None:
        assert normalize_ticker("adib.ca") == "ADIB"
        assert normalize_ticker(" TMGH ") == "TMGH"


async def _make_fact_backed_company(
    db_session: AsyncSession, *, filing_date: date | None
) -> Company:
    company = Company(
        id=uuid.uuid4(),
        ticker=f"RPT_{uuid.uuid4().hex[:8].upper()}",
        isin=f"EG{uuid.uuid4().hex[:10].upper()}",
        name="Report Dated Co",
        sector="Technology",
        industry="Software",
        currency="EGP",
        status=CompanyStatus.ACTIVE,
    )
    db_session.add(company)
    await db_session.flush()
    period = FinancialPeriod(
        id=uuid.uuid4(),
        company_id=company.id,
        period_type="ANNUAL",
        fiscal_year=2024,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    db_session.add(period)
    await db_session.flush()
    source = DataSource(
        id=uuid.uuid4(),
        name=f"Phase6 Source {uuid.uuid4().hex[:8]}",
        source_type="SYNTHETIC",
    )
    db_session.add(source)
    await db_session.flush()
    document = FinancialDocument(
        id=uuid.uuid4(),
        period_id=period.id,
        source_id=source.id,
        document_type="ANNUAL_REPORT",
        document_status="ORIGINAL",
        filing_date=filing_date,
    )
    db_session.add(document)
    await db_session.flush()
    for label, value, fact_type in (
        ("total_debt", Decimal("10"), "BALANCE_SHEET"),
        ("total_assets", Decimal("100"), "BALANCE_SHEET"),
        ("cash_and_equivalents", Decimal("10"), "BALANCE_SHEET"),
        ("interest_income", Decimal("1"), "INCOME_STATEMENT"),
        ("revenue", Decimal("100"), "INCOME_STATEMENT"),
    ):
        db_session.add(
            FinancialFact(
                id=uuid.uuid4(),
                period_id=period.id,
                document_id=document.id,
                company_id=company.id,
                fact_type=fact_type,
                reported_label=label,
                normalized_label=label,
                reported_value=value,
                normalized_value=value,
                currency="EGP",
            )
        )
    await db_session.flush()
    return company


class TestScreeningProvenanceApi:
    async def test_screen_persists_report_date_and_rule_sources(
        self, client: AsyncClient, test_company: Company
    ) -> None:
        response = await client.post(f"/api/screening/companies/{test_company.id}/screen")
        assert response.status_code == 200
        body = response.json()
        assert body["methodology_version"] == "aaoifi-assets-spot/33-33-5"
        # No facts: report_date unknown with reason; every ratio rule cites
        # its missing inputs; industry rule cites the company record.
        assert body["report_date"] is None
        assert body["report_date_reason"] is not None
        rules = {r["rule_name"]: r for r in body["rule_results"]}
        assert rules["debt_ratio"]["missing_input"] == "total_debt, total_assets"
        assert rules["debt_ratio"]["source"] is None
        assert rules["industry_screen"]["source"] == "company record"

        get = await client.get(f"/api/screening/companies/{test_company.id}")
        assert get.status_code == 200
        assert get.json()["report_date"] is None
        assert get.json()["report_date_reason"] == body["report_date_reason"]

    async def test_screen_with_filings_reports_filing_date(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        company = await _make_fact_backed_company(
            db_session, filing_date=date(2024, 3, 15)
        )
        response = await client.post(f"/api/screening/companies/{company.id}/screen")
        assert response.status_code == 200
        body = response.json()
        assert body["report_date"] == "2024-03-15"
        assert body["report_date_reason"] is None
        assert body["is_compliant"] is True
        rules = {r["rule_name"]: r for r in body["rule_results"]}
        assert rules["debt_ratio"]["source"] == "ANNUAL_REPORT filing 2024-03-15"
        assert rules["debt_ratio"]["source_date"] == "2024-03-15"

    async def test_old_version_rows_stay_readable(
        self, client: AsyncClient, test_company: Company
    ) -> None:
        await client.post(f"/api/screening/companies/{test_company.id}/screen")
        listed = await client.get(
            "/api/screening/companies",
            params={"methodology_version": "aaoifi-assets-spot/33-33-5"},
        )
        assert listed.status_code == 200
        assert any(r["company_id"] == str(test_company.id) for r in listed.json())
        listed_old = await client.get(
            "/api/screening/companies", params={"methodology_version": "1.0"}
        )
        assert listed_old.status_code == 200
        assert all(r["methodology_version"] == "1.0" for r in listed_old.json())


class TestPurificationApi:
    async def test_honest_degradation_by_default(
        self, client: AsyncClient, test_company: Company
    ) -> None:
        await client.post(f"/api/screening/companies/{test_company.id}/screen")
        response = await client.post(
            f"/api/screening/companies/{test_company.id}/purification",
            json={"dividend_egp": 300.0, "dps": 0.30, "dps_source": "EGX disclosure"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "INSUFFICIENT_DATA"
        assert body["amount_egp"] is None
        assert body["doctrine"] == "dividend-method"
        assert body["dps_source"] == "EGX disclosure"
        assert body["note"] == NOT_ZAKAT_COPY
        assert "money-market" in (body["reason"] or "")

        get = await client.get(f"/api/screening/companies/{test_company.id}/purification")
        assert get.status_code == 200
        assert get.json()["status"] == "INSUFFICIENT_DATA"
        assert get.json()["amount_egp"] is None

    async def test_ratio_estimate_round_trip(
        self, client: AsyncClient, test_company: Company
    ) -> None:
        await client.post(f"/api/screening/companies/{test_company.id}/screen")
        response = await client.post(
            f"/api/screening/companies/{test_company.id}/purification",
            json={
                "dividend_egp": 300.0,
                "non_permissible_revenue": 2.0,
                "total_revenue": 100.0,
                "ratio_provenance": "FY2024 annual report",
                "dps_source": "EGX disclosure",
                "dps_date": "2026-05-21",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "OK"
        assert body["branch"] == "ratio"
        assert Decimal(body["ratio"]) == Decimal("0.02")
        assert Decimal(body["amount_egp"]) == Decimal("6")
        assert body["methodology_version"] == "aaoifi-assets-spot/33-33-5"

    async def test_fail_holding_purifies_all(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
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
        await client.post(f"/api/screening/companies/{company.id}/screen")
        response = await client.post(
            f"/api/screening/companies/{company.id}/purification",
            json={"dividend_egp": 100.0},
        )
        assert response.status_code == 200
        assert response.json()["branch"] == "fail-holding"
        assert Decimal(response.json()["amount_egp"]) == Decimal("100")

    async def test_bank_carve_out_never_silent_zero(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        from sqlalchemy import select

        # ADIB is seeded in the universe; reuse the row (test writes roll back).
        company = (
            await db_session.execute(select(Company).where(Company.ticker == "ADIB"))
        ).scalar_one()
        await client.post(f"/api/screening/companies/{company.id}/screen")
        response = await client.post(
            f"/api/screening/companies/{company.id}/purification",
            json={
                "dividend_egp": 100.0,
                "non_permissible_revenue": 0.0,
                "total_revenue": 100.0,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["branch"] == "islamic-bank-carve-out"
        assert body["amount_egp"] is None


class TestEgxMembershipApi:
    async def test_side_by_side_flags_discrepancy(
        self, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        company = Company(
            id=uuid.uuid4(),
            ticker=f"EGX_{uuid.uuid4().hex[:8].upper()}",
            isin=f"EG{uuid.uuid4().hex[:10].upper()}",
            name="EGX33 Name",
            sector="Beverages",
            industry="Alcohol Production",
            currency="EGP",
            status=CompanyStatus.ACTIVE,
        )
        db_session.add(company)
        await db_session.flush()
        screen = await client.post(f"/api/screening/companies/{company.id}/screen")
        assert screen.json()["is_compliant"] is False

        record = await client.post(
            f"/api/screening/companies/{company.id}/egx-membership",
            json={
                "member": True,
                "review_cycle": "2026-02",
                "effective_date": "2026-02-01",
                "source": "EGX Feb-2026 semi-annual review PDF",
            },
        )
        assert record.status_code == 200
        assert record.json()["methodology_version"] == "aaoifi-assets-spot/33-33-5"

        side = await client.get(f"/api/screening/companies/{company.id}/egx-membership")
        assert side.status_code == 200
        body = side.json()
        assert body["our_verdict"]["status"] == "NON_COMPLIANT"
        assert body["our_verdict"]["is_compliant"] is False
        assert body["egx33"]["member"] is True
        assert body["egx33"]["review_cycle"] == "2026-02"
        assert body["discrepancy"]["flagged"] is True
        assert body["discrepancy"]["note"] is not None

    async def test_agreement_not_flagged_and_rejects_bad_cycle(
        self, client: AsyncClient, test_company: Company
    ) -> None:
        await client.post(f"/api/screening/companies/{test_company.id}/screen")
        bad = await client.post(
            f"/api/screening/companies/{test_company.id}/egx-membership",
            json={"member": True, "review_cycle": "2026-05", "source": "x"},
        )
        assert bad.status_code == 422
        ok = await client.post(
            f"/api/screening/companies/{test_company.id}/egx-membership",
            json={"member": False, "review_cycle": "2026-08", "source": "EGX review PDF"},
        )
        assert ok.status_code == 200
        side = await client.get(f"/api/screening/companies/{test_company.id}/egx-membership")
        assert side.json()["discrepancy"]["flagged"] is False
        assert side.json()["discrepancy"]["note"] is None
