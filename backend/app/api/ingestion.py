"""API endpoints for the market refresh job."""

from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.ingestion.jobs import current_job, start_refresh

router = APIRouter(prefix="/api/ingestion", tags=["ingestion"])

DEFAULT_HISTORY_DAYS = 400
MIN_HISTORY_DAYS = 1
MAX_HISTORY_DAYS = 3650


def _parse_tickers(raw: str | None) -> list[str] | None:
    """Uppercase and split a comma-separated ticker list; None means universe."""
    if not raw:
        return None
    tickers = [part.strip().upper() for part in raw.split(",") if part.strip()]
    return tickers or None


@router.post("/sync", status_code=202, response_model=None)
async def start_sync(
    tickers: str | None = Query(None, description="Comma-separated EGX tickers"),
    history_days: int = Query(DEFAULT_HISTORY_DAYS, description="Days of price history"),
    universe_only: bool = Query(False, description="Only refresh the company list"),
) -> dict[str, Any] | JSONResponse:
    """Start a refresh; 202 with the job, or 409 while one is accepted/running."""
    clamped = min(max(history_days, MIN_HISTORY_DAYS), MAX_HISTORY_DAYS)
    job = start_refresh(_parse_tickers(tickers), clamped, universe_only)
    if job is None:
        return JSONResponse(status_code=409, content=current_job().to_dict())
    return job.to_dict()


@router.get("/sync/status")
async def sync_status() -> dict[str, Any]:
    """Current refresh job state; always 200 and never touches the database."""
    return current_job().to_dict()
