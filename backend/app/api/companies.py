import logging
import math
import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.market import CompanyStatus
from app.repositories.company import CompanyRepository
from app.repositories.price import PriceRepository
from app.schemas.company import CompanyRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("")
async def list_companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    sector: str | None = Query(None),
    industry: str | None = Query(None),
    status: CompanyStatus | None = Query(None),
    search: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    repo = CompanyRepository(session)
    companies, total = await repo.list_companies(
        page=page,
        page_size=page_size,
        sector=sector,
        industry=industry,
        status=status,
        search=search,
    )
    return {
        "items": [CompanyRead.model_validate(c).model_dump() for c in companies],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0,
    }


MAX_OVERVIEW_TICKERS = 50


@router.get("/overview")
async def companies_overview(
    tickers: str = Query(..., description="Comma-separated tickers (at most 50)"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Everything one Companies-table page needs, in one request.

    Per ticker: the default stance (cached per price date), the latest stored
    price and the gross-margin ratio. Replaces ~3 requests per table row.
    Missing values stay null with their INSUFFICIENT_DATA reason, never zero.
    """
    from app.screening.status import shariah_statuses
    from app.signals.stance import StanceService
    from app.statements.service import StatementService

    wanted = list(dict.fromkeys(t.strip().upper() for t in tickers.split(",") if t.strip()))
    if not wanted or len(wanted) > MAX_OVERVIEW_TICKERS:
        raise HTTPException(
            status_code=422,
            detail=f"tickers must list 1 to {MAX_OVERVIEW_TICKERS} symbols",
        )
    companies = await CompanyRepository(session).list_by_tickers(wanted)
    prices = PriceRepository(session)
    price_date = await prices.latest_price_date()
    shariah = await shariah_statuses(session, [c.id for c in companies])
    stance_service = StanceService(session)
    statements = StatementService(session)

    items: dict[str, dict[str, Any]] = {}
    for company in companies:
        latest = await prices.get_latest(company.id)
        bundle = await statements.company_ratios(company.id)
        margin = next((r for r in bundle.ratios if r.code == "gross_margin"), None)
        stance: dict[str, Any] | None
        try:
            result = await stance_service.compute_cached(
                company.ticker, price_date, shariah=shariah.get(company.id)
            )
            stance = {
                "stance": result.stance.value,
                "confidence": result.confidence,
                "reasons": [f"{r.engine}: {r.text}" for r in result.reasons],
            }
        except Exception:
            logger.warning("stance unavailable for %s", company.ticker, exc_info=True)
            stance = None
        items[company.ticker] = {
            "company_id": str(company.id),
            "stance": stance,
            "latest_price": (
                {"close": str(latest.close), "date": latest.date.isoformat()}
                if latest is not None
                else None
            ),
            "gross_margin": (
                {"value": margin.value, "status": margin.status, "reason": margin.reason}
                if margin is not None
                else None
            ),
        }
    return {
        "items": items,
        "missing": [t for t in wanted if t not in items],
        "price_date": price_date.isoformat() if price_date else None,
    }


@router.get("/{company_id}")
async def get_company(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    repo = CompanyRepository(session)
    company = await repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyRead.model_validate(company).model_dump()


@router.get("/ticker/{ticker}")
async def get_company_by_ticker(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    repo = CompanyRepository(session)
    company = await repo.get_by_ticker(ticker.upper())
    if not company:
        raise HTTPException(status_code=404, detail=f"Company '{ticker}' not found")
    return CompanyRead.model_validate(company).model_dump()


@router.get("/{company_id}/prices")
async def get_company_prices(
    company_id: uuid.UUID,
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="start_date must be <= end_date")

    price_repo = PriceRepository(session)
    prices, total = await price_repo.get_prices(
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )

    return {
        "items": [
            {
                "id": str(p.id),
                "company_id": str(p.company_id),
                "date": p.date.isoformat(),
                "open": str(p.open),
                "high": str(p.high),
                "low": str(p.low),
                "close": str(p.close),
                "adjusted_close": str(p.adjusted_close) if p.adjusted_close else None,
                "volume": p.volume,
                "value_traded": str(p.value_traded) if p.value_traded else None,
                "trades": p.trades,
                "source_id": str(p.source_id),
                "created_at": p.created_at.isoformat(),
            }
            for p in prices
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0,
    }


@router.get("/{company_id}/prices/latest")
async def get_latest_price(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    company_repo = CompanyRepository(session)
    company = await company_repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    price_repo = PriceRepository(session)
    price = await price_repo.get_latest(company_id)
    if not price:
        raise HTTPException(status_code=404, detail="No price data available")

    return {
        "id": str(price.id),
        "company_id": str(price.company_id),
        "date": price.date.isoformat(),
        "open": str(price.open),
        "high": str(price.high),
        "low": str(price.low),
        "close": str(price.close),
        "adjusted_close": str(price.adjusted_close) if price.adjusted_close else None,
        "volume": price.volume,
        "value_traded": str(price.value_traded) if price.value_traded else None,
        "trades": price.trades,
        "source_id": str(price.source_id),
        "created_at": price.created_at.isoformat(),
    }
