"""Alert API endpoints (B2)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.continuous import ActorType, AlertFamily, EventType
from app.repositories.continuous import AlertRepository, EventRepository
from app.schemas.continuous import (
    AlertFiredRead,
    AlertRuleCreate,
    AlertRuleRead,
    AlertRuleUpdate,
)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.post("", response_model=AlertRuleRead, status_code=status.HTTP_201_CREATED)
async def create_alert(
    body: AlertRuleCreate,
    session: AsyncSession = Depends(get_session),
) -> AlertRuleRead:
    """Create a new alert rule."""
    repo = AlertRepository(session)
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    # Validate family
    try:
        family = AlertFamily(body.family)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid family: {body.family}") from None

    # Validate watchlist_id if provided
    if body.watchlist_id is not None:
        from app.repositories.continuous import WatchlistRepository
        wl_repo = WatchlistRepository(session)
        wl = await wl_repo.get(body.watchlist_id)
        if wl is None or wl.user_id != user_id:
            raise HTTPException(status_code=404, detail="Watchlist not found")

    # Validate company_id if provided
    if body.company_id is not None:
        from app.repositories.company import CompanyRepository
        company = await CompanyRepository(session).get_by_id(body.company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

    # Family-specific param validation
    if family == AlertFamily.PRICE:
        if "threshold" not in body.params:
            raise HTTPException(
                status_code=400, detail="Price alert requires 'threshold' parameter"
            )
        if "direction" not in body.params:
            body.params["direction"] = "above"
        if body.params["direction"] not in ("above", "below"):
            raise HTTPException(status_code=400, detail="Direction must be 'above' or 'below'")

    rule = await repo.create_rule(
        user_id=user_id,
        family=family,
        params=body.params,
        methodology_version="CI-1.0",
        watchlist_id=body.watchlist_id,
        company_id=body.company_id,
        enabled=body.enabled,
    )

    # Log event
    event_repo = EventRepository(session)
    await event_repo.append(
        actor_type=ActorType.USER,
        actor_id=user_id,
        rule_version="CI-1.0",
        type=EventType.ALERT_CREATED,
        symbols=[body.company_id] if body.company_id else [],
        inputs_snapshot={"rule_id": str(rule.id), "family": family.value, "params": body.params},
        reason=f"Created {family.value} alert rule",
    )

    return AlertRuleRead.model_validate(rule)


@router.get("", response_model=list[AlertRuleRead])
async def list_alerts(
    watchlist_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    family: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[AlertRuleRead]:
    """List alert rules with optional filters."""
    repo = AlertRepository(session)
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    family_enum = None
    if family is not None:
        try:
            family_enum = AlertFamily(family)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid family: {family}") from None

    rules = await repo.list_rules(
        user_id=user_id,
        watchlist_id=watchlist_id,
        company_id=company_id,
        family=family_enum,
    )
    return [AlertRuleRead.model_validate(r) for r in rules]


@router.get("/fired", response_model=list[AlertFiredRead])
async def list_fired_alerts(
    rule_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    acked: bool | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[AlertFiredRead]:
    """List fired alerts for the current user."""
    repo = AlertRepository(session)
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    fired = await repo.list_fired(
        user_id=user_id,
        rule_id=rule_id,
        company_id=company_id,
        acked=acked,
    )
    return [AlertFiredRead.model_validate(f) for f in fired]


@router.post("/{fired_id}/ack", response_model=AlertFiredRead)
async def ack_fired_alert(
    fired_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> AlertFiredRead:
    """Acknowledge a fired alert."""
    repo = AlertRepository(session)
    fired = await repo.get_fired(fired_id)
    if fired is None:
        raise HTTPException(status_code=404, detail="Fired alert not found")

    # Verify ownership through rule
    rule = await repo.get_rule(fired.rule_id)
    if rule is None or rule.user_id != uuid.UUID("00000000-0000-0000-0000-000000000001"):
        raise HTTPException(status_code=403, detail="Not authorized")

    acked = await repo.ack_fired(fired_id)
    if acked is None:
        raise HTTPException(status_code=404, detail="Fired alert not found")

    # Log event
    event_repo = EventRepository(session)
    await event_repo.append(
        actor_type=ActorType.USER,
        actor_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        rule_version="CI-1.0",
        type=EventType.ALERT_ACKED,
        symbols=[fired.company_id],
        inputs_snapshot={"fired_id": str(fired_id), "rule_id": str(fired.rule_id)},
        reason=f"Acknowledged fired alert {fired_id}",
    )

    return AlertFiredRead.model_validate(acked)


@router.get("/{alert_id}", response_model=AlertRuleRead)
async def get_alert(
    alert_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> AlertRuleRead:
    """Get an alert rule by ID."""
    repo = AlertRepository(session)
    rule = await repo.get_rule(alert_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return AlertRuleRead.model_validate(rule)


@router.patch("/{alert_id}", response_model=AlertRuleRead)
async def update_alert(
    alert_id: uuid.UUID,
    body: AlertRuleUpdate,
    session: AsyncSession = Depends(get_session),
) -> AlertRuleRead:
    """Update an alert rule."""
    repo = AlertRepository(session)
    rule = await repo.get_rule(alert_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    if rule.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    updated = await repo.update_rule(
        rule_id=alert_id,
        params=body.params,
        enabled=body.enabled,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    # Log event
    event_repo = EventRepository(session)
    await event_repo.append(
        actor_type=ActorType.USER,
        actor_id=user_id,
        rule_version="CI-1.0",
        type=EventType.RULE_CHANGED,
        symbols=[rule.company_id] if rule.company_id else [],
        inputs_snapshot={"rule_id": str(rule.id), "changes": body.model_dump(exclude_none=True)},
        reason=f"Updated alert rule {rule.id}",
    )

    return AlertRuleRead.model_validate(updated)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete an alert rule."""
    repo = AlertRepository(session)
    rule = await repo.get_rule(alert_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Alert rule not found")

    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    if rule.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    deleted = await repo.delete_rule(alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert rule not found")
