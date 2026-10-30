"""How fresh a company's fundamentals are (R47 Q3): latest fiscal year and its source tier."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.statements import bridge
from app.statements.bridge import load_company_statements


async def fundamentals_freshness(session: AsyncSession, company_id: uuid.UUID) -> dict[str, Any]:
    """Latest approved annual period: fiscal year, period end, source tier, provisional flag.

    ``source_tier`` is ``vendor`` when any line of the period is vendor-sourced (provisional),
    ``filing`` when all are filing-backed. No approved lines is INSUFFICIENT_DATA, never a year.
    """
    latest = (await load_company_statements(session, company_id)).latest()
    if latest is None:
        return {
            "status": "INSUFFICIENT_DATA",
            "reason": "no approved statement lines",
            "fiscal_year": None,
            "period_end": None,
            "source_tier": None,
            "provisional": None,
            "published_date": None,
        }
    lines = list(latest.lines.values())
    tier = bridge.tier_of(lines)
    dated = [lv.published_date for lv in lines if lv.published_date is not None]
    return {
        "status": "AVAILABLE",
        "reason": None,
        "fiscal_year": latest.fiscal_year,
        "period_end": latest.period_end.isoformat(),
        "source_tier": tier,
        "provisional": tier == "vendor",
        "published_date": max(dated).isoformat() if dated else None,
    }
