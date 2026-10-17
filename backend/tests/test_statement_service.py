"""Task 7: StatementService assembly + endpoints over approved lines."""

import uuid
from datetime import date
from decimal import Decimal
from hashlib import sha256

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.main import app
from app.models.financial import (
    FinancialDocument,
    FinancialPeriod,
    ReportingPeriodType,
)
from app.models.market import Company, CompanyStatus, DataSource, DataSourceType
from app.repositories.statements import DocumentBlobRepository
from app.statements.pipeline import StatementPipeline
from app.statements.ratios import RATIO_VERSION, RatioService
from app.statements.service import StatementService

pytestmark = pytest.mark.asyncio

FIXTURE_2024 = (
    b"<?xml version='1.0'?><xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance'>"
    b"<line item='Revenue' unitRef='EGP' decimals='-2'>1200000</line>"
    b"<line item='Cost of revenue' unitRef='EGP' decimals='-2'>700000</line>"
    b"<line item='Gross profit' unitRef='EGP' decimals='-2'>500000</line>"
    b"<line item='Operating profit' unitRef='EGP' decimals='-2'>240000</line>"
    b"<line item='Net income' unitRef='EGP' decimals='-2'>180000</line>"
    b"<line item='Total Assets' unitRef='EGP' decimals='-2'>2500000</line>"
    b"<line item='Total Liabilities' unitRef='EGP' decimals='-2'>1000000</line>"
    b"<line item='Total Equity' unitRef='EGP' decimals='-2'>1500000</line>"
    b"</xbrli:xbrl>"
)
FIXTURE_2023 = (
    b"<?xml version='1.0'?><xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance'>"
    b"<line item='Revenue' unitRef='EGP' decimals='-2'>1000000</line>"
    b"<line item='Cost of revenue' unitRef='EGP' decimals='-2'>580000</line>"
    b"<line item='Gross profit' unitRef='EGP' decimals='-2'>420000</line>"
    b"<line item='Net income' unitRef='EGP' decimals='-2'>150000</line>"
    b"<line item='Total Assets' unitRef='EGP' decimals='-2'>2200000</line>"
    b"<line item='Total Liabilities' unitRef='EGP' decimals='-2'>900000</line>"
    b"<line item='Total Equity' unitRef='EGP' decimals='-2'>1300000</line>"
    b"</xbrli:xbrl>"
)


async def _seed_two_years(
    db_session: AsyncSession,
) -> tuple[Company, FinancialPeriod, FinancialPeriod, FinancialDocument]:
    company = Company(
        id=uuid.uuid4(),
        ticker=f"SVC_{uuid.uuid4().hex[:6].upper()}",
        isin=f"EG{uuid.uuid4().hex[:10].upper()}",
        name="SVC Co",
        currency="EGP",
        status=CompanyStatus.ACTIVE,
    )
    db_session.add(company)
    await db_session.flush()
    source = DataSource(name=f"SVC_SRC_{uuid.uuid4().hex[:8]}", source_type=DataSourceType.EGX)
    db_session.add(source)
    await db_session.flush()
    period_2024 = FinancialPeriod(
        company_id=company.id,
        period_type=ReportingPeriodType.ANNUAL,
        fiscal_year=2024,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
    )
    period_2023 = FinancialPeriod(
        company_id=company.id,
        period_type=ReportingPeriodType.ANNUAL,
        fiscal_year=2023,
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
    )
    db_session.add_all([period_2024, period_2023])
    await db_session.flush()
    document = FinancialDocument(
        period_id=period_2024.id,
        source_id=source.id,
        document_type="annual_report",
        document_url="https://svc.test/fy2024.xml",
        publication_date=date(2024, 12, 31),
    )
    db_session.add(document)
    await db_session.flush()
    await DocumentBlobRepository(db_session).store(
        document_id=document.id,
        company_id=company.id,
        content_hash=sha256(FIXTURE_2024).hexdigest(),
        content_type="application/xml",
        content=FIXTURE_2024,
    )
    document.content_hash = sha256(FIXTURE_2024).hexdigest()
    doc_2023 = FinancialDocument(
        period_id=period_2023.id,
        source_id=source.id,
        document_type="annual_report",
        document_url="https://svc.test/fy2023.xml",
        publication_date=date(2023, 12, 31),
    )
    db_session.add(doc_2023)
    await db_session.flush()
    await DocumentBlobRepository(db_session).store(
        document_id=doc_2023.id,
        company_id=company.id,
        content_hash=sha256(FIXTURE_2023).hexdigest(),
        content_type="application/xml",
        content=FIXTURE_2023,
    )
    doc_2023.content_hash = sha256(FIXTURE_2023).hexdigest()
    await db_session.flush()
    pipeline = StatementPipeline(db_session)
    await pipeline.process_document(document.id)
    await pipeline.process_document(doc_2023.id)
    return company, period_2024, period_2023, document


