"""Automated fetch of published filings: official feeds only, robots-respecting.

Flow per URL: robots.txt check -> per-host rate limiting -> fetch bytes ->
sha256 de-duplication against stored blobs -> upsert FinancialPeriod from the
fetched scheduling metadata -> register FinancialDocument -> store raw bytes ->
emit a ``fact.landed`` event. No CAPTCHA/authentication bypass anywhere
(AGENTS.md source rule); a document whose period metadata is missing is skipped
as a failure rather than parked in a guessed period.
"""

import asyncio
import hashlib
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.continuous import ActorType, EventType
from app.models.financial import FinancialPeriod, ReportingPeriodType
from app.models.market import Company, DataSourceType
from app.repositories.continuous import EventRepository
from app.repositories.data_source import DataSourceRepository
from app.repositories.financial import (
    FinancialDocumentRepository,
    FinancialPeriodRepository,
)
from app.repositories.statements import DocumentBlobRepository
from app.schemas.financial import FinancialDocumentCreate, FinancialPeriodCreate

FACT_LANDED_RULE_VERSION = "CI-1.0"
USER_AGENT = "EGXResearchBot/0.1 (research tool; respects robots.txt)"
MIN_REQUEST_INTERVAL_SECONDS = 1.0


@dataclass
class FetchSummary:
    """Outcome of fetching one company's feeds."""

    ticker: str
    documents_fetched: int = 0
    documents_deduped: int = 0
    periods_linked: int = 0
    failures: list[str] = field(default_factory=list)


class RobotsDisallowed(Exception):
    pass


def create_fetch_client() -> httpx.AsyncClient:
    """Shared client: research-tool UA, generous timeouts."""
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=httpx.Timeout(30.0),
        follow_redirects=True,
    )


