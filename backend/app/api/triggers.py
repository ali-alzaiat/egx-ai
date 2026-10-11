"""Trigger evaluation API endpoints (B3/B5).

Internal endpoint called by ingestion jobs on fact landing / price crossing.
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.continuous.trigger_service import TriggerService
from app.db.session import get_session
from app.schemas.continuous import TriggerEvaluateResponse

router = APIRouter(prefix="/api/triggers", tags=["triggers"])


class TriggerEvaluateBody(BaseModel):
    """Trigger evaluation request body."""

    company_id: uuid.UUID
    fact_ids: list[uuid.UUID] = []
    price_as_of: str | None = None  # ISO date string
    price_value: str | None = None  # Decimal as string


@router.post("/evaluate", response_model=TriggerEvaluateResponse)
async def evaluate_triggers(
    body: TriggerEvaluateBody,
    session: AsyncSession = Depends(get_session),
) -> TriggerEvaluateResponse:
    """Evaluate triggers for a company (internal endpoint).

    Called by:
    - Ingestion jobs when new facts land (Phase 7 disclosure parsing)
    - Price ingestion when new prices arrive
    """
    service = TriggerService(session)

    if body.fact_ids:
        # Facts landed path
        result = await service.on_facts_landed(body.company_id, body.fact_ids)
    elif body.price_value is not None and body.price_as_of is not None:
        # Price crossing path
        try:
            price = Decimal(body.price_value)
            as_of_str = body.price_as_of
            from datetime import date
            as_of: date = date.fromisoformat(as_of_str)
            result = await service.on_price_crossing(body.company_id, price, as_of)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid price/date: {e}") from None
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide either fact_ids or price_value+price_as_of",
        )

    return TriggerEvaluateResponse(
        evaluated=True,
        alerts_fired=result.alerts_fired,
        checks_run=result.checks_run,
        ledger_rows=result.ledger_rows,
        message=result.message,
    )