class TestStatementService:
    async def test_bundle_groups_three_sections(
        self, db_session: AsyncSession
    ) -> None:
        company, _p24, _p23, _doc = await _seed_two_years(db_session)
        bundle = await StatementService(db_session).company_statements(company.id)
        assert bundle.periods, "at least one period"
        latest = bundle.periods[0]
        codes = {line.ontology_code for line in latest.income}
        assert {"revenue", "net_income", "eps"} <= codes
        assert any(l.ontology_code == "total_assets" for l in latest.balance)
        assert any(l.ontology_code == "cfo" for l in latest.cash_flow)

    async def test_full_ontology_rendered_null_not_zero(
        self, db_session: AsyncSession
    ) -> None:
        company, _p24, _p23, _doc = await _seed_two_years(db_session)
        bundle = await StatementService(db_session).company_statements(company.id)
        latest = bundle.periods[0]
        revenue = next(l for l in latest.income if l.ontology_code == "revenue")
        assert Decimal(revenue.value or "0") == Decimal("1200000")
        assert revenue.status == "AVAILABLE"
        eps = next(l for l in latest.income if l.ontology_code == "eps")
        assert eps.value is None
        assert eps.status == "INSUFFICIENT_DATA"  # candidate excluded, never zero
        finance_costs = next(
            l for l in latest.income if l.ontology_code == "finance_costs"
        )
        assert finance_costs.value is None

    async def test_labels_en_and_ar_from_ontology(
        self, db_session: AsyncSession
    ) -> None:
        company, _p24, _p23, _doc = await _seed_two_years(db_session)
        bundle = await StatementService(db_session).company_statements(company.id)
        revenue = next(
            l for l in bundle.periods[0].income if l.ontology_code == "revenue"
        )
        assert revenue.label_en == "Revenue"
        assert revenue.label_ar == "الإيرادات"

    async def test_provenance_and_period_metadata(
        self, db_session: AsyncSession
    ) -> None:
        company, p24, _p23, _doc = await _seed_two_years(db_session)
        bundle = await StatementService(db_session).company_statements(company.id)
        latest = bundle.periods[0]
        assert latest.period_id == p24.id
        assert latest.fiscal_year == 2024
        assert latest.published_date == date(2024, 12, 31)
        revenue = next(l for l in latest.income if l.ontology_code == "revenue")
        assert revenue.source_label_reported == "Revenue"
        assert revenue.document_url == "https://svc.test/fy2024.xml"

    async def test_periods_descending(self, db_session: AsyncSession) -> None:
        company, _p24, _p23, _doc = await _seed_two_years(db_session)
        bundle = await StatementService(db_session).company_statements(company.id)
        years = [p.fiscal_year for p in bundle.periods]
        assert years == sorted(years, reverse=True)

    async def test_endpoints(self, client, db_session: AsyncSession) -> None:
        company, _p24, _p23, _doc = await _seed_two_years(db_session)
        app.dependency_overrides[get_session] = lambda: db_session
        try:
            resp = await client.get(f"/api/statements/companies/{company.ticker}/statements")
            assert resp.status_code == 200
            body = resp.json()
            assert body["periods"][0]["fiscal_year"] == 2024

            ratios = await client.get(f"/api/statements/companies/{company.ticker}/ratios")
            assert ratios.status_code == 200
            rbody = ratios.json()
            gm = next(r for r in rbody["ratios"] if r["code"] == "gross_margin")
            assert gm["value"] == str(Decimal("500000") / Decimal("1200000"))
            rev_g = next(r for r in rbody["ratios"] if r["code"] == "revenue_growth_yoy")
            assert rev_g["value"] == "0.2"
            assert rev_g["status"] == "AVAILABLE"

            missing = await client.get(
                "/api/statements/companies/NOPE_404/ratios"
            )
            assert missing.status_code == 404
        finally:
            app.dependency_overrides.pop(get_session, None)




