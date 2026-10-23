"""Official-filings intake: priority checklist and assisted manual entry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from app.models.screening import ScreeningEgxMembership
from app.statements.vendor_import import ImportSummary, import_payload

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.market import Company

FILING_URL = "https://www.egx.com.eg/en/NewsDetails.aspx?NewsID=1"


def _filing(ticker: str, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "ticker": ticker,
        "fiscal_year": 2025,
        "period_end": "2025-06-30",
        "document_url": FILING_URL,
        "publication_date": "2025-09-15",
        "currency": "EGP",
        "lines": [
            {"code": "total_assets", "value": "1000", "page": "4"},
            {"code": "total_liabilities", "value": "400", "page": "4"},
            {"code": "total_equity", "value": "580", "page": "4"},
            {"code": "minority_interests", "value": "20", "page": "4"},
            {"code": "revenue", "value": "1002", "page": "6"},
        ],
    }
    body.update(overrides)
    return body


async def _make_member(db_session: AsyncSession, company: Company) -> None:
    db_session.add(
        ScreeningEgxMembership(
            company_id=company.id,
            methodology_version="test",
            member=True,
            review_cycle="2099-02",
            source="https://www.egx.com.eg/test",
        )
    )
    await db_session.flush()


def _row(body: dict[str, Any], ticker: str) -> dict[str, Any]:
    return next(item for item in body["items"] if item["ticker"] == ticker)


class TestChecklist:
    async def test_status_moves_missing_vendor_filed(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        vendor_payload: Any,
    ) -> None:
        await _make_member(db_session, test_company)
        res = await client.get("/api/statements/intake")
        assert res.status_code == 200
        row = _row(res.json(), test_company.ticker)
        assert row["status"] == "missing" and "egx33" in row["reasons"]
        assert {line["code"] for line in res.json()["lines"]} >= {"revenue", "total_assets"}

        await import_payload(db_session, vendor_payload(test_company.ticker), ImportSummary())
        await db_session.flush()
        row = _row((await client.get("/api/statements/intake")).json(), test_company.ticker)
        assert row["status"] == "vendor_only"
        assert row["vendor_years"] == [2025, 2024] and row["target_year"] == 2025

        assert (await client.post("/api/statements/manual-filings",
                                  json=_filing(test_company.ticker))).status_code == 200
        row = _row((await client.get("/api/statements/intake")).json(), test_company.ticker)
        assert row["status"] == "filed" and row["filing_years"] == [2025]


class TestManualEntry:
    async def test_balanced_entry_validates(
        self, client: AsyncClient, test_company: Company
    ) -> None:
        res = await client.post("/api/statements/manual-filings", json=_filing(test_company.ticker))
        assert res.status_code == 200
        statuses = {line["code"]: line["status"] for line in res.json()["lines"]}
        assert set(statuses.values()) == {"auto_validated"}

    async def test_identity_failure_is_rejected_with_reason(
        self, client: AsyncClient, test_company: Company
    ) -> None:
        body = _filing(test_company.ticker)
        body["lines"][0]["value"] = "9999"  # assets no longer = liabilities + equity
        res = await client.post("/api/statements/manual-filings", json=body)
        assert res.status_code == 200
        assets = next(line for line in res.json()["lines"] if line["code"] == "total_assets")
        assert assets["status"] == "rejected" and "ASSETS_IDENTITY" in assets["reason"]

    @pytest.mark.parametrize(
        "overrides",
        [
            {"document_url": "javascript:alert(1)"},
            {"document_url": "not a url"},
            {"lines": [{"code": "made_up_line", "value": "1", "page": "1"}]},
            {"lines": [{"code": "revenue", "value": "1", "page": "1"},
                       {"code": "revenue", "value": "2", "page": "1"}]},
            {"lines": [{"code": "revenue", "value": "1", "page": "  "}]},
            {"lines": [{"code": "revenue", "value": "1", "page": ""}]},
            {"lines": []},
        ],
    )
    async def test_bad_input_is_422(
        self, client: AsyncClient, test_company: Company, overrides: dict[str, Any]
    ) -> None:
        res = await client.post(
            "/api/statements/manual-filings", json=_filing(test_company.ticker, **overrides)
        )
        assert res.status_code == 422

    async def test_unknown_company_404(self, client: AsyncClient) -> None:
        res = await client.post("/api/statements/manual-filings", json=_filing("NOSUCH1"))
        assert res.status_code == 404

    async def test_filing_replaces_vendor_in_statements(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_company: Company,
        vendor_payload: Any,
    ) -> None:
        await import_payload(db_session, vendor_payload(test_company.ticker), ImportSummary())
        await db_session.flush()
        await client.post("/api/statements/manual-filings", json=_filing(test_company.ticker))
        res = await client.get(f"/api/statements/companies/{test_company.ticker}/statements")
        fy2025 = next(p for p in res.json()["periods"] if p["fiscal_year"] == 2025)
        revenue = next(line for line in fy2025["income"] if line["ontology_code"] == "revenue")
        assert revenue["value"] == "1002.0000"
        assert revenue["source_tier"] == "filing" and revenue["provisional"] is False
        assert revenue["source_page"] == "6" and revenue["document_url"] == FILING_URL
        # Lines the filing did not cover keep the provisional vendor value.
        gross = next(line for line in fy2025["income"] if line["ontology_code"] == "gross_profit")
        assert gross["source_tier"] == "vendor"
