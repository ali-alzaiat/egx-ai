"""API endpoints for the deterministic stance layer (signal-rules-1.0)."""

import logging
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories.company import CompanyRepository
from app.repositories.price import PriceRepository
from app.repositories.screening import ScreeningRepository
from app.screening.status import shariah_statuses
from app.signals.rules import Liquidity, ReferenceLevels
from app.signals.stance import SIGNAL_RULES_VERSION, StanceResult, StanceService

if TYPE_CHECKING:
    import uuid

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stance", tags=["stance"])


def _level(level: Any) -> dict[str, Any]:
    return {"value": level.value, "status": level.status, "reason": level.reason}


def _reference_levels(levels: ReferenceLevels | None) -> dict[str, Any] | None:
    if levels is None:
        return None
    return {
        "entry": str(levels.entry),
        "upside": str(levels.upside),
        "downside": str(levels.downside),
        "atr": str(levels.atr),
        "horizon": levels.horizon,
    }


def _liquidity(liq: Liquidity) -> dict[str, Any]:
    return {
        "avg_value_traded": (
            str(liq.avg_value_traded) if liq.avg_value_traded is not None else None
        ),
        "window": liq.window,
        "low": liq.low,
    }


def _serialize(result: StanceResult) -> dict[str, Any]:
    return {
        "company_id": result.company_id,
        "ticker": result.ticker,
        "stance": result.stance.value,
        "confidence": result.confidence,
        "price": str(result.price) if result.price is not None else None,
        "score": str(result.score) if result.score is not None else None,
        "coverage": str(result.coverage),
        "reasons": [
            {"engine": r.engine, "inputs": r.inputs, "text": r.text} for r in result.reasons
        ],
        "limitations": result.limitations,
        "targets": {k: _level(v) for k, v in result.targets.items()},
        "stop_level": _level(result.stop_level),
        "reference_levels": _reference_levels(result.reference_levels),
        "liquidity": _liquidity(result.liquidity),
        "shariah": result.shariah,
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
    shariah: Literal["egx33"] | None = Query(
        None, description="egx33 = only official EGX33 Shariah index members"
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Stance for the most-traded companies (optionally EGX33 Shariah members only)."""
    scope: list[uuid.UUID] | None = None
    if shariah == "egx33":
        members = await ScreeningRepository(session).latest_egx_memberships()
        scope = [cid for cid, row in members.items() if row.member]
    ranked = await PriceRepository(session).most_traded_company_ids(
        page_size, company_ids=scope
    )
    companies = {c.id: c for c in await CompanyRepository(session).list_by_ids(ranked)}
    shariah_blocks = await shariah_statuses(session, ranked)
    service = StanceService(session)
    items: list[dict[str, Any]] = []
    for company_id in ranked:
        company = companies.get(company_id)
        if company is None:
            continue
        try:
            res = await service.compute(company.ticker, shariah=shariah_blocks.get(company.id))
        except Exception:
            logger.warning("stance unavailable for %s", company.ticker, exc_info=True)
            items.append(
                {
                    "ticker": company.ticker,
                    "company_id": str(company.id),
                    "name": company.name,
                    "stance": None,
                    "confidence": None,
                    "score": None,
                    "price": None,
                    "reference_levels": None,
                    "low_liquidity": None,
                    "shariah": None,
                }
            )
            continue
        items.append(
            {
                "ticker": company.ticker,
                "company_id": str(company.id),
                "name": company.name,
                "stance": res.stance.value,
                "confidence": res.confidence,
                "score": str(res.score) if res.score is not None else None,
                "price": str(res.price) if res.price is not None else None,
                "reference_levels": _reference_levels(res.reference_levels),
                "low_liquidity": res.liquidity.low,
                "shariah": res.shariah,
            }
        )
    return {"items": items, "count": len(items), "rules_version": SIGNAL_RULES_VERSION}
