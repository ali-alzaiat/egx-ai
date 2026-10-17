from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PlanTier(StrEnum):
    FREE = "free"
    PRO = "pro"
    MAX = "max"


@dataclass(frozen=True)
class Entitlements:
    daily_stance_quota: int
    daily_radar: int
    company_hub_full: bool


PLAN_ENTITLEMENTS: dict[PlanTier, Entitlements] = {
    PlanTier.FREE: Entitlements(daily_stance_quota=3, daily_radar=1, company_hub_full=False),
    PlanTier.PRO: Entitlements(daily_stance_quota=10_000, daily_radar=100_000, company_hub_full=True),
    PlanTier.MAX: Entitlements(daily_stance_quota=10_000, daily_radar=100_000, company_hub_full=True),
}