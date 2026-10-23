"""Provisional vendor statements: mapping, validation gates, filing precedence.

Uses the ``vendor_payload`` fixture: the saved vendor file layout with
SYNTHETIC test numbers (not any real company's figures).
"""

from __future__ import annotations

import copy
import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.models.financial import FinancialDocument, FinancialPeriod, ReportingPeriodType
from app.models.market import DataSource, DataSourceType
from app.models.statements import ExtractionMethod, ExtStatus, FinancialStatementLine
from app.repositories.statements import StatementLineRepository
from app.statements.vendor_import import ImportSummary, import_payload, vendor_periods

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.market import Company


async def _import(db_session: AsyncSession, payload: dict[str, Any]) -> ImportSummary:
    summary = ImportSummary()
    await import_payload(db_session, payload, summary)
    await db_session.flush()
    return summary


class TestMapping:
    def test_fiscal_years_skip_ttm_and_missing_values(self, vendor_payload: Any) -> None:
        periods = vendor_periods(vendor_payload("T"))
        assert [p.fiscal_year for p in periods] == [2025, 2024]
        codes_2024 = {c.ontology_code for c in periods[1].candidates}
        assert "net_income" not in codes_2024  # vendor null stays missing, never zero
        assert all(c.extraction_method == "vendor_aggregator" for c in periods[0].candidates)

    def test_values_and_signs(self, vendor_payload: Any) -> None:
        candidates = vendor_periods(vendor_payload("T"))[0].candidates
        by_code = {c.ontology_code: c for c in candidates}
        assert by_code["finance_costs"].value == Decimal("20.0000")  # expense magnitude
        assert by_code["capex"].value == Decimal("-30.0000")  # cash-flow sign kept
        assert by_code["total_equity"].value == Decimal("580.0000")  # common equity only
        assert by_code["revenue"].source_label_reported == "Revenue"
        # "equity" (incl. minority) is deliberately not mapped: no double counting.
        assert "Shareholders' Equity" not in {c.source_label_reported for c in candidates}


class TestImport:
    async def test_balanced_period_validates_and_eps_is_held(
        self, db_session: AsyncSession, test_company: Company, vendor_payload: Any
    ) -> None:
        summary = await _import(db_session, vendor_payload(test_company.ticker))
        assert summary.companies == 1 and summary.periods == 2
        lines = await StatementLineRepository(db_session).latest_approved(test_company.id)
        codes = {row.ontology_code for row in lines}
        assert {"revenue", "total_assets", "total_equity", "minority_interests"} <= codes
        assert "eps" not in codes  # passthru code: review queue only
        assert all(row.extraction_method == ExtractionMethod.vendor_aggregator for row in lines)

    async def test_failed_identity_is_rejected(
        self, db_session: AsyncSession, test_company: Company, vendor_payload: Any
    ) -> None:
        payload = copy.deepcopy(vendor_payload(test_company.ticker))
        payload["statements"]["balance"]["financialData"]["assets"] = [1, 5000, 900]
        summary = await _import(db_session, payload)
        assert summary.rejected >= 1
        lines = await StatementLineRepository(db_session).latest_approved(test_company.id)
        assert not any(
            row.ontology_code == "total_assets" and row.value == Decimal("5000") for row in lines
        )

    async def test_non_egp_reporter_is_held(
        self, db_session: AsyncSession, test_company: Company, vendor_payload: Any
    ) -> None:
        summary = await _import(db_session, vendor_payload(test_company.ticker, currency="USD"))
        assert summary.auto_validated == 0 and summary.held > 0
        assert await StatementLineRepository(db_session).latest_approved(test_company.id) == []

    async def test_reimport_is_idempotent(
        self, db_session: AsyncSession, test_company: Company, vendor_payload: Any
    ) -> None:
        repo = StatementLineRepository(db_session)
        await _import(db_session, vendor_payload(test_company.ticker))
        first = len(await repo.latest_approved(test_company.id))
        await _import(db_session, vendor_payload(test_company.ticker))
        second = len(await repo.latest_approved(test_company.id))
        assert first == second > 0

    async def test_unknown_ticker_is_skipped(
        self, db_session: AsyncSession, vendor_payload: Any
    ) -> None:
        summary = await _import(db_session, vendor_payload("NOSUCH1"))
        assert summary.skipped == ["NOSUCH1"] and summary.companies == 0

    async def test_filing_always_beats_vendor(
        self, db_session: AsyncSession, test_company: Company, vendor_payload: Any
    ) -> None:
        await _import(db_session, vendor_payload(test_company.ticker))
        period = (
            await db_session.execute(
                select(FinancialPeriod).where(
                    FinancialPeriod.company_id == test_company.id,
                    FinancialPeriod.fiscal_year == 2025,
                    FinancialPeriod.period_type == ReportingPeriodType.ANNUAL,
                )
            )
        ).scalar_one()
        source = DataSource(
            id=uuid.uuid4(), name=f"FILING_{uuid.uuid4().hex[:6]}",
            source_type=DataSourceType.EGX,
        )
        db_session.add(source)
        await db_session.flush()
        document = FinancialDocument(
            id=uuid.uuid4(), period_id=period.id, source_id=source.id,
            document_type="ANNUAL_REPORT", document_status="ORIGINAL",
        )
        db_session.add(document)
        await db_session.flush()
        db_session.add(
            FinancialStatementLine(
                company_id=test_company.id, period_id=period.id, ontology_code="revenue",
                ontology_version="stmt-ontology-1.0", value=Decimal("1001"), currency="EGP",
                source_document_id=document.id, extraction_method=ExtractionMethod.manual_seed,
                ext_status=ExtStatus.approved,
                published_date=date(2020, 1, 1),  # older than anything: tier still wins
            )
        )
        await db_session.flush()
        lines = await StatementLineRepository(db_session).latest_approved(test_company.id)
        revenue = next(
            r for r in lines if r.ontology_code == "revenue" and r.period_id == period.id
        )
        assert revenue.value == Decimal("1001")
        assert revenue.extraction_method == ExtractionMethod.manual_seed

    async def test_statements_api_marks_vendor_lines_provisional(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        vendor_payload: Any,
    ) -> None:
        await _import(db_session, vendor_payload(test_company.ticker))
        res = await client.get(f"/api/statements/companies/{test_company.ticker}/statements")
        assert res.status_code == 200
        income = res.json()["periods"][0]["income"]
        revenue = next(line for line in income if line["ontology_code"] == "revenue")
        assert revenue["source_tier"] == "vendor" and revenue["provisional"] is True
        missing = next(line for line in income if line["ontology_code"] == "selling_expenses")
        assert missing["status"] == "INSUFFICIENT_DATA" and missing["source_tier"] is None
