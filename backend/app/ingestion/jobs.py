"""In-process market refresh job (universe -> prices -> assessment -> recompute).

State is intentionally in-memory: a single-user tool needs a button, not a job
table, and a process restart simply returns the status to ``idle``. One job runs
at a time; a second request while a job is live is refused by the router (409).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy import select

from app.core.config import settings
from app.dataquality.service import DataQualityService
from app.db.session import async_session_factory
from app.ingestion.egx.provider import INDEX_SOURCE, EGXMarketDataProvider, YahooIndexProvider
from app.ingestion.sync import fetch_and_write_prices
from app.models.market import Company, CompanyStatus
from app.repositories.index_prices import IndexPriceRepository
from app.services.recompute import after_price_sync, company_ids_for_tickers
from app.services.universe import UniverseService

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager
    from decimal import Decimal

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.ingestion.egx.universe import UniverseSource
    from app.ingestion.provider import MarketDataProvider

logger = logging.getLogger(__name__)

STATUS_IDLE = "idle"
STATUS_ACCEPTED = "accepted"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_PARTIAL = "partial"
STATUS_FAILED = "failed"

LIVE_STATUSES = (STATUS_ACCEPTED, STATUS_RUNNING)
FAILED_TICKERS_CAP = 20
PROVIDER_CONCURRENCY = 8
ASSESSMENT_SCOPES = ("price_history", "company_profile", "financial_statements")
#: Indices fetched with the price phase (R50 B10) and the least history kept for 1Y returns.
INDEX_CODES = ("EGX30",)
INDEX_MIN_HISTORY_DAYS = 400


def _open_session() -> AbstractAsyncContextManager[AsyncSession]:
    return async_session_factory()


# Test seam: patched to run the job against the test transaction.
_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] = _open_session


def create_price_provider() -> MarketDataProvider:
    return EGXMarketDataProvider(max_concurrent=PROVIDER_CONCURRENCY)


class IndexProvider(Protocol):
    async def get_index_closes(
        self, index_code: str, start_date: date, end_date: date
    ) -> list[tuple[date, Decimal]]: ...


def create_index_provider() -> IndexProvider:
    """Index price source for the job; tests replace it so nothing touches the network."""
    return YahooIndexProvider()


def create_universe_source() -> UniverseSource | None:
    """Universe source for the job; None lets UniverseService use its default."""
    return None


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


@dataclass
class SyncJob:
    """Frozen-in-memory state of the current (or last) refresh job."""

    status: str = STATUS_IDLE
    started_at: datetime | None = None
    finished_at: datetime | None = None
    phase: str | None = None
    progress: dict[str, int] | None = None
    universe: dict[str, int] | None = None
    prices: dict[str, Any] | None = None
    assessment: dict[str, int] | None = None
    index_prices: dict[str, int] | None = None
    crosschecks: dict[str, int] | None = None
    recompute: dict[str, Any] | None = None
    error: str | None = None
    task: asyncio.Task[None] | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "started_at": _iso(self.started_at),
            "finished_at": _iso(self.finished_at),
            "phase": self.phase,
            "progress": self.progress,
            "universe": self.universe,
            "prices": self.prices,
            "assessment": self.assessment,
            "index_prices": self.index_prices,
            "crosschecks": self.crosschecks,
            "recompute": self.recompute,
            "error": self.error,
        }


_current: SyncJob = SyncJob()


def current_job() -> SyncJob:
    return _current


def reset_job() -> None:
    """Clear the single-flight slot (test seam and restart semantics)."""
    global _current
    _current = SyncJob()


def start_refresh(
    tickers: list[str] | None,
    history_days: int,
    universe_only: bool,
) -> SyncJob | None:
    """Start a refresh unless one is live.

    Returns the accepted job (202) or ``None`` when a job is accepted/running, in
    which case the router answers 409 with :func:`current_job`. A terminal job
    does not block a new one (R16).
    """
    global _current
    if _current.status in LIVE_STATUSES:
        return None
    job = SyncJob(status=STATUS_ACCEPTED, started_at=datetime.now(UTC))
    _current = job
    job.task = asyncio.create_task(run_refresh(job, tickers, history_days, universe_only))
    return job


async def run_refresh(
    job: SyncJob,
    tickers: list[str] | None,
    history_days: int,
    universe_only: bool,
) -> None:
    """Run the phases under a bounded wall clock and record the outcome."""
    timeout = settings.SYNC_JOB_TIMEOUT_SECONDS
    try:
        await asyncio.wait_for(
            _run_phases(job, tickers, history_days, universe_only),
            timeout=timeout,
        )
    except TimeoutError:
        _mark_failed(job, f"TimeoutError: refresh exceeded {timeout}s")
    except Exception as exc:  # noqa: BLE001 - surfaced as job state
        _mark_failed(job, f"{type(exc).__name__}: {exc}")
    finally:
        job.finished_at = datetime.now(UTC)
        if job.status in LIVE_STATUSES:
            job.status = STATUS_FAILED


async def _run_phases(
    job: SyncJob,
    tickers: list[str] | None,
    history_days: int,
    universe_only: bool,
) -> None:
    job.status = STATUS_RUNNING

    job.phase = "universe"
    source = create_universe_source()
    async with _session_factory() as session:
        universe_result = await UniverseService(session, source).sync()
    job.universe = {"discovered": universe_result.discovered}

    if universe_only:
        job.phase = None
        job.status = STATUS_DONE
        return

    job.phase = "prices"
    async with _session_factory() as session:
        targets = (
            [t.upper() for t in tickers] if tickers else await _active_tickers(session)
        )
        job.progress = {"completed": 0, "total": len(targets)}
        end = date.today()
        start = end - timedelta(days=history_days)

        def _progress(completed: int, total: int) -> None:
            job.progress = {"completed": completed, "total": total}

        summary = await fetch_and_write_prices(
            session,
            create_price_provider(),
            targets,
            start,
            end,
            PROVIDER_CONCURRENCY,
            _progress,
        )

    job.prices = {
        "companies_fetched": summary.companies_fetched,
        "companies_total": summary.companies_total,
        "records_written": summary.records_written,
        "failed_count": len(summary.failures),
        "failed_tickers": [
            {"ticker": ticker, "error": error}
            for ticker, error in summary.failures[:FAILED_TICKERS_CAP]
        ],
    }
    job.progress = {
        "completed": summary.companies_total,
        "total": summary.companies_total,
    }
    job.index_prices = await _sync_indices(history_days)

    job.phase = "assessment"
    assessed, written = await _assess_all_companies()
    job.assessment = {"companies_assessed": assessed, "scores_written": written}

    job.phase = "crosschecks"
    job.crosschecks = await _run_crosschecks(summary.fetched_tickers)

    job.phase = "recompute"
    async with _session_factory() as session:
        synced_ids = await company_ids_for_tickers(session, summary.fetched_tickers)
    result = await after_price_sync(synced_ids, session_factory=_session_factory)
    job.recompute = result.as_dict()

    job.phase = None
    job.status = STATUS_PARTIAL if summary.failures else STATUS_DONE


async def _active_tickers(session: AsyncSession) -> list[str]:
    result = await session.execute(
        select(Company.ticker)
        .where(Company.status == CompanyStatus.ACTIVE)
        .order_by(Company.ticker)
    )
    return list(result.scalars().all())


async def _assess_all_companies() -> tuple[int, int]:
    """Assess every company in all three scopes, committing per company."""
    assessed = 0
    written = 0
    async with _session_factory() as session:
        company_ids = list(
            (await session.execute(select(Company.id))).scalars().all()
        )
        service = DataQualityService(session)
        for company_id in company_ids:
            for scope in ASSESSMENT_SCOPES:
                await service.assess(company_id, scope)
                written += 1
            await session.commit()
            assessed += 1
    return assessed, written


async def _sync_indices(history_days: int) -> dict[str, int]:
    """Fetch the benchmark index closes. A failure is logged, never fails the job (R50 B10)."""
    end = date.today()
    start = end - timedelta(days=max(history_days, INDEX_MIN_HISTORY_DAYS))
    written: dict[str, int] = {}
    for code in INDEX_CODES:
        try:
            closes = await create_index_provider().get_index_closes(code, start, end)
            async with _session_factory() as session:
                written[code] = await IndexPriceRepository(session).upsert_many(
                    code, closes, INDEX_SOURCE
                )
                await session.commit()
        except Exception as exc:  # noqa: BLE001 - the benchmark is optional
            logger.warning("Index %s fetch failed: %s: %s", code, type(exc).__name__, exc)
            written[code] = 0
    return written


async def _run_crosschecks(tickers: tuple[str, ...]) -> dict[str, int]:
    """Run the data cross-checks for the synced companies. Never fails the job (R50 B11)."""
    from app.dataquality.crosscheck_service import CrosscheckService

    checked = 0
    failed = 0
    try:
        async with _session_factory() as session:
            ids = await company_ids_for_tickers(session, tickers)
            service = CrosscheckService(session)
            for company_id in ids:
                try:
                    await service.run(company_id)
                    await session.commit()
                    checked += 1
                except Exception as exc:  # noqa: BLE001 - one company must not stop the rest
                    await session.rollback()
                    failed += 1
                    logger.warning("Cross-check failed for %s: %s", company_id, exc)
    except Exception as exc:  # noqa: BLE001 - cross-checks never fail the job
        logger.warning("Cross-checks unavailable: %s: %s", type(exc).__name__, exc)
    return {"companies_checked": checked, "companies_failed": failed}


def _mark_failed(job: SyncJob, message: str) -> None:
    job.status = STATUS_FAILED
    job.error = message
    logger.warning("Refresh job failed: %s", message)
