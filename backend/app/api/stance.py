"""API endpoints for the deterministic stance layer (signal-rules-1.0)."""

from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.company import CompanyRepository
from app.signals.stance import StanceService

router = APIRouter(prefix="/api/stance", tags=["stance"])


def _serialize(result: Any) -> dict[str, Any]:
    return {
        "company_id": result.company_id,
        "ticker": result.ticker,
        "stance": result.stance.value,
        "confidence": result.confidence,
        "reasons": [
            {"engine": r.engine, "inputs": r.inputs, "text": r.text} for r in result.reasons
        ],
        "limitations": result.limitations,
        "targets": {
            k: {"value": v.value, "status": v.status, "reason": v.reason}
            for k, v in result.targets.items()
        },
        "stop_level": {
            "value": result.stop_level.value,
            "status": result.stop_level.status,
            "reason": result.stop_level.reason,
        },
        "statement_freshness": (
            result.statement_freshness.isoformat() if result.statement_freshness else None
        ),
        "rules_version": result.rules_version,
        "as_of": result.as_of.isoformat(),
    }


@router.get("/companies/{ticker}")
async def get_stance(
    ticker: str,
    entry_price: float | None = Query(None),
    stop_pct: float = Query(10.0),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    if stop_pct <= 0 or stop_pct > 90:
        raise HTTPException(status_code=422, detail="stop_pct must be in (0, 90]")
    try:
        ep = Decimal(str(entry_price)) if entry_price is not None else None
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid entry_price") from exc
    try:
        sp = Decimal(str(stop_pct))
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid stop_pct") from exc

    service = StanceService(session)
    result = await service.compute(ticker, entry_price=ep, stop_pct=sp)
    return _serialize(result)


@router.get("/radar")
async def stance_radar(
    page_size: int = Query(50, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    company_repo = CompanyRepository(session)
    companies, _ = await company_repo.list_companies(page_size=page_size)
    service = StanceService(session)
    items: list[dict[str, Any]] = []  # radar row: ticker, stance or nulls
    for company in companies:
        try:
            res = await service.compute(company.ticker)
            items.append(
                {
                    "ticker": company.ticker,
                    "company_id": str(company.id),
                    "stance": res.stance.value,
                    "confidence": res.confidence,
                }
            )
        except Exception:
            radar_item: dict[str, int | str | None] = {  # stance unavailable
                "ticker": company.ticker,
                "company_id": str(company.id),
                "stance": None,
                "confidence": None,
            }
            items.append(radar_item)
    return {"items": items, "count": len(items)}
