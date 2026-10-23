"""Shariah status block shared by the stance and radar surfaces.

Two independent signals, side by side and never merged:
- ``verdict``: our own versioned screening result (or NOT_SCREENED);
- ``egx33``: the company's newest EGX33 Shariah Index membership record
  ("member" / "not_member"), or "unknown" when none was ever recorded.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.screening import ScreeningEgxMembership, ShariahScreeningResult
from app.repositories.screening import ScreeningRepository

NOT_MEMBER_COPY = (
    "Not in the EGX33 Shariah index; absence is not a non-compliance verdict."
)


def shariah_status(
    verdict: ShariahScreeningResult | None,
    membership: ScreeningEgxMembership | None,
) -> dict[str, Any]:
    """Build the Shariah block from our verdict and the company's latest EGX33 row."""
    if membership is None:
        egx33 = "unknown"
    elif membership.member:
        egx33 = "member"
    else:
        egx33 = "not_member"
    return {
        "verdict": verdict.status.value if verdict is not None else "NOT_SCREENED",
        "methodology_version": verdict.methodology_version if verdict is not None else None,
        "egx33": egx33,
        "egx33_review_cycle": membership.review_cycle if membership is not None else None,
        "egx33_source": membership.source if membership is not None else None,
        "note": NOT_MEMBER_COPY if egx33 == "not_member" else None,
    }


async def shariah_statuses(
    session: AsyncSession, company_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, dict[str, Any]]:
    """Shariah block for each company in one round of queries."""
    repo = ScreeningRepository(session)
    memberships = await repo.latest_egx_memberships(company_ids)
    verdicts = await repo.latest_results_by_company(company_ids)
    return {
        cid: shariah_status(verdicts.get(cid), memberships.get(cid)) for cid in company_ids
    }
