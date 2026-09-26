import math
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.market import CompanyStatus
from app.repositories.company import CompanyRepository
from app.repositories.price import PriceRepository
from app.schemas.company import CompanyRead

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
) -> dict:
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


@router.get("/{company_id}")
async def get_company(
    company_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    repo = CompanyRepository(session)
    company = await repo.get_by_id(company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return CompanyRead.model_validate(company).model_dump()


@router.get("/ticker/{ticker}")
async def get_company_by_ticker(
    ticker: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
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
) -> dict:
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
) -> dict:
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