class FetchService:
    def __init__(self, session: AsyncSession, http_client: httpx.AsyncClient | None = None) -> None:
        self.session = session
        self.http_client = http_client
        self._last_request_at: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser] = {}

    async def _load_robots(self, client: httpx.AsyncClient, host: str) -> RobotFileParser:
        parser = self._robots.get(host)
        if parser is None:
            parser = RobotFileParser()
            response = await client.get(f"{host}/robots.txt")
            response.raise_for_status()
            parser.parse(response.text.splitlines())
            self._robots[host] = parser
        return parser

    async def _throttle(self, host: str) -> None:
        now = time.monotonic()
        last = self._last_request_at.get(host)
        if last is not None and now - last < MIN_REQUEST_INTERVAL_SECONDS:
            await asyncio.sleep(MIN_REQUEST_INTERVAL_SECONDS - (now - last))
        self._last_request_at[host] = time.monotonic()

    async def _link_period(
        self,
        company_id: uuid.UUID,
        fiscal_year: int,
        publication_date: date | None,
    ) -> uuid.UUID:
        """Create/reuse the annual period for ``fiscal_year`` and return its id."""
        existing = (
            await self.session.execute(
                select(FinancialPeriod).where(
                    FinancialPeriod.company_id == company_id,
                    FinancialPeriod.fiscal_year == fiscal_year,
                    FinancialPeriod.period_type == ReportingPeriodType.ANNUAL,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing.id
        repo: FinancialPeriodRepository = FinancialPeriodRepository(self.session)
        end_date = publication_date if publication_date else date(fiscal_year, 12, 31)
        created: FinancialPeriod = await repo.upsert(
            FinancialPeriodCreate(
                company_id=company_id,
                period_type=ReportingPeriodType.ANNUAL,
                fiscal_year=fiscal_year,
                fiscal_quarter=None,
                start_date=date(fiscal_year, 1, 1),
                end_date=end_date,
            )
        )
        return created.id

    async def fetch_company(
        self,
        ticker: str,
        urls: list[str] | None = None,
        filing_meta: Mapping[str, Any] | None = None,
    ) -> FetchSummary:
        """Fetch one company's official feeds.

        ``urls`` carries the concrete document links (resolved by the caller
        from the EGX disclosure index or user-verified IR lists).
        ``filing_meta`` carries dates metadata known from the resolved index;
        fiscal years are NOT guessed from names or titles.
        """
        summary = FetchSummary(ticker=ticker)
        company = (
            await self.session.execute(select(Company).where(Company.ticker == ticker.upper()))
        ).scalar_one_or_none()
        if company is None:
            summary.failures.append(f"company not found: {ticker}")
            return summary

        if urls is None:
            summary.failures.append(
                "feed resolution not configured: no fetched document URLs for this company"
            )
            return summary

        client = self.http_client or create_fetch_client()
        owns_client = self.http_client is None
        is_egx = any("egx.com.eg" in u for u in urls)
        try:
            data_source = await DataSourceRepository(self.session).get_or_create(
                name="EGX_DISCLOSURES" if is_egx else "COMPANY_IR",
                source_type=DataSourceType.EGX if is_egx else DataSourceType.COMPANY,
                base_url="https://www.egx.com.eg" if is_egx else None,
            )
            blob_repo = DocumentBlobRepository(self.session)
            doc_repo = FinancialDocumentRepository(self.session)

            for url in urls:
                host = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                try:
                    robots = await self._load_robots(client, host)
                    if not (robots.can_fetch(USER_AGENT, url) or robots.can_fetch("*", url)):
                        raise RobotsDisallowed(f"robots.txt disallows: {url}")
                    await self._throttle(host)
                    response = await client.get(url)
                    response.raise_for_status()
                except RobotsDisallowed as exc:
                    summary.failures.append(str(exc))
                    continue
                except httpx.HTTPError as exc:
                    summary.failures.append(f"{type(exc).__name__}: {url}")
                    continue

                content = response.content
                content_hash = hashlib.sha256(content).hexdigest()
                content_type = (
                    response.headers.get("content-type", "application/pdf").split(";")[0].strip()
                )
                if await blob_repo.get_by_hash(content_hash) is not None:
                    summary.documents_deduped += 1
                    continue

                meta = dict(filing_meta or {})
                publication_date = _as_date(meta.get("publication_date"))
                filing_date = _as_date(meta.get("filing_date"))
                fiscal_year = _as_year(meta.get("fiscal_year"))
                if fiscal_year is None:
                    summary.failures.append(
                        f"no fiscal-year metadata for {url}; document not registered"
                        " (no guessed periods)"
                    )
                    continue

                period_id = await self._link_period(company.id, fiscal_year, publication_date)
                summary.periods_linked += 1

                document = await doc_repo.upsert(
                    FinancialDocumentCreate(
                        period_id=period_id,
                        source_id=data_source.id,
                        document_type=_classify_document_type(url),
                        document_url=url[:500],
                        filing_date=filing_date,
                        publication_date=publication_date,
                    )
                )
                document.source_kind = "EGX_DISCLOSURE" if is_egx else "IR"
                document.fetched_at = datetime.now(UTC)
                document.content_hash = content_hash
                await self.session.flush()

                await blob_repo.store(
                    document_id=document.id,
                    company_id=company.id,
                    content_hash=content_hash,
                    content_type=content_type,
                    content=content,
                )

                await EventRepository(self.session).append(
                    actor_type=ActorType.SYSTEM,
                    actor_id=uuid.uuid4(),
                    rule_version=FACT_LANDED_RULE_VERSION,
                    type=EventType.FACT_LANDED,
                    symbols=[company.id],
                    inputs_snapshot={"url": url[:500], "hash": content_hash},
                    reason=f"document landed: {document.document_type}",
                )
                summary.documents_fetched += 1
            await self.session.commit()
        finally:
            if owns_client:
                await client.aclose()
        return summary

    async def fetch_batch(self, tickers: list[str] | tuple[str, ...]) -> dict[str, FetchSummary]:
        return {ticker: await self.fetch_company(ticker) for ticker in tickers}


def _classify_document_type(url: str) -> str:
    lowered = url.lower()
    if "annual" in lowered:
        return "annual_report"
    if any(k in lowered for k in ("quarterly", "q1", "q2", "q3", "q4")):
        return "quarterly_report"
    return "other"


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _as_year(value: Any) -> int | None:
    try:
        year = int(str(value))
    except (TypeError, ValueError):
        return None
    return year if 1980 <= year <= 2100 else None
