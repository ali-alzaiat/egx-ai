"""Tests for the statements FetchService (robots rules, dedupe, event emission)."""

import uuid
from datetime import date
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.continuous import Event, EventType
from app.models.financial import FinancialDocument
from app.models.market import Company, CompanyStatus
from app.statements.feed_config import feed_for
from app.statements.fetch_service import FetchService

pytestmark = pytest.mark.asyncio


async def _setup_company(db_session: AsyncSession, ticker: str | None = None) -> Company:
    ticker = ticker or f"TST_{uuid.uuid4().hex[:8].upper()}"
    company = Company(
        id=uuid.uuid4(),
        ticker=ticker,
        isin=f"EG{uuid.uuid4().hex[:10].upper()}",
        name=f"{ticker} Co",
        currency="EGP",
        status=CompanyStatus.ACTIVE,
    )
    db_session.add(company)
    await db_session.flush()
    return company


async def _client_for(app_overrides: dict[Any, Any]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(_handler(app_overrides)))


def _handler(overrides: dict[Any, Any]):  # noqa: ANN201
    routes = overrides

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("/robots.txt"):
            hit = next((v for k, v in routes.items() if k.endswith("/robots.txt")), None)
            if hit is None:
                return httpx.Response(200, text="User-agent: *\nAllow: /\n")
            if isinstance(hit, Exception):
                raise hit
            return httpx.Response(200, text=hit)
        for key, value in routes.items():
            if key.endswith("/robots.txt"):
                continue
            if url == key:
                if isinstance(value, Exception):
                    raise value
                return httpx.Response(200, content=value)
        return httpx.Response(404)

    return handler


PDF_BYTES = b"%PDF-1.4\n1 0 obj\n2000 REPORT CONTENT\nx"


class TestFeedConfig:
    async def test_feed_for_returns_egx_disclosure(self) -> None:
        feed = feed_for("COMI")
        assert feed.ticker == "COMI"
        assert feed.egx_disclosure is True

    async def test_ir_urls_not_invented(self) -> None:
        # Ship the config without guessing company IR URLs (AGENTS.md source rule).
        for ticker in ("COMI", "HRHO", "ABUK"):
            assert feed_for(ticker).ir_urls == []


class TestFetchService:
    async def test_fetch_persists_document_and_blob(self, db_session: AsyncSession) -> None:
        company = await _setup_company(db_session)
        client = await _client_for({f"https://feed.test/{company.ticker}.pdf": PDF_BYTES})
        svc = FetchService(db_session, http_client=client)
        summary = await svc.fetch_company(
            company.ticker,
            urls=[
                f"https://feed.test/{company.ticker}.pdf",
            ],
            filing_meta={"fiscal_year": 2024, "publication_date": date(2024, 3, 31)},
        )
        assert summary.documents_fetched == 1
        assert summary.documents_deduped == 0
        doc = (
            await db_session.execute(
                select(FinancialDocument).where(
                    FinancialDocument.document_url.like("https://feed.test/%")
                )
            )
        ).scalar_one()
        assert doc.content_hash is not None
        assert doc.fetched_at is not None

    async def test_missing_period_metadata_is_failure_not_guess(
        self, db_session: AsyncSession
    ) -> None:
        company = await _setup_company(db_session)
        url = f"https://feed.test/{company.ticker}.pdf"
        client = await _client_for({url: PDF_BYTES})
        svc = FetchService(db_session, http_client=client)
        summary = await svc.fetch_company(company.ticker, urls=[url])
        assert summary.documents_fetched == 0
        assert summary.failures and "fiscal-year" in summary.failures[0]

    async def test_hash_dedupe_skips_second_download(self, db_session: AsyncSession) -> None:
        company = await _setup_company(db_session)
        url = f"https://feed.test/{company.ticker}.pdf"
        client = await _client_for({url: PDF_BYTES})
        svc = FetchService(db_session, http_client=client)
        first = await svc.fetch_company(
            company.ticker, urls=[url], filing_meta={"fiscal_year": 2024}
        )
        second = await svc.fetch_company(
            company.ticker, urls=[url], filing_meta={"fiscal_year": 2024}
        )
        assert first.documents_fetched == 1
        assert second.documents_deduped == 1
        assert second.documents_fetched == 0

    async def test_robots_disallowed_is_failure(self, db_session: AsyncSession) -> None:
        company = await _setup_company(db_session)
        url = f"https://blocked.test/{company.ticker}.pdf"
        client = await _client_for(
            {
                url: PDF_BYTES,
                "https://blocked.test/robots.txt": ("User-agent: *\nDisallow: /\n"),
            }
        )
        svc = FetchService(db_session, http_client=client)
        summary = await svc.fetch_company(company.ticker, urls=[url])
        assert summary.documents_fetched == 0
        assert summary.failures and "robots" in summary.failures[0].lower()

    async def test_redirect_to_disallowed_host_is_failure(
        self, db_session: AsyncSession
    ) -> None:
        company = await _setup_company(db_session)
        url = f"https://open.test/{company.ticker}.pdf"
        fetched: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                blocked = request.url.host == "blocked.test"
                body = "User-agent: *\nDisallow: /\n" if blocked else ""
                return httpx.Response(200, text=body)
            fetched.append(str(request.url))
            if request.url.host == "open.test":
                return httpx.Response(302, headers={"location": "https://blocked.test/x.pdf"})
            return httpx.Response(200, content=PDF_BYTES)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        svc = FetchService(db_session, http_client=client)
        summary = await svc.fetch_company(company.ticker, urls=[url])
        assert summary.documents_fetched == 0
        assert summary.failures and "robots" in summary.failures[0].lower()
        assert fetched == [url]

    async def test_fact_landed_event_emitted(self, db_session: AsyncSession) -> None:
        company = await _setup_company(db_session)
        url = f"https://feed.test/{company.ticker}.pdf"
        client = await _client_for({url: PDF_BYTES})
        svc = FetchService(db_session, http_client=client)
        await svc.fetch_company(company.ticker, urls=[url],
                                 filing_meta={"fiscal_year": 2024})
        events = (
            (
                await db_session.execute(
                    select(Event).where(Event.type == EventType.FACT_LANDED.value)
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1
        assert company.id in events[0].symbols

    async def test_period_linked_from_publication_date(self, db_session: AsyncSession) -> None:
        from app.models.financial import FinancialPeriod

        company = await _setup_company(db_session)
        url = f"https://feed.test/{company.ticker}.pdf"
        client = await _client_for({url: PDF_BYTES})
        svc = FetchService(db_session, http_client=client)
        await svc.fetch_company(
            company.ticker,
            urls=[url],
            filing_meta={"publication_date": date(2024, 3, 31), "fiscal_year": 2023},
        )
        periods = (
            (
                await db_session.execute(
                    select(FinancialPeriod).where(FinancialPeriod.company_id == company.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(periods) == 1
        assert periods[0].fiscal_year in (2023, 2024)