class TestRatioServiceGolden:
    def setup_method(self) -> None:
        self.svc = RatioService()

    def _compute_one(self, code: str, lines: dict[str, Decimal]) -> object:
        results = self.svc.compute(lines, None, None)
        return next(r for r in results if r.code == code)

    async def test_gross_margin(self) -> None:
        r = self._compute_one("gross_margin", {"gross_profit": Decimal("500"), "revenue": Decimal("1000")})
        assert r.value == str(Decimal("500") / Decimal("1000"))
        assert r.status == "AVAILABLE"

    async def test_operating_and_net_margin(self) -> None:
        lines = {"operating_profit": Decimal("240"), "net_income": Decimal("150"), "revenue": Decimal("1200")}
        om = self._compute_one("operating_margin", lines)
        nm = self._compute_one("net_margin", lines)
        assert om.value == str(Decimal("240") / Decimal("1200"))
        assert nm.value == str(Decimal("150") / Decimal("1200"))

    async def test_roe_roa(self) -> None:
        lines = {"net_income": Decimal("180"), "total_equity": Decimal("1500"), "total_assets": Decimal("2500")}
        assert self._compute_one("roe", lines).value == str(Decimal("180") / Decimal("1500"))
        assert self._compute_one("roa", lines).value == str(Decimal("180") / Decimal("2500"))

    async def test_leverage_and_current_ratio(self) -> None:
        lines = {
            "interest_bearing_debt": Decimal("500"), "total_equity": Decimal("1000"),
            "current_assets": Decimal("800"), "current_liabilities": Decimal("400"),
        }
        assert self._compute_one("leverage", lines).value == str(Decimal("500") / Decimal("1000"))
        assert self._compute_one("current_ratio", lines).value == str(Decimal("800") / Decimal("400"))

    async def test_eps_from_line_and_from_shares(self) -> None:
        r = self._compute_one("eps", {"eps": Decimal("1.25")})
        assert r.value == "1.25"
        r2 = self._compute_one("eps", {"net_income": Decimal("180")})
        assert r2.status == "INSUFFICIENT_DATA"
        results = self.svc.compute({"net_income": Decimal("180")}, None, Decimal("120"))
        eps2 = next(x for x in results if x.code == "eps")
        assert eps2.value == str(Decimal("180") / Decimal("120"))

    async def test_zero_equity_roe_insufficient(self) -> None:
        results = self.svc.compute({"net_income": Decimal("1"), "total_equity": Decimal("0")}, None, None)
        roe = next(r for r in results if r.code == "roe")
        assert roe.status == "INSUFFICIENT_DATA"
        assert roe.reason == "ZERO_EQUITY"
        assert roe.value is None

    async def test_negative_income_margin_is_negative_value(self) -> None:
        nm = self._compute_one("net_margin", {"net_income": Decimal("-50"), "revenue": Decimal("1000")})
        assert nm.status == "AVAILABLE"
        assert nm.value == "-0.05"

    async def test_missing_input_code_gives_reason(self) -> None:
        results = self.svc.compute({"revenue": Decimal("1000")}, None, None)
        roe = next(r for r in results if r.code == "roe")
        assert roe.status == "INSUFFICIENT_DATA"
        assert roe.reason == "missing:total_equity"

    async def test_growth_prior_missing(self) -> None:
        results = self.svc.compute({"revenue": Decimal("1000")}, None, None)
        g = next(r for r in results if r.code == "revenue_growth_yoy")
        assert g.status == "INSUFFICIENT_DATA"
        assert g.reason == "prior"

    async def test_growth_prior_zero_rejected(self) -> None:
        results = self.svc.compute({"revenue": Decimal(10)}, {}, None)
        g = next(r for r in results if r.code == "revenue_growth_yoy")
        assert g.status == "INSUFFICIENT_DATA"
        assert g.reason == "prior"
        results2 = self.svc.compute(
            {"revenue": Decimal(10)}, {"revenue": Decimal(0)}, None
        )
        g2 = next(r for r in results2 if r.code == "revenue_growth_yoy")
        assert g2.status == "INSUFFICIENT_DATA"
        assert g2.reason == "PRIOR_NON_POSITIVE"

    async def test_growth_available(self) -> None:
        results = self.svc.compute(
            {"revenue": Decimal("1200000"), "net_income": Decimal("180000")},
            {"revenue": Decimal("1000000"), "net_income": Decimal("150000")},
            None,
        )
        rg = next(r for r in results if r.code == "revenue_growth_yoy")
        ng = next(r for r in results if r.code == "net_income_growth_yoy")
        assert rg.value == "0.2"
        assert ng.value == str(Decimal("180000") / Decimal("150000") - 1)
        assert RATIO_VERSION == "stmt-ratios-1.0"
        assert rg.status == "AVAILABLE"
